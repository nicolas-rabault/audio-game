<!--
SYNC IMPACT REPORT
Version: 0.0.0 → 1.0.0 (Initial constitution creation)
Modified Principles: N/A (new constitution)
Added Sections:
  - All core principles (Service Isolation, Performance Testing, Latency Budgets, Async-First, Observability)
  - Performance Standards
  - Development Workflow
Templates Requiring Updates:
  ✅ plan-template.md (constitution check section exists)
  ✅ spec-template.md (user scenarios align with testing principle)
  ⚠ tasks-template.md (may need performance task categories)
Follow-up TODOs: None
-->

# Audio Game Project Constitution

## Core Principles

### I. Service Isolation (NON-NEGOTIABLE)

The TTS (Text-to-Speech), LLM (Large Language Model), and STT (Speech-to-Text) services are **production-stable external dependencies** and MUST NOT be modified, replaced, or reimplemented as part of feature development.

**Rules**:
- All three services (TTS, LLM, STT) are treated as black-box external APIs
- Changes to integration code (handlers, queue management, protocol adapters) are permitted
- Service configuration (URLs, models, parameters) may be adjusted via environment variables
- New features MUST work with existing service interfaces without requiring service modifications
- If a service limitation is discovered, document it and design around it—do not attempt to fix the service

**Rationale**: These services represent mature, performance-optimized components. Maintaining their stability ensures predictable latency characteristics and reduces system complexity. Integration work happens at boundaries, not within services.

### II. Performance Testing (NON-NEGOTIABLE)

Every feature that affects the audio pipeline, user interaction timing, or service integration MUST include performance benchmarking using the loadtest framework before being considered complete.

**Rules**:
- Performance tests MUST measure latency distributions (mean, median, p90, p95) for affected components
- Loadtest MUST use realistic audio samples and multi-worker scenarios (minimum 4 workers for integration tests)
- Test results MUST include:
  - STT latency (time from audio_start to text_start)
  - VAD latency (time from audio_end to response_created)
  - LLM latency (time from response_created to text_start)
  - TTS start latency (time from text_start to audio_start)
  - TTS realtime factor (received_audio_length / generation_time)
- Performance regressions >10% from baseline require explicit justification and approval
- All performance tests run with `--n-workers` ≥ 4 to simulate concurrent load

**Rationale**: This project is latency-sensitive by nature. The loadtest framework (`unmute/loadtest/loadtest_client.py`) provides comprehensive timing measurement across all pipeline stages. Real-time audio interaction requires sub-second response times, making performance testing non-negotiable.

### III. Latency Budgets

All components MUST operate within defined latency budgets derived from production metrics bins. Violations of these budgets require architectural review.

**Target Latencies** (p95, based on metrics.py bins):
- **STT First Token**: <100ms (TTFT_BINS_STT_MS)
- **TTS First Token**: <550ms (TTFT_BINS_TTS_MS)
- **LLM First Token**: <500ms (TTFT_BINS_VLLM_MS)
- **User Turn Duration**: <60s (TURN_DURATION_BINS)
- **TTS Realtime Factor**: >1.0 (audio generation must be faster than playback)

**Frame-Level Constraints**:
- Sample rate: 24000 Hz (SAMPLE_RATE constant)
- Frame size: 1920 samples (SAMPLES_PER_FRAME constant)
- Frame time: 80ms (FRAME_TIME_SEC constant)
- STT delay budget: 500ms (STT_DELAY_SEC constant)

**Rationale**: These budgets emerge from production Prometheus metrics and represent user-perceptible quality thresholds. The frame-level constraints in `kyutai_constants.py` define physical timing limits of the audio pipeline.

### IV. Async-First Architecture

All I/O-bound operations and service interactions MUST use async/await patterns. Blocking operations are prohibited in the main event loop.

**Rules**:
- Use `asyncio.Queue` for inter-task communication (see `output_queue` in `UnmuteHandler`)
- Use `asyncio.create_task()` for concurrent operations (see emit/receive loops in loadtest)
- Use `Stopwatch` and `PhasesStopwatch` from `timer.py` for timing measurements within async contexts
- Long-running blocking operations MUST be offloaded to thread/process pools (see multiprocessing in loadtest)
- WebSocket connections use async context managers (`async with websockets.connect()`)

**Rationale**: Real-time audio streaming requires non-blocking concurrency. The system handles multiple simultaneous audio streams, WebSocket connections, and service calls. Async architecture is essential for meeting latency budgets and maintaining throughput under concurrent load.

### V. Observability & Metrics

All production code paths MUST emit Prometheus metrics for monitoring. Changes affecting user flows require corresponding metric updates.

**Required Metrics Categories** (from `metrics.py`):
- **Counters**: Sessions, errors, interrupts, frames sent/received
- **Histograms**: Latencies (TTFT), durations (session, turn, generation), request/response sizes
- **Gauges**: Active sessions per service (STT, TTS, LLM)

**Mandatory Instrumentation Points**:
- Service connection attempts and failures (e.g., `STT_MISSES`, `TTS_HARD_MISSES`)
- Time-to-first-token for all streaming services (e.g., `STT_TTFT`, `TTS_TTFT`, `VLLM_TTFT`)
- Session lifecycle events (start, end, duration)
- Audio processing metrics (frames sent/received, audio duration)

**Rationale**: Production observability is not optional. The metrics bins defined in `metrics.py` represent operational knowledge about system behavior. Instrumentation must happen at development time, not as an afterthought.

## Performance Standards

### Latency Measurement Protocol

All latency measurements MUST use the standardized timing framework:

1. **User Message Timing** (`UserMessageTiming`):
   - `audio_start`: When user audio begins
   - `text_start`: When STT emits first transcription token
   - `audio_end`: When user audio ends

2. **Assistant Message Timing** (`AssistantMessageTiming`):
   - `response_created`: When LLM response generation starts
   - `text_start`: When LLM emits first text token
   - `audio_start`: When TTS emits first audio chunk
   - `audio_end`: When TTS completes audio generation
   - `received_audio_length`: Total audio duration (for realtime factor calculation)

### Testing Discipline

**Unit Tests** (pytest):
- Pure functions MUST have unit tests with clear input/output examples
- See `tests/test_llm_utils.py` for async iterator testing patterns
- See `tests/test_exponential_moving_average.py` for numerical algorithm testing patterns
- Use `pytest.approx()` for floating-point comparisons

**Integration Tests** (loadtest framework):
- End-to-end pipeline tests MUST use `loadtest_client.py`
- Test with diverse audio samples from `loadtest/voices/` directory
- Multi-worker tests (`--n-workers`) are mandatory for concurrency validation
- Results MUST be analyzed for distribution statistics (not just mean values)

## Development Workflow

### Feature Development Lifecycle

1. **Specification**: Define user scenarios with performance acceptance criteria
2. **Design**: Identify affected services and integration boundaries
3. **Constitution Check**: Verify compliance with service isolation and latency budgets
4. **Implementation**: Develop with async patterns and metrics instrumentation
5. **Performance Validation**: Run loadtest with baseline comparison
6. **Review**: Verify metrics coverage and latency budget compliance

### Code Quality Gates

- All async functions MUST handle `CloseStream` signals for graceful shutdown
- All service clients MUST implement exponential backoff for retries (see `ExponentialMovingAverage`)
- All WebSocket handlers MUST implement ping/health check mechanisms
- All audio processing MUST respect frame boundaries (SAMPLES_PER_FRAME)

### Documentation Requirements

- Performance-critical code MUST include inline comments explaining timing constraints
- Service integration points MUST document expected latency characteristics
- Configuration changes MUST update corresponding environment variable documentation

## Governance

**Amendment Procedure**:
1. Proposed changes to principles require concrete evidence from production metrics or incident analysis
2. New principles require demonstration of cross-cutting impact on ≥3 features
3. All amendments MUST update dependent templates in `.specify/templates/`

**Versioning Policy**:
- **MAJOR**: Service isolation rules change, latency budgets redefined, architectural paradigm shift
- **MINOR**: New principle added, existing principle materially expanded
- **PATCH**: Clarifications, examples added, wording improvements

**Compliance Review**:
- All pull requests MUST reference constitution compliance in description
- Performance regression alerts trigger automatic constitution review
- Quarterly metrics review validates latency budgets remain achievable

**Version**: 1.0.0 | **Ratified**: 2025-10-15 | **Last Amended**: 2025-10-15
