# Quickstart: Per-Session Character Management

**Feature**: 002-multiple-simultaneous-users
**Date**: 2025-10-16
**For**: Developers implementing this feature

## Overview

This guide walks you through implementing per-session character management, enabling multiple simultaneous users to load independent character sets.

**Reading Time**: 15 minutes
**Implementation Time**: 4-6 hours for core functionality

---

## Prerequisites

Before starting, ensure you understand:
- [x] Existing character loading system (`unmute/tts/character_loader.py`)
- [x] WebSocket event handling in `unmute/main_websocket.py`
- [x] `UnmuteHandler` lifecycle (`unmute/unmute_handler.py`)
- [x] Python `importlib` and `sys.modules`
- [x] `asyncio` patterns (tasks, queues, gather)

**Recommended Reading**:
1. [research.md](research.md) - Design decisions
2. [data-model.md](data-model.md) - Entity relationships
3. [contracts/websocket-events.md](contracts/websocket-events.md) - Event specifications

---

## Architecture Overview

### Before (Global State)

```
┌─────────────────────────────────────────┐
│  main_websocket.py                      │
│  ────────────────────────────────────   │
│  _character_manager = CharacterManager() │ ← Global singleton
│                                          │
│  All sessions use the same characters   │
└─────────────────────────────────────────┘
```

### After (Per-Session State)

```
┌─────────────────────────────────────────────────────────┐
│  UnmuteHandler (Session A)                              │
│  ──────────────────────────────────────────────────     │
│  self.character_manager = CharacterManager("abc123")    │ ← Session-specific
│    └─> characters: {                                    │
│          "Charles": VoiceSample(...),                   │
│          "Dev": VoiceSample(...)                        │
│        }                                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  UnmuteHandler (Session B)                              │
│  ──────────────────────────────────────────────────     │
│  self.character_manager = CharacterManager("def456")    │ ← Independent
│    └─> characters: {                                    │
│          "CustomChar1": VoiceSample(...),               │
│          "CustomChar2": VoiceSample(...)                │
│        }                                                │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Refactor `CharacterManager` for Session Scope

**File**: `unmute/tts/character_loader.py`

#### 1.1: Add Session ID to `CharacterManager`

```python
import uuid
import sys
from pathlib import Path

class CharacterManager:
    """Manager for loading and accessing characters from Python files."""

    def __init__(self, session_id: str | None = None):
        """
        Initialize character manager for a session.

        Args:
            session_id: Unique session identifier. If None, generates a new UUID.
        """
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.module_prefix = f"session_{self.session_id}.characters"
        self.characters: Dict[str, VoiceSample] = {}
        self._load_result: CharacterLoadResult | None = None
        self._current_directory: Path | None = None
        logger.info(f"CharacterManager created for session {self.session_id}")
```

**Key Changes**:
- Add `session_id` parameter (optional, defaults to new UUID)
- Create `module_prefix` for namespace isolation
- Add `_current_directory` to track loaded directory
- Log session ID for debugging

---

#### 1.2: Update `_load_character_file_sync` for Namespaced Modules

**Current Code** (loads into global namespace):
```python
def _load_character_file_sync(file_path: Path) -> Dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        f"characters.{file_path.stem}",  # ← Global namespace
        file_path
    )
    # ...
```

**New Code** (loads into session namespace):
```python
def _load_character_file_sync(
    file_path: Path,
    module_prefix: str  # ← NEW parameter
) -> Dict[str, Any]:
    """
    Load a character file with session-specific module namespace.

    Args:
        file_path: Path to character .py file
        module_prefix: Module namespace prefix (e.g., "session_abc123.characters")
    """
    # Ensure characters package exists in sys.modules
    if 'characters' not in sys.modules:
        import characters
        sys.modules['characters'] = characters

    # Load with session-specific namespace
    module_name = f"{module_prefix}.{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)

    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec from {file_path}")

    module = importlib.util.module_from_spec(spec)

    # Register in sys.modules BEFORE execution
    sys.modules[spec.name] = module

    spec.loader.exec_module(module)

    # ... rest of validation code unchanged ...
```

**Update Call Site** in `_load_single_character`:
```python
async def _load_single_character(
    file_path: Path,
    module_prefix: str  # ← NEW parameter
) -> VoiceSample | None:
    try:
        raw_data = await asyncio.to_thread(
            _load_character_file_sync,
            file_path,
            module_prefix  # ← Pass prefix
        )
        # ...
```

**Update Call Site** in `CharacterManager.load_characters`:
```python
async def load_characters(self, characters_dir: Path) -> CharacterLoadResult:
    # ...
    loaded_characters = await asyncio.gather(
        *[
            _load_single_character(file_path, self.module_prefix)  # ← Pass prefix
            for file_path in character_files
        ]
    )
    # ...
```

---

#### 1.3: Add Module Cleanup Method

```python
def cleanup_session_modules(self):
    """
    Remove all session-specific modules from sys.modules.

    This prevents memory leaks when the session ends.
    """
    prefix = f"{self.module_prefix}."
    modules_to_remove = [
        name for name in sys.modules.keys()
        if name.startswith(prefix) or name == self.module_prefix
    ]

    for module_name in modules_to_remove:
        del sys.modules[module_name]
        logger.debug(f"Cleaned up module: {module_name}")

    logger.info(f"Cleaned up {len(modules_to_remove)} modules for session {self.session_id}")
```

---

#### 1.4: Update `reload_characters` Method

Already exists in current implementation, but verify it:
1. Calls `_cleanup_character_modules()` (add if missing)
2. Clears `self.characters` dict
3. Calls `load_characters(new_dir)`
4. Updates `_current_directory`

---

### Step 2: Move `CharacterManager` to `UnmuteHandler`

**File**: `unmute/unmute_handler.py`

#### 2.1: Add `CharacterManager` to `__init__`

```python
class UnmuteHandler(AsyncStreamHandler):
    def __init__(self) -> None:
        super().__init__(
            input_sample_rate=SAMPLE_RATE,
            output_frame_size=480,
            output_sample_rate=SAMPLE_RATE,
        )
        # ... existing initialization ...

        # NEW: Per-session character manager
        from unmute.tts.character_loader import CharacterManager
        self.character_manager = CharacterManager()
        self._characters_loaded = False

        logger.info(f"UnmuteHandler created with session_id={self.character_manager.session_id}")
```

---

#### 2.2: Load Characters in `start_up()`

```python
async def start_up(self):
    """Start up STT and load default characters."""
    await self.start_up_stt()

    # NEW: Load default characters for this session
    from pathlib import Path
    default_dir = Path(__file__).parents[1] / "characters"

    try:
        result = await self.character_manager.load_characters(default_dir)
        logger.info(
            f"Session {self.character_manager.session_id}: "
            f"Loaded {result.loaded_count}/{result.total_files} characters"
        )
        self._characters_loaded = True
    except FileNotFoundError as e:
        logger.warning(f"Default characters not found: {e}")
        self._characters_loaded = False

    self.waiting_for_user_start_time = self.audio_received_sec()
```

---

#### 2.3: Update `update_session()` to Use Session CharacterManager

**Current Code** (uses global manager):
```python
async def update_session(self, session: ora.SessionConfig):
    if session.voice:
        self.tts_voice = session.voice

        from unmute.main_websocket import get_character_manager
        character_manager = get_character_manager()  # ← Global
        character = character_manager.get_character(session.voice)
        # ...
```

**New Code** (uses session manager):
```python
async def update_session(self, session: ora.SessionConfig):
    if session.voice:
        self.tts_voice = session.voice

        # Use session-scoped character manager
        character = self.character_manager.get_character(session.voice)

        if character and hasattr(character, '_prompt_generator'):
            prompt_generator = character._prompt_generator(character.instructions)
            self.chatbot.set_prompt_generator(prompt_generator)
        elif session.instructions:
            # Fallback if character not found
            self.chatbot.set_instructions(session.instructions)
    # ...
```

---

#### 2.4: Add Cleanup to `__aexit__()`

```python
async def __aexit__(self, *exc: Any) -> None:
    """Clean up session resources including character modules."""
    # Existing cleanup
    result = await self.quest_manager.__aexit__(*exc)

    # NEW: Clean up character modules
    if hasattr(self, 'character_manager'):
        self.character_manager.cleanup_session_modules()
        logger.info(f"Session {self.character_manager.session_id} cleanup complete")

    return result
```

---

### Step 3: Add WebSocket Event Handling

**File**: `unmute/openai_realtime_api_events.py`

#### 3.1: Add New Event Models

```python
from typing import Literal
from pydantic import BaseModel, Field

# CLIENT EVENTS

class SessionCharactersReload(BaseModel):
    """Client event to reload characters from a new directory."""
    type: Literal["session.characters.reload"] = "session.characters.reload"
    directory: str = Field(
        ...,
        description="Absolute path to character directory or 'default'"
    )

class SessionCharactersList(BaseModel):
    """Client event to request current character list."""
    type: Literal["session.characters.list"] = "session.characters.list"

# SERVER EVENTS

class CharacterInfo(BaseModel):
    """Character summary for client display."""
    name: str
    good: bool | None = None
    comment: str | None = None

class SessionCharactersReloaded(BaseModel):
    """Server event confirming characters reloaded."""
    type: Literal["session.characters.reloaded"] = "session.characters.reloaded"
    directory: str
    loaded_count: int
    error_count: int
    total_files: int
    characters: list[CharacterInfo]

class SessionCharactersListed(BaseModel):
    """Server event providing current character list."""
    type: Literal["session.characters.listed"] = "session.characters.listed"
    directory: str
    character_count: int
    characters: list[CharacterInfo]
```

#### 3.2: Update `ClientEvent` Union

```python
ClientEvent = (
    SessionUpdate
    | InputAudioBufferAppend
    | InputAudioBufferCommit
    | InputAudioBufferClear
    | SessionCharactersReload  # ← NEW
    | SessionCharactersList    # ← NEW
    # ... other events ...
)

ServerEvent = (
    SessionCreated
    | SessionUpdated
    | ConversationCreated
    | SessionCharactersReloaded  # ← NEW
    | SessionCharactersListed    # ← NEW
    # ... other events ...
)
```

---

### Step 4: Handle Events in WebSocket Route

**File**: `unmute/main_websocket.py`

#### 4.1: Add Event Handlers in `_run_route()`

Find the `_run_route()` function and add handlers:

```python
async def _run_route(websocket: WebSocket, handler: UnmuteHandler):
    """Main WebSocket message loop."""
    # ... existing code ...

    async for receive_loop() and send_loop():
        # ... existing message handling ...

        if event.type == "session.characters.reload":
            await handle_character_reload(websocket, handler, event)

        elif event.type == "session.characters.list":
            await handle_character_list(websocket, handler, event)

        # ... other event types ...
```

#### 4.2: Implement Handler Functions

```python
async def handle_character_reload(
    websocket: WebSocket,
    handler: UnmuteHandler,
    event: ora.SessionCharactersReload
):
    """
    Handle session.characters.reload event.

    Reloads characters from a new directory for this session only.
    """
    from pathlib import Path

    # Resolve "default" keyword
    if event.directory == "default":
        characters_dir = Path(__file__).parents[1] / "characters"
    else:
        characters_dir = Path(event.directory)

    # Validate directory
    if not characters_dir.exists():
        error = make_ora_error(
            type="server_error",
            message=f"Character directory not found: {characters_dir}",
            code="directory_not_found"
        )
        await websocket.send_text(error.model_dump_json())
        return

    if not characters_dir.is_dir():
        error = make_ora_error(
            type="server_error",
            message=f"Path is not a directory: {characters_dir}",
            code="invalid_directory_format"
        )
        await websocket.send_text(error.model_dump_json())
        return

    try:
        # Reload characters (cleans up old modules, loads new ones)
        result = await handler.character_manager.reload_characters(characters_dir)

        if result.loaded_count == 0:
            # Total failure
            error = make_ora_error(
                type="server_error",
                message=f"No valid characters found in directory: {characters_dir}",
                code="no_valid_characters"
            )
            await websocket.send_text(error.model_dump_json())
            return

        # Success response
        character_list = [
            ora.CharacterInfo(
                name=char.name,
                good=char.good,
                comment=char.comment
            )
            for char in result.characters.values()
        ]

        response = ora.SessionCharactersReloaded(
            directory=str(characters_dir),
            loaded_count=result.loaded_count,
            error_count=result.error_count,
            total_files=result.total_files,
            characters=character_list
        )

        await websocket.send_text(response.model_dump_json())
        logger.info(
            f"Session {handler.character_manager.session_id}: "
            f"Reloaded {result.loaded_count} characters from {characters_dir}"
        )

    except Exception as e:
        logger.exception(f"Character reload failed: {e}")
        error = make_ora_error(
            type="server_error",
            message=f"Failed to reload characters: {str(e)}"
        )
        await websocket.send_text(error.model_dump_json())


async def handle_character_list(
    websocket: WebSocket,
    handler: UnmuteHandler,
    event: ora.SessionCharactersList
):
    """
    Handle session.characters.list event.

    Returns the current character list for this session.
    """
    character_list = [
        ora.CharacterInfo(
            name=char.name,
            good=char.good,
            comment=char.comment
        )
        for char in handler.character_manager.characters.values()
    ]

    response = ora.SessionCharactersListed(
        directory=str(handler.character_manager._current_directory or "unknown"),
        character_count=len(character_list),
        characters=character_list
    )

    await websocket.send_text(response.model_dump_json())
```

---

### Step 5: Add Prometheus Metrics

**File**: `unmute/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

# NEW METRICS for per-session character management

CHARACTER_RELOAD_DURATION = Histogram(
    "character_reload_duration_seconds",
    "Time to reload characters mid-session",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

SESSION_CHARACTER_COUNT = Gauge(
    "session_character_count",
    "Number of characters currently loaded in a session",
    ["session_id"]
)

CHARACTER_LOAD_PER_SESSION = Counter(
    "character_load_per_session_total",
    "Characters loaded per session",
    ["session_id"]
)
```

#### Update `CharacterManager.reload_characters()`

```python
async def reload_characters(self, characters_dir: Path) -> CharacterLoadResult:
    from unmute import metrics as mt
    from unmute.timer import Stopwatch

    stopwatch = Stopwatch()
    logger.info(f"Reloading characters from: {characters_dir}")

    # Cleanup and reload
    self._cleanup_character_modules()
    old_count = len(self.characters)
    self.characters = {}

    result = await self.load_characters(characters_dir)

    # Emit metrics
    mt.CHARACTER_RELOAD_DURATION.observe(stopwatch.time())
    mt.SESSION_CHARACTER_COUNT.labels(session_id=self.session_id).set(result.loaded_count)

    logger.info(
        f"Reload complete: {result.loaded_count} characters loaded "
        f"(was {old_count}) in {stopwatch.time():.2f}s"
    )

    return result
```

---

### Step 6: Testing

#### 6.1: Unit Tests

**File**: `tests/test_character_loader_per_session.py` (NEW)

```python
import pytest
import sys
from pathlib import Path
from unmute.tts.character_loader import CharacterManager

@pytest.mark.asyncio
async def test_session_isolation():
    """Test that two sessions can load different characters independently."""
    # Create two character managers with different session IDs
    manager_a = CharacterManager(session_id="test_a")
    manager_b = CharacterManager(session_id="test_b")

    # Load characters from default directory for both
    default_dir = Path(__file__).parents[1] / "characters"
    result_a = await manager_a.load_characters(default_dir)
    result_b = await manager_b.load_characters(default_dir)

    # Both should succeed
    assert result_a.loaded_count > 0
    assert result_b.loaded_count > 0

    # Check module namespaces are different
    modules_a = [k for k in sys.modules.keys() if k.startswith(manager_a.module_prefix)]
    modules_b = [k for k in sys.modules.keys() if k.startswith(manager_b.module_prefix)]

    assert len(modules_a) > 0
    assert len(modules_b) > 0
    assert set(modules_a).isdisjoint(set(modules_b))  # No overlap

    # Cleanup
    manager_a.cleanup_session_modules()
    manager_b.cleanup_session_modules()

@pytest.mark.asyncio
async def test_module_cleanup():
    """Test that session modules are properly removed on cleanup."""
    manager = CharacterManager(session_id="cleanup_test")

    default_dir = Path(__file__).parents[1] / "characters"
    await manager.load_characters(default_dir)

    # Modules should exist
    prefix = manager.module_prefix
    modules_before = [k for k in sys.modules.keys() if k.startswith(prefix)]
    assert len(modules_before) > 0

    # Cleanup
    manager.cleanup_session_modules()

    # Modules should be gone
    modules_after = [k for k in sys.modules.keys() if k.startswith(prefix)]
    assert len(modules_after) == 0
```

---

#### 6.2: Integration Test

**Manual Test Script**:

```python
# test_multi_session.py
import asyncio
import websockets
import json

async def test_two_sessions():
    """Test two simultaneous sessions with different characters."""

    # Session A: Use default characters
    async with websockets.connect("ws://localhost:8000/v1/realtime") as ws_a:
        # Session B: Load custom characters
        async with websockets.connect("ws://localhost:8000/v1/realtime") as ws_b:
            # Session B reloads characters
            reload_msg = {
                "type": "session.characters.reload",
                "directory": "/path/to/custom/characters"
            }
            await ws_b.send(json.dumps(reload_msg))

            # Wait for response
            response_b = await ws_b.recv()
            data_b = json.loads(response_b)
            assert data_b["type"] == "session.characters.reloaded"

            # Session A should still have default characters
            list_msg = {"type": "session.characters.list"}
            await ws_a.send(json.dumps(list_msg))

            response_a = await ws_a.recv()
            data_a = json.loads(response_a)
            assert data_a["type"] == "session.characters.listed"

            print(f"Session A characters: {len(data_a['characters'])}")
            print(f"Session B characters: {len(data_b['characters'])}")

            # Verify they're different
            assert data_a["directory"] != data_b["directory"]

if __name__ == "__main__":
    asyncio.run(test_two_sessions())
```

---

## Verification Checklist

After implementation, verify:

- [ ] Two WebSocket sessions can connect simultaneously
- [ ] Each session loads default characters independently
- [ ] Session A can reload characters without affecting Session B
- [ ] Module namespaces are isolated (check `sys.modules`)
- [ ] Memory cleanup works (modules removed after session ends)
- [ ] Error handling works (invalid directory returns error event)
- [ ] Prometheus metrics are emitted
- [ ] Existing character file format still works
- [ ] No breaking changes to existing clients

---

## Common Pitfalls

### Pitfall 1: Module Conflicts

**Problem**: Two sessions loading the same character file conflict in `sys.modules`.

**Solution**: Ensure `module_prefix` is unique per session and passed to `_load_character_file_sync()`.

---

### Pitfall 2: Memory Leaks

**Problem**: Modules not cleaned up, memory grows with each session.

**Solution**: Always call `cleanup_session_modules()` in `__aexit__()`.

---

### Pitfall 3: Blocking Event Loop

**Problem**: `importlib.util.spec.loader.exec_module()` blocks event loop.

**Solution**: Wrap in `asyncio.to_thread()` (already implemented in current code).

---

### Pitfall 4: Character Registry Not Cleared

**Problem**: Reloading characters doesn't clear old registry, causing duplicates.

**Solution**: Call `self.characters = {}` before loading in `reload_characters()`.

---

## Performance Expectations

| Metric | Target | Typical |
|--------|--------|---------|
| Character load (10 chars) | <1s | 200-500ms |
| Character reload | <2s | 500ms-1s |
| Module cleanup | <100ms | 10-50ms |
| Memory per session | <50 MB | 10-30 MB |
| Concurrent sessions | 50+ | Tested with 10 |

---

## Next Steps

After completing this implementation:

1. **Run tests**: `pytest tests/test_character_loader_per_session.py`
2. **Manual testing**: Use test script above with two WebSocket clients
3. **Monitor metrics**: Check Prometheus dashboard for new metrics
4. **Stress test**: Load 50+ concurrent sessions, monitor memory
5. **Document**: Update README with new WebSocket events

---

## Troubleshooting

### Issue: "Module already in sys.modules"

**Cause**: Module prefix not unique or cleanup didn't run.

**Fix**: Check `session_id` is unique, verify `cleanup_session_modules()` is called.

---

### Issue: Characters not loading

**Cause**: Directory path invalid or character files malformed.

**Fix**: Check logs for specific error, validate character file format.

---

### Issue: Memory keeps growing

**Cause**: Sessions not cleaning up modules.

**Fix**: Verify `__aexit__()` is called, check for exceptions preventing cleanup.

---

## Summary

You've implemented per-session character management! Key achievements:

✅ **Isolation**: Each session has independent character registry
✅ **Namespacing**: Session-unique module prefixes prevent conflicts
✅ **Dynamic Reloading**: Users can switch character sets mid-session
✅ **Resource Cleanup**: Modules removed when sessions end
✅ **Observability**: Prometheus metrics track per-session behavior
✅ **Backward Compatible**: Existing clients continue to work

**Estimated Lines Changed**: ~300-400 lines across 4 files.

---

## Further Reading

- [research.md](research.md) - Detailed design decisions and alternatives
- [data-model.md](data-model.md) - Entity relationships and data flow
- [contracts/websocket-events.md](contracts/websocket-events.md) - Event specifications
- [../003-i-want-the/quickstart.md](../003-i-want-the/quickstart.md) - Character file format
