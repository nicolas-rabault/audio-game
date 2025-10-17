# Tasks: Per-Session Character Management

**Input**: Design documents from `/specs/002-multiple-simultaneous-users/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/websocket-events.md

**Tests**: Not explicitly requested in spec - focus on implementation with manual validation

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions
- Repository root: `/home/metab/audio-game/`
- Source code: `unmute/`
- Tests: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare development environment and verify prerequisites

- [ ] T001 Verify Python 3.12 environment and existing dependencies (FastAPI, Pydantic, importlib, asyncio)
- [ ] T002 [P] Review existing character loading infrastructure in unmute/tts/character_loader.py
- [ ] T003 [P] Review existing WebSocket event handling in unmute/main_websocket.py and unmute/openai_realtime_api_events.py
- [ ] T004 [P] Review UnmuteHandler lifecycle in unmute/unmute_handler.py

**Checkpoint**: Development environment ready, existing code understood

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Add new Prometheus metrics to unmute/metrics.py (CHARACTER_RELOAD_DURATION, SESSION_CHARACTER_COUNT, CHARACTER_LOAD_PER_SESSION)
- [ ] T006 [P] Add new WebSocket event models to unmute/openai_realtime_api_events.py (SessionCharactersReload, SessionCharactersList, CharacterInfo, SessionCharactersReloaded, SessionCharactersListed)
- [ ] T007 [P] Update ClientEvent and ServerEvent unions in unmute/openai_realtime_api_events.py to include new event types
- [ ] T008 Add session_id parameter to CharacterManager.__init__() in unmute/tts/character_loader.py with UUID generation and module_prefix creation
- [ ] T009 Add _current_directory attribute to CharacterManager in unmute/tts/character_loader.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Independent Character Selection Per User (Priority: P1) 🎯 MVP

**Goal**: Enable multiple users to maintain separate character registries without affecting each other. Each session loads and manages its own character set in an isolated namespace.

**Independent Test**: Open two WebSocket sessions, have each load different character directories, verify each session sees only their own characters. Start conversations in both sessions and confirm characters are session-specific.

### Core Namespace Isolation

- [ ] T010 [P] [US1] Update _load_character_file_sync() in unmute/tts/character_loader.py to accept module_prefix parameter and use it for module naming
- [ ] T011 [P] [US1] Update _load_single_character() in unmute/tts/character_loader.py to accept and pass module_prefix parameter
- [ ] T012 [US1] Update CharacterManager.load_characters() in unmute/tts/character_loader.py to pass self.module_prefix to _load_single_character()
- [ ] T013 [US1] Add cleanup_session_modules() method to CharacterManager in unmute/tts/character_loader.py to remove session-specific modules from sys.modules

### Session Integration

- [ ] T014 [US1] Add character_manager instance variable to UnmuteHandler.__init__() in unmute/unmute_handler.py
- [ ] T015 [US1] Add _characters_loaded flag to UnmuteHandler in unmute/unmute_handler.py
- [ ] T016 [US1] Update UnmuteHandler.start_up() in unmute/unmute_handler.py to load default characters using self.character_manager
- [ ] T017 [US1] Update UnmuteHandler.update_session() in unmute/unmute_handler.py to use self.character_manager.get_character() instead of global manager
- [ ] T018 [US1] Update UnmuteHandler.__aexit__() in unmute/unmute_handler.py to call self.character_manager.cleanup_session_modules()

### Metrics Integration

- [ ] T019 [US1] Add metrics instrumentation to CharacterManager.load_characters() in unmute/tts/character_loader.py (SESSION_CHARACTER_COUNT gauge)
- [ ] T020 [US1] Add logging for session_id in CharacterManager initialization and character loading operations in unmute/tts/character_loader.py

**Checkpoint**: At this point, User Story 1 should be fully functional - multiple users can connect simultaneously with independent character sets

---

## Phase 4: User Story 2 - Dynamic Character Set Switching Per Session (Priority: P2)

**Goal**: Enable users to dynamically reload their character set mid-session without disconnecting or affecting other users' sessions.

**Independent Test**: Connect as a single user, load default characters, send session.characters.reload event with custom directory, verify character list updates without disconnection, reload with "default" and verify return to original characters.

### Character Reload Implementation

- [ ] T021 [P] [US2] Implement reload_characters() method in CharacterManager in unmute/tts/character_loader.py (cleanup old modules, clear registry, load new characters)
- [ ] T022 [P] [US2] Add metrics instrumentation to reload_characters() in unmute/tts/character_loader.py (CHARACTER_RELOAD_DURATION histogram)
- [ ] T023 [P] [US2] Update CharacterManager.load_characters() in unmute/tts/character_loader.py to set _current_directory attribute

### WebSocket Event Handling

- [ ] T024 [US2] Add handle_character_reload() function in unmute/main_websocket.py to process session.characters.reload events
- [ ] T025 [US2] Add handle_character_list() function in unmute/main_websocket.py to process session.characters.list events
- [ ] T026 [US2] Add event routing in _run_route() in unmute/main_websocket.py for session.characters.reload and session.characters.list events
- [ ] T027 [US2] Implement directory path validation in handle_character_reload() (check exists, is_dir, handle "default" keyword)
- [ ] T028 [US2] Implement error handling in handle_character_reload() for missing/invalid directories (send appropriate error events)
- [ ] T029 [US2] Build SessionCharactersReloaded response in handle_character_reload() with character list and counts
- [ ] T030 [US2] Build SessionCharactersListed response in handle_character_list() with current character registry

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - users have independent character sets AND can reload them dynamically

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Testing, documentation, and improvements that affect multiple user stories

### Manual Testing

- [ ] T031 Create manual test script for multi-session isolation testing (two WebSocket connections with different characters)
- [ ] T032 Test character reload with invalid directory paths (verify error handling)
- [ ] T033 Test character reload with empty directory (verify error handling)
- [ ] T034 Test character reload with partially invalid characters (verify partial success handling)
- [ ] T035 Test concurrent reload requests from same session (verify behavior)
- [ ] T036 Test memory cleanup by connecting/disconnecting multiple sessions and monitoring sys.modules

### Verification

- [ ] T037 Verify module namespace isolation (check sys.modules has session-unique prefixes)
- [ ] T038 Verify Prometheus metrics are emitted correctly for character operations
- [ ] T039 Verify session cleanup removes all character modules from memory
- [ ] T040 Verify character loading time is <2 seconds for 20 characters
- [ ] T041 Test with 10+ concurrent sessions with different character sets

### Documentation

- [ ] T042 [P] Update CLAUDE.md with per-session character management patterns (if not already updated by agent context script)
- [ ] T043 [P] Add inline code comments explaining session_id and module_prefix logic in unmute/tts/character_loader.py
- [ ] T044 [P] Document new WebSocket events in relevant API documentation (if exists)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on User Story 1 completion (builds on session isolation)
- **Polish (Phase 5)**: Depends on User Stories 1 and 2 being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - **Independent foundation for multi-user support**
- **User Story 2 (P2)**: Can start after User Story 1 complete - **Adds dynamic reloading to existing isolation**

### Within Each User Story

**User Story 1**:
1. Core Namespace Isolation tasks (T010-T013) must complete first
2. Session Integration tasks (T014-T018) depend on namespace isolation
3. Metrics Integration tasks (T019-T020) can happen in parallel with session integration

**User Story 2**:
1. Character Reload Implementation (T021-T023) must complete first
2. WebSocket Event Handling tasks (T024-T030) depend on reload implementation

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 can run in parallel (reviewing different files)
- **Phase 2**: T006 and T007 (events) can run parallel with T008 and T009 (CharacterManager changes)
- **User Story 1**: T010 and T011 can run in parallel, T019 and T020 can run after core tasks
- **User Story 2**: T021, T022, T023 can run in parallel, T024-T030 are sequential but independent of T021-T023 initially
- **Phase 5**: Most documentation tasks (T042-T044) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch namespace isolation tasks together:
Task T010: "Update _load_character_file_sync() with module_prefix in unmute/tts/character_loader.py"
Task T011: "Update _load_single_character() with module_prefix in unmute/tts/character_loader.py"

# After T010-T012 complete, launch session integration tasks:
Task T014: "Add character_manager to UnmuteHandler.__init__() in unmute/unmute_handler.py"
Task T015: "Add _characters_loaded flag in unmute/unmute_handler.py"
Task T019: "Add metrics instrumentation in unmute/tts/character_loader.py"
Task T020: "Add logging for session_id in unmute/tts/character_loader.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch reload implementation tasks together:
Task T021: "Implement reload_characters() in unmute/tts/character_loader.py"
Task T022: "Add metrics to reload_characters() in unmute/tts/character_loader.py"
Task T023: "Update load_characters() to set _current_directory in unmute/tts/character_loader.py"

# After reload is working, launch event handling tasks:
Task T024: "Add handle_character_reload() in unmute/main_websocket.py"
Task T025: "Add handle_character_list() in unmute/main_websocket.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004) - ~30 minutes
2. Complete Phase 2: Foundational (T005-T009) - ~1 hour
3. Complete Phase 3: User Story 1 (T010-T020) - ~3-4 hours
4. **STOP and VALIDATE**: Test with two WebSocket sessions, verify isolation
5. Deploy/demo if ready - **This is a complete, valuable feature on its own**

**Result**: Users can now connect simultaneously with independent character sets - immediate value delivered!

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (~1.5 hours)
2. Add User Story 1 → Test independently → Deploy/Demo (~3-4 hours) - **MVP achieved!**
3. Add User Story 2 → Test independently → Deploy/Demo (~2-3 hours) - **Enhanced with dynamic reloading**
4. Complete Polish phase → Final validation (~2-3 hours) - **Production ready**

**Total Estimated Time**: 8-12 hours for full feature

### Sequential Team Strategy (Single Developer)

1. Work through phases in order (1 → 2 → 3 → 4 → 5)
2. Complete each phase fully before moving to next
3. Test after each user story phase
4. Can stop after User Story 1 for MVP delivery

### Parallel Team Strategy (2 Developers)

With two developers:

1. **Both**: Complete Setup + Foundational together (~1.5 hours)
2. Once Foundational is done:
   - **Developer A**: User Story 1 (Core Isolation) - ~3-4 hours
   - **Developer B**: Prepare User Story 2 tasks (review websocket code, plan event handlers)
3. After User Story 1 complete:
   - **Developer A**: Begin Polish/Testing
   - **Developer B**: User Story 2 (Dynamic Reloading) - ~2-3 hours
4. **Both**: Final testing and validation together

---

## Success Metrics

After implementation, verify:

- ✅ Two WebSocket sessions can connect with independent character sets
- ✅ Session A can load custom characters while Session B keeps default characters
- ✅ Character reload in one session doesn't affect other sessions
- ✅ Module namespaces are isolated (check sys.modules for session-unique prefixes)
- ✅ Memory cleanup works (modules removed from sys.modules after session ends)
- ✅ Character reload completes in <2 seconds for 20 characters
- ✅ Prometheus metrics emit correctly (SESSION_CHARACTER_COUNT, CHARACTER_RELOAD_DURATION)
- ✅ Error handling works for invalid directories
- ✅ "default" keyword reloads original characters/ directory
- ✅ System supports 10+ concurrent sessions with unique character sets

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [US1]/[US2] labels map tasks to specific user stories for traceability
- User Story 1 is the MVP - delivers immediate value (multi-user isolation)
- User Story 2 builds on US1 - adds dynamic reloading capability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- No unit tests explicitly requested - focus on manual validation and integration testing
- Follow quickstart.md for detailed implementation guidance on each task

---

## File Modification Summary

**Modified Files** (~400 lines changed):
- `unmute/tts/character_loader.py` - Core CharacterManager refactoring (~150 lines)
- `unmute/unmute_handler.py` - Session integration (~80 lines)
- `unmute/main_websocket.py` - WebSocket event handling (~100 lines)
- `unmute/openai_realtime_api_events.py` - New event types (~40 lines)
- `unmute/metrics.py` - New metrics (~30 lines)

**New Files** (optional, for testing):
- `tests/test_character_loader_per_session.py` - Session isolation tests
- `tests/test_session_isolation.py` - Multi-session integration tests
- Manual test scripts for WebSocket validation

**Unchanged Files**:
- `unmute/tts/voices.py` - VoiceSample model
- `characters/` - Character file format
- All TTS, LLM, STT services
