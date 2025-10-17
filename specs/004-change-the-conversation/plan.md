# Implementation Plan: Per-Character Conversation History

**Branch**: `003-change-the-conversation` | **Date**: 2025-01-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-change-the-conversation/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement per-character conversation history management within a single user session. Each character will maintain its own isolated conversation history that persists when switching between characters but is cleared when the session disconnects. Users can switch characters via the existing character list UI, and all character histories are cleared on session termination.

**Technical Approach**: Extend the `Chatbot` class to manage multiple character-specific conversation histories using a dictionary keyed by character name. Add character switching logic to the `UnmuteHandler` that preserves and restores conversation context. Implement history management functions (clear single character, clear all) and memory management for histories exceeding 100 messages.

## Technical Context

**Language/Version**: Python 3.12 (as specified in pyproject.toml: `requires-python = ">=3.12,<3.13"`)
**Primary Dependencies**: Existing - FastAPI (WebSocket), Pydantic (validation), asyncio (concurrency)
**Storage**: In-memory dictionary of conversation histories per character within the session
**Testing**: pytest for unit tests, manual WebSocket testing for integration
**Target Platform**: Linux server (existing deployment)
**Project Type**: Web application (FastAPI backend + Next.js frontend)
**Performance Goals**:

- Character switching in <2 seconds without session interruption
- Support up to 10 different character conversation histories per session
- Zero message loss or corruption during switches
- History clearing in <1 second
  **Constraints**:
- Memory: Linear growth with character count and message count (~100 messages × 10 characters × ~500 bytes per message = ~500KB per session)
- Must not modify TTS, LLM, or STT services
- Must maintain conversation context integrity during switches
- Must complete current character's response before switching
  **Scale/Scope**:
- Single user session with multiple characters
- 10 different character histories per session (SC-005)
- 100 messages maximum per character before memory management kicks in
- No persistent storage across sessions

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

**I. Service Isolation**

- [x] Feature does NOT require modifications to TTS, LLM, or STT services
- [x] All service interactions happen via existing interfaces/protocols
- [x] Any service limitations are documented with workarounds (not fixes)

**Analysis**: This feature is entirely within the conversation management layer. The chatbot passes conversation history to the LLM service through the existing interface. TTS and STT services are unaffected - they receive the same inputs as before. Character switching only affects which conversation history is active.

**II. Performance Testing**

- [x] Feature includes loadtest scenarios if it affects audio pipeline or user interaction timing
- [x] Performance acceptance criteria defined with specific latency targets
- [x] Baseline metrics identified for regression comparison

**Analysis**: Character switching happens outside the audio pipeline (triggered by user UI interaction). Performance tests will measure:

- Character switch latency (target: <2s per SC-001)
- Memory usage with multiple character histories
- No impact on existing audio pipeline latency (STT/TTS/LLM should remain unchanged)
- History clearing latency (target: <1s per SC-004)

**III. Latency Budgets**

- [x] Feature design respects frame-level constraints (24kHz sample rate, 1920 sample frames, 80ms frame time)
- [x] Any new pipeline stages fit within relevant latency budgets
- [x] Feature does not introduce blocking operations in audio path

**Analysis**: Character switching is triggered by UI events outside the audio pipeline. History management (switching, clearing) happens in the control plane, not the data plane. All operations are async and non-blocking. The only interaction with the audio path is that switching waits for the current character's response to complete (FR-008), which prevents mid-speech interruption but doesn't add latency to the audio processing itself.

**IV. Async-First Architecture**

- [x] All I/O operations use async/await patterns
- [x] Inter-task communication uses `asyncio.Queue`
- [x] Timing measurements use `Stopwatch`/`PhasesStopwatch` from `timer.py`
- [x] No blocking operations in main event loop

**Analysis**: Character switching logic will be async. History management operations (switching, clearing) are in-memory dictionary operations (non-blocking). Will use existing async patterns in `UnmuteHandler` and `receive_loop`. No file I/O or network operations involved.

**V. Observability & Metrics**

- [x] New user flows include Prometheus metrics instrumentation
- [x] Metrics cover: counters (sessions/errors), histograms (latencies), gauges (active sessions)
- [x] Service integration points emit connection attempt/failure metrics

**Analysis**: Will add new metrics:

- `CHARACTER_SWITCH_COUNT` (counter with labels: from_character, to_character)
- `CHARACTER_SWITCH_DURATION` (histogram)
- `CHARACTER_HISTORY_SIZE` (gauge with character label)
- `CHARACTER_HISTORY_CLEARS` (counter with labels: character, reason)
- `CHARACTER_HISTORIES_PER_SESSION` (gauge)

**Constitution Check Result**: ✅ PASSED - All gates satisfied, feature aligns with architecture principles

### Post-Design Re-evaluation

**Status**: ✅ **ALL CHECKS PASS**

After completing Phase 0 (research) and Phase 1 (design), the constitution compliance remains valid:

1. **Service Isolation**: Design uses existing `Chatbot` class refactored to manage multiple histories. No changes to TTS/LLM/STT services. Character data flows through existing interfaces via `update_session()`.

2. **Performance Testing**: Character switching is control-plane operation (dictionary lookup and property update). Design includes performance metrics (CHARACTER_SWITCH_DURATION histogram). Target: <2s per SC-001, actual expected: <100ms. No impact on audio pipeline latency.

3. **Latency Budgets**: No new pipeline stages. History management is in-memory dictionary operations (non-blocking). Character switching waits for response completion using existing `turn_transition_lock` (satisfies FR-008 without adding latency to audio processing).

4. **Async-First Architecture**: Design uses existing async patterns in `UnmuteHandler`. All operations are in-memory (non-blocking). History clearing in `__aexit__()` is synchronous dict.clear() (fast enough). No file I/O or network operations.

5. **Observability & Metrics**: Design includes 6 new Prometheus metrics (CHARACTER_SWITCH_COUNT, CHARACTER_SWITCH_DURATION, CHARACTER_HISTORY_SIZE, CHARACTER_HISTORY_CLEARS, CHARACTER_HISTORIES_PER_SESSION, CHARACTER_HISTORY_TRUNCATIONS). Follows existing patterns in `metrics.py`.

**Conclusion**: No constitution violations. Feature is ready for implementation.

## Project Structure

### Documentation (this feature)

```
specs/003-change-the-conversation/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── websocket-events.md  # WebSocket event definitions for character switching
├── checklists/          # Existing
│   └── requirements.md  # Existing requirements checklist
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```
unmute/
├── llm/
│   ├── chatbot.py                       # [MODIFIED] Add per-character history management
│   └── llm_utils.py                     # [UNCHANGED] Existing LLM utilities
├── unmute_handler.py                     # [MODIFIED] Add character switching logic
├── main_websocket.py                     # [MODIFIED] Add WebSocket event handling for switches
├── openai_realtime_api_events.py        # [MODIFIED] Add new event types
└── metrics.py                            # [MODIFIED] Add character switching metrics

frontend/src/app/
├── Unmute.tsx                            # [MODIFIED] Add character switch UI event handling
└── chatHistory.ts                        # [POTENTIALLY MODIFIED] May need character context

tests/
├── test_chatbot_character_history.py    # [NEW] Unit tests for per-character history
└── test_character_switching.py          # [NEW] Integration tests for switching
```

**Structure Decision**: Single project modification (web application backend and frontend). Changes are primarily in the conversation management layer (`Chatbot` class) and session management layer (`UnmuteHandler`). Frontend changes are minimal - leveraging the existing character list UI that already highlights the active character in green.

## Complexity Tracking

_Fill ONLY if Constitution Check has violations that must be justified_

No violations - Constitution Check passed all gates.

---

## Phase 0: Research

**Status**: ✅ **COMPLETE**

### Research Questions

All 6 research questions have been answered and documented in `research.md`:

1. ✅ **Current Conversation History Implementation**: Single global `chat_history` list in `Chatbot` class
2. ✅ **Character Switching Mechanism**: Via `update_session()` which updates system prompt but doesn't manage separate histories
3. ✅ **Session Lifecycle**: Clear initialization (`start_up()`) and cleanup (`__aexit__()`) hooks exist
4. ✅ **WebSocket Event Handling**: Existing `session.update` event can be reused; frontend currently disconnects on character change
5. ✅ **Memory Management Patterns**: No existing truncation; need to implement FIFO truncation with system prompt preservation
6. ✅ **Frontend Character List**: UI exists with green highlighting for active character; triggers config update

### Research Findings

**Key Findings**:

- Current implementation has NO per-character history - just one continuous history
- Character switching just updates system prompt, doesn't preserve/restore histories
- Frontend currently disconnects/reconnects on character change (needs to be fixed)
- Perfect lifecycle hooks exist for initialization and cleanup
- FIFO truncation recommended (keep system prompt + last 99 messages)
- Memory estimate: ~500 KB per session for 10 characters × 100 messages

**See**: `research.md` for detailed findings and analysis

---

## Phase 1: Design

**Status**: ✅ **COMPLETE**

### Deliverables

All 3 design documents have been created:

1. ✅ **data-model.md**: Entity definitions and relationships

   - `CharacterHistory` entity (stores per-character messages)
   - Modified `Chatbot` class (manages multiple character histories)
   - Backward compatible via `chat_history` property
   - Memory management with FIFO truncation
   - Metrics definitions

2. ✅ **quickstart.md**: Developer guide

   - Testing scenarios (basic, multiple characters, truncation, disconnect)
   - Architecture overview and data structures
   - Unit test examples (pytest)
   - Integration test examples (WebSocket)
   - Debugging guide with common issues
   - Performance profiling techniques

3. ✅ **contracts/websocket-events.md**: API contract
   - Reuse existing `session.update` / `session.updated` events
   - Error event definitions
   - Event sequence diagrams
   - Frontend changes required (remove disconnect behavior)
   - Backward compatibility guarantees
   - Performance requirements

### Design Decisions

**Key Decisions**:

- Use dictionary `character_histories: dict[str, CharacterHistory]` instead of single list
- Implement `CharacterHistory` helper class to encapsulate per-character data
- Provide backward compatibility via `chat_history` property (no breaking changes)
- Use FIFO truncation at 100 messages per character
- Reuse existing `turn_transition_lock` for race condition prevention
- No new WebSocket events needed (reuse `session.update`)
- Frontend needs minimal change (remove disconnect behavior)

**See**: `data-model.md`, `quickstart.md`, and `contracts/websocket-events.md` for detailed design

---

## Phase 2: Tasks

_To be completed by `/speckit.tasks` command_

_Will break down implementation into specific, actionable tasks_

---

## Risk Assessment

### Technical Risks

| Risk                                                        | Likelihood | Impact | Mitigation                                                  |
| ----------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------- |
| Memory growth with multiple long conversations              | Medium     | Medium | Implement strict 100-message limit with truncation (FR-011) |
| Race conditions during character switch while LLM streaming | Low        | High   | Use existing `turn_transition_lock` in `UnmuteHandler`      |
| History corruption during switch                            | Low        | High   | Implement atomic switch operation with validation           |
| Frontend state sync issues                                  | Medium     | Low    | Leverage existing character list state management           |

### Implementation Risks

| Risk                                        | Likelihood | Impact | Mitigation                                           |
| ------------------------------------------- | ---------- | ------ | ---------------------------------------------------- |
| Breaking existing conversation flow         | Low        | High   | Comprehensive unit and integration tests             |
| Performance degradation with 10+ characters | Low        | Medium | Benchmark memory and CPU usage during testing        |
| Unclear history clearing UX (deferred)      | High       | Low    | Defer to future phase as specified in clarifications |

---

## Success Criteria Mapping

| Success Criteria                    | Implementation Components                    | Verification Method                      |
| ----------------------------------- | -------------------------------------------- | ---------------------------------------- |
| SC-001: Switch in <2s               | Character switching logic in `UnmuteHandler` | Integration test with timing             |
| SC-002: 100% history accuracy       | History preservation in `Chatbot`            | Unit tests comparing before/after        |
| SC-003: Clear individual histories  | Clear function in `Chatbot`                  | Unit test clearing one, verifying others |
| SC-004: Clear all in <1s            | Cleanup in `UnmuteHandler.__aexit__()`       | Integration test with timing             |
| SC-005: Support 10 characters       | Memory management and benchmarking           | Load test with 10 characters             |
| SC-006: No message loss/duplication | Atomic switching logic                       | Integration tests with validation        |
| SC-007: Resume 100% of time         | History restoration in switch                | Integration tests switching back/forth   |

---

## Dependencies & Prerequisites

### Code Dependencies

- Feature 002 (multiple-simultaneous-users) must be complete - ✅ IMPLEMENTED
- Per-session `CharacterManager` infrastructure exists
- `Chatbot` class must be refactored to support multiple histories

### External Dependencies

- None (no external services or APIs)

### Testing Dependencies

- Pytest with async support
- WebSocket testing infrastructure
- Frontend testing framework (for UI verification)

---

## Timeline Estimate

| Phase                   | Estimated Duration | Key Deliverables                                                  |
| ----------------------- | ------------------ | ----------------------------------------------------------------- |
| Phase 0: Research       | 2-3 hours          | `research.md` with findings                                       |
| Phase 1: Design         | 3-4 hours          | `data-model.md`, `quickstart.md`, `contracts/websocket-events.md` |
| Phase 2: Implementation | 8-12 hours         | Modified `Chatbot`, `UnmuteHandler`, WebSocket handling           |
| Phase 3: Testing        | 4-6 hours          | Unit tests, integration tests, manual testing                     |
| Phase 4: Documentation  | 2-3 hours          | Code comments, user guide updates                                 |

**Total Estimated Duration**: 19-28 hours

---

## Next Steps

**Phase 0 & Phase 1 Complete** ✅

The planning and design phases are now complete. The following documents have been created:

- ✅ `plan.md` - This document (implementation plan)
- ✅ `research.md` - Research findings from codebase analysis
- ✅ `data-model.md` - Entity definitions and data structures
- ✅ `quickstart.md` - Developer guide for testing and debugging
- ✅ `contracts/websocket-events.md` - WebSocket API contracts

**Ready for Phase 2: Implementation**

To proceed with implementation:

1. **Generate Tasks**: Run `/speckit.tasks` command to create `tasks.md` with detailed implementation tasks
2. **Begin Implementation**: Follow the task breakdown to implement:
   - `CharacterHistory` class
   - Modified `Chatbot` class
   - Updated `UnmuteHandler.update_session()`
   - Updated `UnmuteHandler.__aexit__()`
   - New Prometheus metrics
   - Frontend changes (remove disconnect behavior)
3. **Write Tests**: Create unit and integration tests as outlined in `quickstart.md`
4. **Manual Testing**: Follow testing scenarios in `quickstart.md`
5. **Performance Validation**: Verify performance meets success criteria (SC-001 through SC-007)
6. **Documentation**: Update inline code comments and user-facing documentation

**Estimated Implementation Time**: 8-12 hours (per timeline estimate)

---

## Notes

- The feature leverages existing per-session architecture from feature 002
- History clearing UX is deferred - function will be created but trigger mechanism TBD
- Character switch UI already exists (character list with green highlight)
- Session disconnect cleanup already exists - just needs history clearing added
- Memory management (100 message limit) is a hard requirement for scalability
