# WebSocket Events Contract: Per-Character Conversation History

**Feature**: 003-change-the-conversation
**Date**: 2025-01-27

## Overview

This document defines the WebSocket event contracts for character switching and conversation history management. Most events already exist in the OpenAI Realtime API format; this feature reuses existing events with modified behavior.

---

## Existing Events (Modified Behavior)

### 1. session.update (Client → Server)

**Purpose**: Switch to a different character without disconnecting the session.

**Existing Behavior** (Feature 002):

- Updates TTS voice
- Updates system prompt for the character
- Conversation history continues (NOT cleared)

**New Behavior** (Feature 003):

- Updates TTS voice
- Switches to character-specific conversation history
- Restores previous conversation if character was used before
- Creates fresh conversation if character is new
- **No disconnection required**

**Event Structure**:

```json
{
  "type": "session.update",
  "event_id": "event_ABC123...",
  "session": {
    "voice": "charles", // Character name to switch to
    "allow_recording": true // Recording preference (unchanged)
  }
}
```

**Backend Handler**: `unmute/main_websocket.py:receive_loop()`

**Processing Flow**:

1. Receive `SessionUpdate` event
2. Call `handler.update_session(message.session)`
3. UnmuteHandler looks up character from `character_manager`
4. Calls `chatbot.switch_character(character_name, system_prompt)`
5. Updates `self.tts_voice`
6. Sends `SessionUpdated` response

**Success Response**: `session.updated` (see below)

**Error Scenarios**:

- Character not found → Send `error` event with `code="character_not_found"`
- Invalid character name → Send `error` event with `code="invalid_character"`
- Switch requested mid-response → Queue switch for after response completes

---

### 2. session.updated (Server → Client)

**Purpose**: Confirm that character switch was successful.

**Event Structure**:

```json
{
  "type": "session.updated",
  "event_id": "event_XYZ789...",
  "session": {
    "voice": "charles", // Character that is now active
    "allow_recording": true // Recording preference (unchanged)
  }
}
```

**Client Behavior**:

- Update UI to reflect active character
- **Do NOT disconnect or reconnect**
- Continue conversation with new character

**Note**: This event already exists; no changes to its structure.

---

## New Events (Future Extensions)

These events are NOT implemented in the initial version but are defined here for future reference.

### 3. character.history.clear (Client → Server) - DEFERRED

**Purpose**: Clear conversation history for a specific character.

**Status**: Function will be implemented, but trigger mechanism is deferred per clarifications.

**Potential Event Structure** (for future implementation):

```json
{
  "type": "character.history.clear",
  "event_id": "event_DEF456...",
  "character_name": "charles" // Character whose history to clear
}
```

**Backend Handler**: Would call `chatbot.clear_character_history(character_name)`

**Success Response**:

```json
{
  "type": "character.history.cleared",
  "event_id": "event_GHI789...",
  "character_name": "charles",
  "cleared_at": 1706368800.0 // Timestamp
}
```

**Note**: This may be triggered programmatically by character code rather than user action.

---

### 4. character.history.clear_all (Client → Server) - DEFERRED

**Purpose**: Clear all character conversation histories in the current session.

**Status**: Function will be implemented, but trigger mechanism is deferred.

**Potential Event Structure** (for future implementation):

```json
{
  "type": "character.history.clear_all",
  "event_id": "event_JKL012..."
}
```

**Backend Handler**: Would call `chatbot.clear_all_histories()`

**Success Response**:

```json
{
  "type": "character.history.all_cleared",
  "event_id": "event_MNO345...",
  "cleared_count": 5, // Number of character histories cleared
  "cleared_at": 1706368800.0
}
```

**Note**: Session disconnect automatically clears all histories; this event would be for manual clearing mid-session.

---

## Error Events

### Character Not Found

**Trigger**: `session.update` specifies a character that doesn't exist in the session's character manager.

**Event Structure**:

```json
{
  "type": "error",
  "event_id": "event_ERR123...",
  "error": {
    "type": "server_error",
    "code": "character_not_found",
    "message": "Character 'invalid_name' not found in available characters",
    "param": "session.voice",
    "details": {
      "requested_character": "invalid_name",
      "available_characters": ["charles", "développeuse", "gertrude", "..."]
    }
  }
}
```

**Client Behavior**:

- Display error message to user
- Remain on current character
- Do NOT disconnect

**Backend Behavior**:

- Log warning
- Keep current character active
- Do NOT crash or disconnect session

---

### Character Switch Failed

**Trigger**: Unexpected error during character switch operation.

**Event Structure**:

```json
{
  "type": "error",
  "event_id": "event_ERR456...",
  "error": {
    "type": "server_error",
    "code": "character_switch_failed",
    "message": "Failed to switch to character 'charles': Internal error",
    "param": "session.voice",
    "details": {
      "requested_character": "charles",
      "error_details": "Exception during prompt generation"
    }
  }
}
```

**Client Behavior**:

- Display error message
- Remain on current character
- Optionally retry switch

**Backend Behavior**:

- Log error with stack trace
- Emit `CHARACTER_SWITCH_ERRORS` metric
- Keep current character active
- Session remains connected

---

## Event Sequences

### Sequence 1: First-Time Character Switch

```
Client                          Server (Backend)
  │                                  │
  ├──── session.update ─────────────►│ (voice: "charles")
  │                                  ├─ Lookup character
  │                                  ├─ Create new CharacterHistory
  │                                  ├─ Set system prompt
  │                                  ├─ Update current_character
  │                                  ├─ Emit CHARACTER_SWITCH metric
  │◄───── session.updated ───────────┤
  │                                  │
```

**Timing**: < 100ms (in-memory operations)

**State After**:

- `chatbot.current_character = "charles"`
- `chatbot.character_histories["charles"]` exists with 1 message (system prompt)
- Previous character's history (if any) preserved

---

### Sequence 2: Switch Back to Previous Character

```
Client                          Server (Backend)
  │                                  │
  ├──── session.update ─────────────►│ (voice: "développeuse")
  │                                  ├─ Lookup character
  │                                  ├─ Find existing CharacterHistory
  │                                  ├─ Restore history
  │                                  ├─ Update current_character
  │                                  ├─ Update last_accessed timestamp
  │                                  ├─ Emit CHARACTER_SWITCH metric
  │◄───── session.updated ───────────┤
  │                                  │
```

**Timing**: < 50ms (simple dictionary lookup)

**State After**:

- `chatbot.current_character = "développeuse"`
- Previous conversation history for "développeuse" is now active
- "charles" history remains preserved

---

### Sequence 3: Switch During Response (Edge Case)

```
Client                          Server (Backend)
  │                                  │
  ├──── (User message) ─────────────►│
  │◄───── response.created ──────────┤
  │                                  ├─ LLM generating...
  │◄───── response.text.delta ───────┤ "Hello, I'm thinking..."
  │                                  │
  ├──── session.update ─────────────►│ (voice: "charles" - switch request)
  │                                  ├─ Acquire turn_transition_lock
  │                                  ├─ BLOCKED - LLM response in progress
  │                                  │
  │◄───── response.text.delta ───────┤ "...about your question..."
  │◄───── response.text.done ────────┤
  │◄───── response.audio.done ───────┤
  │                                  ├─ Release turn_transition_lock
  │                                  │
  │                                  ├─ NOW process character switch
  │                                  ├─ Switch to "charles"
  │◄───── session.updated ───────────┤
  │                                  │
```

**Timing**: Switch waits for response completion (variable, typically 5-30s)

**State After**:

- Original character completed their response
- Response added to original character's history
- Switch to new character executed
- New character's history is now active

**Important**: This satisfies FR-008 (complete current response before switching).

---

### Sequence 4: Session Disconnect Clears All

```
Client                          Server (Backend)
  │                                  │
  ├──── (WebSocket close) ──────────►│
  │                                  ├─ UnmuteHandler.__aexit__()
  │                                  ├─ chatbot.clear_all_histories()
  │                                  │   ├─ Emit CHARACTER_HISTORY_CLEARS
  │                                  │   │  for each character
  │                                  │   ├─ Clear character_histories dict
  │                                  │   └─ Set current_character = None
  │                                  ├─ character_manager.cleanup_session_modules()
  │                                  └─ Session destroyed
```

**Timing**: < 1 second (per SC-004)

**State After**:

- All character histories destroyed
- Session handler destroyed
- Memory freed

---

## Backward Compatibility

### Existing Code Using chat_history

**Challenge**: Many parts of the codebase access `chatbot.chat_history` directly.

**Solution**: `chat_history` becomes a property that delegates to current character's history.

**Example**:

```python
# Old code (still works)
messages = handler.chatbot.chat_history
print(f"Message count: {len(messages)}")

# New internal implementation
@property
def chat_history(self) -> list[dict]:
    return self.get_current_history()
```

**Affected Code** (no changes needed):

- `unmute_handler.py:159` - GradioUpdate creation
- `unmute_handler.py:197` - ResponseCreated event
- `unmute_handler.py:251` - Interruption detection
- Frontend display via additional outputs

**All existing code continues to work without modification.**

---

## Frontend Changes Required

### Current Behavior (Feature 002)

**File**: `frontend/src/app/Unmute.tsx:243-248`

```typescript
// Disconnect when the voice changes.
// TODO: If it's a voice change, immediately reconnect with the new voice.
useEffect(() => {
  setShouldConnect(false);
  shutdownAudio();
}, [shutdownAudio, unmuteConfig.voice]);
```

**Issue**: This disconnects and reconnects on every character change.

### New Behavior (Feature 003)

**File**: `frontend/src/app/Unmute.tsx:243-248`

```typescript
// Character switching is handled via session.update without disconnecting
// REMOVED: useEffect that disconnects on voice change
```

**Alternative** (if you want to keep the useEffect for other purposes):

```typescript
// Allow character switching without disconnect
useEffect(() => {
  // Character switching handled by session.update event
  // Only disconnect if explicit user action (not implemented yet)
  // setShouldConnect(false);  // COMMENTED OUT
  // shutdownAudio();           // COMMENTED OUT
}, [shutdownAudio, unmuteConfig.voice]);
```

**Result**: Character switches send `session.update` but don't trigger disconnect/reconnect.

---

## Testing Contract Compliance

### Test 1: session.update Triggers Character Switch

```python
# Backend test
async def test_session_update_switches_character():
    handler = UnmuteHandler()
    await handler.start_up()

    # Send session.update
    await handler.update_session(ora.SessionConfig(
        voice="charles",
        allow_recording=True
    ))

    # Verify switch occurred
    assert handler.chatbot.current_character == "charles"
    assert handler.tts_voice == "charles"
```

### Test 2: session.updated Response Sent

```python
# Backend test with mock WebSocket
async def test_session_updated_sent(mock_websocket):
    handler = UnmuteHandler()
    await handler.start_up()

    emit_queue = asyncio.Queue()

    # Process session.update
    message = ora.SessionUpdate(session=ora.SessionConfig(
        voice="charles",
        allow_recording=True
    ))

    await handler.update_session(message.session)
    await emit_queue.put(ora.SessionUpdated(session=message.session))

    # Verify response
    response = await emit_queue.get()
    assert isinstance(response, ora.SessionUpdated)
    assert response.session.voice == "charles"
```

### Test 3: Error on Invalid Character

```python
# Backend test
async def test_invalid_character_error():
    handler = UnmuteHandler()
    await handler.start_up()

    # Try to switch to non-existent character
    with pytest.raises(Exception):  # or specific error type
        await handler.update_session(ora.SessionConfig(
            voice="nonexistent_character",
            allow_recording=True
        ))

    # Verify current character unchanged
    assert handler.chatbot.current_character is not None  # Remains on previous
```

### Test 4: Frontend Doesn't Disconnect

```typescript
// Frontend test (pseudo-code)
test("character switch does not disconnect", async () => {
  const { rerender } = render(<Unmute />);

  // Connect
  await connectToSession();

  // Change character
  const charlésButton = screen.getByText("/ charles /");
  await user.click(charlesButton);

  // Verify connection remains
  expect(websocketState).toBe("OPEN");
  expect(shouldConnect).toBe(true);
});
```

---

## Performance Requirements

| Operation                   | Target Latency | Measured By                           |
| --------------------------- | -------------- | ------------------------------------- |
| Character switch (new)      | < 100ms        | `CHARACTER_SWITCH_DURATION` histogram |
| Character switch (existing) | < 50ms         | `CHARACTER_SWITCH_DURATION` histogram |
| History retrieval           | < 1ms          | Direct property access (not measured) |
| Session disconnect + clear  | < 1s           | `__aexit__()` timing                  |

**Note**: These are in-memory operations and should be very fast. Network latency is separate.

---

## Security Considerations

### Session Isolation

- Character histories are session-scoped (per `UnmuteHandler` instance)
- No cross-session access possible
- Histories destroyed on session end

### Data Privacy

- No persistent storage of conversation content
- All data in memory only
- Cleared immediately on disconnect
- No logging of conversation content (only metadata)

### Input Validation

- Character names validated against loaded character list
- Invalid characters rejected with error event
- No arbitrary code execution from character names

---

## Metrics Emitted

### CHARACTER_SWITCH_COUNT

```python
CHARACTER_SWITCH_COUNT.labels(
    from_character="charles",
    to_character="développeuse"
).inc()
```

**When**: Every successful character switch

**Labels**: `from_character`, `to_character`

### CHARACTER_SWITCH_DURATION

```python
CHARACTER_SWITCH_DURATION.observe(duration_seconds)
```

**When**: Every character switch (success or failure)

**Buckets**: [0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0]

### CHARACTER_HISTORY_SIZE

```python
CHARACTER_HISTORY_SIZE.labels(character="charles").set(message_count)
```

**When**: After each message addition or switch

**Labels**: `character`

### CHARACTER_HISTORY_CLEARS

```python
CHARACTER_HISTORY_CLEARS.labels(
    character="charles",
    reason="session_end"  # or "manual"
).inc()
```

**When**: History cleared (per character or all)

**Labels**: `character`, `reason`

---

## Summary

**Key Points**:

- ✅ Reuses existing `session.update` / `session.updated` events
- ✅ No new events required for initial implementation
- ✅ Backward compatible via `chat_history` property
- ✅ Frontend requires minor change (remove disconnect behavior)
- ✅ Clear error handling for edge cases
- ✅ Performance targets defined and measurable

**Future Extensions**:

- `character.history.clear` event (deferred)
- `character.history.clear_all` event (deferred)
- Trigger mechanisms TBD in later phase

---

## References

- **OpenAI Realtime API Events**: `unmute/openai_realtime_api_events.py`
- **Data Model**: `data-model.md`
- **Research**: `research.md`
- **Quickstart**: `quickstart.md`
