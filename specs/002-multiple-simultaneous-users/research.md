# Research & Design Decisions: Per-Session Character Management

**Feature**: 002-multiple-simultaneous-users
**Date**: 2025-10-16
**Status**: Design Complete

## Overview

This document captures the research, design decisions, and technical approaches for implementing per-session character management, enabling multiple simultaneous users to maintain independent character sets.

## Key Design Decisions

### 1. Module Namespace Isolation Strategy

**Decision**: Use session-unique module prefixes in `sys.modules` to prevent naming conflicts

**Rationale**:
- Python's `sys.modules` is a global dictionary where imported modules are cached
- Two sessions loading `charles.py` from different directories would conflict if both use `characters.charles`
- Solution: Prefix each session's modules with a unique identifier (e.g., `session_abc123.characters.charles`)
- This allows `importlib.util.module_from_spec()` to load the same filename multiple times with different namespaces

**Implementation Approach**:
```python
# In CharacterManager.__init__()
self.session_id = str(uuid.uuid4())[:8]  # Short unique ID
self.module_prefix = f"session_{self.session_id}.characters"

# When loading charles.py:
module_name = f"{self.module_prefix}.charles"
# Results in: session_abc123.characters.charles
```

**Alternatives Considered**:
1. **Reload existing modules**: Use `importlib.reload()` - rejected because it would affect all sessions using that module
2. **No isolation, shared modules**: Rejected because two sessions can't load different `charles.py` files
3. **Separate Python processes per session**: Rejected due to high memory overhead and complexity

**Trade-offs**:
- ✅ Pro: Complete isolation, no cross-session interference
- ✅ Pro: Simple implementation, leverages Python's module system
- ⚠️  Con: Higher memory usage (each session loads its own module instances)
- ⚠️  Con: Need explicit cleanup of `sys.modules` on session end

---

### 2. CharacterManager Lifecycle

**Decision**: Move `CharacterManager` from global singleton to per-session instance in `UnmuteHandler`

**Rationale**:
- `UnmuteHandler` is already per-session (created for each WebSocket connection)
- Storing `CharacterManager` in `UnmuteHandler` provides natural session scope
- Session cleanup (`UnmuteHandler.__aexit__()`) can trigger character cleanup
- No need for session ID tracking at global level

**Implementation Approach**:
```python
class UnmuteHandler(AsyncStreamHandler):
    def __init__(self) -> None:
        super().__init__(...)
        # ... existing code ...
        self.character_manager = CharacterManager()  # NEW: Per-session instance
        self._characters_loaded = False
```

**Current Architecture** (global):
```
main_websocket.py:
  _character_manager = CharacterManager()  # Global singleton

  @app.on_event("startup")
  async def startup_event():
      await _character_manager.load_characters(default_dir)
```

**New Architecture** (per-session):
```
UnmuteHandler:
  __init__():
      self.character_manager = CharacterManager()  # Per-session instance

  start_up():
      await self.character_manager.load_characters(default_dir)
```

**Alternatives Considered**:
1. **Global registry of CharacterManagers by session ID**: Rejected as more complex, requires manual cleanup tracking
2. **Keep global singleton, add session_id parameter to all methods**: Rejected because it doesn't prevent module conflicts
3. **Lazy loading (don't load until first character access)**: Rejected because it adds latency to first conversation

**Trade-offs**:
- ✅ Pro: Natural scoping, automatic cleanup with session
- ✅ Pro: No global state to manage
- ⚠️  Con: Slightly higher session initialization time (character loading on connect)

---

### 3. Character Loading Timing

**Decision**: Load default characters at session startup (`UnmuteHandler.start_up()`), support async reload via WebSocket event

**Rationale**:
- Users expect characters to be immediately available when they connect
- Loading at startup spreads the cost across session initialization (already async)
- Async reload allows users to switch character sets without reconnecting

**Implementation Approach**:
```python
async def start_up(self):
    # Existing STT startup
    await self.start_up_stt()

    # NEW: Load default characters for this session
    default_dir = Path(__file__).parents[1] / "characters"
    await self.character_manager.load_characters(default_dir)
    self._characters_loaded = True

    self.waiting_for_user_start_time = self.audio_received_sec()
```

**Alternatives Considered**:
1. **Lazy loading on first character access**: Rejected because it adds unpredictable latency to first interaction
2. **Pre-fork worker pool with pre-loaded characters**: Rejected as too complex for this use case
3. **Load on first message only**: Rejected because empty message handling already starts response generation

**Trade-offs**:
- ✅ Pro: Predictable session startup time
- ✅ Pro: Characters ready immediately
- ⚠️  Con: Adds ~200-500ms to session initialization (measured in current global implementation)

---

### 4. WebSocket Protocol Extension

**Decision**: Add new client event type `session.characters.reload` to trigger per-session reload

**Rationale**:
- Existing OpenAI Realtime API events don't cover character management
- WebSocket is the natural communication channel (already authenticated session)
- Follows existing event pattern in `openai_realtime_api_events.py`

**Event Schema**:
```python
class SessionCharactersReload(BaseModel):
    """Client event to reload characters from a different directory"""
    type: Literal["session.characters.reload"] = "session.characters.reload"
    directory: str  # Absolute path or "default"

class SessionCharactersReloaded(BaseModel):
    """Server event confirming characters reloaded"""
    type: Literal["session.characters.reloaded"] = "session.characters.reloaded"
    loaded_count: int
    error_count: int
    directory: str
```

**Event Flow**:
```
Client                          Server (UnmuteHandler)
  |                                    |
  |--session.characters.reload------->|
  |   {directory: "/custom/chars"}    |
  |                                    |
  |                          [Load characters]
  |                          [Clear old modules]
  |                          [Update registry]
  |                                    |
  |<--session.characters.reloaded-----|
  |   {loaded_count: 5, errors: 0}    |
  |                                    |
  |<--session.update-------------------|  (Optional: new character list)
```

**Alternatives Considered**:
1. **HTTP endpoint + session token**: Rejected because it requires out-of-band authentication
2. **Extend existing `session.update` event**: Rejected to avoid polluting existing well-defined event
3. **Automatic detection of directory changes**: Rejected as too magical, no clear user intent

**Trade-offs**:
- ✅ Pro: Clean separation of concerns
- ✅ Pro: Follows existing event patterns
- ⚠️  Con: Requires client-side support (but gracefully degraded if not implemented)

---

### 5. Module Cleanup Strategy

**Decision**: Clean up session-specific modules from `sys.modules` in `UnmuteHandler.__aexit__()`

**Rationale**:
- Python doesn't automatically remove modules from `sys.modules`
- Without cleanup, memory usage grows indefinitely as sessions connect/disconnect
- `UnmuteHandler.__aexit__()` is called on session close (normal or exceptional)

**Implementation Approach**:
```python
class CharacterManager:
    def cleanup_session_modules(self):
        """Remove all session-specific modules from sys.modules"""
        prefix = f"{self.module_prefix}."
        modules_to_remove = [
            name for name in sys.modules.keys()
            if name.startswith(prefix)
        ]
        for name in modules_to_remove:
            del sys.modules[name]
            logger.debug(f"Cleaned up module: {name}")

class UnmuteHandler:
    async def __aexit__(self, *exc):
        # Existing cleanup
        await self.quest_manager.__aexit__(*exc)

        # NEW: Clean up character modules
        if hasattr(self, 'character_manager'):
            self.character_manager.cleanup_session_modules()
```

**Alternatives Considered**:
1. **Garbage collection only**: Rejected because modules in `sys.modules` have strong references
2. **Periodic cleanup task**: Rejected as more complex, cleanup should happen synchronously with session end
3. **No cleanup (rely on process restart)**: Rejected because it leaks memory in long-running server

**Trade-offs**:
- ✅ Pro: Prevents memory leaks
- ✅ Pro: Explicit, predictable cleanup
- ⚠️  Con: Must ensure all references to character modules are cleared before cleanup

---

### 6. Character Access Pattern

**Decision**: Characters are accessed via `self.character_manager.get_character(name)` in `UnmuteHandler.update_session()`

**Rationale**:
- Existing code path: `update_session()` receives voice name, looks up character
- Per-session `CharacterManager` naturally provides session-scoped lookup
- No changes needed to TTS or LLM integration

**Current Flow** (global):
```python
async def update_session(self, session: ora.SessionConfig):
    if session.voice:
        self.tts_voice = session.voice
        from unmute.main_websocket import get_character_manager
        character_manager = get_character_manager()  # Global
        character = character_manager.get_character(session.voice)
```

**New Flow** (per-session):
```python
async def update_session(self, session: ora.SessionConfig):
    if session.voice:
        self.tts_voice = session.voice
        # Use session's own CharacterManager (no import needed)
        character = self.character_manager.get_character(session.voice)
```

**Alternatives Considered**:
1. **Pass session_id to global manager**: Rejected because it doesn't solve module isolation
2. **Create new character lookup service**: Rejected as unnecessary abstraction
3. **Cache characters in UnmuteHandler directly**: Rejected because CharacterManager already provides this

**Trade-offs**:
- ✅ Pro: Minimal code changes
- ✅ Pro: Natural scoping
- ✅ Pro: Type-safe, no runtime session ID lookups

---

### 7. Error Handling During Reload

**Decision**: Partial failure is acceptable - load valid characters, report errors for invalid ones

**Rationale**:
- Existing `CharacterManager.load_characters()` already implements this pattern
- Users should know which characters failed to load but can continue with valid ones
- Matches principle of graceful degradation

**Implementation Approach**:
```python
result = await self.character_manager.load_characters(new_dir)
# result.loaded_count, result.error_count, result.characters

if result.loaded_count == 0:
    # Total failure - send error event
    await self.output_queue.put(make_ora_error(
        type="error",
        message=f"Failed to load any characters from {new_dir}"
    ))
else:
    # Partial or full success - send success event with counts
    await self.output_queue.put(ora.SessionCharactersReloaded(
        loaded_count=result.loaded_count,
        error_count=result.error_count,
        directory=str(new_dir)
    ))
```

**Alternatives Considered**:
1. **All-or-nothing loading**: Rejected because one bad character file shouldn't block all others
2. **Silent failures**: Rejected because users need feedback on what went wrong
3. **Automatic retry**: Rejected because character file errors are typically permanent (syntax errors, etc.)

**Trade-offs**:
- ✅ Pro: Resilient to partial failures
- ✅ Pro: Clear user feedback
- ⚠️  Con: Users might not notice some characters failed to load if they don't check counts

---

### 8. Prometheus Metrics Strategy

**Decision**: Add session-level character metrics with session_id labels where appropriate

**Rationale**:
- Existing metrics infrastructure uses Prometheus client library
- Session-level metrics help diagnose per-user issues
- Aggregate metrics (no labels) still useful for overall system health

**New Metrics**:
```python
# In metrics.py

CHARACTER_LOAD_PER_SESSION = Counter(
    "character_load_per_session_total",
    "Characters loaded per session",
    ["session_id"]  # High cardinality, but sessions are transient
)

SESSION_CHARACTER_COUNT = Gauge(
    "session_character_count",
    "Number of characters currently loaded in a session",
    ["session_id"]
)

CHARACTER_RELOAD_DURATION = Histogram(
    "character_reload_duration_seconds",
    "Time to reload characters mid-session",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)
```

**Alternatives Considered**:
1. **No per-session metrics**: Rejected because debugging multi-user issues requires session-level visibility
2. **Only aggregate metrics**: Rejected because it hides per-session problems
3. **Full session history in metrics**: Rejected because it increases cardinality too much

**Trade-offs**:
- ✅ Pro: Detailed observability
- ✅ Pro: Can track memory/performance per session
- ⚠️  Con: Higher cardinality (but mitigated by session transience)

---

## Technical Constraints & Assumptions

### Constraints

1. **Python Module System Limitations**:
   - `sys.modules` is global across all threads
   - Module imports are not thread-safe without GIL
   - Must use unique module names to avoid conflicts

2. **Memory Constraints**:
   - Each character: ~1-2 MB (module code + PromptGenerator instance)
   - Estimated 10-50 MB per session with 10-20 characters
   - 50 sessions × 30 MB = ~1.5 GB character data (acceptable for server)

3. **Performance Constraints**:
   - Character loading must complete in <2 seconds (user expectation)
   - Module import is CPU-bound (benefit from GIL-free periods in asyncio)
   - File I/O for reading `.py` files is relatively fast

### Assumptions

1. **Session Lifetime**:
   - Average session: 5-30 minutes
   - Character reload: Rare operation (1-2 times per session max)
   - Most users will use default characters (no custom loading)

2. **Character File Validity**:
   - Character files are trusted (not user-uploaded)
   - Character directories are pre-created by administrators
   - No malicious code in character files (same trust level as current implementation)

3. **Concurrency**:
   - Multiple sessions loading characters concurrently is common
   - Character file reads don't conflict (read-only, separate files)
   - `asyncio.to_thread()` provides sufficient isolation for blocking imports

4. **WebSocket Client Support**:
   - Clients may not implement `session.characters.reload` event (optional feature)
   - Fallback: Users can disconnect/reconnect to get new characters (existing behavior)
   - Frontend can add support incrementally

---

## Best Practices Applied

### From Python Ecosystem

1. **Dynamic Module Loading**:
   - Use `importlib.util.spec_from_file_location()` for safe module loading
   - Use `importlib.util.module_from_spec()` to create module objects
   - Register in `sys.modules` before execution (supports internal imports)

2. **Async Patterns**:
   - Use `asyncio.to_thread()` for blocking operations (module import)
   - Use `asyncio.gather()` for concurrent character loading
   - Maintain existing async queue patterns for event communication

3. **Resource Cleanup**:
   - Use context managers (`async with`) for session lifecycle
   - Explicit cleanup in `__aexit__()` for deterministic resource release
   - Remove modules from `sys.modules` to prevent leaks

### From FastAPI/WebSocket Patterns

1. **Event-Driven Architecture**:
   - Extend existing OpenAI Realtime API event pattern
   - Use Pydantic models for event validation
   - Maintain backward compatibility (new events optional)

2. **Error Handling**:
   - Graceful degradation (partial character loading success)
   - Clear error messages to clients
   - Non-fatal errors don't disconnect session

### From Observability Best Practices

1. **Metrics Coverage**:
   - Counter for success/failure events
   - Histogram for duration measurements
   - Gauge for current state
   - Labels for dimensionality (session_id, error_type)

2. **Structured Logging**:
   - Log character loading events with session context
   - Log module cleanup for debugging
   - Use log levels appropriately (INFO for lifecycle, DEBUG for details)

---

## Migration Strategy

### Phase 1: Preparation (No Breaking Changes)

1. Add per-session metrics to `metrics.py`
2. Add new event types to `openai_realtime_api_events.py`
3. Update `CharacterManager` to support session-scoped initialization
4. Add tests for module namespace isolation

### Phase 2: Core Refactor

1. Move `CharacterManager` to `UnmuteHandler.__init__()`
2. Update `character_loader.py` to use session-specific module prefixes
3. Update `UnmuteHandler.start_up()` to load characters per session
4. Update `UnmuteHandler.update_session()` to use session character manager

### Phase 3: Feature Addition

1. Add WebSocket event handler for `session.characters.reload`
2. Implement module cleanup in `UnmuteHandler.__aexit__()`
3. Add session initialization character loading metrics

### Phase 4: Testing & Validation

1. Unit tests for module isolation
2. Integration tests for multi-session scenarios
3. Memory profiling with 50+ concurrent sessions
4. Performance validation (character loading <2s)

### Rollback Plan

If issues arise:
1. Keep global `_character_manager` as fallback
2. Add feature flag: `ENABLE_PER_SESSION_CHARACTERS` (default: false)
3. Run both paths in parallel (A/B test)
4. Monitor metrics for regressions

---

## Open Questions & Future Work

### Open Questions

None - all design decisions are resolved.

### Future Enhancements (Out of Scope for This Feature)

1. **Character Caching**: Cache frequently-used characters at global level, copy to sessions
2. **Character Preloading**: Predict which characters users will want, preload in background
3. **Character Sharing**: Allow users to share custom character directories with others
4. **Character Versioning**: Track character file versions, support rollback
5. **Admin Dashboard**: Web UI to monitor which users have which characters loaded
6. **Character Quotas**: Limit number of characters per session or per user
7. **Hot Reload**: Detect character file changes on disk, automatically reload

---

## References

- Current implementation: `unmute/tts/character_loader.py`
- Session management: `unmute/unmute_handler.py`
- WebSocket events: `unmute/openai_realtime_api_events.py`
- Metrics: `unmute/metrics.py`
- Constitution: `.specify/memory/constitution.md`
