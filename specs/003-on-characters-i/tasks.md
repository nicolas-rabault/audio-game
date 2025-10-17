---
description: "Implementation tasks for Optional TOOLS Variable for Character Function Calling"
---

# Tasks: Optional TOOLS Variable for Character Function Calling

**Input**: Design documents from `/home/metab/audio-game/specs/003-on-characters-i/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Not explicitly requested in specification - focusing on implementation tasks only

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions
- Repository root structure: `unmute/`, `characters/`, `tests/`
- Character files in `characters/` directory
- Core system in `unmute/tts/`, `unmute/llm/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Remove legacy format code and prepare for TOOLS implementation

- [X] T001 Remove legacy format documentation from characters/README.md (sections referencing INSTRUCTIONS['type'] field)
- [X] T002 Update CLAUDE.md to remove legacy format references and add TOOLS documentation overview
- [X] T003 [P] Add Pydantic models for tool validation in unmute/tts/character_loader.py (ToolFunctionDefinition, ToolDefinition, CharacterTools)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core tool infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create tool_executor.py module in unmute/llm/ for tool validation and execution logic
- [X] T005 [P] Add Prometheus metrics infrastructure for tool calls (CHARACTER_TOOL_CALLS, CHARACTER_TOOL_ERRORS, CHARACTER_TOOL_LATENCY) in unmute/llm/tool_executor.py
- [X] T006 [P] Implement JSON Schema to Pydantic model conversion in unmute/llm/tool_executor.py (create_parameter_model function)
- [X] T007 Implement execute_tool function in unmute/llm/tool_executor.py with parameter validation, timeout enforcement, and error handling
- [X] T008 Update _validate_character_data in unmute/tts/character_loader.py to validate TOOLS variable structure
- [X] T009 Add tool validator generation logic to unmute/tts/character_loader.py (calls create_parameter_model for each tool)
- [X] T010 Verify handle_tool_call method exists when TOOLS defined in unmute/tts/character_loader.py validation

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 2.5: Performance Infrastructure

**Purpose**: Performance testing and metrics infrastructure for tool execution latency

**⚠️ INCLUDED**: Feature affects conversation latency through tool execution

- [X] T011 [P] Add Stopwatch timing instrumentation to tool execution in unmute/llm/tool_executor.py
- [ ] T012 [P] Create baseline loadtest scenario using unmute/loadtest/loadtest_client.py with narrator character (no tools) - DEFERRED to post-implementation
- [X] T013 Document performance acceptance criteria in specs/003-on-characters-i/performance-baseline.md (tool execution <100ms, total latency increase <10%)

**Checkpoint**: Performance infrastructure ready - proceed with feature implementation

---

## Phase 3: User Story 1 - Character Developer Adds Tool to Existing Character (Priority: P1) 🎯 MVP

**Goal**: Enable character developers to add TOOLS variable to existing characters with LLM-triggered function calling

**Independent Test**: Add TOOLS variable with logging tool to narrator.py, start conversation, verify tool gets called when LLM decides to use it and output appears in terminal

### Implementation for User Story 1

- [X] T014 [US1] Integrate tools parameter into VLLMStream.chat_completion() in unmute/llm/llm_utils.py (add tools to API call)
- [X] T015 [US1] Add tool call detection in streaming response processing in unmute/llm/llm_utils.py (check for chunk.choices[0].delta.tool_calls) - Implemented in VLLMStream.chat_completion()
- [X] T016 [US1] Implement tool call execution flow in unmute/llm/llm_utils.py (call execute_tool when LLM requests tool) - Implemented in VLLMStream.chat_completion()
- [X] T017 [US1] Add tool response formatting and message queue handling in unmute/llm/llm_utils.py (create tool message, re-query LLM) - Implemented in VLLMStream.chat_completion()
- [X] T018 [US1] Add TOOLS variable to characters/narrator.py with log_story_event tool definition
- [X] T019 [US1] Implement get_tools() method in PromptGenerator class in characters/narrator.py
- [X] T020 [US1] Implement handle_tool_call() method in PromptGenerator class in characters/narrator.py
- [X] T021 [US1] Add error handling for tool execution failures in unmute/llm/tool_executor.py (JSON parse errors, validation errors, timeouts, execution errors)
- [X] T022 [US1] Add logging for tool calls and errors in unmute/llm/tool_executor.py

**Checkpoint**: At this point, User Story 1 should be fully functional - narrator.py can use logging tool during conversations

---

## Phase 4: User Story 2 - Character Developer Creates New Tool-Enabled Character (Priority: P2)

**Goal**: Enable character developers to create new characters from scratch with multiple custom tools defined from the beginning

**Independent Test**: Create a new character file with TOOLS defined from start, load it, verify tools work in conversation

### Implementation for User Story 2

- [ ] T023 [P] [US2] Update characters/README.md with complete TOOLS documentation (definition format, best practices, examples)
- [ ] T024 [P] [US2] Add tool definition examples to characters/README.md (minimal example, multi-tool example, parameter types)
- [ ] T025 [US2] Create character template with TOOLS in characters/README.md (copy-paste ready template)
- [ ] T026 [US2] Validate that empty TOOLS list is handled correctly in unmute/tts/character_loader.py (loads normally, treated as no tools)
- [ ] T027 [US2] Add tool name uniqueness validation in unmute/tts/character_loader.py (prevent duplicate tool names within character)
- [ ] T028 [US2] Add tool parameter constraint validation in unmute/tts/character_loader.py (max 10 tools, max 10 parameters per tool, description <200 chars)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - existing characters can add tools, new characters can be created with tools

---

## Phase 5: User Story 3 - User Interacts with Tool-Enabled Character (Priority: P3)

**Goal**: End users experience enhanced character capabilities through transparent tool execution without conversation interruption

**Independent Test**: Have conversation with narrator character, trigger logging tool through natural dialogue, verify tool executes without breaking conversation flow

### Implementation for User Story 3

- [ ] T029 [P] [US3] Add tool execution success metrics in unmute/llm/tool_executor.py (increment CHARACTER_TOOL_CALLS counter)
- [ ] T030 [P] [US3] Add tool latency histogram recording in unmute/llm/tool_executor.py (observe execution time)
- [ ] T031 [US3] Verify tool results are properly integrated into LLM conversation context in unmute/unmute_handler.py
- [ ] T032 [US3] Test tool error scenarios return helpful messages to LLM in unmute/llm/tool_executor.py (verify error format)
- [ ] T033 [US3] Add terminal logging for tool executions to aid debugging in unmute/llm/tool_executor.py

**Checkpoint**: All user stories should now be independently functional - end-to-end tool calling works seamlessly

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, testing, and validation improvements

- [ ] T034 [P] Update quickstart.md with testing instructions and common troubleshooting scenarios
- [ ] T035 [P] Create unit tests for tool validation in tests/test_character_loader.py (test TOOLS detection, schema validation, missing handler detection)
- [ ] T036 [P] Create unit tests for tool executor in tests/test_tool_executor.py (test parameter validation, error handling, timeout enforcement)
- [ ] T037 Create end-to-end integration test in tests/integration/test_tools_e2e.py (load narrator, trigger tool via conversation, verify execution)
- [ ] T038 Run performance comparison loadtest (narrator without tools vs with tools) and verify <10% latency increase
- [ ] T039 Document any vLLM-specific function calling limitations or quirks found during testing in specs/003-on-characters-i/vllm-notes.md
- [ ] T040 Validate quickstart.md examples work correctly (test all code samples)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **Performance Infrastructure (Phase 2.5)**: Depends on Foundational completion - needed for performance validation
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
  - Core tool integration into LLM and character loading
  - Adds logging tool to narrator.py as demonstration
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - No dependencies on US1
  - Focuses on documentation and validation for new character creation
  - Builds on same infrastructure as US1
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - No dependencies on US1/US2
  - Focuses on metrics and end-user experience validation
  - Enhances observability of tool usage

### Within Each User Story

**User Story 1 (Core Integration)**:
1. LLM integration (T014-T015) - Add tools to API calls and detect tool calls
2. Tool execution flow (T016-T017) - Execute tools and handle responses
3. Character implementation (T018-T020) - Add tools to narrator.py
4. Error handling (T021-T022) - Handle all error scenarios

**User Story 2 (Documentation & Validation)**:
- All tasks can run in parallel (documentation updates and validation enhancements)
- T023-T025 focus on documentation
- T026-T028 focus on validation

**User Story 3 (Metrics & UX)**:
- T029-T030 can run in parallel (metrics)
- T031-T033 verify integration quality

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003 independent of T001-T002)
- All Foundational tasks marked [P] can run in parallel (T005-T006 once T004 exists)
- Performance infrastructure tasks (T011-T012) can run in parallel
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- Within US2: all tasks can run in parallel
- Within US3: T029-T030 can run in parallel

---

## Parallel Example: User Story 1

```bash
# After T014-T015 complete, can parallelize character implementation:
Task T018: "Add TOOLS variable to characters/narrator.py"
Task T019: "Implement get_tools() method in characters/narrator.py"
Task T020: "Implement handle_tool_call() method in characters/narrator.py"

# (These touch same file but are sequential edits to same PromptGenerator class)

# Error handling can be enhanced in parallel with integration testing
Task T021: "Add error handling for tool execution failures"
Task T022: "Add logging for tool calls and errors"
```

---

## Parallel Example: User Story 2

```bash
# All documentation tasks can run together:
Task T023: "Update characters/README.md with complete TOOLS documentation"
Task T024: "Add tool definition examples to characters/README.md"

# All validation tasks can run together:
Task T026: "Validate empty TOOLS handling in unmute/tts/character_loader.py"
Task T027: "Add tool name uniqueness validation in unmute/tts/character_loader.py"
Task T028: "Add tool parameter constraints in unmute/tts/character_loader.py"
```

---

## Parallel Example: Polish Phase

```bash
# All documentation and testing can run in parallel:
Task T034: "Update quickstart.md with testing instructions"
Task T035: "Create unit tests for tool validation in tests/test_character_loader.py"
Task T036: "Create unit tests for tool executor in tests/test_tool_executor.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (Remove legacy format, add Pydantic models)
2. Complete Phase 2: Foundational (Tool executor, validation, metrics) - **CRITICAL**
3. Complete Phase 2.5: Performance Infrastructure (Baseline metrics)
4. Complete Phase 3: User Story 1 (Core integration + narrator.py example)
5. **STOP and VALIDATE**: Test narrator.py tool independently via conversation
6. Deploy/demo if ready - **This is the MVP!**

### Incremental Delivery

1. Complete Setup + Foundational → Tool infrastructure ready
2. Add User Story 1 → Test narrator.py independently → Deploy/Demo (MVP - core functionality working!)
3. Add User Story 2 → Validate new character creation → Deploy/Demo (Enhanced documentation and validation)
4. Add User Story 3 → Validate end-user experience → Deploy/Demo (Complete observability)
5. Polish phase → Final testing and documentation → Production ready

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (T001-T013)
2. **Once Foundational is done:**
   - Developer A: User Story 1 (T014-T022) - Core integration
   - Developer B: User Story 2 (T023-T028) - Documentation
   - Developer C: User Story 3 (T029-T033) - Metrics
3. **Converge for Polish** (T034-T040) - Testing and validation

---

## Summary

**Total Tasks**: 40
- Setup: 3 tasks
- Foundational: 7 tasks (blocking)
- Performance Infrastructure: 3 tasks
- User Story 1 (P1 - MVP): 9 tasks
- User Story 2 (P2): 6 tasks
- User Story 3 (P3): 5 tasks
- Polish: 7 tasks

**Parallel Opportunities Identified**: 15 parallelizable tasks across all phases

**Independent Test Criteria**:
- **US1**: Add TOOLS to narrator.py, trigger tool in conversation, see terminal output
- **US2**: Create new tool-enabled character from scratch, verify it loads and works
- **US3**: Have natural conversation with tool-enabled character, tools execute transparently

**Suggested MVP Scope**: User Story 1 only (Tasks T001-T022)
- Delivers core functionality: optional TOOLS variable with LLM-triggered function calling
- Includes working example: narrator.py with logging tool
- Demonstrates end-to-end flow: tool definition → LLM decides → tool executes → result returned
- Removes legacy format code as specified

**Format Validation**: ✅ All tasks follow checklist format (checkbox, ID, labels, file paths)

---

## Notes

- [P] tasks = different files or sections, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Legacy format removal (T001-T002) is included as part of this feature per requirements
- Tool execution timeout enforced at 100ms to maintain latency budgets
- All tool errors returned to LLM for graceful user-facing responses
- Performance testing ensures <10% conversation latency increase
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
