# Data Model: Per-Session Character Management

**Feature**: 002-multiple-simultaneous-users
**Date**: 2025-10-16

## Overview

This document defines the data structures and relationships for per-session character management. All entities are in-memory only (no database persistence).

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  UserSession (WebSocket Connection)                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ UnmuteHandler                                         │  │
│  │ ─────────────                                         │  │
│  │ + session_id: str                                     │  │
│  │ + character_manager: CharacterManager                 │  │
│  │ + chatbot: Chatbot                                    │  │
│  │ + tts_voice: str | None                               │  │
│  │ ─────────────                                         │  │
│  │ + start_up() -> None                                  │  │
│  │ + update_session(session: SessionConfig) -> None     │  │
│  │                                                       │  │
│  │   ┌───────────────────────────────────────────┐      │  │
│  │   │ CharacterManager                          │      │  │
│  │   │ ────────────────                          │      │  │
│  │   │ + session_id: str                         │      │  │
│  │   │ + module_prefix: str                      │      │  │
│  │   │ + characters: Dict[str, VoiceSample]      │      │  │
│  │   │ + _current_directory: Path                │      │  │
│  │   │ ────────────────                          │      │  │
│  │   │ + load_characters(dir: Path) -> Result    │      │  │
│  │   │ + reload_characters(dir: Path) -> Result  │      │  │
│  │   │ + get_character(name: str) -> VoiceSample │      │  │
│  │   │ + cleanup_session_modules() -> None       │      │  │
│  │   │                                           │      │  │
│  │   │   ┌──────────────────────────────┐       │      │  │
│  │   │   │ VoiceSample                  │       │      │  │
│  │   │   │ ───────────                  │       │      │  │
│  │   │   │ + name: str                  │       │      │  │
│  │   │   │ + source: VoiceSource        │       │      │  │
│  │   │   │ + instructions: dict         │       │      │  │
│  │   │   │ + good: bool | None          │       │      │  │
│  │   │   │ + _source_file: str          │       │      │  │
│  │   │   │ + _prompt_generator: Type    │       │      │  │
│  │   │   └──────────────────────────────┘       │      │  │
│  │   │                                           │      │  │
│  │   └───────────────────────────────────────────┘      │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

Relationships:
- UserSession (1) ──── (1) UnmuteHandler
- UnmuteHandler (1) ──── (1) CharacterManager
- CharacterManager (1) ──── (0..*) VoiceSample
```

---

## Core Entities

### 1. UserSession (WebSocket Connection)

**Conceptual Entity**: Represents a single user's WebSocket connection to the system.

**Implementation**: Managed by FastAPI WebSocket lifecycle (`websocket_route()` in `main_websocket.py`).

**Lifecycle**:
1. **Created**: When WebSocket connection established
2. **Active**: During conversation (audio streaming, character interactions)
3. **Destroyed**: When WebSocket disconnects (normal or error)

**Relationships**:
- Has exactly one `UnmuteHandler` instance
- May have zero or more character reloads during its lifetime

---

### 2. UnmuteHandler

**Purpose**: Per-session handler for audio stream processing and character management.

**Attributes**:

| Attribute | Type | Description | Validation |
|-----------|------|-------------|------------|
| `character_manager` | `CharacterManager` | Session-scoped character registry | Required, initialized in `__init__()` |
| `tts_voice` | `str \| None` | Currently selected character name | Optional, set via `update_session()` |
| `chatbot` | `Chatbot` | Conversation manager | Required |
| `output_queue` | `asyncio.Queue` | Event queue for WebSocket | Required |

**State Transitions**:

```
┌──────────┐     start_up()      ┌───────────┐    update_session()   ┌─────────────┐
│ Created  │ ──────────────────> │  Started  │ ───────────────────>  │  Character  │
│          │                     │           │                       │   Loaded    │
└──────────┘                     └───────────┘                       └─────────────┘
     │                                 │                                     │
     │                                 │                                     │
     └────────────────────__aexit__()───────────────────────────────────────┘
                                       │
                                       ▼
                               ┌──────────────┐
                               │  Cleaned Up  │
                               └──────────────┘
```

**Behavior**:
- **Initialization**: Creates session-scoped `CharacterManager`
- **Startup**: Loads default characters from `characters/` directory
- **Runtime**: Responds to `session.characters.reload` events
- **Cleanup**: Calls `character_manager.cleanup_session_modules()` on exit

---

### 3. CharacterManager

**Purpose**: Manages character loading, registry, and module isolation for a single session.

**Attributes**:

| Attribute | Type | Description | Validation | Example |
|-----------|------|-------------|------------|---------|
| `session_id` | `str` | Unique session identifier | 8-character UUID prefix | `"abc12345"` |
| `module_prefix` | `str` | Namespace prefix for modules | `f"session_{session_id}.characters"` | `"session_abc12345.characters"` |
| `characters` | `Dict[str, VoiceSample]` | Character registry (name → instance) | Key = character name, must be unique | `{"Charles": VoiceSample(...)}` |
| `_current_directory` | `Path \| None` | Currently loaded directory | Absolute path or None | `Path("/home/user/characters")` |
| `_load_result` | `CharacterLoadResult \| None` | Most recent load result | Contains counts and metrics | `CharacterLoadResult(...)` |

**Methods**:

#### `load_characters(characters_dir: Path) -> CharacterLoadResult`

Loads characters from a directory into the session's registry.

**Behavior**:
1. Validates directory exists
2. Discovers all `.py` files (except `__init__.py`)
3. Loads each file concurrently using `asyncio.gather()`
4. Validates character structure (PromptGenerator, required attributes)
5. Registers characters in `self.characters` dict
6. Detects duplicates (first-loaded-wins)
7. Updates Prometheus metrics
8. Returns result with counts

**Validation Rules**:
- Directory must exist and be readable
- Character files must have `.py` extension
- Each character must have: `CHARACTER_NAME`, `VOICE_SOURCE`, `INSTRUCTIONS`, `PromptGenerator` class
- Duplicate character names rejected (logged as error)

**Error Handling**:
- Partial failure allowed (some characters load, others fail)
- Each failed character logged with specific error type
- Metrics track errors by type (ImportError, ValidationError, etc.)

#### `reload_characters(characters_dir: Path) -> CharacterLoadResult`

Reloads characters from a new directory, clearing previous characters.

**Behavior**:
1. Cleans up old modules from `sys.modules` (via `_cleanup_character_modules()`)
2. Clears `self.characters` dict
3. Calls `load_characters(characters_dir)`
4. Updates `_current_directory`
5. Logs reload event

**Side Effects**:
- Removes all `session_{session_id}.characters.*` modules from `sys.modules`
- Clears character registry (old characters no longer accessible)
- Active conversations using old characters are invalidated

#### `get_character(name: str) -> VoiceSample | None`

Retrieves a character by name from the session's registry.

**Behavior**:
- Simple dict lookup: `return self.characters.get(name)`
- Returns `None` if character not found (caller handles missing character)

#### `cleanup_session_modules()`

Removes all session-specific modules from `sys.modules`.

**Behavior**:
1. Finds all modules with prefix `session_{session_id}.characters.`
2. Deletes each from `sys.modules`
3. Logs cleanup (DEBUG level)

**Called By**: `UnmuteHandler.__aexit__()` on session termination

---

### 4. VoiceSample

**Purpose**: Represents a single character with voice configuration and conversation instructions.

**Attributes**:

| Attribute | Type | Description | Validation | Example |
|-----------|------|-------------|------------|---------|
| `name` | `str \| None` | Character display name | Must be unique within session | `"Charles de Gaulle"` |
| `source` | `VoiceSource` | Voice audio source | Pydantic discriminated union | `FileVoiceSource(...)` |
| `instructions` | `dict[str, Any] \| None` | Character behavior config | Arbitrary dict | `{"language": "fr"}` |
| `good` | `bool \| None` | Is character production-ready | Optional | `True` |
| `comment` | `str \| None` | Developer notes | Optional | `"Historical figure"` |
| `_source_file` | `str` | Original filename | Internal, not serialized | `"charles.py"` |
| `_prompt_generator` | `Type[PromptGenerator]` | Prompt generator class | Internal, not serialized | `charles.PromptGenerator` |

**Validation Rules**:
- `name`: Must be non-empty if provided
- `source`: Must be valid `FileVoiceSource` or `FreesoundVoiceSource`
- `instructions`: No validation (arbitrary dict)
- `_prompt_generator`: Must have `__init__(self, instructions)` and `make_system_prompt() -> str` methods

**Relationships**:
- Belongs to exactly one `CharacterManager`
- Referenced by `UnmuteHandler.update_session()` for character selection
- Used by `Chatbot` to generate system prompts

---

### 5. CharacterLoadResult

**Purpose**: Result object containing metrics from character loading operation.

**Attributes**:

| Attribute | Type | Description |
|-----------|------|-------------|
| `characters` | `Dict[str, VoiceSample]` | Successfully loaded characters |
| `total_files` | `int` | Total `.py` files discovered |
| `loaded_count` | `int` | Successfully loaded characters |
| `error_count` | `int` | Failed character loads |
| `load_duration` | `float` | Time in seconds to complete loading |

**Usage**:
- Returned by `load_characters()` and `reload_characters()`
- Used to emit Prometheus metrics
- Sent to client in `SessionCharactersReloaded` event

---

## Data Flow

### Session Initialization (Default Characters)

```
WebSocket Connect
       │
       ▼
websocket_route()
       │
       ▼
UnmuteHandler.__init__()
       │
       ├─> CharacterManager.__init__()
       │       │
       │       └─> session_id = uuid.uuid4()[:8]
       │       └─> module_prefix = f"session_{session_id}.characters"
       │       └─> characters = {}
       │
       ▼
UnmuteHandler.start_up()
       │
       ├─> start_up_stt()
       │
       └─> character_manager.load_characters(default_dir)
               │
               ├─> Discover .py files
               ├─> Load concurrently (asyncio.gather)
               ├─> Validate each character
               ├─> Register in characters dict
               └─> Return CharacterLoadResult
```

### Character Reload (Mid-Session)

```
Client sends: session.characters.reload
       │
       ▼
_run_route() receives event
       │
       ▼
handler.handle_character_reload(event)
       │
       ├─> Validate directory path
       │
       ├─> character_manager.reload_characters(new_dir)
       │       │
       │       ├─> _cleanup_character_modules()
       │       │       └─> Delete session_*.characters.* from sys.modules
       │       │
       │       ├─> Clear characters dict
       │       │
       │       └─> load_characters(new_dir)
       │               └─> (same flow as initialization)
       │
       └─> Send SessionCharactersReloaded event to client
               └─> {loaded_count, error_count, directory}
```

### Character Selection (Update Session)

```
Client sends: session.update {voice: "Charles"}
       │
       ▼
UnmuteHandler.update_session(session)
       │
       ├─> self.tts_voice = session.voice
       │
       └─> character = self.character_manager.get_character(session.voice)
               │
               ├─> Lookup in characters dict
               │
               └─> if found:
                       └─> Instantiate character._prompt_generator
                       └─> chatbot.set_prompt_generator(prompt_gen)
```

### Session Cleanup

```
WebSocket Disconnect
       │
       ▼
UnmuteHandler.__aexit__()
       │
       ├─> quest_manager.__aexit__()  (existing cleanup)
       │
       └─> character_manager.cleanup_session_modules()
               │
               └─> Delete all session_*.characters.* from sys.modules
                       └─> Free memory
```

---

## Module Namespace Isolation

### Problem

Multiple sessions loading the same character filename would conflict in `sys.modules`:

```
Session A loads /custom1/charles.py  → sys.modules["characters.charles"]
Session B loads /custom2/charles.py  → sys.modules["characters.charles"] (CONFLICT!)
```

### Solution

Use session-unique module prefixes:

```
Session A (id: "abc123"):
  /custom1/charles.py → sys.modules["session_abc123.characters.charles"]

Session B (id: "def456"):
  /custom2/charles.py → sys.modules["session_def456.characters.charles"]
```

### Implementation

```python
# In CharacterManager._load_character_file_sync()
module_name = f"{self.module_prefix}.{file_path.stem}"
# Example: "session_abc123.characters.charles"

spec = importlib.util.spec_from_file_location(module_name, file_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module  # Register with unique name
spec.loader.exec_module(module)
```

---

## Validation Rules Summary

### CharacterManager
- `session_id`: Must be unique (generated via UUID)
- `module_prefix`: Must follow pattern `session_{session_id}.characters`
- `characters`: Keys must be unique character names

### Character Files (Validated During Load)
- Must have `.py` extension
- Must define `CHARACTER_NAME` (str)
- Must define `VOICE_SOURCE` (dict with `source_type`)
- Must define `INSTRUCTIONS` (dict)
- Must define `PromptGenerator` class with:
  - `__init__(self, instructions)` method
  - `make_system_prompt(self) -> str` method

### Directory Paths
- Must be absolute paths (or "default" keyword)
- Must exist on filesystem
- Must be readable by server process

---

## State Transitions

### CharacterManager States

```
┌─────────────┐
│   Created   │  CharacterManager.__init__()
└──────┬──────┘
       │
       │ load_characters(dir)
       │
       ▼
┌─────────────┐
│   Loaded    │  characters dict populated
└──────┬──────┘
       │
       │ reload_characters(new_dir)
       │
       ▼
┌─────────────┐
│  Reloading  │  Old modules cleaned up
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Loaded    │  New characters dict populated
└──────┬──────┘
       │
       │ cleanup_session_modules()
       │
       ▼
┌─────────────┐
│  Cleaned Up │  Modules removed from sys.modules
└─────────────┘
```

---

## Memory Management

### Per-Session Memory Estimate

| Component | Size per Instance | Quantity per Session | Total |
|-----------|-------------------|----------------------|-------|
| CharacterManager | ~1 KB | 1 | 1 KB |
| VoiceSample | ~2 KB | 10-20 | 20-40 KB |
| Character Module | ~500 KB - 2 MB | 10-20 | 5-40 MB |
| **Total** | | | **~5-40 MB** |

### 50 Concurrent Sessions

- **Minimum**: 50 × 5 MB = 250 MB
- **Maximum**: 50 × 40 MB = 2 GB
- **Typical**: 50 × 20 MB = 1 GB

**Acceptable for server deployment**: Yes (typical servers have 8-16 GB RAM)

---

## Relationships to Existing Entities

### UnmuteHandler (Existing)
- **Before**: No character manager (used global singleton)
- **After**: Has `self.character_manager` (per-session instance)

### Chatbot (Existing)
- **No changes required**: Receives `PromptGenerator` instance as before
- Still calls `set_prompt_generator(prompt_gen)`

### TTS Service (Existing)
- **No changes required**: Receives voice configuration as before
- `UnmuteHandler.tts_voice` still passed to TTS initialization

### WebSocket Events (Extended)
- **New events**: `SessionCharactersReload`, `SessionCharactersReloaded`
- **Existing events unchanged**: `SessionConfig`, `SessionUpdate`, etc.

---

## Prometheus Metrics

### New Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `character_load_per_session_total` | Counter | `session_id` | Characters loaded per session |
| `character_reload_duration_seconds` | Histogram | - | Time to reload characters |
| `session_character_count` | Gauge | `session_id` | Current character count per session |

### Existing Metrics (Reused)

| Metric | Type | Labels | Usage |
|--------|------|--------|-------|
| `CHARACTER_LOAD_COUNT` | Counter | - | Total characters loaded (aggregate) |
| `CHARACTER_LOAD_ERRORS` | Counter | `error_type` | Character loading errors |
| `CHARACTER_LOAD_DURATION` | Histogram | - | Character loading duration |

---

## Summary

This data model provides:
- ✅ **Isolation**: Per-session character registries with unique module namespaces
- ✅ **Lifecycle**: Clear creation → loading → reloading → cleanup flow
- ✅ **Validation**: Comprehensive rules for characters and directories
- ✅ **Observability**: Prometheus metrics for monitoring
- ✅ **Memory Safety**: Explicit cleanup prevents leaks
- ✅ **Backward Compatibility**: Existing character file format unchanged
