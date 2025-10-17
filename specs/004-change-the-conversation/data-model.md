# Data Model: Per-Character Conversation History

**Feature**: 003-change-the-conversation
**Date**: 2025-01-27

## Overview

This document defines the data structures and relationships for per-character conversation history management. All entities are in-memory only (no persistent storage across sessions).

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  UserSession (WebSocket Connection)                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ UnmuteHandler                                                    │   │
│  │ ─────────────                                                    │   │
│  │ + session_id: str (inherited from character_manager)            │   │
│  │ + character_manager: CharacterManager                           │   │
│  │ + chatbot: Chatbot                    ◄──────────┐              │   │
│  │ + tts_voice: str | None                          │              │   │
│  │ + turn_transition_lock: asyncio.Lock             │              │   │
│  │ ─────────────                                    │              │   │
│  │ + start_up() -> None                             │              │   │
│  │ + update_session(session) -> None  ──────┐      │              │   │
│  │ + __aexit__() -> None                     │      │              │   │
│  │                                           │      │              │   │
│  │   ┌───────────────────────────────────────▼──────▼──────────┐  │   │
│  │   │ Chatbot                                                  │  │   │
│  │   │ ─────────                                                │  │   │
│  │   │ # Data Storage                                           │  │   │
│  │   │ + character_histories: dict[str, CharacterHistory]      │  │   │
│  │   │ + current_character: str | None                          │  │   │
│  │   │ + _prompt_generator: PromptGenerator | None             │  │   │
│  │   │                                                          │  │   │
│  │   │ # Character Management                                   │  │   │
│  │   │ + switch_character(name: str) -> None                   │  │   │
│  │   │ + get_current_history() -> list[ChatMessage]            │  │   │
│  │   │ + clear_character_history(name: str) -> None            │  │   │
│  │   │ + clear_all_histories() -> None                         │  │   │
│  │   │                                                          │  │   │
│  │   │ # Backward Compatibility (delegate to current)           │  │   │
│  │   │ + chat_history: property -> list[ChatMessage]           │  │   │
│  │   │ + add_chat_message_delta(delta, role, ...) -> bool     │  │   │
│  │   │ + conversation_state() -> ConversationState             │  │   │
│  │   │ + set_prompt_generator(gen: PromptGenerator) -> None   │  │   │
│  │   │ + get_system_prompt() -> str                            │  │   │
│  │   │ + preprocessed_messages() -> list[ChatMessage]          │  │   │
│  │   │ + last_message(role: str) -> str | None                 │  │   │
│  │   └──────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

Entity Details:

┌──────────────────────────────────────────────────────────────────────┐
│ CharacterHistory                                                     │
│ ────────────────                                                     │
│ + character_name: str                                                │
│ + messages: list[ChatMessage]                                        │
│ + created_at: float (audio_received_sec timestamp)                  │
│ + last_accessed: float (audio_received_sec timestamp)               │
│ + message_count: int (derived: len(messages))                       │
│ ─────────────────                                                    │
│ Methods:                                                             │
│ + add_message(message: ChatMessage) -> None                         │
│ + truncate_if_needed(max_messages: int) -> int (returns # removed)  │
│ + get_system_prompt() -> str                                        │
│ + update_system_prompt(prompt: str) -> None                         │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ ChatMessage (existing type, no changes)                             │
│ ───────────                                                          │
│ + role: Literal["system", "user", "assistant"]                      │
│ + content: str                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Entity Definitions

### 1. CharacterHistory

**Purpose**: Represents a single character's conversation history within a session.

**Attributes**:

- `character_name` (str): Name of the character (e.g., "charles", "développeuse")
- `messages` (list[ChatMessage]): Ordered list of messages (system, user, assistant)
- `created_at` (float): Timestamp when this history was created (from `audio_received_sec()`)
- `last_accessed` (float): Timestamp of last access/switch (from `audio_received_sec()`)

**Invariants**:

- First message MUST always have `role="system"` (the character's system prompt)
- Maximum length: 100 messages (enforced by `truncate_if_needed()`)
- Messages are append-only (no modification except truncation)

**Methods**:

```python
class CharacterHistory:
    def __init__(self, character_name: str, system_prompt: str, created_at: float):
        self.character_name = character_name
        self.messages = [{"role": "system", "content": system_prompt}]
        self.created_at = created_at
        self.last_accessed = created_at

    def add_message(self, message: dict[str, str]) -> None:
        """Add a message to history. Does NOT enforce max length."""
        self.messages.append(message)

    def truncate_if_needed(self, max_messages: int = 100) -> int:
        """Remove oldest messages if exceeding max. Returns number removed."""
        if len(self.messages) <= max_messages:
            return 0

        num_to_remove = len(self.messages) - max_messages
        # Keep system prompt (index 0) + last (max_messages - 1) messages
        self.messages = [self.messages[0]] + self.messages[-max_messages + 1:]
        return num_to_remove

    def get_system_prompt(self) -> str:
        """Get the system prompt (always first message)."""
        assert self.messages[0]["role"] == "system"
        return self.messages[0]["content"]

    def update_system_prompt(self, prompt: str) -> None:
        """Update the system prompt (always first message)."""
        assert self.messages[0]["role"] == "system"
        self.messages[0]["content"] = prompt

    @property
    def message_count(self) -> int:
        """Total number of messages in history."""
        return len(self.messages)
```

**Memory Characteristics**:

- Average message: ~100-500 bytes
- Max 100 messages: ~10-50 KB per character
- Max 10 characters per session: ~100-500 KB total

---

### 2. Chatbot (Modified)

**Purpose**: Manages multiple per-character conversation histories and provides unified interface.

**New Attributes**:

- `character_histories` (dict[str, CharacterHistory]): Maps character name → history
- `current_character` (str | None): Currently active character name

**Existing Attributes** (unchanged):

- `_prompt_generator` (PromptGenerator | None): Current character's prompt generator

**Removed Attributes**:

- `chat_history` (list) - REPLACED by `character_histories` dictionary

**New Methods**:

```python
def switch_character(self, character_name: str, system_prompt: str) -> None:
    """Switch to a different character, creating history if needed.

    Args:
        character_name: Name of character to switch to
        system_prompt: System prompt for this character

    Effects:
        - Updates self.current_character
        - Creates new CharacterHistory if character is new
        - Updates last_accessed timestamp
        - Emits CHARACTER_SWITCH metric
    """

def get_current_history(self) -> list[dict]:
    """Get the current character's message history.

    Returns the messages list for the current character, or an empty list
    with default system prompt if no character is active.
    """

def clear_character_history(self, character_name: str) -> None:
    """Clear conversation history for a specific character.

    Removes the character from character_histories dict. Next switch
    to this character will create fresh history.

    Emits CHARACTER_HISTORY_CLEARS metric.
    """

def clear_all_histories(self) -> None:
    """Clear all character conversation histories.

    Called on session disconnect (__aexit__). Clears the entire
    character_histories dict and resets current_character to None.

    Emits CHARACTER_HISTORY_CLEARS metric for each character.
    """
```

**Modified Property** (backward compatibility):

```python
@property
def chat_history(self) -> list[dict]:
    """Backward compatibility property - returns current character's history."""
    return self.get_current_history()
```

**Existing Methods** (unchanged behavior, internally delegate to current history):

- `add_chat_message_delta(delta, role, generating_message_i)` → operates on current character
- `conversation_state()` → checks current character's last message
- `set_prompt_generator(generator)` → updates current character's system prompt
- `get_system_prompt()` → returns current character's system prompt
- `preprocessed_messages()` → preprocesses current character's messages
- `last_message(role)` → searches current character's history

---

### 3. ConversationState (Existing, No Changes)

**Purpose**: Represents the current state of conversation flow.

**Type**: `Literal["waiting_for_user", "user_speaking", "bot_speaking"]`

**Usage**: Determined by examining the last message in current character's history.

---

## Data Flow Diagrams

### Character Switch Flow

```
User Clicks Character → Frontend Updates unmuteConfig.voice
                                    ↓
                        Frontend Sends session.update event
                                    ↓
                        Backend receive_loop receives SessionUpdate
                                    ↓
                        UnmuteHandler.update_session(session)
                                    ↓
                    [Acquire turn_transition_lock] ──────────────┐
                                    ↓                            │
            Look up character from character_manager             │
                                    ↓                            │
            Get character's system prompt & generator            │
                                    ↓                            │
            Chatbot.switch_character(name, system_prompt)        │
                - Create/retrieve CharacterHistory               │
                - Update current_character                       │
                - Update last_accessed timestamp                 │
                - Emit CHARACTER_SWITCH metric                   │
                                    ↓                            │
            Chatbot.set_prompt_generator(generator)              │
                - Updates system prompt in current history       │
                                    ↓                            │
            Update self.tts_voice                                │
                                    ↓                            │
            [Release turn_transition_lock] ◄──────────────────────┘
                                    ↓
            Send SessionUpdated event to frontend
```

### Message Addition Flow

```
User speaks → STT transcribes → UnmuteHandler._stt_loop
                                        ↓
                    handler.add_chat_message_delta(text, "user")
                                        ↓
                    Chatbot.add_chat_message_delta(delta, "user")
                                        ↓
                Get current character's history
                                        ↓
                Append/update message in current history
                                        ↓
                Check if history exceeds 100 messages
                                        ↓
                If yes: truncate_if_needed()
                    - Keep system prompt
                    - Remove oldest messages
                    - Emit CHARACTER_HISTORY_SIZE metric
```

### Session Disconnect Flow

```
WebSocket closes → UnmuteHandler.__aexit__()
                            ↓
        character_manager.cleanup_session_modules()
                            ↓
        Chatbot.clear_all_histories()  ◄── NEW
            - Iterate over all characters
            - Emit CHARACTER_HISTORY_CLEARS for each
            - Clear character_histories dict
            - Set current_character = None
```

---

## Memory Management

### Truncation Strategy

**Trigger**: When `CharacterHistory.message_count` exceeds 100

**Algorithm**: FIFO (First-In-First-Out) with system prompt preservation

```python
MAX_MESSAGES_PER_CHARACTER = 100

def truncate_if_needed(history: CharacterHistory) -> int:
    if len(history.messages) <= MAX_MESSAGES_PER_CHARACTER:
        return 0

    # Keep system prompt (index 0) + last 99 messages
    num_removed = len(history.messages) - MAX_MESSAGES_PER_CHARACTER
    history.messages = [
        history.messages[0]  # system prompt
    ] + history.messages[-(MAX_MESSAGES_PER_CHARACTER - 1):]

    return num_removed
```

**When Applied**:

1. After adding a message via `add_chat_message_delta()`
2. When switching characters (to ensure clean state)

**Metrics Emitted**:

- `CHARACTER_HISTORY_TRUNCATIONS` (counter, labels: character)
- `CHARACTER_HISTORY_SIZE` (gauge, labels: character, measured before truncation)

---

## Backward Compatibility

### Existing Code That Uses Chatbot

**Challenge**: Many parts of the codebase access `chatbot.chat_history` directly.

**Solution**: Provide `chat_history` as a property that returns current character's history:

```python
@property
def chat_history(self) -> list[dict]:
    """Backward compatibility - returns current character's message list."""
    if self.current_character is None or self.current_character not in self.character_histories:
        # No character active - return default empty history with system prompt
        return [{"role": "system", "content": _default_system_prompt()}]
    return self.character_histories[self.current_character].messages
```

**Locations Using chat_history**:

- `unmute_handler.py:159-164` - GradioUpdate (reading)
- `unmute_handler.py:197` - ResponseCreated event (reading)
- `unmute_handler.py:251` - Interruption detection (reading length)
- `unmute_handler.py:321` - TTS debugging (writing)
- `unmute_handler.py:328` - Initial message check (reading length)
- Frontend display via additional outputs

All of these will continue to work via the property delegation.

---

## Testing Considerations

### Unit Test Scenarios

1. **CharacterHistory Creation**:

   - New history starts with system prompt
   - created_at and last_accessed are set correctly

2. **Message Addition**:

   - Messages append correctly
   - Message count updates

3. **Truncation**:

   - No truncation when under limit
   - Correct truncation when over limit
   - System prompt always preserved
   - Returns correct number of removed messages

4. **Character Switching**:

   - Switch to new character creates new history
   - Switch to existing character restores history
   - current_character updates correctly
   - last_accessed timestamp updates

5. **History Clearing**:
   - clear_character_history() removes one character
   - clear_all_histories() removes all
   - Other characters unaffected by single clear

### Integration Test Scenarios

1. **Multi-Character Conversation**:

   - Talk to character A
   - Switch to character B
   - Switch back to character A
   - Verify A's history preserved

2. **Session Disconnect**:

   - Create multiple character histories
   - Disconnect session
   - Verify all histories cleared

3. **Memory Management**:
   - Create 150-message conversation
   - Verify truncation to 100
   - Verify system prompt still present

---

## Metrics

### New Prometheus Metrics

```python
# unmute/metrics.py

CHARACTER_SWITCH_COUNT = Counter(
    'character_switch_total',
    'Number of character switches',
    ['from_character', 'to_character']
)

CHARACTER_SWITCH_DURATION = Histogram(
    'character_switch_duration_seconds',
    'Time taken to switch characters',
    buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0]
)

CHARACTER_HISTORY_SIZE = Gauge(
    'character_history_messages',
    'Number of messages in character history',
    ['character']
)

CHARACTER_HISTORY_CLEARS = Counter(
    'character_history_clears_total',
    'Number of times character history was cleared',
    ['character', 'reason']  # reason: "manual", "session_end"
)

CHARACTER_HISTORIES_PER_SESSION = Gauge(
    'character_histories_per_session',
    'Number of different character histories in current session'
)

CHARACTER_HISTORY_TRUNCATIONS = Counter(
    'character_history_truncations_total',
    'Number of times history was truncated due to size limit',
    ['character']
)
```

---

## Migration Strategy

### Phase 1: Refactor Chatbot (Backward Compatible)

1. Add new attributes: `character_histories`, `current_character`
2. Keep `chat_history` as property (delegates to current character)
3. All existing methods work via delegation
4. **No breaking changes**

### Phase 2: Update UnmuteHandler

1. Modify `update_session()` to call `chatbot.switch_character()`
2. Add `chatbot.clear_all_histories()` to `__aexit__()`
3. Add metrics instrumentation

### Phase 3: Update Frontend

1. Remove disconnect behavior on voice change
2. Test character switching without reconnection

### Phase 4: Testing & Validation

1. Run unit tests for new Chatbot methods
2. Run integration tests for character switching
3. Manual testing with multiple characters

---

## Constraints & Assumptions

### Constraints

1. **Memory Limit**: 100 messages per character (hard limit, per FR-011)
2. **Session Scope**: Histories cleared on disconnect (per FR-005)
3. **No Persistence**: No database or file storage
4. **Backward Compatibility**: Existing code must continue to work

### Assumptions

1. **Character Names Are Unique**: Within a session, each character has a unique name
2. **System Prompt Required**: Every character has a system prompt
3. **Sequential Switches**: Users switch one character at a time (no parallel switches)
4. **Session Lifetime**: Sessions last minutes to hours, not days
5. **Character Set Size**: Max 10-20 characters per session (practical limit)

---

## Security & Privacy

### Data Retention

- **In-Session**: Conversation data retained in memory
- **On Disconnect**: ALL data immediately cleared (privacy by design)
- **No Persistence**: No logs or storage of conversation content

### Access Control

- **Session Isolation**: Per-session character managers prevent cross-session access
- **WebSocket Scope**: Only the connected client can access their conversation data

---

## Future Extensions

Potential future enhancements not in current scope:

1. **Conversation Export**: Allow users to download their conversation history
2. **History Search**: Search across all character conversations
3. **Conversation Summaries**: LLM-generated summaries of long conversations
4. **Persistent Storage**: Optional save/load of conversations across sessions
5. **History Analytics**: Metrics on conversation length, character preference, etc.

---

## References

- Research findings: `research.md`
- Existing character management: Feature 002 (`specs/002-multiple-simultaneous-users/`)
- Current Chatbot implementation: `unmute/llm/chatbot.py`
- Message types: `unmute/openai_realtime_api_events.py`
