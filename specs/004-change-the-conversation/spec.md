# Feature Specification: Per-Character Conversation History

**Feature Branch**: `003-change-the-conversation`  
**Created**: 2025-01-27  
**Status**: Draft  
**Input**: User description: "Change the Conversation history mechanism. I would like to store the Conversation history per characters. For example I'm talking to "Développeuse" and the Conversation history is stored on this character space. If I switch to "Charles" I want a fresh Conversation history in charles space. If I go back to "Développeuse" I want to get back the previous Conversation history I had with her previously (on the Développeuse space)."

## Clarifications

### Session 2025-01-27

- Q: What should happen when a user switches characters while the current character is actively speaking (mid-response)? → A: Complete the current character's response, then switch to the new character
- Q: What is the maximum conversation history length per character before the system should implement memory management (e.g., truncation, compression)? → A: 100 messages per character (approximately 30-50 exchanges)
- Q: What should happen to all character conversation histories when the session is interrupted unexpectedly (network issues, browser crash)? → A: Treat it the same as intentional disconnect - clear all histories immediately
- Q: How should users trigger clearing a character's conversation history? → A: Deferred - will be determined later, potentially through character code triggering the clear function
- Q: How should users initiate switching between characters in the frontend interface? → A: Click on a character from the existing character list (active character shown in green)

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Switch Between Characters with Preserved History (Priority: P1)

A user can switch between different characters during an active session, with each character maintaining their own separate conversation history. When switching back to a previously used character, the user sees the complete conversation history from their previous interactions with that character.

**Why this priority**: This is the core functionality that enables the main user value proposition of having separate conversation contexts per character.

**Independent Test**: Can be fully tested by having a user start a conversation with Character A, switch to Character B, have a conversation, then switch back to Character A and verify the original conversation history is preserved.

**Acceptance Scenarios**:

1. **Given** a user is talking to "Développeuse" with 3 message exchanges, **When** the user switches to "Charles", **Then** Charles starts with a fresh conversation history
2. **Given** a user has conversations with both "Développeuse" and "Charles", **When** the user switches back to "Développeuse", **Then** the user sees the complete previous conversation history with Développeuse
3. **Given** a user is in an active conversation with any character, **When** the user switches to a different character, **Then** the switch happens without disconnecting the session

---

### User Story 2 - Clear Character-Specific Conversation History (Priority: P2)

A user can selectively clear the conversation history for a specific character without affecting other characters' conversation histories or disconnecting from the session. The trigger mechanism for this action will be determined in a later phase (potentially through character code).

**Why this priority**: Provides users control over their conversation data and privacy, allowing them to reset specific character relationships while maintaining others.

**Independent Test**: Can be fully tested by having conversations with multiple characters, then clearing history for one character and verifying only that character's history is removed while others remain intact.

**Acceptance Scenarios**:

1. **Given** a user has conversation histories with both "Développeuse" and "Charles", **When** the user clears the history for "Développeuse", **Then** only Développeuse's history is removed while Charles's history remains
2. **Given** a user is in an active session with multiple character histories, **When** the user clears a character's history, **Then** the session remains connected and other characters' histories are unaffected
3. **Given** a user has cleared a character's history, **When** the user switches to that character, **Then** the character starts with a fresh conversation history

---

### User Story 3 - Session Disconnection Clears All Histories (Priority: P3)

When a user disconnects from their session, all character-specific conversation histories are cleared, ensuring no persistent memory across sessions.

**Why this priority**: Ensures privacy and prevents data accumulation across sessions while maintaining the ephemeral nature of conversations.

**Independent Test**: Can be fully tested by having conversations with multiple characters, disconnecting, reconnecting, and verifying all previous conversation histories are gone.

**Acceptance Scenarios**:

1. **Given** a user has conversation histories with multiple characters, **When** the user disconnects from the session, **Then** all character-specific conversation histories are cleared
2. **Given** a user disconnects and reconnects, **When** the user switches to any previously used character, **Then** the character starts with a fresh conversation history
3. **Given** a user disconnects during an active conversation, **When** the user reconnects and switches to the same character, **Then** the previous conversation history is not available

---

### Edge Cases

- When switching to a character that has never been used before, the system creates a new empty conversation history for that character
- When switching characters while one character is actively speaking, the system completes the current character's response before switching to the new character
- When a character's conversation history reaches 100 messages, the system implements memory management (e.g., truncation of oldest messages or compression) to prevent excessive memory usage
- When switching to a character that was previously cleared, the system treats it as a fresh character with empty conversation history
- When the session is interrupted unexpectedly (network issues, browser crash), the system clears all character conversation histories immediately, treating it the same as an intentional disconnect

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST maintain separate conversation histories for each character within a session
- **FR-002**: System MUST allow users to switch between characters without disconnecting from the session
- **FR-003**: System MUST preserve conversation history when switching back to a previously used character
- **FR-004**: System MUST provide a function to clear conversation history for a specific character
- **FR-005**: System MUST clear all character-specific conversation histories when a session disconnects (both intentional and unexpected interruptions)
- **FR-006**: System MUST start with fresh conversation history when switching to a character for the first time in a session
- **FR-007**: System MUST maintain conversation history integrity during character switches (no message loss or corruption)
- **FR-008**: System MUST complete the current character's response before switching to a new character when a switch is requested mid-response
- **FR-009**: System MUST expose conversation history management functions through the chat API
- **FR-010**: System MUST ensure that clearing one character's history does not affect other characters' histories
- **FR-011**: System MUST implement memory management when a character's conversation history reaches 100 messages to prevent excessive memory usage
- **FR-012**: System MUST allow users to switch characters by clicking on a character in the character list, with the active character visually indicated

### Key Entities _(include if feature involves data)_

- **Character Conversation History**: Represents the complete conversation thread between a user and a specific character, including all messages, timestamps, and context
- **Character Session State**: Tracks which character is currently active and manages the switching between character contexts
- **Session Manager**: Oversees the overall session state and coordinates character-specific data management

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Users can switch between characters in under 2 seconds without session interruption
- **SC-002**: Character conversation histories are preserved with 100% accuracy when switching between characters
- **SC-003**: Users can clear individual character histories without affecting other characters' data
- **SC-004**: All conversation histories are completely cleared within 1 second of session disconnection
- **SC-005**: System supports up to 10 different character conversation histories per session without performance degradation
- **SC-006**: Character switching maintains conversation context integrity (no message duplication or loss)
- **SC-007**: Users can successfully resume conversations with previously used characters 100% of the time
