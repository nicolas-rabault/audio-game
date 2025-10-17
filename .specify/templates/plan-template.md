# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [single/web/mobile - determines source structure]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

**I. Service Isolation**

- [ ] Feature does NOT require modifications to TTS, LLM, or STT services
- [ ] All service interactions happen via existing interfaces/protocols
- [ ] Any service limitations are documented with workarounds (not fixes)

**II. Performance Testing**

- [ ] Feature includes loadtest scenarios if it affects audio pipeline or user interaction timing
- [ ] Performance acceptance criteria defined with specific latency targets
- [ ] Baseline metrics identified for regression comparison

**III. Latency Budgets**

- [ ] Feature design respects frame-level constraints (24kHz sample rate, 1920 sample frames, 80ms frame time)
- [ ] Any new pipeline stages fit within relevant latency budgets:
  - STT first token: <100ms (p95)
  - TTS first token: <550ms (p95)
  - LLM first token: <500ms (p95)
- [ ] Feature does not introduce blocking operations in audio path

**IV. Async-First Architecture**

- [ ] All I/O operations use async/await patterns
- [ ] Inter-task communication uses `asyncio.Queue`
- [ ] Timing measurements use `Stopwatch`/`PhasesStopwatch` from `timer.py`
- [ ] No blocking operations in main event loop

**V. Observability & Metrics**

- [ ] New user flows include Prometheus metrics instrumentation
- [ ] Metrics cover: counters (sessions/errors), histograms (latencies), gauges (active sessions)
- [ ] Service integration points emit connection attempt/failure metrics

**VI. Clean Break Evolution**

- [ ] If modifying existing functionality, plan includes complete removal of old implementation
- [ ] No backward compatibility layers, feature flags, or compatibility shims introduced
- [ ] Documentation updates remove all references to deprecated/legacy approaches
- [ ] Data migration strategy is one-way with migration code removal planned
- [ ] Configuration cleanup removes unused legacy parameters

## Project Structure

### Documentation (this feature)

```
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

_Fill ONLY if Constitution Check has violations that must be justified_

| Violation                  | Why Needed         | Simpler Alternative Rejected Because |
| -------------------------- | ------------------ | ------------------------------------ |
| [e.g., 4th project]        | [current need]     | [why 3 projects insufficient]        |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient]  |
