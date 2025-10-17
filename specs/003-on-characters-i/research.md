# Research Findings: Optional TOOLS Variable for Character Function Calling

**Feature**: 003-on-characters-i
**Date**: 2025-10-17
**Status**: Complete

## Executive Summary

This document consolidates research findings for implementing optional TOOLS variable support in character files with LLM-triggered function calling, while simultaneously removing legacy character format support. All research questions have been resolved with concrete technical decisions backed by existing standards and codebase analysis.

## 1. OpenAI Function Calling Format

### Decision

Use OpenAI's standard function calling schema (`tools` parameter with `function` type objects).

### Rationale

1. **Compatibility**: vLLM explicitly supports OpenAI-compatible function calling API
2. **Documentation**: Well-documented, widely adopted standard with extensive examples
3. **Ecosystem**: Maximizes compatibility with future LLM providers
4. **Tooling**: Existing libraries (AsyncOpenAI) have built-in support

### Technical Specification

**Tool Definition Format** (OpenAI specification):
```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "What the tool does",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description"
                    },
                    "param2": {
                        "type": "number",
                        "enum": [1, 2, 3],
                        "description": "Optional enum parameter"
                    }
                },
                "required": ["param1"]  # Required parameters list
            }
        }
    }
]
```

**API Integration** (AsyncOpenAI client):
```python
response = await client.chat.completions.create(
    model="model-name",
    messages=[...],
    tools=tools_list,  # List of tool definitions
    tool_choice="auto",  # or "none" or {"type": "function", "function": {"name": "tool_name"}}
    stream=True
)
```

**LLM Response with Tool Call**:
```python
# Streamed chunks contain:
{
    "choices": [{
        "delta": {
            "tool_calls": [{
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "arguments": '{"param1": "value"}'  # JSON string
                }
            }]
        }
    }]
}
```

**Tool Result Format** (returned to LLM):
```python
{
    "role": "tool",
    "tool_call_id": "call_abc123",  # Must match LLM's ID
    "content": "Tool execution result as string"
}
```

### References

- OpenAI Function Calling Guide: https://platform.openai.com/docs/guides/function-calling
- vLLM OpenAI Compatibility: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html#function-calling
- AsyncOpenAI Documentation: https://github.com/openai/openai-python

### Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Custom JSON Schema | Full control | No LLM compatibility | Rejected |
| Anthropic Tool Use Format | Claude-optimized | Different from OpenAI, less universal | Rejected |
| Simple String Commands | Minimal complexity | No structured parameters, error-prone parsing | Rejected |

---

## 2. Parameter Validation Strategy

### Decision

Use Pydantic V2 models generated from tool parameter schemas for runtime validation.

### Rationale

1. **Existing Infrastructure**: Pydantic already used throughout codebase (VoiceSample, session configs)
2. **JSON Schema Support**: Pydantic can generate/validate JSON schemas natively
3. **Error Messages**: Automatic clear, detailed validation error messages
4. **Type Safety**: Python type hints provide IDE support and static analysis
5. **Performance**: Pydantic V2 has Rust-based validation (fast enough for real-time use)

### Implementation Approach

**At Character Load Time**:
```python
# In character_loader.py _validate_character_data()

def _validate_tools(tools_list: list[dict]) -> dict[str, Any]:
    """Validate TOOLS variable and create validators."""
    tool_validators = {}

    for tool in tools_list:
        if tool["type"] != "function":
            raise ValueError(f"Unsupported tool type: {tool['type']}")

        func = tool["function"]
        name = func["name"]
        params_schema = func.get("parameters", {})

        # Generate Pydantic model from JSON schema
        model = create_model_from_json_schema(name, params_schema)
        tool_validators[name] = model

    return tool_validators
```

**At Tool Execution Time**:
```python
# In tool_executor.py

async def execute_tool(
    prompt_generator: PromptGenerator,
    tool_name: str,
    tool_input_json: str,
    tool_validators: dict
) -> str:
    """Execute character tool with validation."""
    try:
        # Parse JSON arguments
        tool_input = json.loads(tool_input_json)

        # Validate using Pydantic model
        validator = tool_validators.get(tool_name)
        if validator:
            validated_input = validator(**tool_input)
            tool_input = validated_input.model_dump()

        # Execute tool
        result = await asyncio.to_thread(
            prompt_generator.handle_tool_call,
            tool_name,
            tool_input
        )
        return result

    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON arguments - {e}"
    except ValidationError as e:
        return f"Error: Invalid parameters - {e}"
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return f"Error: Tool execution failed - {type(e).__name__}"
```

### Error Handling Strategy

**Validation Errors → Returned to LLM**:
- JSON parsing errors: "Invalid JSON arguments"
- Parameter type errors: "Expected string, got number for param X"
- Missing required params: "Missing required parameter: param_name"
- Constraint violations: "Value must be one of [options]"

**Execution Errors → Returned to LLM**:
- All exceptions caught and converted to error strings
- Logged for debugging
- LLM can acknowledge error to user gracefully

### Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Manual dict validation | Simple, no dependencies | Verbose code, poor error messages | Rejected |
| JSON Schema + jsonschema lib | Standard approach | Less Pythonic, verbose validation logic | Rejected |
| No validation | Fastest | Crashes on invalid input, poor UX | Rejected |

---

## 3. Legacy Format Removal Scope

### Decision

Remove detection/handling of `INSTRUCTIONS['type']` field in README.md and any conditional logic, but keep embedded format validation as-is.

### Rationale

**Findings from Codebase Analysis**:
1. **Zero Legacy Characters**: All 10 current characters use embedded format
2. **Already Migrated**: Project already completed migration to embedded format
3. **Minimal Code Impact**: Legacy format code consists of:
   - README.md documentation (lines 25-55)
   - Character file examples mentioning 'type' field
   - No actual code processing 'type' field exists

**Files to Modify**:

| File | Change Type | Details |
|------|-------------|---------|
| `characters/README.md` | Major update | Remove legacy format sections, add tools documentation |
| `CLAUDE.md` | Update | Remove legacy format references, add tools examples |
| (No actual Python code changes needed) | N/A | System already doesn't use 'type' field |

**Current README.md Legacy Section** (to be removed):
```markdown
## Legacy Format (Deprecated)

### Type: smalltalk
INSTRUCTIONS = { 'type': 'smalltalk', ... }

### Type: constant
INSTRUCTIONS = { 'type': 'constant', 'instruction_prompt': '...' }

### Type: quiz_show
...
```

**Replacement Section** (to be added):
```markdown
## Embedded Format with Tools (Recommended)

All characters use embedded format with PromptGenerator class.
Optional: Add TOOLS variable for LLM function calling.

See quickstart.md for complete guide.
```

### Migration Path (None Required)

**Status**: Migration already complete
- All 10 characters analyzed use embedded format
- No character files require modification for format migration
- Only documentation updates needed

### Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Keep legacy format support | Backward compatible | Adds complexity, unused code | Rejected per user request |
| Force all characters to new format | Clean break | No characters need migration anyway | Accepted (already done) |

---

## 4. Tool Execution Isolation & Error Handling

### Decision

Wrap all tool executions in try/except, return errors as string results to LLM for graceful user-facing responses.

### Rationale

1. **Conversation Continuity**: Errors shouldn't crash conversations or disconnect users
2. **LLM Context**: Returning errors to LLM allows it to apologize, explain, or retry with different parameters
3. **Debugging**: Errors logged to console/metrics for developer visibility
4. **User Experience**: Better than silent failures or technical stack traces

### Implementation Pattern

**Error Handling Layers**:

```python
# Layer 1: Character Tool Implementation
class PromptGenerator:
    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        # Character code can raise exceptions
        # No try/except required here - handled in executor
        if tool_name == "my_tool":
            result = do_something(tool_input["param"])
            return f"Success: {result}"
        raise ValueError(f"Unknown tool: {tool_name}")

# Layer 2: Tool Executor (catches all errors)
async def execute_tool(...) -> str:
    try:
        # JSON parsing
        tool_input = json.loads(tool_input_json)
    except json.JSONDecodeError as e:
        CHARACTER_TOOL_ERRORS.labels(error_type="json_parse").inc()
        return f"Error: Invalid JSON - {e}"

    try:
        # Parameter validation
        validated = validator(**tool_input)
    except ValidationError as e:
        CHARACTER_TOOL_ERRORS.labels(error_type="validation").inc()
        return f"Error: {e.errors()[0]['msg']}"

    try:
        # Tool execution (with timeout)
        with Stopwatch() as timer:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    prompt_generator.handle_tool_call,
                    tool_name,
                    tool_input
                ),
                timeout=0.1  # 100ms max
            )
        CHARACTER_TOOL_LATENCY.observe(timer.elapsed)
        return result

    except asyncio.TimeoutError:
        CHARACTER_TOOL_ERRORS.labels(error_type="timeout").inc()
        logger.warning(f"Tool {tool_name} exceeded 100ms timeout")
        return "Error: Tool execution timed out"

    except Exception as e:
        CHARACTER_TOOL_ERRORS.labels(error_type="execution").inc()
        logger.error(f"Tool {tool_name} error: {e}", exc_info=True)
        return f"Error: {type(e).__name__}"

# Layer 3: LLM Response Processing (receives error string)
# Adds tool result to messages, LLM generates user-facing response
```

### Error Categories & Metrics

| Error Type | Label | Example | User Impact |
|------------|-------|---------|-------------|
| JSON Parse | `json_parse` | `"Invalid JSON: Expecting property name"` | LLM retries with valid JSON |
| Validation | `validation` | `"Missing required parameter: event"` | LLM provides missing parameter |
| Timeout | `timeout` | `"Tool execution timed out"` | LLM apologizes, suggests retry |
| Execution | `execution` | `"ValueError: Invalid importance level"` | LLM explains constraint |

### Timeout Strategy

**100ms Timeout Justification**:
- Fits within LLM first-token budget (500ms p95)
- Allows ~5 tool calls before approaching budget
- Prevents runaway tool execution
- Fast enough for terminal logging, calculations, simple lookups

**Slow Tools Anti-Pattern**:
- Document that tools >100ms should be async jobs, not synchronous calls
- Provide examples of proper async patterns for future enhancements
- Emit warning logs for tools approaching timeout

### Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Silent failure (return empty) | No user confusion | Hard to debug, LLM confused | Rejected |
| Crash conversation | Fail-fast | Poor UX, user disconnected | Rejected |
| Retry logic | Auto-recovery | Adds latency, may retry bad inputs | Deferred to future |
| Return error to LLM | Graceful UX | Requires LLM to handle errors | **Accepted** |

---

## 5. vLLM Function Calling Compatibility

### Decision

Use OpenAI-compatible function calling format; test with actual vLLM server during implementation.

### Rationale

**vLLM Documentation Findings**:
1. vLLM supports OpenAI-compatible function calling API (v0.4.0+)
2. Compatible models: Llama 3.1, Mistral variants with tool-calling fine-tuning
3. Same `tools` parameter format as OpenAI API
4. Tool calls returned in identical JSON structure

**Potential Differences**:
- Some models may have lower function calling accuracy than GPT-4
- Tool call streaming behavior may vary by model
- Not all models support function calling (depends on fine-tuning)

**Testing Plan**:
1. Verify current LLM server (`autoselect_model()`) supports function calling
2. Test with narrator.py logging tool in development environment
3. Measure tool call accuracy and latency
4. Document any model-specific quirks or limitations

**Fallback Strategy**:
If vLLM function calling has issues:
1. Document model requirements (must be tool-calling fine-tuned)
2. Provide manual testing instructions
3. Consider prompt-based tool invocation as fallback (parse from LLM text output)

### References

- vLLM Function Calling Docs: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html#function-calling
- Supported Models: https://docs.vllm.ai/en/latest/models/supported_models.html

---

## 6. Integration Patterns & Best Practices

### Character File Structure

**Minimal Tool-Enabled Character**:
```python
CHARACTER_NAME = "Tool Example"
VOICE_SOURCE = {...}
INSTRUCTIONS = {'instruction_prompt': '...'}

# Optional TOOLS variable
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "example_tool",
            "description": "Short description for LLM",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                },
                "required": ["input"]
            }
        }
    }
]

class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        # Standard system prompt generation
        ...

    def get_tools(self) -> list[dict] | None:
        """Return TOOLS if defined, None otherwise."""
        return globals().get('TOOLS')

    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Execute tool and return result string."""
        if tool_name == "example_tool":
            result = process(tool_input["input"])
            return f"Processed: {result}"
        raise ValueError(f"Unknown tool: {tool_name}")
```

### Tool Design Best Practices

**DO**:
- Keep tools simple and fast (<100ms)
- Return descriptive success messages
- Use clear parameter names and descriptions
- Validate inputs thoroughly
- Log important tool executions
- Document tool behavior in character docstring

**DON'T**:
- Make blocking network requests (use async patterns instead)
- Access mutable global state (thread-safety concerns)
- Return large data structures (LLM context limits)
- Raise exceptions without message (use descriptive ValueError/TypeError)
- Modify character state (tools should be stateless)

### Example: Narrator Logging Tool

**Purpose**: Demonstrate minimal working tool implementation

```python
# In narrator.py

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "log_story_event",
            "description": "Log an important narrative event to the terminal for the developer to see",
            "parameters": {
                "type": "object",
                "properties": {
                    "event": {
                        "type": "string",
                        "description": "The story event to log (e.g., 'User asked about backstory')"
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Importance level of this event"
                    }
                },
                "required": ["event"]
            }
        }
    }
]

class PromptGenerator:
    # ... existing code ...

    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "log_story_event":
            event = tool_input["event"]
            importance = tool_input.get("importance", "medium")

            # Log to terminal
            print(f"[NARRATOR EVENT] [{importance.upper()}] {event}")

            # Return confirmation to LLM
            return f"Logged story event: {event}"

        raise ValueError(f"Unknown tool: {tool_name}")
```

**Expected Behavior**:
1. LLM detects significant story moment in conversation
2. LLM calls `log_story_event` with event description
3. Tool prints to terminal for developer visibility
4. Tool returns confirmation to LLM
5. LLM continues conversation (may acknowledge logging or stay silent)

---

## 7. Metrics & Observability

### New Prometheus Metrics

**Character Loading Metrics**:
```python
# In character_loader.py
CHARACTER_TOOLS_LOADED = Counter(
    'character_tools_loaded_total',
    'Number of tools loaded per character',
    ['character_name']
)

CHARACTER_TOOL_VALIDATION_ERRORS = Counter(
    'character_tool_validation_errors_total',
    'Tool definition validation errors',
    ['error_type']  # missing_handler, invalid_schema, duplicate_name
)
```

**Runtime Metrics**:
```python
# In tool_executor.py
CHARACTER_TOOL_CALLS = Counter(
    'character_tool_calls_total',
    'Tool invocations by character and tool name',
    ['character_name', 'tool_name']
)

CHARACTER_TOOL_ERRORS = Counter(
    'character_tool_errors_total',
    'Tool execution errors',
    ['error_type']  # json_parse, validation, timeout, execution
)

CHARACTER_TOOL_LATENCY = Histogram(
    'character_tool_latency_seconds',
    'Tool execution duration',
    ['tool_name'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25]  # 1ms to 250ms
)
```

### Logging Strategy

**Character Load Time**:
```python
logger.info(f"Character {name} loaded with {len(tools)} tools: {tool_names}")
logger.error(f"Character {name} tool validation failed: {error}")
```

**Runtime**:
```python
logger.debug(f"Tool call: {character}.{tool_name}({params})")
logger.warning(f"Tool {tool_name} exceeded 100ms: {latency}ms")
logger.error(f"Tool execution error: {tool_name}", exc_info=True)
```

---

## 8. Testing Strategy

### Unit Tests

**Character Loader**:
- Test TOOLS variable detection
- Test tool validation (valid/invalid schemas)
- Test missing handle_tool_call() detection
- Test empty TOOLS handling

**Tool Executor**:
- Test parameter validation (valid/invalid/missing)
- Test error handling (all error types)
- Test timeout enforcement
- Test result formatting

### Integration Tests

**End-to-End Tool Calling**:
1. Load narrator.py with logging tool
2. Start WebSocket session
3. Trigger LLM tool call via conversation
4. Verify tool execution
5. Verify LLM receives result
6. Verify conversation continues

### Performance Tests

**Load test Scenario**:
```bash
# Baseline: narrator without tools
python -m unmute.loadtest.loadtest_client --character narrator --n-workers 4

# With tools: narrator with logging tool
python -m unmute.loadtest.loadtest_client --character narrator --n-workers 4

# Compare latency distributions
```

**Acceptance Criteria**:
- p95 latency increase <10%
- No tool-related crashes
- Tool calls appear in metrics

---

## Summary of Decisions

| Question | Decision | Key Rationale |
|----------|----------|---------------|
| Function calling format | OpenAI standard | vLLM compatibility, ecosystem support |
| Parameter validation | Pydantic V2 models | Existing infrastructure, clear errors |
| Error handling | Return errors to LLM | Graceful UX, debugging visibility |
| Tool execution | Sync with async wrapper | Simple tools, 100ms timeout |
| Legacy format | Remove documentation only | Already unused, zero migration needed |
| Metrics | Tool calls, errors, latency | Observability for production use |

## Next Steps

1. Proceed to Phase 1: Design Artifacts
   - Data model (tool schemas)
   - API contracts (JSON Schema)
   - Developer guide (quickstart.md)

2. Validate decisions with implementation prototype
   - Test vLLM function calling with dev server
   - Verify Pydantic validation performance
   - Confirm AsyncOpenAI compatibility

3. Proceed to Phase 2: Implementation Tasks
   - Generated by /speckit.tasks command
   - Prioritized by user story dependencies
