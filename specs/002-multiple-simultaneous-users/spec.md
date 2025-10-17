# Feature Specification: Per-Session Character Management

**Feature Branch**: `002-multiple-simultaneous-users`
**Created**: 2025-10-16
**Status**: Draft
**Input**: User description: "Multiple simultaneous users need different character sets each"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Independent Character Selection Per User (Priority: P1)

Each user connecting to the system can access and interact with their own set of characters without affecting other users' character availability or choices. When User A loads a custom character set, User B continues to see and use their own character set (either default or custom).

**Why this priority**: This is the core requirement - without this, the feature doesn't exist. Multi-user isolation is the foundational capability that enables all other scenarios.

**Independent Test**: Can be fully tested by opening two browser sessions (or two different users), having each session load different character directories, and verifying that each session sees only their own characters. Delivers immediate value by allowing multiple users to work simultaneously without interference.

**Acceptance Scenarios**:

1. **Given** User A is connected to the system with default characters loaded, **When** User B connects and loads a custom character set from `/custom/characters`, **Then** User A continues to see default characters and User B sees only the custom characters
2. **Given** multiple users are connected simultaneously, **When** one user changes their character set, **Then** other users' character sets remain unchanged
3. **Given** a user has loaded a custom character set, **When** they start a conversation with a character, **Then** the conversation uses the character from their session-specific character set

---

### User Story 2 - Dynamic Character Set Switching Per Session (Priority: P2)

A user can dynamically switch their character set during an active session by requesting a reload from a different directory. This reload only affects their own session and does not disrupt their connection or other users' sessions.

**Why this priority**: Enables flexible workflow where users can experiment with different character sets without needing to reconnect or affecting others. Adds significant usability value on top of the base isolation.

**Independent Test**: Connect as a single user, load default characters, switch to custom characters, then switch back to default - all within the same WebSocket session. Verify character list updates correctly each time without disconnection.

**Acceptance Scenarios**:

1. **Given** a user is connected with default characters, **When** they request to reload with a custom character directory, **Then** their character list updates to show only custom characters without disconnecting their session
2. **Given** a user has custom characters loaded, **When** they reload with "default", **Then** their character list updates to show default characters
3. **Given** a user is mid-conversation with a character, **When** they reload characters, **Then** the conversation gracefully ends and they can start a new conversation with characters from the new set

---

### Edge Cases

- What happens when a user tries to load a character directory that doesn't exist or has no valid characters?
- How does the system handle concurrent reload requests from the same user?
- What happens when a user is actively speaking with a character (mid-generation) when they trigger a reload?
- How does the system handle two users trying to load the same custom character directory simultaneously?
- What happens when a character file in a user's loaded directory is invalid or fails validation?
- How does the system behave when a user's session is disconnected during a character reload operation?
- What happens when multiple sessions are using characters with the same name from different directories?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain separate character registries for each active user session
- **FR-002**: System MUST support loading characters from any valid directory path on the filesystem per session
- **FR-003**: System MUST isolate character module loading per session to prevent naming conflicts (e.g., two sessions loading different `charles.py` files)
- **FR-004**: Users MUST be able to reload their character set without disconnecting their WebSocket session
- **FR-005**: System MUST validate that the requested character directory exists and contains valid character files before attempting to load
- **FR-006**: System MUST provide feedback to users about the status of character loading (success, partial failure, total failure)
- **FR-007**: System MUST handle character loading errors gracefully without affecting other active sessions
- **FR-008**: System MUST support a "default" keyword to reload the standard characters directory
- **FR-009**: System MUST prevent one user's character reload from affecting other users' loaded characters
- **FR-010**: System MUST clean up session-specific character modules from memory when a session ends
- **FR-011**: System MUST handle mid-conversation character reloads by gracefully ending the active conversation
- **FR-012**: Users MUST be able to query which characters are currently available in their session

### Key Entities

- **User Session**: Represents a single user's connection to the system, maintains its own character registry, conversation state, and preferences
- **Session Character Manager**: Per-session instance that manages character loading, validation, and lookup for one user
- **Character Module**: Dynamically loaded Python module containing character definition, must be isolated per session to prevent conflicts
- **Character Registry**: Session-scoped dictionary mapping character names to character instances, unique per user session

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Multiple users (at least 10 concurrent) can connect and load different character sets simultaneously without conflicts or errors
- **SC-002**: Users can reload their character set within their session in under 2 seconds for directories with up to 20 characters
- **SC-003**: Character reloads in one session cause zero observable impact on other active sessions (no latency increase, no errors)
- **SC-004**: System maintains stable memory usage - memory per session increases linearly with character count, not exponentially
- **SC-005**: 100% isolation guarantee - no user can see or interact with another user's custom characters
- **SC-006**: Users receive clear feedback within 1 second when character loading succeeds, partially fails, or completely fails
- **SC-007**: System handles at least 50 concurrent sessions each with unique character sets without performance degradation

## Assumptions

- The system has sufficient memory to handle multiple concurrent character sets (estimated 10-50 MB per session with 10-20 characters)
- Character files are stored on a filesystem accessible to the server process
- Users have a way to specify which character directory they want to load (via WebSocket message or API call)
- Character validation logic is already implemented and can be reused for per-session loading
- The existing global character manager can be refactored to a session-scoped implementation
- WebSocket protocol can be extended to support character reload commands
- Session cleanup mechanisms exist to prevent memory leaks when users disconnect

## Dependencies

- Existing character loading infrastructure (CharacterManager, validation, importlib-based loading)
- WebSocket session management and message handling
- Module loading and namespace isolation capabilities in Python
- Current character file format and validation logic

## Out of Scope

- Sharing characters between users (each user's characters remain private to their session)
- Persistent storage of per-user character preferences across sessions
- Authentication or authorization for accessing specific character directories
- Real-time synchronization of character sets across multiple devices for the same user
- Character version control or rollback mechanisms
- Quota limits or restrictions on how many character sets a user can load
- Administrative tools for monitoring which users have which characters loaded
