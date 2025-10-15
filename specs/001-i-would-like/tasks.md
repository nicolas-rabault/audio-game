# Tasks: Self-Contained Character Management System

**Input**: Design documents from `/specs/001-i-would-like/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-endpoints.md

**Tests**: Tests are NOT explicitly requested in this feature specification, so test tasks are excluded.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions
- Single Python project at repository root
- Source: `unmute/`
- Characters: `story_characters/`
- Scripts: `scripts/`
- Tests: `tests/` (minimal - only if needed later)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create `story_characters/` directory at repository root
- [ ] T002 [P] Create `unmute/tts/character_loader.py` module stub for character loading logic
- [ ] T003 [P] Review existing models in `unmute/tts/voices.py` (VoiceSample, VoiceSource, FileVoiceSource, FreesoundVoiceSource)
- [ ] T004 [P] Review existing instruction classes in `unmute/llm/system_prompt.py` (ConstantInstructions, SmalltalkInstructions, QuizShowInstructions, NewsInstructions, GuessAnimalInstructions, UnmuteExplanationInstructions)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Add Prometheus metrics to `unmute/metrics.py`: CHARACTER_LOAD_COUNT (counter), CHARACTER_LOAD_ERRORS (counter with error_type label), CHARACTER_LOAD_DURATION (histogram with buckets [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]), CHARACTERS_LOADED (gauge)
- [ ] T006 [P] Implement character file discovery logic in `unmute/tts/character_loader.py` to find all .py files in story_characters/ directory
- [ ] T007 [P] Implement dynamic module loading using importlib.util.spec_from_file_location in `unmute/tts/character_loader.py`
- [ ] T008 Implement character file validation (two-phase: structure check for required attributes, then Pydantic validation) in `unmute/tts/character_loader.py`
- [ ] T009 Implement duplicate name detection with first-loaded-wins logic in `unmute/tts/character_loader.py`
- [ ] T010 Implement async character loading using asyncio.to_thread() and asyncio.gather() for concurrent file loading in `unmute/tts/character_loader.py`
- [ ] T011 Create CharacterLoadResult dataclass in `unmute/tts/character_loader.py` with fields: characters dict, total_files, loaded_count, error_count, load_duration
- [ ] T012 Implement CharacterManager class in `unmute/tts/character_loader.py` with load_characters() async method and get_character() sync method
- [ ] T013 Add error logging for invalid files (import errors, validation errors, missing attributes, duplicates) in `unmute/tts/character_loader.py`
- [ ] T014 Emit all Prometheus metrics during character loading in `unmute/tts/character_loader.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Character Bank Loading (Priority: P1) 🎯 MVP

**Goal**: Load a specific bank of characters from the story_characters/ folder so that characters are organized without mixing unrelated character sets

**Independent Test**: Create a `story_characters/` folder with at least 2 character files. Start the system and verify that only characters from that folder are available for voice selection, not characters from any legacy `voices.yaml` file.

### Implementation for User Story 1

- [ ] T015 [US1] Create example character file `story_characters/watercooler.py` with CHARACTER_NAME="Watercooler", VOICE_SOURCE (file type), INSTRUCTIONS (smalltalk type), METADATA, and PromptGenerator class
- [ ] T016 [US1] Create example character file `story_characters/quiz-show.py` with CHARACTER_NAME="Quiz show", VOICE_SOURCE (freesound type), INSTRUCTIONS (quiz_show type), METADATA, and PromptGenerator class
- [ ] T017 [US1] Initialize CharacterManager singleton instance at startup in `unmute/main_websocket.py` (load characters from story_characters/ directory using asyncio)
- [ ] T018 [US1] Update `/v1/voices` endpoint in `unmute/main_websocket.py` to use CharacterManager instead of VoiceList (read from story_characters/)
- [ ] T019 [US1] Ensure `/v1/voices` endpoint excludes internal fields (_source_file, _prompt_generator) from response in `unmute/main_websocket.py`
- [ ] T020 [US1] Ensure `/v1/voices` endpoint only returns characters where good=True in `unmute/main_websocket.py`
- [ ] T021 [US1] Add startup logging to show character load summary (total files, loaded count, error count, duration) in `unmute/main_websocket.py`
- [ ] T022 [US1] Test that empty story_characters/ directory logs appropriate warning and system starts successfully
- [ ] T023 [US1] Test that character list API returns all loaded characters with names and metadata
- [ ] T024 [US1] Verify VoiceSample models from character files include _source_file and _prompt_generator attributes after loading

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. System loads characters from story_characters/ folder and exposes them via /v1/voices API.

---

## Phase 4: User Story 2 - Self-Contained Character Files (Priority: P1)

**Goal**: Each character's complete definition (name, voice sample reference, LLM instructions, metadata, and prompt generation logic) stored in a single file for independent management

**Independent Test**: Create a single character file with all required fields (name, voice path, instructions, metadata). Load this character into the system and verify that both LLM and TTS services can successfully use the character without requiring any external configuration files.

### Implementation for User Story 2

- [ ] T025 [P] [US2] Create example character file `story_characters/gertrude.py` with ConstantInstructions type and custom text in INSTRUCTIONS
- [ ] T026 [P] [US2] Add validation in `unmute/tts/character_loader.py` to verify PromptGenerator class has __init__(instructions) method
- [ ] T027 [P] [US2] Add validation in `unmute/tts/character_loader.py` to verify PromptGenerator class has make_system_prompt() method returning string
- [ ] T028 [US2] Test character with missing required field (CHARACTER_NAME) is rejected with descriptive error logged
- [ ] T029 [US2] Test character with missing required field (VOICE_SOURCE) is rejected with descriptive error logged
- [ ] T030 [US2] Test character with missing required field (INSTRUCTIONS) is rejected with descriptive error logged
- [ ] T031 [US2] Test character with missing PromptGenerator class is rejected with descriptive error logged
- [ ] T032 [US2] Verify LLM service can call character._prompt_generator(instructions).make_system_prompt() to get system prompt without external dependencies
- [ ] T033 [US2] Verify TTS service can access character.source.path_on_server (or character.source.url for freesound) from loaded character
- [ ] T034 [US2] Create example characters for all 6 instruction types: constant, smalltalk, quiz_show, news, guess_animal, unmute_explanation in story_characters/

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently. Characters are fully self-contained with prompt generation logic inside character files.

---

## Phase 5: User Story 3 - Legacy Character Migration (Priority: P2)

**Goal**: Convert all existing characters from voices.yaml into the new self-contained format to preserve existing character configurations

**Independent Test**: Run the migration script on the current `voices.yaml` file. Verify that each entry in `voices.yaml` produces exactly one character file in `story_characters/` with all original data preserved (name, voice source, instructions).

### Implementation for User Story 3

- [ ] T035 [P] [US3] Create migration script stub `scripts/migrate_voices_yaml.py` with command-line argument parsing (--dry-run, --output-dir)
- [ ] T036 [P] [US3] Implement YAML reading logic in `scripts/migrate_voices_yaml.py` using ruamel.yaml to load voices.yaml
- [ ] T037 [US3] Create PromptGenerator template mappings in `scripts/migrate_voices_yaml.py` for all 6 instruction types (constant, smalltalk, quiz_show, news, guess_animal, unmute_explanation)
- [ ] T038 [US3] Implement character file generation logic in `scripts/migrate_voices_yaml.py` that creates .py file with CHARACTER_NAME, VOICE_SOURCE, INSTRUCTIONS, METADATA, and PromptGenerator class
- [ ] T039 [US3] Implement filename sanitization in `scripts/migrate_voices_yaml.py` (lowercase, spaces to hyphens, .py extension)
- [ ] T040 [US3] Implement duplicate name handling in `scripts/migrate_voices_yaml.py` (suffix with _2, _3 for duplicates with warning log)
- [ ] T041 [US3] Add --dry-run mode in `scripts/migrate_voices_yaml.py` that prints generated files without writing to disk
- [ ] T042 [US3] Add summary logging in `scripts/migrate_voices_yaml.py` (files created, skipped, errors)
- [ ] T043 [US3] Create migration log file `migration.log` with detailed migration results in `scripts/migrate_voices_yaml.py`
- [ ] T044 [US3] Test migration script on existing voices.yaml file: verify character count matches
- [ ] T045 [US3] Test migrated character with type: smalltalk produces file with SmalltalkInstructions in PromptGenerator
- [ ] T046 [US3] Test migrated character with Freesound voice source preserves URL, license, and description fields
- [ ] T047 [US3] Test that migrated characters load successfully into the system and function identically to voices.yaml counterparts
- [ ] T048 [US3] Run migration script on production voices.yaml to generate all character files in story_characters/

**Checkpoint**: All user stories should now be independently functional. Legacy characters migrated to new format.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T049 [P] Add deprecation notice to VoiceList class in `unmute/tts/voices.py` docstring indicating migration to character_loader
- [ ] T050 [P] Update quickstart.md with validation instructions (how to create character, test loading, API verification)
- [ ] T051 [P] Create character file template documentation comment in `story_characters/README.md` with required attributes and PromptGenerator interface
- [ ] T052 [P] Add character loading error troubleshooting guide in quickstart.md
- [ ] T053 Code review: Verify all constitution checks pass (Service Isolation, Async-First Architecture, Observability & Metrics)
- [ ] T054 Performance test: Load 50 character files and verify load time <5 seconds
- [ ] T055 Performance test: Load 100 character files and verify load time <10 seconds
- [ ] T056 Graceful degradation test: Create character files with 20% error rate and verify system starts successfully
- [ ] T057 Verify /v1/voices endpoint contract unchanged (response structure, field types, field names, only good=True returned)
- [ ] T058 Manual test: Copy character file to different environment and verify it works without additional configuration
- [ ] T059 [P] Update CLAUDE.md with character management commands and file structure
- [ ] T060 Final integration test: Start server with migrated characters and verify all functionality works end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User Story 1 (P1): Can start after Phase 2
  - User Story 2 (P1): Can start after Phase 2 (independent of US1)
  - User Story 3 (P2): Can start after Phase 2 (ideally after US1 and US2 for validation)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Independent of US1, but complements it
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Benefits from US1+US2 completion for validation, but technically independent

### Within Each User Story

- Setup tasks (Phase 1): All [P] tasks can run in parallel
- Foundational tasks (Phase 2): T005 can run in parallel with T006-T007; T008-T014 are sequential
- User Story 1: T015-T016 (character files) can run in parallel; T017-T024 are mostly sequential
- User Story 2: T025-T027 can run in parallel; T028-T034 can be done concurrently
- User Story 3: T035-T037 can run in parallel; T038-T048 are mostly sequential

### Parallel Opportunities

- All Setup tasks marked [P] (T002, T003, T004) can run in parallel
- Phase 2: T005 (metrics), T006 (file discovery), T007 (module loading) can start in parallel
- User Story 1: T015 and T016 (example character files) can be created in parallel
- User Story 2: T025 (gertrude character), T026 (validation), T027 (validation) can run in parallel
- User Story 3: T035 (script stub), T036 (YAML reading), T037 (templates) can run in parallel
- Polish: T049, T050, T051, T052, T059 can all run in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch in parallel (different files, no dependencies):
Task T005: "Add Prometheus metrics to unmute/metrics.py"
Task T006: "Implement character file discovery logic in unmute/tts/character_loader.py"
Task T007: "Implement dynamic module loading in unmute/tts/character_loader.py"
```

## Parallel Example: User Story 1

```bash
# Launch character file creation in parallel:
Task T015: "Create example character file story_characters/watercooler.py"
Task T016: "Create example character file story_characters/quiz-show.py"
```

## Parallel Example: Polish Phase

```bash
# Launch documentation tasks in parallel:
Task T049: "Add deprecation notice to VoiceList class in unmute/tts/voices.py"
Task T050: "Update quickstart.md with validation instructions"
Task T051: "Create character file template documentation in story_characters/README.md"
Task T052: "Add error troubleshooting guide in quickstart.md"
Task T059: "Update CLAUDE.md with character management commands"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only - Both P1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Character Bank Loading)
4. Complete Phase 4: User Story 2 (Self-Contained Character Files)
5. **STOP and VALIDATE**: Test that characters can be created, loaded, and used by LLM/TTS services
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Characters load from folder (MVP milestone 1!)
3. Add User Story 2 → Test independently → Characters are fully self-contained (MVP milestone 2!)
4. Add User Story 3 → Test independently → Legacy characters migrated
5. Polish → Production ready

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T014)
2. Once Foundational is done:
   - Developer A: User Story 1 (T015-T024)
   - Developer B: User Story 2 (T025-T034)
   - Developer C: Can prepare User Story 3 or help with US1/US2
3. After US1+US2 complete:
   - Developer C: User Story 3 (T035-T048)
4. Team completes Polish together (T049-T060)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests are NOT included per specification - focus is on implementation
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Performance targets: 50 characters in <5s, 100 characters in <10s
- Constitution compliance: No TTS/LLM/STT service modifications, async file I/O, Prometheus metrics
- Migration is one-time operation, no backward compatibility required

---

## Task Count Summary

- **Total Tasks**: 60
- **Phase 1 (Setup)**: 4 tasks
- **Phase 2 (Foundational)**: 10 tasks
- **Phase 3 (User Story 1)**: 10 tasks
- **Phase 4 (User Story 2)**: 10 tasks
- **Phase 5 (User Story 3)**: 14 tasks
- **Phase 6 (Polish)**: 12 tasks

**Parallel Opportunities**: 19 tasks marked [P] can run concurrently with other tasks in their phase

**MVP Scope**: Phases 1-4 (34 tasks) deliver User Stories 1 & 2, which provide core character loading and self-contained file format

**Independent Test Criteria**:
- **US1**: Create 2 character files → Start system → Verify /v1/voices returns exactly those 2 characters
- **US2**: Create 1 complete character file → Load into system → Verify LLM and TTS can use it without external config
- **US3**: Run migration script on voices.yaml → Verify each entry produces 1 character file with preserved data
