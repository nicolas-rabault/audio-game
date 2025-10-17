import asyncio
import base64
import json
import logging
from functools import cache, partial
from typing import Annotated

import numpy as np
import requests
import sphn
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketState
from fastrtc import AdditionalOutputs, CloseStream, audio_to_float32
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field, TypeAdapter, ValidationError, computed_field
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

import unmute.openai_realtime_api_events as ora
from unmute import metrics as mt
from unmute.exceptions import (
    MissingServiceAtCapacity,
    MissingServiceTimeout,
    WebSocketClosedError,
    make_ora_error,
)
from unmute.kyutai_constants import (
    KYUTAI_LLM_API_KEY,
    LLM_SERVER,
    MAX_VOICE_FILE_SIZE_MB,
    SAMPLE_RATE,
    STT_SERVER,
    TTS_SERVER,
    VOICE_CLONING_SERVER,
)
from unmute.service_discovery import async_ttl_cached
from unmute.timer import Stopwatch
from unmute.tts.voice_cloning import clone_voice
from unmute.tts.voice_donation import (
    VoiceDonationSubmission,
    generate_verification,
    submit_voice_donation,
)
from unmute.tts.character_loader import CharacterManager
from unmute.tts.voices import VoiceList
from unmute.unmute_handler import UnmuteHandler

app = FastAPI()

# Global CharacterManager instance (used only for /v1/voices endpoint for initial character discovery)
# Per-session character management is handled by UnmuteHandler.character_manager
_character_manager: CharacterManager | None = None

# Global set to track active WebSocket connections (legacy, kept for compatibility)
_active_websockets: set[WebSocket] = set()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# We prefer to scale this by running more instances of the server than having a single
# server handle more. This is to avoid the GIL.
MAX_CLIENTS = 4
SEMAPHORE = asyncio.Semaphore(MAX_CLIENTS)

Instrumentator().instrument(app).expose(app)
PROFILE_ACTIVE = False
_last_profile = None
_current_profile = None

ClientEventAdapter = TypeAdapter(
    Annotated[ora.ClientEvent, Field(discriminator="type")]
)

# Allow CORS for local development
CORS_ALLOW_ORIGINS = ["http://localhost", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Load default characters for /v1/voices endpoint.

    Note: Each WebSocket session creates its own CharacterManager instance.
    This global manager is only used for the /v1/voices HTTP endpoint.
    """
    global _character_manager
    from pathlib import Path

    _character_manager = CharacterManager(session_id="global")
    characters_dir = Path(__file__).parents[1] / "characters"

    try:
        result = await _character_manager.load_characters(characters_dir)
        logger.info(
            f"Global character loading complete: {result.loaded_count}/{result.total_files} files loaded "
            f"({result.error_count} errors) in {result.load_duration:.2f}s"
        )
    except FileNotFoundError as e:
        logger.warning(f"Character directory not found: {e}. Starting with empty character list.")
        _character_manager.characters = {}


def get_character_manager() -> CharacterManager:
    """Get the global CharacterManager instance (used for /v1/voices endpoint only).

    Note: For WebSocket sessions, use handler.character_manager instead.
    """
    if _character_manager is None:
        raise RuntimeError("CharacterManager not initialized. Call startup_event() first.")
    return _character_manager


async def terminate_all_sessions(reason: str = "Server is reloading characters"):
    """
    Terminate all active WebSocket sessions.

    This is called when characters are reloaded to force clients to reconnect
    with the new character set.

    Args:
        reason: Message to send to clients explaining why they're being disconnected
    """
    global _active_websockets

    if not _active_websockets:
        logger.info("No active sessions to terminate")
        return

    logger.info(f"Terminating {len(_active_websockets)} active sessions: {reason}")

    # Create a copy of the set to iterate over, as it will be modified during iteration
    websockets_to_close = list(_active_websockets)

    for ws in websockets_to_close:
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                # Send a graceful error message before closing
                error_event = make_ora_error(
                    type="fatal",
                    message=reason + ". Please reconnect."
                )
                await ws.send_text(error_event.model_dump_json())
                await ws.close(code=1012, reason=reason)  # 1012 = Service Restart
                logger.debug(f"Closed WebSocket connection: {ws.client}")
        except Exception as e:
            logger.warning(f"Error closing WebSocket: {e}")

    logger.info("All active sessions terminated")


@app.get("/")
def root():
    return {"message": "You've reached the Unmute backend server."}


if PROFILE_ACTIVE:

    @app.get("/profile")
    def profile():
        if _last_profile is None:
            return HTMLResponse("<body>No last profiler saved</body>")
        else:
            return HTMLResponse(_last_profile.output_html())  # type: ignore


def _ws_to_http(ws_url: str) -> str:
    """Convert a WebSocket URL to an HTTP URL."""
    return ws_url.replace("ws://", "http://").replace("wss://", "https://")


def _check_server_status(server_url: str, headers: dict | None = None) -> bool:
    """Check if the server is up by sending a GET request."""
    try:
        response = requests.get(
            server_url,
            timeout=2,
            headers=headers or {},
        )
        logger.info(f"Response from {server_url}: {response}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.info(f"Couldn't connect to {server_url}: {e}")
        return False


async def debug_running_tasks():
    while True:
        logger.debug(f"Running tasks: {len(asyncio.all_tasks())}")
        for task in asyncio.all_tasks():
            logger.debug(f"  Task: {task.get_name()} - {task.get_coro()}")
        await asyncio.sleep(5)


class HealthStatus(BaseModel):
    tts_up: bool
    stt_up: bool
    llm_up: bool
    voice_cloning_up: bool

    @computed_field
    @property
    def ok(self) -> bool:
        # Note that voice cloning is not required for the server to be healthy.
        return self.tts_up and self.stt_up and self.llm_up


@partial(async_ttl_cached, ttl_sec=0.5)
async def _get_health(
    _none: None,
):  # dummy param _none because caching function expects a single param as cache key.
    async with asyncio.TaskGroup() as tg:
        tts_up = tg.create_task(
            asyncio.to_thread(
                _check_server_status, _ws_to_http(TTS_SERVER) + "/api/build_info"
            )
        )
        stt_up = tg.create_task(
            asyncio.to_thread(
                _check_server_status, _ws_to_http(STT_SERVER) + "/api/build_info"
            )
        )
        llm_up = tg.create_task(
            asyncio.to_thread(
                _check_server_status,
                _ws_to_http(LLM_SERVER) + "/v1/models",
                # The default vLLM server doesn't use auth, but this is needed if you
                # use OpenAI or another LLM server.
                headers={"Authorization": f"Bearer {KYUTAI_LLM_API_KEY}"},
            )
        )
        voice_cloning_up = tg.create_task(
            asyncio.to_thread(
                _check_server_status,
                _ws_to_http(VOICE_CLONING_SERVER) + "/api/build_info",
            )
        )
        tts_up_res = await tts_up
        stt_up_res = await stt_up
        llm_up_res = await llm_up
        voice_cloning_up_res = await voice_cloning_up

    return HealthStatus(
        tts_up=tts_up_res,
        stt_up=stt_up_res,
        llm_up=llm_up_res,
        voice_cloning_up=voice_cloning_up_res,
    )


@app.get("/v1/health")
async def get_health():
    health = await _get_health(None)
    mt.HEALTH_OK.observe(health.ok)
    return health


@app.get("/v1/voices")
@cache
def voices():
    character_manager = get_character_manager()
    # Note that `voice.good` is bool | None, here we really take only True values.
    good_voices = [
        voice.model_dump(exclude={"comment", "_source_file", "_prompt_generator"})
        for voice in character_manager.characters.values()
        if voice.good
    ]
    return good_voices


class CharacterReloadRequest(BaseModel):
    """Request model for reloading characters from a new directory."""
    directory: str = Field(
        ...,
        description="Absolute path to the directory containing character files. "
        "Use 'default' to reload the default characters/ directory."
    )


@app.post("/v1/characters/reload")
async def reload_characters_endpoint(request: CharacterReloadRequest):
    """
    [DEPRECATED] Global character reload endpoint.

    This endpoint reloads the global character manager used by /v1/voices.
    It does NOT affect active WebSocket sessions, which have their own character managers.

    **Recommended approach**: Use the WebSocket event `session.characters.reload` for
    per-session character reloading without affecting other users.

    Args:
        request: CharacterReloadRequest with directory path

    Returns:
        JSON with reload results

    Example:
        POST /v1/characters/reload
        {
            "directory": "/home/user/my-characters"
        }

        Or to reload the default characters/ directory:
        {
            "directory": "default"
        }
    """
    from pathlib import Path

    character_manager = get_character_manager()

    # Handle "default" keyword to reload original characters directory
    if request.directory == "default":
        characters_dir = Path(__file__).parents[1] / "characters"
        logger.info("Reloading default characters directory")
    else:
        characters_dir = Path(request.directory)

    # Validate the directory exists
    if not characters_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Directory not found: {characters_dir}"
        )

    if not characters_dir.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {characters_dir}"
        )

    try:
        # Step 1: Reload characters
        result = await character_manager.reload_characters(characters_dir)

        # Step 2: Clear the cache for the /v1/voices endpoint
        voices.cache_clear()

        # Note: We no longer terminate sessions since they have their own character managers
        # This only affects the global manager used by /v1/voices
        logger.info(
            f"Global characters reloaded successfully: {result.loaded_count}/{result.total_files} loaded "
            f"from {characters_dir}. Active sessions are unaffected."
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "directory": str(characters_dir),
                "total_files": result.total_files,
                "loaded_count": result.loaded_count,
                "error_count": result.error_count,
                "load_duration": result.load_duration,
                "message": f"Successfully loaded {result.loaded_count} characters from {characters_dir}"
            }
        )

    except FileNotFoundError as e:
        logger.error(f"Character reload failed: {e}")
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Character reload failed with unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload characters: {str(e)}"
        )


class LimitUploadSizeForPath(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_upload_size: int, path: str) -> None:
        super().__init__(app)
        self.max_upload_size = max_upload_size
        self.path = path

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "POST" and request.url.path == self.path:
            if "content-length" not in request.headers:
                return Response(status_code=status.HTTP_411_LENGTH_REQUIRED)

            content_length = int(request.headers["content-length"])
            if content_length > self.max_upload_size:
                return Response(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        return await call_next(request)


app.add_middleware(
    LimitUploadSizeForPath,
    max_upload_size=MAX_VOICE_FILE_SIZE_MB * 1024 * 1024,
    path="/v1/voices",
)


@app.post("/v1/voices")
async def post_voices(file: UploadFile):
    """Upload a voice list file.

    Make sure the maximum file size is configured in uvicorn.
    """
    name = clone_voice(file.file.read())
    return {"name": name}


@app.get("/v1/voice-donation")
async def get_voice_donation():
    """Initiate a voice donation by asking for a verification text."""
    verification = generate_verification()
    return verification


app.add_middleware(
    LimitUploadSizeForPath,
    max_upload_size=MAX_VOICE_FILE_SIZE_MB * 1024 * 1024,
    path="/v1/voice-donation",
)


@app.post("/v1/voice-donation")
async def post_voice_donation(
    file: UploadFile = File(...),  # noqa: B008
    metadata: str = Form(...),
):
    """Finish a voice donation."""
    file_bytes = file.file.read()

    try:
        metadata_parsed = VoiceDonationSubmission(**json.loads(metadata))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid submission: {e.errors()}",
        ) from e

    try:
        submit_voice_donation(metadata_parsed, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {}


@app.websocket("/v1/realtime")
async def websocket_route(websocket: WebSocket):
    global _last_profile, _current_profile, _active_websockets
    mt.SESSIONS.inc()
    mt.ACTIVE_SESSIONS.inc()
    session_watch = Stopwatch()
    if PROFILE_ACTIVE and _current_profile is None:
        from pyinstrument import Profiler

        logger.info("Profiler started.")
        _current_profile = Profiler(interval=0.0001, async_mode="disabled")
        import inspect

        frame = inspect.currentframe()
        while frame is not None and frame.f_back:
            frame = frame.f_back
        _current_profile.start(caller_frame=frame)

    async with SEMAPHORE:
        try:
            # The `subprotocol` argument is important because the client specifies what
            # protocol(s) it supports and OpenAI uses "realtime" as the value. If we
            # don't set this, the client will think this is not the right endpoint and
            # will not connect.
            await websocket.accept(subprotocol="realtime")

            # Register this websocket for reload tracking
            _active_websockets.add(websocket)

            handler = UnmuteHandler()
            async with handler:
                await handler.start_up()
                await _run_route(websocket, handler)

        except Exception as exc:
            await _report_websocket_exception(websocket, exc)
        finally:
            # Unregister websocket
            _active_websockets.discard(websocket)

            if _current_profile is not None:
                _current_profile.stop()
                logger.info("Profiler saved.")
                _last_profile = _current_profile
                _current_profile = None

            mt.ACTIVE_SESSIONS.dec()
            mt.SESSION_DURATION.observe(session_watch.time())


async def _report_websocket_exception(websocket: WebSocket, exc: Exception):
    if isinstance(exc, ExceptionGroup):
        exceptions = exc.exceptions
    else:
        exceptions = [exc]

    error_message = None

    for exc in exceptions:
        if isinstance(exc, (MissingServiceAtCapacity)):
            mt.FATAL_SERVICE_MISSES.inc()
            error_message = (
                f"Too many people are connected to service '{exc.service}'. "
                "Please try again later."
            )
        elif isinstance(exc, MissingServiceTimeout):
            mt.FATAL_SERVICE_MISSES.inc()
            error_message = (
                f"Service '{exc.service}' timed out. Please try again later."
            )
        elif isinstance(exc, WebSocketClosedError):
            logger.debug("Websocket was closed.")
        else:
            logger.exception("Unexpected error: %r", exc)
            mt.HARD_ERRORS.inc()
            error_message = "Internal server error :( Complain to Kyutai"

    if error_message is not None:
        mt.FORCE_DISCONNECTS.inc()

        try:
            await websocket.send_text(
                make_ora_error(type="fatal", message=error_message).model_dump_json()
            )
        except WebSocketDisconnect:
            logger.warning("Failed to send error message due to disconnect.")

        try:
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR,
                reason=error_message,
            )
        except RuntimeError:
            logger.warning("Socket already closed.")


async def _run_route(websocket: WebSocket, handler: UnmuteHandler):
    health = await get_health()
    if not health.ok:
        logger.info("Health check failed, closing WebSocket connection.")
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason=f"Server is not healthy: {health}",
        )
        return

    emit_queue: asyncio.Queue[ora.ServerEvent] = asyncio.Queue()
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                receive_loop(websocket, handler, emit_queue), name="receive_loop()"
            )
            tg.create_task(
                emit_loop(websocket, handler, emit_queue), name="emit_loop()"
            )
            tg.create_task(handler.quest_manager.wait(), name="quest_manager.wait()")
            tg.create_task(debug_running_tasks(), name="debug_running_tasks()")
    finally:
        await handler.cleanup()
        logger.info("websocket_route() finished")


async def receive_loop(
    websocket: WebSocket,
    handler: UnmuteHandler,
    emit_queue: asyncio.Queue[ora.ServerEvent],
):
    """Receive messages from the WebSocket.

    Can decide to send messages via `emit_queue`.
    """
    opus_reader = sphn.OpusStreamReader(SAMPLE_RATE)
    wait_for_first_opus = True
    while True:
        try:
            message_raw = await websocket.receive_text()
        except WebSocketDisconnect as e:
            logger.info(
                "receive_loop() stopped because WebSocket disconnected: "
                f"{e.code=} {e.reason=}"
            )
            raise WebSocketClosedError() from e
        except RuntimeError as e:
            # This is expected when the client disconnects
            if "WebSocket is not connected" not in str(e):
                raise  # re-raise unexpected errors

            logger.info("receive_loop() stopped because WebSocket disconnected.")
            raise WebSocketClosedError() from e

        try:
            message: ora.ClientEvent = ClientEventAdapter.validate_json(message_raw)
        except json.JSONDecodeError as e:
            await emit_queue.put(
                ora.Error(
                    error=ora.ErrorDetails(
                        type="invalid_request_error",
                        message=f"Invalid JSON: {e}",
                    )
                )
            )
            continue
        except ValidationError as e:
            await emit_queue.put(
                ora.Error(
                    error=ora.ErrorDetails(
                        type="invalid_request_error",
                        message="Invalid message",
                        details=json.loads(e.json()),
                    )
                )
            )
            continue

        message_to_record = message

        if isinstance(message, ora.InputAudioBufferAppend):
            opus_bytes = base64.b64decode(message.audio)
            if wait_for_first_opus:
                # Somehow the UI is sending us potentially old messages from a previous
                # connection on reconnect, so that we might get some old OGG packets,
                # waiting for the bit set for first packet to feed to the decoder.
                if opus_bytes[5] & 2:
                    wait_for_first_opus = False
                else:
                    continue
            pcm = await asyncio.to_thread(opus_reader.append_bytes, opus_bytes)

            message_to_record = ora.UnmuteInputAudioBufferAppendAnonymized(
                number_of_samples=pcm.size,
            )

            if pcm.size:
                await handler.receive((SAMPLE_RATE, pcm[np.newaxis, :]))
        elif isinstance(message, ora.SessionUpdate):
            await handler.update_session(message.session)
            await emit_queue.put(ora.SessionUpdated(session=message.session))

        elif isinstance(message, ora.SessionCharactersReload):
            # Handle character reload request
            try:
                # Resolve "default" to actual default directory
                if message.directory == "default":
                    from pathlib import Path
                    characters_dir = Path(__file__).parent / "characters"
                else:
                    from pathlib import Path
                    characters_dir = Path(message.directory)

                # Validate directory exists
                if not characters_dir.exists():
                    await emit_queue.put(
                        ora.Error(
                            error=ora.ErrorDetails(
                                type="server_error",
                                code="directory_not_found",
                                message=f"Character directory not found: {characters_dir}",
                            )
                        )
                    )
                    continue

                if not characters_dir.is_dir():
                    await emit_queue.put(
                        ora.Error(
                            error=ora.ErrorDetails(
                                type="server_error",
                                code="invalid_directory_format",
                                message=f"Path is not a directory: {characters_dir}",
                            )
                        )
                    )
                    continue

                # Load characters
                result = await handler.character_manager.reload_characters(characters_dir)

                # Check if any characters loaded successfully
                if result.loaded_count == 0:
                    await emit_queue.put(
                        ora.Error(
                            error=ora.ErrorDetails(
                                type="server_error",
                                code="no_valid_characters",
                                message=f"No valid characters found in directory: {characters_dir}",
                            )
                        )
                    )
                    continue

                # Build character info list
                characters = [
                    ora.CharacterInfo(
                        name=char.name,
                        good=char.good if hasattr(char, 'good') else None,
                        comment=char.comment if hasattr(char, 'comment') else None,
                    )
                    for char in result.characters.values()
                ]

                # Send success response
                await emit_queue.put(
                    ora.SessionCharactersReloaded(
                        directory=str(characters_dir),
                        loaded_count=result.loaded_count,
                        error_count=result.error_count,
                        total_files=result.total_files,
                        characters=characters,
                    )
                )

                logger.info(
                    f"Session {handler.character_manager.session_id}: Reloaded {result.loaded_count} "
                    f"characters from {characters_dir}"
                )

            except Exception as e:
                logger.error(f"Failed to reload characters: {e}", exc_info=True)
                await emit_queue.put(
                    ora.Error(
                        error=ora.ErrorDetails(
                            type="server_error",
                            code="character_reload_failed",
                            message=f"Failed to reload characters: {str(e)}",
                        )
                    )
                )

        elif isinstance(message, ora.SessionCharactersList):
            # Handle character list request
            try:
                characters = [
                    ora.CharacterInfo(
                        name=char.name,
                        good=char.good if hasattr(char, 'good') else None,
                        comment=char.comment if hasattr(char, 'comment') else None,
                    )
                    for char in handler.character_manager.characters.values()
                ]

                await emit_queue.put(
                    ora.SessionCharactersListed(
                        directory=str(handler.character_manager._current_directory or ""),
                        character_count=len(characters),
                        characters=characters,
                    )
                )

            except Exception as e:
                logger.error(f"Failed to list characters: {e}", exc_info=True)
                await emit_queue.put(
                    ora.Error(
                        error=ora.ErrorDetails(
                            type="server_error",
                            code="character_list_failed",
                            message=f"Failed to list characters: {str(e)}",
                        )
                    )
                )

        elif isinstance(message, ora.UnmuteAdditionalOutputs):
            # Don't record this: it's a debugging message and can be verbose. Anything
            # important to store should be in the other event types.
            message_to_record = None

        else:
            logger.info("Ignoring message:", str(message)[:100])

        if message_to_record is not None and handler.recorder is not None:
            await handler.recorder.add_event("client", message_to_record)


class EmitDebugLogger:
    def __init__(self):
        self.last_emitted_n = 0
        self.last_emitted_type = ""

    def on_emit(self, to_emit: ora.ServerEvent):
        if self.last_emitted_type == to_emit.type:
            self.last_emitted_n += 1
        else:
            self.last_emitted_n = 1
            self.last_emitted_type = to_emit.type

        if self.last_emitted_n == 1:
            logger.debug(f"Emitting: {to_emit.type}")
        else:
            logger.debug(f"Emitting ({self.last_emitted_n}): {self.last_emitted_type}")


async def emit_loop(
    websocket: WebSocket,
    handler: UnmuteHandler,
    emit_queue: asyncio.Queue[ora.ServerEvent],
):
    """Send messages to the WebSocket."""
    emit_debug_logger = EmitDebugLogger()

    opus_writer = sphn.OpusStreamWriter(SAMPLE_RATE)

    while True:
        if (
            websocket.application_state == WebSocketState.DISCONNECTED
            or websocket.client_state == WebSocketState.DISCONNECTED
        ):
            logger.info("emit_loop() stopped because WebSocket disconnected")
            raise WebSocketClosedError()

        try:
            to_emit = emit_queue.get_nowait()
        except asyncio.QueueEmpty:
            emitted_by_handler = await handler.emit()

            if emitted_by_handler is None:
                continue
            elif isinstance(emitted_by_handler, AdditionalOutputs):
                assert len(emitted_by_handler.args) == 1
                to_emit = ora.UnmuteAdditionalOutputs(
                    args=emitted_by_handler.args[0],
                )
            elif isinstance(emitted_by_handler, CloseStream):
                # Close here explicitly so that the receive loop stops too
                await websocket.close()
                break
            elif isinstance(emitted_by_handler, ora.ServerEvent):
                to_emit = emitted_by_handler
            else:
                _sr, audio = emitted_by_handler
                audio = audio_to_float32(audio)
                opus_bytes = await asyncio.to_thread(opus_writer.append_pcm, audio)
                # Due to buffering/chunking, Opus doesn't necessarily output something on every PCM added
                if opus_bytes:
                    to_emit = ora.ResponseAudioDelta(
                        delta=base64.b64encode(opus_bytes).decode("utf-8"),
                    )
                else:
                    continue

        emit_debug_logger.on_emit(to_emit)

        if handler.recorder is not None:
            await handler.recorder.add_event("server", to_emit)

        try:
            await websocket.send_text(to_emit.model_dump_json())
        except (WebSocketDisconnect, RuntimeError) as e:
            if isinstance(e, RuntimeError):
                if "Unexpected ASGI message 'websocket.send'" in str(e):
                    # This is expected when the client disconnects
                    message = f"emit_loop() stopped because WebSocket disconnected: {e}"
                else:
                    raise
            else:
                message = (
                    "emit_loop() stopped because WebSocket disconnected: "
                    f"{e.code=} {e.reason=}"
                )

            logger.info(message)
            raise WebSocketClosedError() from e


def _cors_headers_for_error(request: Request):
    origin = request.headers.get("origin")
    allow_origin = origin if origin in CORS_ALLOW_ORIGINS else None
    headers = {"Access-Control-Allow-Credentials": "true"}
    if allow_origin:
        headers["Access-Control-Allow-Origin"] = allow_origin

    return headers


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # We need this so that CORS header are added even when the route raises an
    # exception. Otherwise you get a confusing CORS error even if the issue is totally
    # unrelated.
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=_cors_headers_for_error(request),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # We need this so that CORS header are added even when the route raises an
    # exception. Otherwise you get a confusing CORS error even if the issue is totally
    # unrelated.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=_cors_headers_for_error(request),
    )


if __name__ == "__main__":
    import sys

    print(f"Run this via:\nfastapi dev {sys.argv[0]}")
    exit(1)
