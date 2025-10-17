# Performance Baseline: Character Tools

**Feature**: Optional TOOLS Variable for Character Function Calling
**Date**: 2025-10-17
**Status**: Acceptance Criteria Defined

## Overview

This document defines performance acceptance criteria for the character tools feature to ensure tool execution does not degrade conversation latency beyond acceptable thresholds.

## Baseline Metrics (Without Tools)

**Reference Character**: Narrator (no tools)
**Test Scenario**: Standard conversation flow via WebSocket
**Measurement Points**:
- LLM first token latency (p50, p95, p99)
- End-to-end response generation time
- WebSocket message throughput

## Performance Acceptance Criteria

### Tool Execution Latency

**Individual Tool Execution**:
- **Target**: <100ms per tool call (p95)
- **Maximum**: <250ms per tool call (p99)
- **Measurement**: `CHARACTER_TOOL_LATENCY` histogram

**Rationale**:
- LLM first token budget: <500ms p95
- Allows up to 5 tool calls within budget
- Maintains conversational feel

### Total Conversation Latency Impact

**End-to-End Latency Increase**:
- **Target**: <10% increase over baseline (tool-enabled vs non-tool-enabled character)
- **Measurement**: Compare narrator without tools vs narrator with logging tool
- **Test Method**: Run loadtest with identical prompts, measure p95 latency difference

**Example Calculation**:
```
Baseline (no tools):     p95 = 800ms
With tools (1-2 calls):  p95 = 860ms
Increase:                60ms / 800ms = 7.5% ✓ PASS
```

### Tool Call Frequency

**Expected Frequency**:
- **Typical**: 0-2 tool calls per LLM response
- **Maximum**: 5 tool calls per response (enforced by LLM context)
- **Measurement**: `CHARACTER_TOOL_CALLS` counter rate

**High-Frequency Scenario**:
If character uses >2 tools per response consistently, verify:
- Total latency still <10% increase
- Tool execution times within budget
- User experience remains conversational

## Test Scenarios

### Scenario 1: Baseline Comparison

**Setup**:
1. Load narrator.py without TOOLS variable
2. Run 100 conversations with standard prompts
3. Record p50/p95/p99 latency metrics

**With Tools**:
1. Load narrator.py with `log_story_event` tool
2. Run 100 conversations with identical prompts
3. Compare latency distributions

**Pass Criteria**:
- p95 latency increase <10%
- No timeout errors
- All tool calls complete successfully

### Scenario 2: Tool Execution Timeout

**Setup**:
1. Create test character with intentionally slow tool (>100ms)
2. Trigger tool call via conversation
3. Verify timeout handling

**Expected Behavior**:
- Tool execution times out at 100ms
- Error returned to LLM: "Error: Tool execution timed out"
- LLM continues conversation gracefully
- `CHARACTER_TOOL_ERRORS{error_type="timeout"}` incremented

### Scenario 3: High-Frequency Tool Usage

**Setup**:
1. Create character with multiple tools
2. Design prompts that trigger 3-5 tool calls per response
3. Measure cumulative latency impact

**Pass Criteria**:
- Total tool execution time <400ms (5 tools × ~80ms each)
- End-to-end latency <10% increase over baseline
- No degradation in user experience

## Metrics to Monitor

### Prometheus Metrics

**Tool Execution**:
- `character_tool_calls_total{character_name, tool_name}` - Total invocations
- `character_tool_errors_total{error_type}` - Error breakdown
- `character_tool_latency_seconds{tool_name}` - Execution duration histogram

**Character Loading**:
- `character_load_duration_seconds` - Should not increase significantly with tools

**Query Metrics**:
```promql
# p95 tool execution latency
histogram_quantile(0.95, rate(character_tool_latency_seconds_bucket[5m]))

# Tool error rate
rate(character_tool_errors_total[5m])

# Tool calls per minute
rate(character_tool_calls_total[5m])
```

### Logging

**Debug Logs** (tool execution):
```
[INFO] Tool executed: Narrator.log_story_event({"event": "..."}) -> Logged: ... (45.2ms)
[WARNING] Tool log_story_event took 85.3ms (approaching 100ms timeout)
[ERROR] Tool log_story_event timeout after 100ms
```

## Benchmark Commands

### Run Baseline Test (No Tools)

```bash
# Ensure narrator.py has no TOOLS variable
python -m unmute.loadtest.loadtest_client \
    --character narrator \
    --n-workers 4 \
    --duration 60
```

### Run With-Tools Test

```bash
# Ensure narrator.py has TOOLS defined
python -m unmute.loadtest.loadtest_client \
    --character narrator \
    --n-workers 4 \
    --duration 60
```

### Compare Results

```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics | grep character_tool

# Compare p95 latency
# (Extract from loadtest output or Prometheus queries)
```

## Acceptance Checklist

- [ ] Tool execution p95 <100ms
- [ ] Tool execution p99 <250ms
- [ ] Conversation latency increase <10% with tools vs without
- [ ] Tool timeout errors handled gracefully
- [ ] No crashes or exceptions during tool execution
- [ ] Metrics correctly emitted to Prometheus
- [ ] High-frequency tool usage (3-5 calls) stays within budget

## Performance Anti-Patterns

**Avoid These**:
- Blocking network requests in tools (use async patterns instead)
- Heavy computation (>50ms) in tool execution
- Database queries without connection pooling
- File I/O operations (disk reads/writes)

**Recommended Patterns**:
- Terminal logging (fast, non-blocking)
- Simple calculations (math, string formatting)
- In-memory lookups (dicts, lists)
- Return immediately, defer work to background jobs (future)

## Continuous Monitoring

**Production Alerts**:
- Tool execution p95 >100ms for 5 minutes → Warning
- Tool execution p95 >250ms for 5 minutes → Critical
- Tool error rate >5% → Warning
- Tool timeout rate >10% → Critical

**Dashboard Panels**:
- Tool execution latency histogram
- Tool call rate by character and tool name
- Tool error breakdown by type
- Conversation latency comparison (with/without tools)

## Next Steps

1. Implement character tools (T014-T022)
2. Run baseline tests with narrator (no tools)
3. Add tools to narrator, re-run tests
4. Compare metrics against acceptance criteria
5. Document actual performance in this file
6. Adjust timeout or budgets if needed
