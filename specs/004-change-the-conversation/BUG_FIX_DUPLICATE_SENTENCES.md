# Bug Fix: Characters Saying Sentences Twice

**Date**: 2025-10-17  
**Feature**: 004-change-the-conversation  
**Status**: Fixed  
**Fixes**: Two separate bugs - frontend useEffect + backend system prompt duplication

## Problem Statement

After implementing the improved memory management feature in 004-change-the-conversation, users reported:

1. **Characters repeat sentences twice** (except Narrator)
2. **Cannot switch FROM Narrator** to another character
3. Backend per-character history management was working correctly
4. Text was being sent to TTS duplicated or twice

## Two Separate Issues Found

### Issue #1: Frontend useEffect Dependency (FIXED)

Location: `/frontend/src/app/Unmute.tsx` lines 225-241

### Issue #2: Backend System Prompt Double-Generation (FIXED)

Location: `/unmute/unmute_handler.py` lines 728-736 and `/unmute/llm/chatbot.py` lines 359-367

---

## Root Cause Analysis: Issue #1 (Frontend)

The first issue was found in `/frontend/src/app/Unmute.tsx` at lines 225-241.

### The Bug

A `useEffect` hook that sends `session.update` events to the backend had an **unstable dependency**:

```typescript
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
}, [unmuteConfig, readyState, sendMessage]); // ← BUG: sendMessage is unstable!
```

### Why This Caused Duplicate Sentences

The `sendMessage` function from `react-use-websocket` is **recreated frequently** (on renders or internal state changes), causing the `useEffect` to fire multiple times:

**Sequence of Events:**

1. **User switches character** → `unmuteConfig.voice` changes
2. **Effect #1 fires** → Sends `session.update` to backend
3. **Backend processes** → Switches character, generates initial response
4. **Response arrives** → Audio plays, state updates occur
5. **sendMessage recreates** → React-use-websocket updates the function reference
6. **Effect #2 fires** → Sends DUPLICATE `session.update` to backend
7. **Backend receives duplicate** → Although backend has protection against duplicate switches (line 700-703 in `unmute_handler.py`), the duplicate event can trigger race conditions or side effects
8. **Result** → Responses get duplicated, sentences play twice

### Why Narrator Was Different

The Narrator didn't exhibit this issue as consistently due to timing differences in its conversation state when the duplicate `session.update` arrived. The duplicate event arrived at a different point in the conversation flow, preventing the visible duplication.

### Why You Couldn't Switch FROM Narrator

The repeated `session.update` events created race conditions that interfered with subsequent character switches, especially when trying to switch away from Narrator.

---

## Root Cause Analysis: Issue #2 (Backend)

### The Bug: System Prompt Generated Twice

In `unmute_handler.py` lines 728-736, the system prompt was being generated **twice** for the same character:

```python
system_prompt = prompt_generator.make_system_prompt()  # ← Call #1

# Switch character (creates/retrieves history)
self.chatbot.switch_character(session.voice, system_prompt)

# Update prompt generator for future system prompt updates
self.chatbot.set_prompt_generator(prompt_generator)  # ← Calls make_system_prompt() AGAIN!
```

In `chatbot.py` line 366:

```python
def set_prompt_generator(self, prompt_generator: PromptGenerator):
    self._update_system_prompt(prompt_generator.make_system_prompt())  # ← Call #2!
```

### Why This Caused Duplicate/Inconsistent Text

Characters like **Développeuse** and **Charles** have **non-deterministic system prompts**:

**Développeuse** (line 47):

```python
conversation_starter_suggestion=random.choice(CONVERSATION_STARTER_SUGGESTIONS)
```

- Uses `random.choice()` to select a conversation starter
- Also includes dynamic timestamp
- Each call to `make_system_prompt()` produces a **DIFFERENT** prompt!

**Charles** (line 9):

```python
'instruction_prompt': "...Pour ton premier tour de parole, tu te présentes en français en 2 phrases..."
```

- Explicit instruction: "For your first turn, you introduce yourself"
- This triggers initial greeting generation

### Why Narrator Didn't Have This Issue

**Narrator** (line 13-20):

```python
INSTRUCTIONS = {
    'instruction_prompt': """
    Tu es le narrateur et tu dois aider ton hote a selectionner une histoire...
    """,
    'language': 'fr'
}
```

- **No random elements** - static instructions
- **No dynamic values** - no timestamps or random choices
- **No "greet first" directive** - just describes role
- Calling `make_system_prompt()` twice produces **identical** results
- **No duplication!**

---

## The Fixes

### Fix #1: Frontend useEffect Dependency

**File**: `/frontend/src/app/Unmute.tsx`  
**Lines**: 225-246

Remove `sendMessage` from the dependency array since:

- It's only being **called**, not used for its value
- It doesn't need to be a dependency
- Including it causes excessive re-runs of the effect

**Before:**

```typescript
}, [unmuteConfig, readyState, sendMessage]); // ❌ Causes duplicates
```

**After:**

```typescript
  // Note: sendMessage is intentionally NOT in the dependency array
  // because it's an unstable reference from react-use-websocket that
  // changes frequently. We only want this effect to run when the
  // config or connection state changes, not when sendMessage is recreated.
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [unmuteConfig, readyState]); // ✅ Only re-run on config or connection changes
```

### Fix #2: Backend System Prompt Double-Generation

**File**: `/unmute/llm/chatbot.py`  
**Lines**: 369-379 (new method added)

**File**: `/unmute/unmute_handler.py`  
**Lines**: 733-736

**Solution**: Add a new method `set_prompt_generator_without_updating()` that stores the generator without regenerating the system prompt:

**Before (BUGGY):**

```python
# Switch character (creates/retrieves history)
self.chatbot.switch_character(session.voice, system_prompt)

# Update prompt generator - BUG: calls make_system_prompt() AGAIN!
self.chatbot.set_prompt_generator(prompt_generator)
```

**After (FIXED):**

```python
# Switch character (creates/retrieves history)
self.chatbot.switch_character(session.voice, system_prompt)

# Store prompt generator for tools and future use
# Use set_prompt_generator_without_updating to avoid calling make_system_prompt() twice
self.chatbot.set_prompt_generator_without_updating(prompt_generator)
```

**New method in chatbot.py:**

```python
def set_prompt_generator_without_updating(self, prompt_generator: PromptGenerator):
    """Set the prompt generator WITHOUT regenerating/updating the system prompt.

    Use this when the system prompt has already been set (e.g., via switch_character())
    and you just need to store the generator for later use (tools, etc.).

    This avoids calling make_system_prompt() twice, which is important because
    make_system_prompt() may be non-deterministic (contain random elements or
    dynamic timestamps).
    """
    self._prompt_generator = prompt_generator
```

---

## Backend Protection (Already in Place)

The backend already had protection against duplicate character switches in `unmute_handler.py` lines 699-703:

```python
# Skip if already on this character (prevents duplicate switches)
if (self.chatbot.current_character == session.voice and
    self.tts_voice == session.voice):
    logger.debug(f"Already on character {session.voice}, skipping switch")
    return
```

However, this protection alone wasn't sufficient because:

1. The duplicate `session.update` events were arriving rapidly
2. Race conditions could occur between the check and subsequent processing
3. Other side effects (audio processing, response generation) could be triggered

## Verification

To verify the fix works:

### Test Case 1: Character Switching

1. Connect to the application
2. Select character A (e.g., "Développeuse")
3. Listen to initial response
4. Switch to character B (e.g., "Charles")
5. Listen to initial response
6. **Expected**: Each character speaks their greeting exactly once (no duplicates)

### Test Case 2: Switching from Narrator

1. Connect to the application
2. Select "Narrator" character
3. Interact briefly
4. Switch to another character (e.g., "Charles")
5. **Expected**: Character switch succeeds, Charles responds normally

### Test Case 3: Rapid Character Switching

1. Connect to the application
2. Rapidly switch between multiple characters (A → B → C → A)
3. **Expected**: Each switch completes successfully, no duplicate responses

### Test Case 4: Chat History Preservation

1. Talk to character A (3 exchanges)
2. Switch to character B (2 exchanges)
3. Switch back to character A
4. **Expected**: Previous 3 exchanges with A are still visible, no duplicates

## Technical Details

### React useEffect Dependencies

**General Rule**: Only include dependencies that you actually **use** or **observe** in the effect.

**When to exclude a function**:

- If it's an event handler or callback that you only **call**
- If it's an unstable reference that changes frequently
- If including it would cause unnecessary re-renders

**When to include a function**:

- If you use its **return value**
- If you observe its **properties**
- If it's a stable reference (memoized with `useCallback`)

### React-use-websocket sendMessage

The `sendMessage` function from `react-use-websocket`:

- Is **recreated** when the WebSocket reconnects
- May be **recreated** on internal state changes
- Is **intentionally designed** to be called, not depended upon
- Should **rarely** be in dependency arrays

## Related Files Modified

### Issue #1 (Frontend):

1. **`/frontend/src/app/Unmute.tsx`** (lines 225-246)
   - Removed `sendMessage` from useEffect dependencies
   - Added explanatory comment
   - Added eslint-disable comment for exhaustive-deps rule

### Issue #2 (Backend):

1. **`/unmute/llm/chatbot.py`** (lines 369-379)

   - Added new method `set_prompt_generator_without_updating()`
   - Avoids double-generation of non-deterministic system prompts

2. **`/unmute/unmute_handler.py`** (lines 733-736)
   - Changed from `set_prompt_generator()` to `set_prompt_generator_without_updating()`
   - Added explanatory comments about avoiding double-generation

## Impact

**Before Fixes:**

- ❌ Characters repeated sentences twice (both issues contributed)
- ❌ Inconsistent system prompts (Issue #2)
- ❌ Duplicate session.update events (Issue #1)
- ❌ Difficult to switch from Narrator
- ❌ Poor user experience
- ❌ Wasted backend resources on duplicate processing

**After Both Fixes:**

- ✅ Characters speak each sentence exactly once
- ✅ Consistent system prompts (no random re-generation)
- ✅ Single session.update per character switch
- ✅ Seamless character switching (including from/to Narrator)
- ✅ Clean, predictable behavior
- ✅ Efficient backend usage

## Lessons Learned

1. **Unstable function references** in React dependency arrays can cause subtle bugs
2. **Event handlers and callbacks** should rarely be dependencies
3. **Non-deterministic functions** (with random/dynamic values) should NEVER be called multiple times
4. **System prompt generation** should happen exactly once per character switch
5. **Backend protection** alone isn't sufficient if frontend sends duplicates
6. **Timing-dependent bugs** can manifest differently across characters
7. **React-use-websocket's `sendMessage`** should not be in dependency arrays
8. **Read the comments!** The code comment said "make_system_prompt() might not be deterministic, so we run it only once" - but then called it twice!

## References

- Feature spec: `/specs/004-change-the-conversation/spec.md`
- Implementation tasks: `/specs/004-change-the-conversation/tasks.md`
- Backend handler: `/unmute/unmute_handler.py` (lines 692-757)
- Frontend component: `/frontend/src/app/Unmute.tsx` (lines 225-246)
- React hooks docs: https://react.dev/reference/react/useEffect#removing-unnecessary-function-dependencies
