# Developer Quickstart: Per-Character Conversation History

**Feature**: 003-change-the-conversation
**Date**: 2025-01-27

## Overview

This guide helps developers understand, test, and debug the per-character conversation history feature.

---

## Quick Start: Testing the Feature

### Prerequisites

1. Backend server running (`unmute/main_websocket.py`)
2. Frontend server running (`frontend/`)
3. At least 2 characters loaded (e.g., "charles", "développeuse")
4. WebSocket connection established

### Basic Test Scenario

**Goal**: Verify that switching between characters preserves separate histories.

**Steps**:

1. **Connect and select first character**:

   ```typescript
   // Frontend automatically sends on connect
   {
     type: "session.update",
     session: {
       voice: "charles",
       allow_recording: true
     }
   }
   ```

2. **Have a conversation with Charles**:

   - Say: "Hello Charles, what's your favorite color?"
   - Wait for response
   - Say: "That's interesting!"
   - Wait for response
   - **Result**: Charles's history has 5 messages (system + 2 user + 2 assistant)

3. **Switch to another character** (click "Développeuse" in UI):

   ```typescript
   // Frontend sends
   {
     type: "session.update",
     session: {
       voice: "développeuse",
       allow_recording: true
     }
   }
   ```

4. **Have a conversation with Développeuse**:

   - Say: "Hello, can you help me with code?"
   - Wait for response
   - **Result**: Développeuse's history has 3 messages (system + 1 user + 1 assistant)
   - **Important**: Développeuse should NOT know about the conversation with Charles

5. **Switch back to Charles**:

   - Click "charles" in UI
   - Say: "What was my question again?"
   - **Expected**: Charles should remember the conversation about favorite colors
   - **Result**: Charles's history now has 7 messages (original 5 + 2 new)

6. **Disconnect**:

   - Click disconnect button
   - **Result**: All character histories cleared

7. **Reconnect and select Charles**:
   - Connect again
   - Select Charles
   - **Expected**: Charles starts with fresh history (no memory of previous session)

**Success Criteria**:

- ✅ Each character maintains separate conversation history
- ✅ Switching characters preserves previous conversations
- ✅ Characters don't share conversation context
- ✅ Disconnect clears all histories

---

## Architecture Overview

### Key Components

```
Frontend (Unmute.tsx)
    ↓ WebSocket: session.update
Backend (main_websocket.py:receive_loop)
    ↓ calls
UnmuteHandler.update_session()
    ↓ calls
Chatbot.switch_character()
    ↓ manages
CharacterHistory (per character)
```

### Data Structures

```python
# In Chatbot class
self.character_histories = {
    "charles": CharacterHistory(
        character_name="charles",
        messages=[
            {"role": "system", "content": "You are Charles..."},
            {"role": "user", "content": "Hello Charles..."},
            {"role": "assistant", "content": "Hello! ..."},
        ],
        created_at=123.45,
        last_accessed=126.78
    ),
    "développeuse": CharacterHistory(
        character_name="développeuse",
        messages=[
            {"role": "system", "content": "You are Développeuse..."},
            {"role": "user", "content": "Can you help..."},
            {"role": "assistant", "content": "Of course! ..."},
        ],
        created_at=125.67,
        last_accessed=128.90
    )
}
self.current_character = "charles"  # or "développeuse"
```

---

## Development Workflow

### Setting Up Local Environment

```bash
# Terminal 1: Start backend
cd /path/to/audio-game
python -m unmute.main_websocket

# Terminal 2: Start frontend
cd frontend/
npm run dev

# Terminal 3: Monitor logs
tail -f logs/unmute.log  # or wherever logs are configured
```

### Enabling Debug Logging

Add to `unmute/llm/chatbot.py`:

```python
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def switch_character(self, character_name: str, system_prompt: str):
    logger.debug(f"Switching character: {self.current_character} → {character_name}")
    logger.debug(f"Existing histories: {list(self.character_histories.keys())}")
    # ... rest of implementation
```

### Using Python REPL for Testing

```python
# Test CharacterHistory class
from unmute.llm.chatbot import CharacterHistory

history = CharacterHistory("test_char", "You are a test character", 0.0)
history.add_message({"role": "user", "content": "Hello"})
history.add_message({"role": "assistant", "content": "Hi there!"})

print(f"Message count: {history.message_count}")
print(f"System prompt: {history.get_system_prompt()}")

# Test truncation
for i in range(150):
    history.add_message({"role": "user", "content": f"Message {i}"})

removed = history.truncate_if_needed(max_messages=100)
print(f"Removed {removed} messages")
print(f"New count: {history.message_count}")  # Should be 100
```

---

## Testing Guide

### Unit Tests

**Location**: `tests/test_chatbot_character_history.py`

**Run**: `pytest tests/test_chatbot_character_history.py -v`

**Key Test Cases**:

```python
import pytest
from unmute.llm.chatbot import Chatbot, CharacterHistory

def test_character_history_creation():
    """Test that new character history is created correctly."""
    history = CharacterHistory("charles", "You are Charles", 0.0)
    assert history.character_name == "charles"
    assert history.message_count == 1  # system prompt
    assert history.messages[0]["role"] == "system"

def test_switch_to_new_character():
    """Test switching to a character for the first time."""
    chatbot = Chatbot()
    chatbot.switch_character("charles", "You are Charles")

    assert chatbot.current_character == "charles"
    assert "charles" in chatbot.character_histories
    assert chatbot.get_current_history()[0]["role"] == "system"

def test_switch_preserves_history():
    """Test that switching back restores previous history."""
    chatbot = Chatbot()

    # Talk to Charles
    chatbot.switch_character("charles", "You are Charles")
    chatbot.chat_history.append({"role": "user", "content": "Hello"})

    # Switch to Développeuse
    chatbot.switch_character("développeuse", "You are Développeuse")
    chatbot.chat_history.append({"role": "user", "content": "Bonjour"})

    # Switch back to Charles
    chatbot.switch_character("charles", "You are Charles")

    # Verify Charles's history preserved
    messages = chatbot.get_current_history()
    assert len(messages) == 2  # system + user
    assert messages[1]["content"] == "Hello"

def test_clear_character_history():
    """Test clearing a specific character's history."""
    chatbot = Chatbot()
    chatbot.switch_character("charles", "You are Charles")
    chatbot.switch_character("développeuse", "You are Développeuse")

    chatbot.clear_character_history("charles")

    assert "charles" not in chatbot.character_histories
    assert "développeuse" in chatbot.character_histories

def test_clear_all_histories():
    """Test clearing all character histories."""
    chatbot = Chatbot()
    chatbot.switch_character("charles", "You are Charles")
    chatbot.switch_character("développeuse", "You are Développeuse")

    chatbot.clear_all_histories()

    assert len(chatbot.character_histories) == 0
    assert chatbot.current_character is None

def test_truncation():
    """Test that history truncates at 100 messages."""
    history = CharacterHistory("test", "System prompt", 0.0)

    # Add 150 messages
    for i in range(150):
        history.add_message({"role": "user", "content": f"Message {i}"})

    removed = history.truncate_if_needed(max_messages=100)

    assert removed == 51  # 151 total - 100 max = 51 removed
    assert history.message_count == 100
    assert history.messages[0]["role"] == "system"  # System prompt preserved
    assert history.messages[1]["content"] == "Message 50"  # Oldest kept is #50

def test_backward_compatibility():
    """Test that chat_history property works for existing code."""
    chatbot = Chatbot()
    chatbot.switch_character("charles", "You are Charles")

    # Existing code can still access chat_history
    assert isinstance(chatbot.chat_history, list)
    assert len(chatbot.chat_history) == 1  # system prompt
```

### Integration Tests

**Location**: `tests/test_character_switching.py`

**Run**: `pytest tests/test_character_switching.py -v`

**Requires**: Mock WebSocket and UnmuteHandler

```python
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from unmute.unmute_handler import UnmuteHandler
import unmute.openai_realtime_api_events as ora

@pytest.mark.asyncio
async def test_character_switch_via_session_update():
    """Test character switching through session.update event."""
    handler = UnmuteHandler()
    await handler.start_up()

    # Initial character
    await handler.update_session(ora.SessionConfig(
        voice="charles",
        allow_recording=True
    ))

    # Add a message
    await handler.add_chat_message_delta("Hello", "user")
    assert len(handler.chatbot.chat_history) == 2  # system + user

    # Switch character
    await handler.update_session(ora.SessionConfig(
        voice="développeuse",
        allow_recording=True
    ))

    # New character should have fresh history
    assert len(handler.chatbot.chat_history) == 1  # only system prompt

    # Switch back
    await handler.update_session(ora.SessionConfig(
        voice="charles",
        allow_recording=True
    ))

    # Charles's history should be restored
    assert len(handler.chatbot.chat_history) == 2  # system + user
    assert handler.chatbot.chat_history[1]["content"] == "Hello"

@pytest.mark.asyncio
async def test_session_disconnect_clears_histories():
    """Test that disconnect clears all histories."""
    handler = UnmuteHandler()
    await handler.start_up()

    # Create multiple character histories
    await handler.update_session(ora.SessionConfig(voice="charles", allow_recording=True))
    await handler.add_chat_message_delta("Hello Charles", "user")

    await handler.update_session(ora.SessionConfig(voice="développeuse", allow_recording=True))
    await handler.add_chat_message_delta("Hello Dev", "user")

    # Verify histories exist
    assert len(handler.chatbot.character_histories) == 2

    # Disconnect (trigger __aexit__)
    async with handler:
        pass  # Context exit triggers cleanup

    # Verify all histories cleared
    assert len(handler.chatbot.character_histories) == 0
```

### Manual Testing Checklist

**Test Case 1: Basic Character Switching**

- [ ] Connect to session
- [ ] Select Character A
- [ ] Have 2-3 exchanges with Character A
- [ ] Switch to Character B
- [ ] Verify Character B starts with fresh conversation
- [ ] Have 1-2 exchanges with Character B
- [ ] Switch back to Character A
- [ ] Verify Character A's previous conversation is restored
- [ ] Verify correct message count for each character

**Test Case 2: Multiple Characters**

- [ ] Connect to session
- [ ] Switch between 5+ different characters
- [ ] Have at least 1 exchange with each
- [ ] Switch back to first character
- [ ] Verify first character's history preserved
- [ ] Check memory usage is reasonable (<10 MB)

**Test Case 3: History Truncation**

- [ ] Connect to session
- [ ] Select one character
- [ ] Have ~60 exchanges (120 messages)
- [ ] Verify history truncates to 100 messages
- [ ] Verify system prompt still present
- [ ] Verify oldest messages removed

**Test Case 4: Session Disconnect**

- [ ] Connect to session
- [ ] Create histories for 3+ characters
- [ ] Disconnect (close WebSocket)
- [ ] Reconnect to new session
- [ ] Select same character as before
- [ ] Verify history is fresh (no memory of previous session)

**Test Case 5: Mid-Response Switch**

- [ ] Connect to session
- [ ] Select Character A
- [ ] Ask a question
- [ ] While Character A is responding, click Character B
- [ ] Verify Character A completes their response
- [ ] Verify switch happens after response completes
- [ ] Verify Character B starts fresh

---

## Debugging Guide

### Common Issues

#### Issue 1: Character History Not Preserved

**Symptoms**: Switching back to a character shows fresh history instead of previous conversation.

**Debugging Steps**:

1. Check if character name is consistent:

   ```python
   # Add logging in switch_character()
   logger.debug(f"Switching to: '{character_name}'")
   logger.debug(f"Existing keys: {list(self.character_histories.keys())}")
   ```

2. Verify character lookup:

   ```python
   # In UnmuteHandler.update_session()
   character = self.character_manager.get_character(session.voice)
   logger.debug(f"Character lookup result: {character}")
   ```

3. Check for unintended history clearing:
   ```python
   # Search for calls to clear_character_history or clear_all_histories
   grep -r "clear.*history" unmute/
   ```

**Solution**: Ensure character names are exactly consistent (case-sensitive, no extra whitespace).

---

#### Issue 2: History Not Cleared on Disconnect

**Symptoms**: After reconnecting, character remembers previous session.

**Debugging Steps**:

1. Verify `__aexit__` is called:

   ```python
   # Add logging in UnmuteHandler.__aexit__()
   logger.info("Session cleanup: clearing all character histories")
   ```

2. Check if cleanup is executed:

   ```python
   # In __aexit__()
   logger.debug(f"Histories before clear: {list(self.chatbot.character_histories.keys())}")
   self.chatbot.clear_all_histories()
   logger.debug(f"Histories after clear: {list(self.chatbot.character_histories.keys())}")
   ```

3. Verify new session creates new handler:
   ```python
   # In main_websocket.py:websocket_route
   logger.info(f"Creating new UnmuteHandler (id: {id(handler)})")
   ```

**Solution**: Ensure `__aexit__` is properly called and `clear_all_histories()` is executed.

---

#### Issue 3: Memory Growth with Long Conversations

**Symptoms**: Memory usage increases without bounds during long conversations.

**Debugging Steps**:

1. Check if truncation is being called:

   ```python
   # Add logging in truncate_if_needed()
   if len(self.messages) > max_messages:
       logger.warning(f"Truncating {self.character_name}: {len(self.messages)} → {max_messages}")
   ```

2. Monitor message counts:

   ```python
   # In add_chat_message_delta()
   logger.debug(f"Current message count for {self.current_character}: {len(self.get_current_history())}")
   ```

3. Check memory usage:
   ```python
   import sys
   history_size_bytes = sys.getsizeof(self.character_histories)
   logger.debug(f"Character histories size: {history_size_bytes / 1024:.2f} KB")
   ```

**Solution**: Ensure `truncate_if_needed()` is called after each message addition.

---

#### Issue 4: System Prompt Lost After Truncation

**Symptoms**: After truncation, character behaves differently or loses personality.

**Debugging Steps**:

1. Verify system prompt position:

   ```python
   # In truncate_if_needed()
   logger.debug(f"First message before truncate: {self.messages[0]}")
   # ... truncation logic ...
   logger.debug(f"First message after truncate: {self.messages[0]}")
   assert self.messages[0]["role"] == "system", "System prompt lost!"
   ```

2. Check truncation logic:
   ```python
   # Should be: [messages[0]] + messages[-(MAX-1):]
   # NOT: messages[:MAX] (would keep old messages, lose recent ones)
   ```

**Solution**: Ensure truncation preserves system prompt at index 0.

---

#### Issue 5: Race Condition During Switch

**Symptoms**: Character switch happens mid-response, causing corrupted or mixed responses.

**Debugging Steps**:

1. Verify lock usage:

   ```python
   # In update_session()
   async with self.turn_transition_lock:
       logger.debug("Acquired turn_transition_lock for character switch")
       # ... switching logic ...
   ```

2. Check if lock is held during response generation:

   ```python
   # In _generate_response()
   async with self.turn_transition_lock:
       # ... LLM generation ...
   ```

3. Log switch timing:
   ```python
   logger.debug(f"Conversation state during switch: {self.chatbot.conversation_state()}")
   ```

**Solution**: Ensure `turn_transition_lock` is used consistently in both `update_session()` and `_generate_response()`.

---

### Metrics for Debugging

Use Prometheus metrics to diagnose issues:

```bash
# Check character switch count
curl http://localhost:8000/metrics | grep character_switch_total

# Check history sizes
curl http://localhost:8000/metrics | grep character_history_messages

# Check truncations
curl http://localhost:8000/metrics | grep character_history_truncations_total

# Check clears
curl http://localhost:8000/metrics | grep character_history_clears_total
```

**Example Output**:

```
character_switch_total{from_character="charles",to_character="développeuse"} 5
character_switch_total{from_character="développeuse",to_character="charles"} 3

character_history_messages{character="charles"} 45
character_history_messages{character="développeuse"} 23

character_history_truncations_total{character="charles"} 1

character_history_clears_total{character="charles",reason="session_end"} 1
character_history_clears_total{character="développeuse",reason="session_end"} 1
```

---

## Performance Profiling

### Memory Profiling

```python
import tracemalloc

# In UnmuteHandler.start_up()
tracemalloc.start()

# In UnmuteHandler.__aexit__()
current, peak = tracemalloc.get_traced_memory()
logger.info(f"Memory usage: current={current/1024/1024:.2f} MB, peak={peak/1024/1024:.2f} MB")
tracemalloc.stop()
```

### Timing Profiling

```python
from unmute.timer import Stopwatch

# In Chatbot.switch_character()
stopwatch = Stopwatch()
# ... switching logic ...
logger.debug(f"Character switch took {stopwatch.time():.3f} seconds")

# Should be < 0.1 seconds for in-memory operations
```

---

## Troubleshooting Frontend Issues

### Frontend Not Sending session.update

**Check**: `frontend/src/app/Unmute.tsx:243-248`

**Issue**: Frontend disconnects instead of sending `session.update`

**Fix**: Comment out or remove the disconnect behavior:

```typescript
// BEFORE (disconnects on voice change)
useEffect(() => {
  setShouldConnect(false);
  shutdownAudio();
}, [shutdownAudio, unmuteConfig.voice]);

// AFTER (allows in-place switching)
useEffect(() => {
  // Character switching handled by session.update event
  // No need to disconnect
}, [shutdownAudio, unmuteConfig.voice]);
```

### Frontend Not Reflecting Active Character

**Check**: `frontend/src/app/UnmuteConfigurator.tsx:175-178`

**Verify**: `kind="primary"` is set for active character

```typescript
kind={
  voice.source.path_on_server === config.voice
    ? "primary"    // Should be green/highlighted
    : "secondary"
}
```

---

## Next Steps

After successfully testing:

1. ✅ Verify all unit tests pass
2. ✅ Verify all integration tests pass
3. ✅ Complete manual testing checklist
4. ✅ Review metrics in Prometheus
5. ✅ Performance profile with 10 characters
6. ✅ Update documentation with any learnings
7. ✅ Submit PR for review

---

## Resources

- **Data Model**: `data-model.md` - Entity definitions and relationships
- **Research**: `research.md` - Current implementation analysis
- **Spec**: `spec.md` - Requirements and acceptance criteria
- **Contracts**: `contracts/websocket-events.md` - WebSocket event definitions
- **Existing Tests**: `tests/test_chatbot.py` - Current chatbot tests

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check existing logs in `logs/unmute.log`
2. Add debug logging as shown in "Debugging Guide"
3. Review Prometheus metrics
4. Compare with data model in `data-model.md`
5. Review research findings in `research.md`

Happy coding! 🚀
