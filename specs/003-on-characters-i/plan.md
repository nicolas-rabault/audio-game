# Implementation Plan: Optional TOOLS Variable for Character Function Calling

**Branch**: `003-on-characters-i` | **Date**: 2025-10-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/home/metab/audio-game/specs/003-on-characters-i/spec.md`

## Summary

This feature adds optional TOOLS variable support to character files, enabling LLM-triggered function calling for extended character capabilities. Simultaneously, this feature removes all legacy character format support code, simplifying the system to support only the embedded format going forward. The implementation provides a self-contained tool definition and execution framework within individual character files, with proper validation, error handling, and parameter checking.

## Technical Context

**Language/Version**: Python 3.12 (as specified in pyproject.toml: `requires-python = ">=3.12,<3.13"`)
**Primary Dependencies**: FastAPI (WebSocket), Pydantic (validation), AsyncOpenAI (LLM client), importlib (dynamic loading), asyncio (concurrency)
**Storage**: File-based character definitions in `characters/` directory (no database)
**Testing**: pytest (unit tests), existing loadtest framework (integration tests)
**Target Platform**: Linux server (WebSocket API)
**Project Type**: Single (audio-game server application)
**Performance Goals**: No impact on existing latency budgets (tools execute synchronously within conversation flow)
**Constraints**:
- Tools must execute quickly (<100ms) to avoid conversation latency
- Error handling must prevent conversation crashes
- Character loading must fail fast on invalid tool configurations
**Scale/Scope**:
- ~10 existing character files (all embedded format)
- Expected: 1-5 tools per character maximum
- Small-scale feature (impacts character loading and LLM integration layers only)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**I. Service Isolation**
- [x] Feature does NOT require modifications to TTS, LLM, or STT services
- [x] All service interactions happen via existing interfaces/protocols (OpenAI-compatible API)
- [x] Any service limitations are documented with workarounds (not fixes)

**Compliance Notes**:
- TTS/STT services completely untouched
- LLM integration uses existing AsyncOpenAI client, only adds `tools` parameter to existing API calls
- Function calling is a standard OpenAI API feature, no service modification required

**II. Performance Testing**
- [x] Feature includes loadtest scenarios if it affects audio pipeline or user interaction timing
- [x] Performance acceptance criteria defined with specific latency targets
- [x] Baseline metrics identified for regression comparison

**Compliance Notes**:
- Tools execute synchronously within LLM response generation flow
- Performance test: measure end-to-end conversation latency with tool-enabled character vs. baseline
- Target: tool execution <100ms, total conversation latency increase <10%
- Baseline: existing narrator.py without tools → narrator.py with logging tool

**III. Latency Budgets**
- [x] Feature design respects frame-level constraints (24kHz sample rate, 1920 sample frames, 80ms frame time)
- [x] Any new pipeline stages fit within relevant latency budgets (LLM first token: <500ms p95)
- [x] Feature does not introduce blocking operations in audio path

**Compliance Notes**:
- Tool execution happens during LLM response generation (already async)
- Tools return synchronously but within LLM's existing 500ms first-token budget
- No audio pipeline changes (TTS/STT flows unchanged)
- Character loading happens at startup (one-time cost, not in hot path)

**IV. Async-First Architecture**
- [x] All I/O operations use async/await patterns
- [x] Inter-task communication uses `asyncio.Queue` (existing patterns)
- [x] Timing measurements use `Stopwatch`/`PhasesStopwatch` from `timer.py`
- [x] No blocking operations in main event loop

**Compliance Notes**:
- Tool execution will use `asyncio.to_thread()` for potentially blocking character tool functions
- LLM response processing already async via AsyncOpenAI client
- Character loading already uses `asyncio.to_thread()` and `asyncio.gather()`
- Tool result handling integrates into existing async message loop

**V. Observability & Metrics**
- [x] New user flows include Prometheus metrics instrumentation
- [x] Metrics cover: counters (sessions/errors), histograms (latencies), gauges (active sessions)
- [x] Service integration points emit connection attempt/failure metrics

**Compliance Notes**:
- Add metrics: `CHARACTER_TOOL_CALLS` (counter), `CHARACTER_TOOL_ERRORS` (counter), `CHARACTER_TOOL_LATENCY` (histogram)
- Track tool validation failures during character loading
- Emit metrics for tool parameter validation errors at runtime
- Log all tool executions for debugging

## Project Structure

### Documentation (this feature)

```
specs/003-on-characters-i/
├── plan.md              # This file
├── spec.md              # Feature specification (created by /speckit.specify)
├── research.md          # Phase 0 output (research findings)
├── data-model.md        # Phase 1 output (tool definition schema)
├── quickstart.md        # Phase 1 output (developer guide)
├── contracts/           # Phase 1 output (tool definition JSON schemas)
│   └── tool-schema.json
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```
unmute/
├── llm/
│   ├── chatbot.py           # Add: tools field, get_tools() integration
│   ├── llm_utils.py         # Add: tools parameter to OpenAI API calls
│   ├── system_prompt.py     # Keep: shared constants (no changes needed)
│   └── tool_executor.py     # NEW: Tool validation and execution logic
├── tts/
│   ├── character_loader.py  # Modify: Add TOOLS validation, remove legacy format code
│   └── voices.py            # Keep: VoiceSample model (no changes needed)
└── unmute_handler.py        # Modify: Handle tool call responses from LLM

characters/
├── narrator.py              # Modify: Add TOOLS variable + tool implementation
├── README.md                # Update: Remove legacy format docs, add tools guide
└── (other characters)       # Unchanged initially

tests/
├── test_character_loader.py # Modify: Test tool validation
├── test_tool_executor.py    # NEW: Test tool execution and error handling
└── integration/
    └── test_tools_e2e.py    # NEW: End-to-end tool calling test
```

**Structure Decision**: Single project structure maintained. This is a feature enhancement to existing character system, not a new service or subsystem. All changes localized to character loading (`unmute/tts/character_loader.py`), LLM integration (`unmute/llm/`), and character files (`characters/`).

## Complexity Tracking

*No constitution violations requiring justification.*

All gates pass cleanly:
- Service isolation maintained (no TTS/STT/LLM service modifications)
- Performance testing planned with clear latency targets
- Latency budgets respected (tools execute within LLM response flow)
- Async architecture preserved (tool execution via asyncio.to_thread)
- Observability enhanced with new metrics

## Phase 0: Research & Technical Decisions

### Research Questions

1. **OpenAI Function Calling Format**: What is the exact JSON schema for the `tools` parameter in OpenAI API?
   - **Decision**: Use OpenAI's standard function calling schema (tools array with function objects)
   - **Rationale**: Maximizes LLM compatibility, well-documented, widely adopted
   - **Reference**: https://platform.openai.com/docs/guides/function-calling

2. **Tool Response Handling**: How should tool results be formatted and returned to the LLM?
   - **Decision**: Use standard OpenAI tool message format: `{"role": "tool", "tool_call_id": "...", "content": "result"}`
   - **Rationale**: Follows OpenAI API conventions, ensures LLM can process results correctly
   - **Alternative Considered**: Custom formatting → rejected due to LLM compatibility concerns

3. **Parameter Validation Strategy**: How to validate tool parameters at runtime?
   - **Decision**: Use Pydantic models generated from tool parameter schemas
   - **Rationale**: Leverages existing validation framework, provides clear error messages
   - **Alternative Considered**: Manual dict validation → rejected due to code complexity and error-prone nature

4. **Legacy Format Removal Scope**: What code specifically needs to be removed?
   - **Decision**: Remove detection/handling of `INSTRUCTIONS['type']` field, update README.md
   - **Rationale**: All 10 existing characters already use embedded format, no migration needed
   - **Finding**: Legacy format code is already unused (0/10 characters use it)

5. **Tool Execution Isolation**: How to prevent tool errors from crashing conversations?
   - **Decision**: Wrap all tool executions in try/except, return errors as tool results to LLM
   - **Rationale**: Allows LLM to generate user-friendly error responses, maintains conversation flow
   - **Alternative Considered**: Silent failure → rejected due to poor UX and debugging difficulty

### Technology Choices

**Function Calling Protocol**: OpenAI-compatible function calling
- **Why**: AsyncOpenAI client already used, vLLM supports OpenAI-compatible function calling
- **How**: Add `tools` parameter to `chat.completions.create()` call
- **Reference**: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html#function-calling

**Parameter Validation**: Pydantic V2
- **Why**: Already used for VoiceSample, provides JSON schema generation
- **How**: Generate Pydantic models from tool parameter definitions at character load time
- **Alternative**: JSON Schema validation → rejected due to less Pythonic, more verbose

**Tool Execution**: Synchronous with async wrapper
- **Why**: Most tools will be simple (logging, calculations), async would add complexity
- **How**: Use `asyncio.to_thread()` to run synchronous tool functions without blocking event loop
- **Constraint**: Tools must complete quickly (<100ms target)

### Integration Patterns

**Character File Pattern** (narrator.py example):
```python
# Optional TOOLS variable
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "log_story_event",
            "description": "Log an important story event to the terminal",
            "parameters": {
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "The event to log"},
                    "importance": {"type": "string", "enum": ["low", "medium", "high"]}
                },
                "required": ["event"]
            }
        }
    }
]

class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        # ... existing code ...

    def get_tools(self) -> list[dict] | None:
        """Return tool definitions for OpenAI API."""
        return TOOLS if 'TOOLS' in globals() else None

    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Execute tool and return result."""
        if tool_name == "log_story_event":
            print(f"[STORY EVENT] {tool_input['event']} (importance: {tool_input.get('importance', 'medium')})")
            return f"Logged event: {tool_input['event']}"
        return f"Unknown tool: {tool_name}"
```

**LLM Integration Pattern**:
```python
# In VLLMStream.chat_completion()
tools = self.tools if self.tools else None
stream = await self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    tools=tools,  # Add tools parameter
    stream=True,
    temperature=self.temperature,
)

# In response processing
if chunk.choices[0].delta.tool_calls:
    # Handle tool call
    tool_call = chunk.choices[0].delta.tool_calls[0]
    result = await execute_tool(tool_call)
    # Add tool result to messages and re-query LLM
```

## Phase 1: Design Artifacts

### Data Model

See [data-model.md](data-model.md) for complete schema definitions:
- Tool Definition Schema (OpenAI-compatible)
- Tool Call Schema (LLM request format)
- Tool Response Schema (character execution result)
- Validation Rules

### API Contracts

See [contracts/tool-schema.json](contracts/tool-schema.json) for JSON Schema definitions:
- Tool definition structure
- Parameter validation schemas
- Error response formats

### Developer Guide

See [quickstart.md](quickstart.md) for:
- Adding tools to existing characters
- Creating new tool-enabled characters
- Tool implementation best practices
- Testing and debugging tools
- Migration guide (legacy format removal)

## Implementation Phases

### Phase 0: Research ✓
- [x] OpenAI function calling format research
- [x] Parameter validation strategy
- [x] Legacy format removal scope
- [x] Tool execution isolation approach
- [x] Integration pattern design

### Phase 1: Design ✓
- [x] Data model design (tool schemas)
- [x] API contract definition
- [x] Developer guide creation
- [x] Architecture review

### Phase 2: Implementation (via /speckit.tasks)
1. Remove legacy format support code
2. Add TOOLS variable validation to character loading
3. Implement tool executor module
4. Integrate tools into LLM API calls
5. Add tool response handling
6. Update narrator.py with example tool
7. Add tests and metrics
8. Update documentation

## Risks & Mitigations

**Risk**: vLLM function calling support may differ from OpenAI
- **Mitigation**: Test with actual vLLM server during Phase 2, adapt schema if needed
- **Fallback**: Document limitations, provide workaround patterns

**Risk**: Tool execution latency could impact conversation flow
- **Mitigation**: Enforce <100ms execution time, measure with performance tests
- **Fallback**: Document slow tools as anti-pattern, recommend async alternatives

**Risk**: Character developers may create tools with side effects
- **Mitigation**: Document best practices, log all tool executions
- **Monitoring**: Prometheus metrics for tool errors and latency

## Next Steps

1. Generate Phase 0 research.md (detailed findings)
2. Generate Phase 1 data-model.md (schemas)
3. Generate Phase 1 contracts/tool-schema.json (JSON Schema)
4. Generate Phase 1 quickstart.md (developer guide)
5. Update agent context with new technologies
6. Proceed to `/speckit.tasks` for implementation breakdown
