# Implementation Plan: Per-Session Character Management

**Branch**: `002-multiple-simultaneous-users` | **Date**: 2025-10-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-multiple-simultaneous-users/spec.md`

## Summary

Enable multiple simultaneous users to maintain independent character sets without affecting each other. Each WebSocket session will have its own `CharacterManager` instance that loads and manages characters in an isolated namespace. Users can dynamically reload their character set mid-session without disconnecting or impacting other users.

**Technical Approach**: Refactor `CharacterManager` from global module-level singleton to session-scoped instance stored in `UnmuteHandler`. Implement per-session module namespace isolation using Python's `importlib` with unique module prefixes (e.g., `session_{id}.characters.charles`). Add WebSocket event handling for character reload requests.

## Technical Context

**Language/Version**: Python 3.12 (as specified in pyproject.toml: `requires-python = ">=3.12,<3.13"`)
**Primary Dependencies**: Existing - FastAPI (WebSocket), Pydantic (validation), importlib (dynamic loading), asyncio (concurrency)
**Storage**: File-based character definitions in user-specified directories (no database)
**Testing**: pytest for unit tests, manual WebSocket testing for integration
**Target Platform**: Linux server (existing deployment)
**Project Type**: Web application (FastAPI backend + WebSocket protocol)
**Performance Goals**:
- Character reload <2 seconds for 20 characters
- Support 50+ concurrent sessions with unique character sets
- Zero latency impact on other sessions during reload
**Constraints**:
- Memory: Linear growth with character count (~10-50 MB per session with 10-20 characters)
- Must not modify TTS, LLM, or STT services
- Must maintain existing character file format compatibility
**Scale/Scope**:
- 50+ concurrent user sessions
- 10-20 characters per session typical
- Character files unchanged (existing format)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**I. Service Isolation**
- [x] Feature does NOT require modifications to TTS, LLM, or STT services
- [x] All service interactions happen via existing interfaces/protocols
- [x] Any service limitations are documented with workarounds (not fixes)

**Analysis**: This feature is entirely within the character management and session handling layers. TTS receives character voice configuration as before; LLM receives generated prompts as before. No service protocol changes required.

**II. Performance Testing**
- [x] Feature includes loadtest scenarios if it affects audio pipeline or user interaction timing
- [x] Performance acceptance criteria defined with specific latency targets
- [x] Baseline metrics identified for regression comparison

**Analysis**: Character loading happens at session initialization and on-demand reload (not in audio pipeline). Performance tests will measure:
- Character loading time (target: <2s for 20 characters)
- Memory usage per session
- Session initialization latency
- No impact on existing loadtest metrics (STT/TTS/LLM latencies should remain unchanged)

**III. Latency Budgets**
- [x] Feature design respects frame-level constraints (24kHz sample rate, 1920 sample frames, 80ms frame time)
- [x] Any new pipeline stages fit within relevant latency budgets
- [x] Feature does not introduce blocking operations in audio path

**Analysis**: Character loading is async and happens outside the audio pipeline. Module loading uses `asyncio.to_thread()` to avoid blocking the event loop (same pattern as current implementation). No audio path modifications.

**IV. Async-First Architecture**
- [x] All I/O operations use async/await patterns
- [x] Inter-task communication uses `asyncio.Queue`
- [x] Timing measurements use `Stopwatch`/`PhasesStopwatch` from `timer.py`
- [x] No blocking operations in main event loop

**Analysis**: Existing `CharacterManager.load_characters()` is already async. Will reuse this pattern for per-session loading. WebSocket event handling is async. Module loading wrapped in `asyncio.to_thread()`.

**V. Observability & Metrics**
- [x] New user flows include Prometheus metrics instrumentation
- [x] Metrics cover: counters (sessions/errors), histograms (latencies), gauges (active sessions)
- [x] Service integration points emit connection attempt/failure metrics

**Analysis**: Will add new metrics:
- `CHARACTER_LOAD_COUNT_PER_SESSION` (counter with session_id label)
- `CHARACTER_LOAD_DURATION_PER_SESSION` (histogram)
- `SESSION_CHARACTER_COUNT` (gauge)
- Reuse existing `CHARACTER_LOAD_ERRORS` with additional context

**Constitution Check Result**: ✅ PASSED - All gates satisfied, feature aligns with architecture principles

## Project Structure

### Documentation (this feature)

```
specs/002-multiple-simultaneous-users/
├── plan.md              # This file
├── research.md          # Phase 0 output (design decisions)
├── data-model.md        # Phase 1 output (entity relationships)
├── quickstart.md        # Phase 1 output (developer guide)
├── contracts/           # Phase 1 output (WebSocket events)
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```
unmute/
├── tts/
│   ├── character_loader.py          # [MODIFIED] CharacterManager refactored
│   └── voices.py                     # [UNCHANGED] VoiceSample model
├── unmute_handler.py                 # [MODIFIED] Add session CharacterManager
├── main_websocket.py                 # [MODIFIED] Add WebSocket reload event handling
├── openai_realtime_api_events.py    # [MODIFIED] Add new event types
└── metrics.py                        # [MODIFIED] Add per-session metrics

tests/
├── test_character_loader.py          # [NEW] Per-session loading tests
└── test_session_isolation.py         # [NEW] Multi-session isolation tests

characters/                           # [UNCHANGED] Default character directory
```

**Structure Decision**: Single project (web application backend). All changes are within the existing `unmute/` package. No frontend changes required (WebSocket protocol extension handled transparently by existing client code).

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

No violations - Constitution Check passed all gates.
