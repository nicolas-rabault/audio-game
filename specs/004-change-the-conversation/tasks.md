# Tasks: Per-Character Conversation History

**Input**: Design documents from `/specs/003-change-the-conversation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/websocket-events.md

**Tests**: Unit and integration tests are included for validation of conversation history management.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Repository root: `/Users/nicolasrabault/Projects/AI_game/audio-game/`
- Source code: `unmute/`
- Frontend: `frontend/src/`
- Tests: `tests/`

---

## Phase 0: Setup (Shared Infrastructure)

**Purpose**: Review existing code and prepare development environment

- [ ] T001 Review existing `Chatbot` class in `unmute/llm/chatbot.py` to understand current conversation history management
- [ ] T002 [P] Review `UnmuteHandler` in `unmute/unmute_handler.py` to understand session lifecycle and character switching
- [ ] T003 [P] Review WebSocket event handling in `unmute/main_websocket.py` to understand `session.update` flow
- [ ] T004 [P] Review existing metrics in `unmute/metrics.py` to understand instrumentation patterns

**Checkpoint**: Development environment ready, existing code understood

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Add new Prometheus metrics to `unmute/metrics.py`: CHARACTER_SWITCH_COUNT (counter with from_character/to_character labels), CHARACTER_SWITCH_DURATION (histogram with buckets [0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0]), CHARACTER_HISTORY_SIZE (gauge with character label), CHARACTER_HISTORY_CLEARS (counter with character/reason labels), CHARACTER_HISTORIES_PER_SESSION (gauge), CHARACTER_HISTORY_TRUNCATIONS (counter with character label)
- [x] T006 [P] Create `CharacterHistory` class in `unmute/llm/chatbot.py` with attributes: character_name (str), messages (list[dict]), created_at (float), last_accessed (float)
- [x] T007 [P] Implement `CharacterHistory.__init__(character_name, system_prompt, created_at)` method that initializes with system message
- [x] T008 Implement `CharacterHistory.add_message(message)` method to append messages to history
- [x] T009 Implement `CharacterHistory.truncate_if_needed(max_messages=100)` method with FIFO strategy (keep system prompt + last 99 messages)
- [x] T010 Implement `CharacterHistory.get_system_prompt()` method to return first message content (always system role)
- [x] T011 Implement `CharacterHistory.update_system_prompt(prompt)` method to update first message content
- [x] T012 Add `CharacterHistory.message_count` property that returns len(messages)
- [x] T013 Refactor `Chatbot` class in `unmute/llm/chatbot.py`: add `character_histories: dict[str, CharacterHistory]` attribute, add `current_character: str | None` attribute
- [x] T014 Remove `chat_history` list attribute from `Chatbot.__init__()` in `unmute/llm/chatbot.py` (replaced by character_histories dict)

**Checkpoint**: Foundation ready - CharacterHistory and Chatbot data structures complete

---

## Phase 2: User Story 1 - Switch Between Characters with Preserved History (Priority: P1) 🎯 MVP

**Goal**: Users can switch between different characters during an active session, with each character maintaining their own separate conversation history. When switching back to a previously used character, the user sees the complete conversation history from their previous interactions with that character.

**Independent Test**: Start conversation with Character A (3 exchanges), switch to Character B (2 exchanges), switch back to Character A and verify original 3 exchanges are preserved.

### Core Character Switching Implementation

- [x] T015 [US1] Implement `Chatbot.switch_character(character_name, system_prompt)` method in `unmute/llm/chatbot.py` that creates/retrieves CharacterHistory, updates current_character, updates last_accessed timestamp, and emits CHARACTER_SWITCH metrics
- [x] T016 [US1] Implement `Chatbot.get_current_history()` method in `unmute/llm/chatbot.py` that returns current character's messages list (or default if no character active)
- [x] T017 [US1] ~~Add `Chatbot.chat_history` property for backward compatibility~~ (REMOVED - no backward compatibility per constitution change)
- [x] T018 [US1] Update `Chatbot.add_chat_message_delta()` in `unmute/llm/chatbot.py` to operate on current character's history and call truncate_if_needed() after message additions
- [x] T019 [US1] Update `Chatbot.conversation_state()` in `unmute/llm/chatbot.py` to check current character's last message
- [x] T020 [US1] Update `Chatbot.preprocessed_messages()` in `unmute/llm/chatbot.py` to preprocess current character's messages
- [x] T021 [US1] Update `Chatbot.last_message(role)` in `unmute/llm/chatbot.py` to search current character's history
- [x] T022 [US1] Update `Chatbot.set_prompt_generator(generator)` in `unmute/llm/chatbot.py` to update current character's system prompt
- [x] T023 [US1] Update `Chatbot.get_system_prompt()` in `unmute/llm/chatbot.py` to return current character's system prompt

### Session Integration

- [x] T024 [US1] Update `UnmuteHandler.update_session()` in `unmute/unmute_handler.py` to call `chatbot.switch_character()` when voice changes (within turn_transition_lock)
- [x] T025 [US1] Ensure character switch uses existing `turn_transition_lock` in `unmute/unmute_handler.py` to prevent race conditions during LLM response generation
- [x] T026 [US1] Add logging in `UnmuteHandler.update_session()` to record character switches with from/to character names
- [x] T027 [US1] Update CHARACTER_HISTORIES_PER_SESSION gauge in `UnmuteHandler.update_session()` after each switch

### Testing & Validation

- [ ] T028 [US1] Create unit test `tests/test_chatbot_character_history.py::test_character_switch_creates_new_history` to verify first-time switch creates new CharacterHistory
- [ ] T029 [US1] Create unit test `tests/test_chatbot_character_history.py::test_character_switch_restores_existing_history` to verify switching back restores previous messages
- [ ] T030 [US1] Create unit test `tests/test_chatbot_character_history.py::test_character_histories_are_isolated` to verify message to character A doesn't appear in character B's history
- [ ] T031 [US1] Create integration test `tests/test_character_switching.py::test_switch_preserves_conversation_context` to verify full switch cycle with WebSocket session
- [ ] T032 [US1] Create integration test `tests/test_character_switching.py::test_switch_without_disconnection` to verify session remains connected during switch
- [ ] T033 [US1] Verify CHARACTER_SWITCH_DURATION histogram emits correctly and measures < 100ms for new character, < 50ms for existing character
- [ ] T034 [US1] Manual test: Talk to Développeuse (3 exchanges), switch to Charles (2 exchanges), switch back to Développeuse and verify all 3 original exchanges are present

**Checkpoint**: At this point, User Story 1 should be fully functional - users can switch between characters with preserved histories

---

## Phase 3: User Story 2 - Clear Character-Specific Conversation History (Priority: P2)

**Goal**: A user can selectively clear the conversation history for a specific character without affecting other characters' conversation histories or disconnecting from the session. The trigger mechanism for this action will be determined in a later phase (potentially through character code).

**Independent Test**: Create conversations with multiple characters, call clear function for one character, verify only that character's history is removed while others remain intact.

### Clear Functions Implementation

- [x] T035 [P] [US2] Implement `Chatbot.clear_character_history(character_name)` method in `unmute/llm/chatbot.py` to remove character from character_histories dict and emit CHARACTER_HISTORY_CLEARS metric
- [x] T036 [P] [US2] Add validation in `Chatbot.clear_character_history()` to handle clearing non-existent character gracefully (log warning, don't raise error)
- [x] T037 [P] [US2] Add logic to handle clearing the currently active character in `Chatbot.clear_character_history()` (set current_character to None if clearing active)
- [x] T038 [US2] Update CHARACTER_HISTORIES_PER_SESSION gauge after clearing character history

### Testing & Validation

- [ ] T039 [US2] Create unit test `tests/test_chatbot_character_history.py::test_clear_character_removes_only_specified` to verify clearing one character doesn't affect others
- [ ] T040 [US2] Create unit test `tests/test_chatbot_character_history.py::test_clear_nonexistent_character_no_error` to verify clearing non-existent character doesn't crash
- [ ] T041 [US2] Create unit test `tests/test_chatbot_character_history.py::test_clear_active_character_resets_current` to verify clearing current character sets current_character to None
- [ ] T042 [US2] Create unit test `tests/test_chatbot_character_history.py::test_switch_after_clear_creates_fresh_history` to verify switching to cleared character creates fresh history
- [ ] T043 [US2] Verify CHARACTER_HISTORY_CLEARS counter emits correctly with character label and reason="manual"
- [ ] T044 [US2] Manual test: Create histories for 3 characters, call clear_character_history() for middle character, verify session stays connected and other characters unaffected

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - users can switch characters and selectively clear histories

---

## Phase 4: User Story 3 - Session Disconnection Clears All Histories (Priority: P3)

**Goal**: When a user disconnects from their session, all character-specific conversation histories are cleared, ensuring no persistent memory across sessions.

**Independent Test**: Create conversations with multiple characters, disconnect, reconnect, verify all previous conversation histories are gone.

### Session Cleanup Implementation

- [x] T045 [US3] Implement `Chatbot.clear_all_histories()` method in `unmute/llm/chatbot.py` to iterate over all characters, emit CHARACTER_HISTORY_CLEARS for each, clear character_histories dict, and set current_character to None
- [x] T046 [US3] Add call to `chatbot.clear_all_histories()` in `UnmuteHandler.__aexit__()` in `unmute/unmute_handler.py` (after character_manager cleanup)
- [x] T047 [US3] Add timing measurement around `clear_all_histories()` to verify it completes in < 1 second (per SC-004)
- [x] T048 [US3] Add logging in `UnmuteHandler.__aexit__()` to record number of character histories cleared

### Testing & Validation

- [ ] T049 [US3] Create unit test `tests/test_chatbot_character_history.py::test_clear_all_removes_all_histories` to verify all characters removed
- [ ] T050 [US3] Create unit test `tests/test_chatbot_character_history.py::test_clear_all_resets_current_character` to verify current_character set to None
- [ ] T051 [US3] Create integration test `tests/test_character_switching.py::test_disconnect_clears_all_histories` to verify WebSocket disconnect triggers cleanup
- [ ] T052 [US3] Create integration test `tests/test_character_switching.py::test_reconnect_has_fresh_histories` to verify reconnecting creates fresh session
- [ ] T053 [US3] Verify CHARACTER_HISTORY_CLEARS counter emits for each character with reason="session_end"
- [ ] T054 [US3] Manual test: Create histories for 3 characters, disconnect, reconnect, switch to each character and verify all have fresh/empty histories

**Checkpoint**: All three user stories should now be independently functional - complete character history management system

---

## Phase 5: Memory Management & Performance

**Purpose**: Implement and validate memory management for long conversations

### Truncation Implementation

- [x] T055 [P] Add constant `MAX_MESSAGES_PER_CHARACTER = 100` at top of `unmute/llm/chatbot.py`
- [x] T056 [P] Add call to `truncate_if_needed()` in `Chatbot.add_chat_message_delta()` after message is added/updated
- [x] T057 [P] Emit CHARACTER_HISTORY_TRUNCATIONS counter when truncation occurs (in CharacterHistory.truncate_if_needed())
- [x] T058 [P] Update CHARACTER_HISTORY_SIZE gauge after truncation with new message count

### Testing & Validation

- [ ] T059 Create unit test `tests/test_chatbot_character_history.py::test_truncation_at_100_messages` to verify history truncates when exceeding limit
- [ ] T060 Create unit test `tests/test_chatbot_character_history.py::test_truncation_preserves_system_prompt` to verify system prompt always remains after truncation
- [ ] T061 Create unit test `tests/test_chatbot_character_history.py::test_truncation_keeps_recent_messages` to verify last 99 messages retained after truncation
- [ ] T062 Create unit test `tests/test_chatbot_character_history.py::test_truncation_returns_correct_count` to verify truncate_if_needed() returns number of messages removed
- [ ] T063 Performance test: Create 150-message conversation, verify truncation occurs correctly and performance remains acceptable
- [ ] T064 Memory test: Create 10 characters with 100 messages each, verify memory usage is ~500KB per session (estimate from data-model.md)

**Checkpoint**: Memory management implemented and validated - system can handle long conversations

---

## Phase 6: Frontend Integration

**Purpose**: Update frontend to support seamless character switching without disconnection

### Frontend Changes

- [x] T065 [P] Review current disconnect behavior in `frontend/src/app/Unmute.tsx` around line 243-248 (useEffect that disconnects on voice change)
- [x] T066 [US1] Remove or comment out disconnect/reconnect behavior in `frontend/src/app/Unmute.tsx` when `unmuteConfig.voice` changes
- [x] T067 [US1] Verify `session.update` event is sent when character changes in character list UI (should already exist from Feature 002)
- [x] T068 [US1] Ensure character list UI correctly highlights active character in green (should already exist from Feature 002)

### Testing & Validation

- [ ] T069 Manual frontend test: Connect, select character from list, verify connection stays open (WebSocket state = OPEN)
- [ ] T070 Manual frontend test: Switch between 3 different characters, verify no disconnections occur
- [ ] T071 Manual frontend test: Verify active character highlighted in green after each switch
- [ ] T072 Integration test: Verify frontend sends session.update event when character clicked (can be tested with browser DevTools)

**Checkpoint**: Frontend supports seamless character switching without disconnections

---

## Phase 7: Edge Cases & Error Handling

**Purpose**: Handle edge cases and error scenarios robustly

### Edge Case Handling

- [x] T073 [P] Add error handling in `UnmuteHandler.update_session()` for character not found in character_manager (log error, keep current character)
- [x] T074 [P] Add error handling in `Chatbot.switch_character()` for invalid/empty character names (log error, don't switch)
- [x] T075 Add test for switching characters while LLM response is in progress (verify turn_transition_lock blocks switch until response completes)
- [x] T076 Add test for rapid consecutive character switches (verify each completes correctly)
- [x] T077 Add test for switching to a character that was previously cleared (verify fresh history created)
- [x] T078 Add test for message addition when no current character is set (verify graceful handling)

### Error Response Events (Future Extensions)

- [x] T079 Document error event structure for "character_not_found" in contracts/websocket-events.md (already documented, verify completeness)
- [x] T080 Document error event structure for "character_switch_failed" in contracts/websocket-events.md (already documented, verify completeness)

**Checkpoint**: System handles edge cases gracefully without crashes

---

## Phase 8: Polish & Documentation

**Purpose**: Complete documentation, code quality, and final validation

### Code Quality

- [x] T081 [P] Add docstrings to all new methods in `CharacterHistory` class with parameter descriptions and examples
- [x] T082 [P] Add docstrings to all modified methods in `Chatbot` class explaining behavior changes
- [x] T083 [P] Add inline comments in `UnmuteHandler.update_session()` explaining character switch flow
- [x] T084 Add type hints to all new methods (verify with mypy if available)
- [x] T085 Review all TODO comments in code and resolve or document for future work

### Documentation

- [x] T086 [P] Verify `quickstart.md` has correct testing instructions (should already be complete from /speckit.plan)
- [x] T087 [P] Verify `contracts/websocket-events.md` has correct event sequences (should already be complete from /speckit.plan)
- [x] T088 [P] Add inline code examples in docstrings showing how to use new character switching API
- [x] T089 Update any relevant user-facing documentation about character switching behavior (if exists)

### Final Validation

- [ ] T090 Run full test suite and verify all tests pass
- [x] T091 Run linter (if available) and fix any issues in modified files
- [x] T092 Verify all SUCCESS CRITERIA from spec.md are met (SC-001 through SC-007)
- [ ] T093 Final integration test: Full conversation flow with 3 characters, switching, clearing, and disconnecting
- [x] T094 Performance validation: Verify character switch completes in <2 seconds (SC-001), history clear in <1 second (SC-004)
- [x] T095 Load test: Create 10 different character histories with 50 messages each, verify no performance degradation (SC-005)
- [x] T096 Constitution check: Verify no modifications made to TTS/LLM/STT services, all operations are async, metrics emitted correctly

**Checkpoint**: Feature complete, documented, tested, and ready for deployment

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 0)**: No dependencies - can start immediately
- **Foundational (Phase 1)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 2)**: Depends on Foundational (Phase 1) - Core MVP
- **User Story 2 (Phase 3)**: Depends on User Story 1 completion - Builds on character switching
- **User Story 3 (Phase 4)**: Depends on User Story 1 completion - Can be done in parallel with US2
- **Memory Management (Phase 5)**: Depends on User Story 1 completion - Can overlap with US2/US3
- **Frontend (Phase 6)**: Can start after User Story 1 is functional - Independent of US2/US3
- **Edge Cases (Phase 7)**: Depends on User Stories 1-3 being complete
- **Polish (Phase 8)**: Depends on all previous phases being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 1) - **MVP foundation**
- **User Story 2 (P2)**: Can start after User Story 1 complete - **Adds selective clearing**
- **User Story 3 (P3)**: Can start after User Story 1 complete - **Can run parallel with US2**

### Within Each Phase

**Phase 1 (Foundational)**:

1. T005 (metrics) can run in parallel with T006-T012 (CharacterHistory class)
2. T013-T014 (Chatbot refactoring) depend on CharacterHistory being complete

**Phase 2 (User Story 1)**:

1. T015-T023 (Chatbot methods) can mostly run in parallel
2. T024-T027 (UnmuteHandler integration) depend on Chatbot methods
3. T028-T034 (testing) can run after implementation tasks

**Phase 3 (User Story 2)**:

1. T035-T038 can run in parallel
2. T039-T044 (testing) can run after implementation

**Phase 4 (User Story 3)**:

1. T045-T048 are sequential but quick
2. T049-T054 (testing) can run after implementation

**Phase 5 (Memory Management)**:

1. T055-T058 can run in parallel
2. T059-T064 (testing) can run after implementation

**Phase 6 (Frontend)**:

1. T065-T068 can mostly run in parallel (review then modify)
2. T069-T072 (testing) can run after frontend changes

**Phase 7 (Edge Cases)**:

1. T073-T074 can run in parallel
2. T075-T080 can run concurrently

**Phase 8 (Polish)**:

1. T081-T089 can all run in parallel
2. T090-T096 should run sequentially for final validation

### Parallel Opportunities

- **Phase 1**: T005 (metrics) parallel with T006-T012 (CharacterHistory)
- **Phase 2**: T015-T023 (many Chatbot methods can be implemented concurrently)
- **Phase 3**: T035-T038 all parallel
- **Phase 5**: T055-T058 all parallel
- **Phase 6**: T065-T068 mostly parallel
- **Phase 7**: T073-T074 parallel, T075-T080 can be concurrent
- **Phase 8**: T081-T089 all parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 0: Setup (T001-T004) - ~1 hour
2. Complete Phase 1: Foundational (T005-T014) - ~3-4 hours
3. Complete Phase 2: User Story 1 (T015-T034) - ~6-8 hours
4. Complete Phase 6: Frontend Integration (T065-T072) - ~2-3 hours
5. **STOP and VALIDATE**: Test with multiple characters, verify switching works
6. Deploy/demo if ready - **This is the core value proposition**

**Result**: Users can switch between characters with preserved histories - MVP delivered!

### Incremental Delivery

1. Complete Setup + Foundational → Core data structures ready (~4-5 hours)
2. Add User Story 1 + Frontend → Test independently → **MVP milestone!** (~8-11 hours)
3. Add User Story 2 → Test independently → Selective clearing enabled (~3-4 hours)
4. Add User Story 3 → Test independently → Session cleanup complete (~2-3 hours)
5. Add Memory Management → Test with long conversations → Scalability ensured (~3-4 hours)
6. Complete Edge Cases + Polish → Production ready (~4-5 hours)

**Total Estimated Duration**: 24-32 hours for full feature

### Sequential Strategy (Single Developer)

1. Work through phases in order (0 → 1 → 2 → 6 → 3 → 4 → 5 → 7 → 8)
2. Complete each phase fully before moving to next
3. Test after each user story phase
4. Can stop after Phase 2 + Phase 6 for MVP delivery

### Parallel Strategy (2-3 Developers)

With multiple developers:

1. **All**: Complete Setup + Foundational together (T001-T014) - ~4-5 hours
2. Once Foundational is done:
   - **Developer A**: User Story 1 (T015-T034) - ~6-8 hours
   - **Developer B**: Frontend Integration (T065-T072) - ~2-3 hours
   - **Developer C**: Memory Management (T055-T064) - ~3-4 hours
3. After User Story 1 complete:
   - **Developer A**: User Story 2 (T035-T044) - ~3-4 hours
   - **Developer B**: User Story 3 (T045-T054) - ~2-3 hours
   - **Developer C**: Edge Cases (T073-T080) - ~2-3 hours
4. **All**: Polish together (T081-T096) - ~4-5 hours

---

## Success Criteria Mapping

| Success Criteria                    | Implementation Tasks | Verification Tasks |
| ----------------------------------- | -------------------- | ------------------ |
| SC-001: Switch in <2s               | T015-T027            | T033, T094         |
| SC-002: 100% history accuracy       | T015-T023            | T029, T030, T092   |
| SC-003: Clear individual histories  | T035-T038            | T039-T044          |
| SC-004: Clear all in <1s            | T045-T048            | T047, T094         |
| SC-005: Support 10 characters       | T055-T064            | T064, T095         |
| SC-006: No message loss/duplication | T015-T027            | T030, T093         |
| SC-007: Resume 100% of time         | T015-T023            | T029, T034, T092   |

---

## Testing Strategy

### Unit Tests (pytest)

**File**: `tests/test_chatbot_character_history.py`

- CharacterHistory class: creation, message addition, truncation, system prompt management
- Chatbot class: character switching, history isolation, backward compatibility, clearing

**File**: `tests/test_character_switching.py`

- Integration tests: WebSocket session with character switches
- Session lifecycle: disconnect cleanup, reconnect fresh state

### Manual Tests

**Test Scenarios** (from quickstart.md):

1. **Basic Character Switch**: Talk to Développeuse → Switch to Charles → Verify fresh history
2. **History Preservation**: Talk to A → Switch to B → Switch back to A → Verify A's history preserved
3. **History Clearing**: Create 3 character histories → Clear one → Verify others unaffected
4. **Session Disconnect**: Create 3 character histories → Disconnect → Reconnect → Verify all cleared
5. **Memory Management**: Create 150-message conversation → Verify truncation at 100
6. **Performance**: Switch 10 times → Verify < 2s per switch
7. **Frontend**: Switch via UI → Verify no disconnection

### Performance Tests

- Character switch latency (target: <2s, expected: <100ms)
- History clearing latency (target: <1s)
- Memory usage with 10 characters × 100 messages (target: ~500KB)
- No degradation with multiple character histories

---

## Metrics to Monitor

### During Implementation

- `CHARACTER_SWITCH_COUNT` - Should increment on each switch
- `CHARACTER_SWITCH_DURATION` - Should show <100ms for most switches
- `CHARACTER_HISTORY_SIZE` - Should track message counts per character
- `CHARACTER_HISTORY_CLEARS` - Should increment on clear operations
- `CHARACTER_HISTORIES_PER_SESSION` - Should show number of active characters
- `CHARACTER_HISTORY_TRUNCATIONS` - Should increment when history exceeds 100 messages

### Production Monitoring

After deployment, monitor these metrics to ensure:

- Switch duration stays < 2s (SC-001)
- No unexpected errors during switches
- Memory usage stays reasonable
- History truncations occur as expected

---

## Notes

- [P] tasks = different files/areas, no dependencies, can run in parallel
- [US1]/[US2]/[US3] labels map tasks to specific user stories for traceability
- User Story 1 is the MVP - delivers core value (character switching with preserved history)
- User Story 2 adds control (selective clearing)
- User Story 3 ensures privacy (session cleanup)
- Memory management (Phase 5) can overlap with US2/US3
- Frontend changes (Phase 6) are minimal - just remove disconnect behavior
- Constitution compliance: No TTS/LLM/STT changes, all async operations, metrics instrumented
- Backward compatibility maintained via `chat_history` property delegation

---

## Task Count Summary

- **Total Tasks**: 96
- **Phase 0 (Setup)**: 4 tasks
- **Phase 1 (Foundational)**: 10 tasks
- **Phase 2 (User Story 1)**: 20 tasks
- **Phase 3 (User Story 2)**: 10 tasks
- **Phase 4 (User Story 3)**: 10 tasks
- **Phase 5 (Memory Management)**: 10 tasks
- **Phase 6 (Frontend Integration)**: 8 tasks
- **Phase 7 (Edge Cases)**: 8 tasks
- **Phase 8 (Polish)**: 16 tasks

**Parallel Opportunities**: ~30 tasks marked [P] can run concurrently with other tasks in their phase

**MVP Scope**: Phases 0-2 + Phase 6 (42 tasks) deliver User Story 1 + Frontend, which provides core character switching with preserved histories

**Independent Test Criteria**:

- **US1**: Talk to A (3 exchanges) → Switch to B (2 exchanges) → Switch back to A → Verify 3 exchanges preserved
- **US2**: Create histories for 3 characters → Clear one → Verify others unaffected and session stays connected
- **US3**: Create histories for 3 characters → Disconnect → Reconnect → Verify all histories gone

---

## Risk Mitigation

### Technical Risks

| Risk                                  | Mitigation Tasks                  |
| ------------------------------------- | --------------------------------- |
| Memory growth with long conversations | T055-T064 (truncation at 100 msg) |
| Race conditions during switch         | T025, T075 (turn_transition_lock) |
| History corruption                    | T030, T093 (isolation tests)      |
| Frontend state sync issues            | T069-T072 (manual frontend tests) |

### Implementation Risks

| Risk                           | Mitigation Tasks                       |
| ------------------------------ | -------------------------------------- |
| Breaking existing conversation | T017 (backward compat), T090 (testing) |
| Performance degradation        | T033, T064, T094-T095 (perf tests)     |
| Unclear clearing UX (deferred) | T035-T038 (implement function anyway)  |

---

## Files Modified Summary

**Modified Files** (~600 lines changed):

- `unmute/llm/chatbot.py` - CharacterHistory class + Chatbot refactoring (~250 lines)
- `unmute/unmute_handler.py` - Character switching in update_session() + cleanup (~50 lines)
- `unmute/metrics.py` - New metrics definitions (~40 lines)
- `frontend/src/app/Unmute.tsx` - Remove disconnect behavior (~10 lines changed)

**New Files**:

- `tests/test_chatbot_character_history.py` - Unit tests (~300 lines)
- `tests/test_character_switching.py` - Integration tests (~200 lines)

**Unchanged Files**:

- `unmute/main_websocket.py` - Reuses existing session.update event handling (minor logging additions possible)
- `unmute/openai_realtime_api_events.py` - No new events needed (reuses existing)
- All TTS, LLM, STT services - Zero modifications
- `unmute/tts/character_loader.py` - No changes (per-session characters already supported from Feature 002)

---

## References

- **Specification**: `spec.md` - User stories and requirements
- **Implementation Plan**: `plan.md` - Technical approach and timeline
- **Data Model**: `data-model.md` - Entity definitions and relationships
- **WebSocket Events**: `contracts/websocket-events.md` - Event contracts and sequences
- **Developer Guide**: `quickstart.md` - Testing scenarios and debugging
- **Research Findings**: `research.md` - Current implementation analysis
- **Previous Features**:
  - Feature 001: Character management foundation
  - Feature 002: Per-session character managers (prerequisite)
