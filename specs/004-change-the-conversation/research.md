# Research: Per-Character Conversation History

**Feature**: 003-change-the-conversation
**Date**: 2025-01-27

## Overview

This document contains research findings about the current implementation that will inform the design of per-character conversation history management.

---

## Research Question 1: Current Conversation History Implementation

### Finding: Single Global Chat History in Chatbot

**Location**: `unmute/llm/chatbot.py`

The `Chatbot` class currently maintains a single conversation history for the entire session:

```python:36:42:unmute/llm/chatbot.py
class Chatbot:
    def __init__(self):
        # It's actually a list of ChatCompletionStreamRequestMessagesTypedDict but then
        # it's really difficult to convince Python you're passing in the right type
        self.chat_history: list[dict[Any, Any]] = [
            {"role": "system", "content": _default_system_prompt()}
        ]
        self._prompt_generator: PromptGenerator | None = None
```

**Key Characteristics**:

- **Structure**: List of dictionaries with `"role"` (system/user/assistant) and `"content"` (string) keys
- **Initial State**: Always starts with a system prompt message at index 0
- **Message Addition**: Via `add_chat_message_delta()` which appends or extends the last message
- **System Prompt Management**: First message (index 0) is always the system prompt, updated via `_update_system_prompt()`

**Relevant Methods**:

- `add_chat_message_delta(delta, role, generating_message_i)`: Adds or appends to messages
- `preprocessed_messages()`: Returns messages formatted for LLM, ensures at least system + user message
- `set_prompt_generator(prompt_generator)`: Updates system prompt based on character
- `get_system_prompt()`: Returns current system prompt
- `conversation_state()`: Returns current state (waiting_for_user, user_speaking, bot_speaking)
- `last_message(role)`: Gets the last message for a specific role

**Message Size Estimate**:

- Average message: ~100-500 characters (100-500 bytes)
- 100 messages per character: ~10-50 KB
- 10 characters: ~100-500 KB per session (manageable)

---

## Research Question 2: Character Switching Mechanism

### Finding: Character Switching via Session Update

**Location**: `unmute/unmute_handler.py:663-676`

Character switching happens through the `update_session()` method:

```python:663:676:unmute/unmute_handler.py
async def update_session(self, session: ora.SessionConfig):
    if session.voice:
        self.tts_voice = session.voice

        # Look up the character from this session's character manager
        character = self.character_manager.get_character(session.voice)

        if character and hasattr(character, '_prompt_generator'):
            # Instantiate the PromptGenerator with the character's instructions
            logger.info(f"Setting prompt generator for character: {session.voice}")
            logger.info(f"Character instructions: {getattr(character, '_instructions', 'NOT FOUND')}")
            prompt_generator = character._prompt_generator(character._instructions)  # type: ignore
            self.chatbot.set_prompt_generator(prompt_generator)
            logger.info(f"System prompt updated: {self.chatbot.get_system_prompt()[:200]}...")
```

**Current Behavior**:

1. When a new voice/character is selected, `update_session()` is called
2. The system prompt is updated to match the new character's instructions
3. **The conversation history is NOT cleared or preserved** - it continues with the new character
4. This means currently there's only ONE continuous conversation history regardless of character switches

**Character State**:

- Active character is tracked via `self.tts_voice` (string, character name)
- Character definition comes from `self.character_manager.get_character(name)`
- Each character has a `_prompt_generator` and `_instructions` attribute

**Key Insight**: The current implementation does NOT have per-character history - switching characters just changes the system prompt while keeping the same chat history.

---

## Research Question 3: Session Lifecycle

### Finding: Clear Initialization and Cleanup Hooks

**Initialization**: `unmute/unmute_handler.py:420-436`

```python:420:436:unmute/unmute_handler.py
async def start_up(self):
    await self.start_up_stt()

    # Load default characters for this session
    default_characters_dir = Path(__file__).parents[1] / "characters"
    try:
        result = await self.character_manager.load_characters(default_characters_dir)
        self._characters_loaded = True
        logger.info(
            f"Session {self.character_manager.session_id}: Loaded {result.loaded_count} characters "
            f"from {default_characters_dir} ({result.error_count} errors)"
        )
    except Exception as e:
        logger.error(f"Session {self.character_manager.session_id}: Failed to load characters: {e}")
        # Continue without characters - session can still function

    self.waiting_for_user_start_time = self.audio_received_sec()
```

**Cleanup**: `unmute/unmute_handler.py:438-443`

```python:438:443:unmute/unmute_handler.py
async def __aexit__(self, *exc: Any) -> None:
    # Clean up session-specific character modules from sys.modules
    if hasattr(self, 'character_manager'):
        self.character_manager.cleanup_session_modules()

    return await self.quest_manager.__aexit__(*exc)
```

**Lifecycle Hooks**:

- ✅ **Initialization**: `start_up()` - called when session begins, good place for history initialization
- ✅ **Cleanup**: `__aexit__()` - called when session ends, perfect for clearing all character histories (FR-005)
- ✅ **Async Context Manager**: `UnmuteHandler` uses `async with` pattern, ensuring cleanup happens

**Additional Cleanup**: `unmute/unmute_handler.py:124-126`

```python:124:126:unmute/unmute_handler.py
async def cleanup(self):
    if self.recorder is not None:
        await self.recorder.shutdown()
```

**Session Creation**: `unmute/main_websocket.py:501-504`

```python
handler = UnmuteHandler()
async with handler:
    await handler.start_up()
    await _run_route(websocket, handler)
```

**Key Insight**: Clear lifecycle hooks exist for initialization and cleanup. The `__aexit__()` is the perfect place to clear all character histories on session disconnect.

---

## Research Question 4: WebSocket Event Handling

### Finding: Session Update Event Mechanism

**Frontend Event Trigger**: `frontend/src/app/Unmute.tsx:223-241`

When the WebSocket connects or the character changes, the frontend sends a `session.update` event:

```typescript:223:241:frontend/src/app/Unmute.tsx
// When we connect, we send the initial config (voice) to the server.
// Also clear the chat history.
useEffect(() => {
  if (readyState !== ReadyState.OPEN) return;

  const recordingConsent =
    localStorage.getItem(RECORDING_CONSENT_STORAGE_KEY) === "true";

  setRawChatHistory([]);
  sendMessage(
    JSON.stringify({
      type: "session.update",
      session: {
        voice: unmuteConfig.voice,
        allow_recording: recordingConsent,
      },
    })
  );
}, [unmuteConfig, readyState, sendMessage]);
```

**Important Behavior**: Lines 243-248 show that currently, **changing voice disconnects the session**:

```typescript:243:248:frontend/src/app/Unmute.tsx
// Disconnect when the voice changes.
// TODO: If it's a voice change, immediately reconnect with the new voice.
useEffect(() => {
  setShouldConnect(false);
  shutdownAudio();
}, [shutdownAudio, unmuteConfig.voice]);
```

**Backend Event Handling**: `unmute/main_websocket.py:receive_loop`

The backend receives `session.update` events in the `receive_loop()` function and processes them via:

```python
elif isinstance(message, ora.SessionUpdate):
    await handler.update_session(message.session)
    await emit_queue.put(ora.SessionUpdated(session=message.session))
```

**Event Model**: `unmute/openai_realtime_api_events.py:64-74`

```python:64:74:unmute/openai_realtime_api_events.py
class SessionConfig(BaseModel):
    voice: str | None = None
    allow_recording: bool


class SessionUpdate(BaseEvent[Literal["session.update"]]):
    session: SessionConfig


class SessionUpdated(BaseEvent[Literal["session.updated"]]):
    session: SessionConfig
```

**Character Reload Event**: The codebase also has a `SessionCharactersReload` event (lines 670-710 in `main_websocket.py`) for per-session character reloading, but this is different from character switching.

**Key Insights**:

1. **Current Implementation**: Character switching triggers a full disconnect/reconnect cycle
2. **Desired Implementation**: Per FR-002, we need to support character switching WITHOUT disconnecting
3. **Frontend Change Needed**: Remove the disconnect behavior in lines 243-248 of `Unmute.tsx`
4. **Backend Already Ready**: The `session.update` event mechanism already exists and can handle character switches without reconnecting

---

## Research Question 5: Memory Management Patterns

### Finding: No Existing History Truncation

**Current State**: The `Chatbot` class has no built-in mechanism for limiting chat history size.

**Chat History Usage**:

- Messages are continuously appended via `add_chat_message_delta()`
- Only preprocessing happens in `preprocessed_messages()` (ensures minimum 2 messages)
- No truncation, compression, or pruning logic exists

**Memory Growth Risk**:

- Long conversations will continuously grow the list
- With 10 characters × 100 messages × ~500 bytes = ~500 KB per session (acceptable)
- Per FR-011, we MUST implement 100-message limit per character

**Truncation Strategy Options**:

1. **FIFO Truncation** (Recommended):
   - Keep first message (system prompt)
   - Remove oldest user/assistant messages when limit reached
   - Simple and predictable
2. **Sliding Window**:
   - Keep last N messages
   - Maintains recent context
   - May lose important early context
3. **Summarization** (Complex):
   - Compress old messages into summaries
   - Requires LLM call
   - More expensive, added complexity

**Recommendation**: Implement FIFO truncation (Option 1):

```python
MAX_MESSAGES_PER_CHARACTER = 100

def _truncate_history(history: list[dict]) -> list[dict]:
    """Keep system prompt + last 99 messages."""
    if len(history) <= MAX_MESSAGES_PER_CHARACTER:
        return history

    # Keep system prompt (index 0) + last (MAX-1) messages
    return [history[0]] + history[-(MAX_MESSAGES_PER_CHARACTER - 1):]
```

**Key Insight**: No existing truncation logic exists. We must implement it as part of this feature to satisfy FR-011.

---

## Research Question 6: Frontend Character List

### Finding: Character Selection UI Already Exists

**Location**: `frontend/src/app/UnmuteConfigurator.tsx:164-184`

The character list UI already exists with visual indicators:

```typescript:164:184:frontend/src/app/UnmuteConfigurator.tsx
<div className="w-full max-w-6xl grid grid-flow-row grid-cols-2 md:grid-cols-3 gap-3 p-3">
  {voices &&
    voices.map((voice) => (
      <SquareButton
        key={voice.source.path_on_server}
        onClick={() => {
          setConfig({
            voice: voice.source.path_on_server,
            voiceName: voice.name || "Unnamed",
          });
        }}
        kind={
          voice.source.path_on_server === config.voice
            ? "primary"    // Active character
            : "secondary"  // Inactive character
        }
        extraClasses="bg-gray md:bg-black"
      >
        {"/ " + getVoiceName(voice) + " /"}
      </SquareButton>
    ))}
```

**Active Character Indication**:

- Active character uses `kind="primary"` (likely styled with green/highlighted appearance)
- Inactive characters use `kind="secondary"`
- Clicking a character calls `setConfig()` which updates `unmuteConfig.voice`

**Character Change Flow**:

1. User clicks character button
2. `setConfig()` updates `unmuteConfig` state
3. Currently (line 243-248 in `Unmute.tsx`): Triggers disconnect
4. **After this feature**: Should send `session.update` without disconnecting

**Key Insight**: The UI already exists and meets FR-012. We just need to change the behavior from "disconnect and reconnect" to "switch character in-place".

---

## Additional Findings

### Character Manager Architecture

**Per-Session Character Management** (from Feature 002):

- Each `UnmuteHandler` has its own `CharacterManager` instance
- Characters are loaded in isolated module namespaces (e.g., `session_{id}.characters.charles`)
- This enables multiple simultaneous users with different character sets

**Character Lookup**:

```python
character = self.character_manager.get_character(session.voice)
```

Returns a character object with:

- `_prompt_generator`: Callable that creates system prompts
- `_instructions`: Character-specific instructions
- `name`: Character name (used as key)

### Turn Transition Lock

**Location**: `unmute/unmute_handler.py:109`

```python
self.turn_transition_lock = asyncio.Lock()
```

This lock is used to prevent race conditions during conversation state transitions. We should use this to ensure character switches don't happen mid-response (satisfies FR-008).

### Interruption Handling

The system already handles interruptions during LLM generation:

```python:251:252:unmute/unmute_handler.py
if len(self.chatbot.chat_history) > generating_message_i:
    break  # We've been interrupted
```

This pattern checks if new messages were added during generation, indicating an interruption. We can use similar logic to detect if a character switch was requested mid-response.

---

## Design Implications

Based on these research findings, the implementation should:

1. **Refactor Chatbot Class**:

   - Replace single `chat_history` list with a dictionary: `character_histories: dict[str, list[dict]]`
   - Add `current_character: str | None` to track active character
   - Create methods: `switch_character(name)`, `clear_character_history(name)`, `clear_all_histories()`

2. **Modify UnmuteHandler**:

   - Call `chatbot.switch_character(session.voice)` in `update_session()`
   - Add history clearing to `__aexit__()`
   - Use `turn_transition_lock` to prevent mid-response switches

3. **Update Frontend**:

   - Remove disconnect behavior on character change (lines 243-248 in `Unmute.tsx`)
   - Let `session.update` event handle character switch

4. **Implement Memory Management**:

   - Add `MAX_MESSAGES_PER_CHARACTER = 100` constant
   - Implement FIFO truncation when switching or adding messages
   - Emit metrics when truncation occurs

5. **Add Metrics**:
   - Follow existing patterns in `unmute/metrics.py`
   - Use Prometheus `Counter`, `Histogram`, and `Gauge` types

---

## Risk Mitigations

| Risk                          | Research Finding                      | Mitigation Strategy                        |
| ----------------------------- | ------------------------------------- | ------------------------------------------ |
| Race conditions during switch | `turn_transition_lock` exists         | Use existing lock in switch logic          |
| Frontend disconnect behavior  | Currently disconnects on voice change | Remove disconnect code in `Unmute.tsx`     |
| Missing truncation logic      | No existing pattern                   | Implement FIFO truncation with tests       |
| System prompt synchronization | System prompt is first message        | Preserve system prompt per character       |
| Mid-response switching        | Interruption detection exists         | Wait for response completion before switch |

---

## Next Steps

Proceed to **Phase 1: Design** to create:

1. `data-model.md` - Entity definitions and data structures
2. `quickstart.md` - Developer guide for testing and debugging
3. `contracts/websocket-events.md` - API contracts (minimal changes needed)

---

## References

- Feature 002 Implementation: `specs/002-multiple-simultaneous-users/IMPLEMENTATION_COMPLETE.md`
- Per-session architecture: `unmute/tts/character_loader.py`
- Character switching flow: `docs/character-reload.md`
- OpenAI Realtime API events: `unmute/openai_realtime_api_events.py`
