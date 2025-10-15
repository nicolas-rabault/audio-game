# Implementation Plan: Self-Contained Character Management System

**Branch**: `001-i-would-like` | **Date**: 2025-10-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-i-would-like/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create a self-contained character management system that loads character definitions (name, voice, instructions, metadata, prompt generation logic) from individual Python files in a `story_characters/` folder. Each character file must be completely self-contained with no external dependencies for prompt generation. Migrate existing `voices.yaml` entries to the new format. No backward compatibility with `voices.yaml` required.

## Technical Context

**Language/Version**: Python 3.12 (as specified in pyproject.toml: `requires-python = ">=3.12,<3.13"`)
**Primary Dependencies**: FastAPI, Pydantic (for validation), ruamel.yaml (for migration only), Prometheus client (for metrics)
**Storage**: File-based - Python (.py) character files in `story_characters/` folder at repository root
**Testing**: pytest with pytest-asyncio for async tests
**Target Platform**: Linux server (audio-game project is a FastAPI web service)
**Project Type**: Single project - server-side Python application
**Performance Goals**: Load 50+ character files in <5 seconds, 100 characters in <10 seconds
**Constraints**: Must not modify TTS/LLM/STT services (per constitution); character loading must be non-blocking (async); must emit Prometheus metrics (load count, errors, duration)
**Scale/Scope**: Expected to handle 50-100+ character files, each <10KB; gracefully handle 20% file error rate

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**I. Service Isolation**
- [x] Feature does NOT require modifications to TTS, LLM, or STT services
- [x] All service interactions happen via existing interfaces/protocols
- [x] Any service limitations are documented with workarounds (not fixes)

**Justification**: Character management is purely a data layer change. Services receive character data through existing interfaces (voice paths for TTS, system prompts for LLM). No service code modifications needed.

**II. Performance Testing**
- [x] Feature includes loadtest scenarios if it affects audio pipeline or user interaction timing
- [x] Performance acceptance criteria defined with specific latency targets
- [x] Baseline metrics identified for regression comparison

**Justification**: Character loading happens at startup, not in audio pipeline. Performance criteria: 50+ characters in <5s, 100 in <10s (SC-001). No loadtest needed as this doesn't affect runtime audio latency. Will measure file loading performance separately.

**III. Latency Budgets**
- [x] Feature design respects frame-level constraints (24kHz sample rate, 1920 sample frames, 80ms frame time)
- [x] Any new pipeline stages fit within relevant latency budgets
- [x] Feature does not introduce blocking operations in audio path

**Justification**: Character loading occurs at startup only. No runtime impact on audio pipeline. Character data is loaded into memory and accessed synchronously during session initialization (outside audio path).

**IV. Async-First Architecture**
- [x] All I/O operations use async/await patterns
- [x] Inter-task communication uses `asyncio.Queue` (N/A - no inter-task communication)
- [x] Timing measurements use `Stopwatch`/`PhasesStopwatch` from `timer.py` (N/A - startup only)
- [x] No blocking operations in main event loop

**Justification**: Character file loading will use `asyncio.to_thread()` to avoid blocking the event loop during startup. Once loaded, character data is accessed from memory (non-blocking).

**V. Observability & Metrics**
- [x] New user flows include Prometheus metrics instrumentation
- [x] Metrics cover: counters (sessions/errors), histograms (latencies), gauges (active sessions)
- [x] Service integration points emit connection attempt/failure metrics

**Justification**: FR-015 mandates metrics: character load count (counter), load errors by type (counter), load duration (histogram). Will add to metrics.py following existing patterns.

### Post-Design Re-evaluation

**Status**: ✅ **ALL CHECKS PASS**

After completing Phase 0 (research) and Phase 1 (design), the constitution compliance remains valid:

1. **Service Isolation**: Design uses existing `VoiceSample` and `Instructions` models. No changes to TTS/LLM/STT services. Character data flows through existing interfaces.

2. **Performance Testing**: Character loading is startup-only operation. Design includes performance metrics (CHARACTER_LOAD_DURATION histogram) to monitor load time. No impact on runtime audio latency budgets.

3. **Latency Budgets**: No new pipeline stages introduced. Character lookup is O(1) dict access (non-blocking). Prompt generation happens during session initialization (before audio streaming starts).

4. **Async-First Architecture**: Design uses `asyncio.to_thread()` for file I/O during startup. `asyncio.gather()` for concurrent loading. No blocking operations in event loop.

5. **Observability & Metrics**: Design includes 4 new Prometheus metrics (CHARACTER_LOAD_COUNT, CHARACTER_LOAD_ERRORS with labels, CHARACTER_LOAD_DURATION, CHARACTERS_LOADED). Follows existing patterns in `metrics.py`.

**Conclusion**: No constitution violations. Feature is ready for implementation.

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

```
story_characters/                    # NEW: Character definition files
├── watercooler.py                  # Example: Smalltalk character
├── quiz-show.py                    # Example: Quiz show host character
├── gertrude.py                     # Example: Constant instruction character
└── [other-character-files].py      # One file per character

unmute/
├── main_websocket.py               # MODIFY: Update /v1/voices endpoint to use new loader
├── tts/
│   ├── voices.py                   # MODIFY: Keep VoiceSample/VoiceSource models, refactor VoiceList
│   └── character_loader.py         # NEW: Character file discovery and loading
├── llm/
│   └── system_prompt.py            # REFERENCE: Instruction classes used by characters
└── metrics.py                      # MODIFY: Add character loading metrics

tests/
├── test_character_loader.py        # NEW: Unit tests for character loading
└── test_character_validation.py    # NEW: Tests for character file validation

scripts/
└── migrate_voices_yaml.py          # NEW: One-time migration script

voices.yaml                          # DEPRECATED: Will be replaced by story_characters/
```

**Structure Decision**: Single project (Python server application). Character files are Python modules stored in `story_characters/` at repo root. The existing `unmute/tts/voices.py` module will be refactored - keeping Pydantic models (`VoiceSample`, `FreesoundVoiceSource`, `FileVoiceSource`) but replacing `VoiceList` class logic. New `character_loader.py` module will handle file discovery, dynamic import, and validation.

## Complexity Tracking

*No constitution violations - this section is empty.*
