# Browser-backend communication protocol

This document explains how the browser frontend and backend service communicate through WebSocket connections in the Unmute system.

## Overview

Unmute uses a WebSocket-based protocol inspired by the [OpenAI Realtime API](https://platform.openai.com/docs/api-reference/realtime) for real-time voice conversations. The protocol handles:

- Real-time audio streaming (bidirectional)
- Voice conversation transcription
- Session configuration
- Error handling and debugging

## WebSocket connection

### Endpoint
- **URL**: `/v1/realtime`
- **Protocol**: `realtime` (specified in WebSocket subprotocol)
- **Port**: 8000 (development), routed through Traefik in Docker Swarm and Compose. Traefik uses http (port 80) and https (port 443).

### Connection setup

**Frontend** ([`frontend/src/app/Unmute.tsx`](../frontend/src/app/Unmute.tsx)):
```typescript
const { sendMessage, lastMessage, readyState } = useWebSocket(
  webSocketUrl || null,
  {
    protocols: ["realtime"],
  },
  shouldConnect
);
```

**Backend** ([`unmute/main_websocket.py`](../unmute/main_websocket.py)):
```python
@app.websocket("/v1/realtime")
async def websocket_route(websocket: WebSocket):
    await websocket.accept(subprotocol="realtime")
    # ... handler logic
```

## Message protocol

All messages are JSON-encoded with a common structure defined in [`unmute/openai_realtime_api_events.py`](../unmute/openai_realtime_api_events.py).

### Base message structure

```python
class BaseEvent(BaseModel, Generic[T]):
    type: T                    # Message type identifier
    event_id: str             # Unique event ID (auto-generated)
```

## Client → server messages

### 1. Audio input streaming

**Message Type**: `input_audio_buffer.append`

**Purpose**: Stream real-time audio data from microphone to backend

**Frontend Implementation** ([`frontend/src/app/Unmute.tsx`](../frontend/src/app/Unmute.tsx)):
```typescript
const onOpusRecorded = useCallback(
  (opus: Uint8Array) => {
    sendMessage(
      JSON.stringify({
        type: "input_audio_buffer.append",
        audio: base64EncodeOpus(opus),
      })
    );
  },
  [sendMessage]
);
```

**Backend Model** ([`unmute/openai_realtime_api_events.py`](../unmute/openai_realtime_api_events.py)):
```python
class InputAudioBufferAppend(BaseEvent[Literal["input_audio_buffer.append"]]):
    audio: str  # Base64-encoded Opus data
```

**Audio Format**:
- **Codec**: Opus
- **Sample Rate**: 24kHz
- **Channels**: Mono
- **Encoding**: Base64-encoded bytes

### 2. Session configuration

**Message Type**: `session.update`

**Purpose**: Configure voice character and conversation instructions

**Frontend Implementation** ([`frontend/src/app/Unmute.tsx`](../frontend/src/app/Unmute.tsx)):
```typescript
sendMessage(
  JSON.stringify({
    type: "session.update",
    session: {
      instructions: unmuteConfig.instructions,
      voice: unmuteConfig.voice,
    },
  })
);
```

**Backend Models** ([`unmute/openai_realtime_api_events.py`](../unmute/openai_realtime_api_events.py)):
```python
class SessionConfig(BaseModel):
    instructions: Instructions | None = None  # Character instructions
    voice: str | None = None                  # Voice ID from voices.yaml

class SessionUpdate(BaseEvent[Literal["session.update"]]):
    session: SessionConfig
```

## Server → client messages

### 1. Audio response streaming

**Message Type**: `response.audio.delta`

**Purpose**: Stream generated speech audio to frontend

**Backend Implementation** ([`unmute/main_websocket.py`](../unmute/main_websocket.py)):
```python
opus_bytes = await asyncio.to_thread(opus_writer.append_pcm, audio)
if opus_bytes:
    to_emit = ora.ResponseAudioDelta(
        delta=base64.b64encode(opus_bytes).decode("utf-8"),
    )
```

**Frontend Handling** ([`frontend/src/app/Unmute.tsx`](../frontend/src/app/Unmute.tsx)):
```typescript
if (data.type === "response.audio.delta") {
  const opus = base64DecodeOpus(data.delta);
  const ap = audioProcessor.current;
  if (!ap) return;

  ap.decoder.postMessage(
    {
      command: "decode",
      pages: opus,
    },
    [opus.buffer]
  );
}
```

### 2. Speech transcription

**Message Type**: `conversation.item.input_audio_transcription.delta`

**Purpose**: Real-time transcription of user speech

**Backend Implementation** ([`unmute/unmute_handler.py`](../unmute/unmute_handler.py)):
```python
await self.output_queue.put(
    ora.ConversationItemInputAudioTranscriptionDelta(
        delta=data.text,
        start_time=data.start_time,
    )
)
```

**Frontend Handling** ([`frontend/src/app/Unmute.tsx`](../frontend/src/app/Unmute.tsx)):
```typescript
else if (data.type === "conversation.item.input_audio_transcription.delta") {
  setRawChatHistory((prev) => [
    ...prev,
    { role: "user", content: data.delta },
  ]);
}
```

### 3. Text response streaming

**Message Type**: `response.text.delta`

**Purpose**: Stream generated text responses (for display/debugging)

**Backend Implementation** ([`unmute/unmute_handler.py`](../unmute/unmute_handler.py)):
```python
await output_queue.put(ora.ResponseTextDelta(delta=message.text))
```

**Frontend Handling** ([`frontend/src/app/Unmute.tsx`](../frontend/src/app/Unmute.tsx)):
```typescript
else if (data.type === "response.text.delta") {
  setRawChatHistory((prev) => [
    ...prev,
    { role: "assistant", content: " " + data.delta },
  ]);
}
```

### 4. Speech detection events

**Message Types**:
- `input_audio_buffer.speech_started`
- `input_audio_buffer.speech_stopped`

**Purpose**: Indicate when user starts/stops speaking (for UI feedback)

**Backend Implementation** ([`unmute/unmute_handler.py`](../unmute/unmute_handler.py)):
```python
# Speech stopped (pause detected)
await self.output_queue.put(ora.InputAudioBufferSpeechStopped())

# Speech started (first transcription received)
await self.output_queue.put(ora.InputAudioBufferSpeechStarted())
```

### 5. Response status updates

**Message Type**: `response.created`

**Purpose**: Indicate when assistant starts generating a response

**Backend Model** ([`unmute/openai_realtime_api_events.py`](../unmute/openai_realtime_api_events.py)):
```python
class Response(BaseModel):
    object: Literal["realtime.response"] = "realtime.response"
    status: Literal["in_progress", "completed", "cancelled", "failed", "incomplete"]
    voice: str
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
```

### 6. Error handling

**Message Type**: `error`

**Purpose**: Communicate errors and warnings

**Backend Implementation** ([`unmute/main_websocket.py`](../unmute/main_websocket.py)):
```python
await emit_queue.put(
    ora.Error(
        error=ora.ErrorDetails(
            type="invalid_request_error",
            message="Invalid message",
            details=json.loads(e.json()),
        )
    )
)
```

**Frontend Handling** ([`frontend/src/app/Unmute.tsx`](../frontend/src/app/Unmute.tsx)):
```typescript
else if (data.type === "error") {
  if (data.error.type === "warning") {
    console.warn(`Warning from server: ${data.error.message}`, data);
  } else {
    console.error(`Error from server: ${data.error.message}`, data);
    setErrors((prev) => [...prev, makeErrorItem(data.error.message)]);
  }
}
```

## Connection lifecycle

1. **Health Check**: Frontend checks `/v1/health` endpoint
2. **WebSocket Connection**: Establish connection with `realtime` protocol
3. **Session Setup**: Send `session.update` with voice and instructions
4. **Audio Streaming**: Bidirectional real-time audio communication
5. **Graceful Shutdown**: Handle disconnection and cleanup

