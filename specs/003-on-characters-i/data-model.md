# Data Model: Optional TOOLS Variable for Character Function Calling

**Feature**: 003-on-characters-i
**Date**: 2025-10-17
**Status**: Design Complete

## Overview

This document defines the data structures, schemas, and validation rules for the TOOLS variable feature. All schemas follow OpenAI function calling standards to ensure LLM compatibility.

## Entity Definitions

### 1. Tool Definition

**Location**: Character file (`TOOLS` variable)
**Purpose**: Describes a callable function that the LLM can invoke
**Format**: OpenAI function calling schema

**Schema**:
```python
{
    "type": "function",  # Required: Always "function"
    "function": {
        "name": str,  # Required: Tool identifier (alphanumeric + underscore)
        "description": str,  # Required: What the tool does (for LLM understanding)
        "parameters": {  # Optional: Tool parameters (JSON Schema object)
            "type": "object",
            "properties": {
                "<param_name>": {
                    "type": str,  # "string", "number", "boolean", "array", "object"
                    "description": str,  # Parameter explanation for LLM
                    "enum": list,  # Optional: Allowed values
                    "items": dict,  # Optional: For array types
                    ...  # Other JSON Schema fields
                }
            },
            "required": list[str]  # Optional: Required parameter names
        }
    }
}
```

**Example**:
```python
{
    "type": "function",
    "function": {
        "name": "log_story_event",
        "description": "Log an important narrative event to the terminal",
        "parameters": {
            "type": "object",
            "properties": {
                "event": {
                    "type": "string",
                    "description": "The story event to log"
                },
                "importance": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Event importance level"
                }
            },
            "required": ["event"]
        }
    }
}
```

**Validation Rules**:
1. `type` must be "function" (only supported type)
2. `function.name` must be:
   - Unique within character's TOOLS list
   - Valid Python identifier (alphanumeric + underscore)
   - Not start with underscore (reserved for internal methods)
3. `function.description` must be:
   - Non-empty string
   - <200 characters (LLM context limits)
   - Clear enough for LLM to understand when to use tool
4. `function.parameters` must be:
   - Valid JSON Schema object type
   - Top-level type must be "object"
   - No recursive schemas (LLM limitations)
   - No `$ref` pointers (inline all definitions)

### 2. Tool Call (LLM Request)

**Location**: LLM streaming response
**Purpose**: LLM's decision to invoke a specific tool
**Format**: OpenAI tool call delta

**Schema**:
```python
{
    "id": str,  # Required: Unique call ID (e.g., "call_abc123")
    "type": "function",  # Required: Always "function"
    "function": {
        "name": str,  # Required: Tool name from definition
        "arguments": str  # Required: JSON string of parameters
    }
}
```

**Example**:
```python
{
    "id": "call_9a7b3c2d",
    "type": "function",
    "function": {
        "name": "log_story_event",
        "arguments": '{"event": "User revealed backstory", "importance": "high"}'
    }
}
```

**Received Via**:
```python
# AsyncOpenAI streaming response
async for chunk in stream:
    if chunk.choices[0].delta.tool_calls:
        tool_call = chunk.choices[0].delta.tool_calls[0]
        # tool_call contains id, type, function.name, function.arguments
```

**Validation Rules** (runtime):
1. `function.name` must match a tool defined in character's TOOLS
2. `function.arguments` must be:
   - Valid JSON string
   - Parseable to dict
   - Conforming to tool's parameter schema (validated via Pydantic)

### 3. Tool Response (Character Execution Result)

**Location**: Returned to LLM after tool execution
**Purpose**: Provide tool execution result for LLM to process
**Format**: OpenAI tool message

**Schema**:
```python
{
    "role": "tool",  # Required: Message role
    "tool_call_id": str,  # Required: Must match LLM's call ID
    "content": str  # Required: Tool result or error message
}
```

**Example (Success)**:
```python
{
    "role": "tool",
    "tool_call_id": "call_9a7b3c2d",
    "content": "Logged story event: User revealed backstory"
}
```

**Example (Error)**:
```python
{
    "role": "tool",
    "tool_call_id": "call_9a7b3c2d",
    "content": "Error: Missing required parameter: event"
}
```

**Content Format Rules**:
1. Success: Descriptive confirmation message
2. Errors: Prefixed with "Error: " + specific problem
3. Length: <1000 characters (LLM context limits)
4. Format: Plain text, human-readable

### 4. Tool Validator (Internal)

**Location**: CharacterManager instance
**Purpose**: Validate tool call parameters at runtime
**Format**: Dict of Pydantic models

**Schema**:
```python
{
    "<tool_name>": Type[BaseModel],  # Pydantic model for parameters
    ...
}
```

**Generated At**: Character load time
**Used For**: Runtime parameter validation before tool execution

**Example**:
```python
# Generated from log_story_event parameters
class LogStoryEventParams(BaseModel):
    event: str  # Required
    importance: Literal["low", "medium", "high"] = "medium"  # Optional with default
```

**Validation Flow**:
```python
validator = tool_validators["log_story_event"]
try:
    validated_params = validator(**tool_input_dict)
    # Pass validated_params.model_dump() to handle_tool_call()
except ValidationError as e:
    # Return error to LLM
    return f"Error: {e.errors()[0]['msg']}"
```

---

## Relationships

```
Character File
    ├── TOOLS (list[ToolDefinition])
    │   └── Used to generate tool_validators at load time
    │
    └── PromptGenerator
        ├── get_tools() → Returns TOOLS list to LLM
        └── handle_tool_call() → Executes tool

LLM (OpenAI API)
    ├── Receives: TOOLS definitions
    ├── Generates: ToolCall (when appropriate)
    └── Receives: ToolResponse (after execution)

Tool Execution Flow:
    1. LLM sends ToolCall
    2. System validates using tool_validators
    3. System calls handle_tool_call()
    4. System formats result as ToolResponse
    5. System adds ToolResponse to messages
    6. LLM generates follow-up text
```

---

## State Transitions

### Character Loading States

```
UNLOADED
    ↓ (character_loader.py discovers file)
LOADING
    ↓ (import module, extract TOOLS)
VALIDATING_TOOLS
    ├→ (TOOLS missing or empty) → LOADED_NO_TOOLS ✓
    ├→ (TOOLS invalid schema) → FAILED_VALIDATION ✗
    ├→ (missing handle_tool_call) → FAILED_VALIDATION ✗
    └→ (validation passes) → LOADED_WITH_TOOLS ✓
```

### Tool Call Lifecycle

```
IDLE (LLM generating text)
    ↓ (LLM decides to use tool)
TOOL_CALL_INITIATED
    ↓ (parse arguments JSON)
VALIDATING_PARAMETERS
    ├→ (invalid JSON) → EXECUTION_FAILED (return error to LLM)
    ├→ (validation fails) → EXECUTION_FAILED (return error to LLM)
    └→ (validation passes)
EXECUTING_TOOL
    ├→ (execution error) → EXECUTION_FAILED (return error to LLM)
    ├→ (timeout) → EXECUTION_FAILED (return error to LLM)
    └→ (success) → TOOL_COMPLETED (return result to LLM)
AWAITING_LLM_RESPONSE
    ↓ (LLM processes tool result)
IDLE (LLM continues conversation)
```

---

## Validation Rules Summary

### Character Load Time

| Field | Rule | Error Type |
|-------|------|------------|
| TOOLS | Must be list or None | `TypeError` |
| TOOLS items | Must be dict with 'type' and 'function' | `ValueError` |
| function.name | Must be unique, valid identifier | `DuplicateName`, `InvalidName` |
| function.description | Must be non-empty string <200 chars | `ValueError` |
| function.parameters | Must be valid JSON Schema object | `ValidationError` |
| handle_tool_call | Must exist if TOOLS defined | `MissingMethod` |

### Runtime (Tool Execution)

| Field | Rule | Error Response |
|-------|------|----------------|
| function.name | Must match defined tool | "Error: Unknown tool: {name}" |
| function.arguments | Must be valid JSON | "Error: Invalid JSON arguments - {error}" |
| Parameters | Must pass Pydantic validation | "Error: Invalid parameters - {msg}" |
| Execution time | Must complete <100ms | "Error: Tool execution timed out" |
| Return value | Must be string | "Error: Tool must return string" |

---

## Data Constraints

### Size Limits

| Entity | Field | Limit | Reason |
|--------|-------|-------|--------|
| ToolDefinition | name | 50 chars | Function name length |
| ToolDefinition | description | 200 chars | LLM context efficiency |
| ToolDefinition | parameters | 10 properties max | LLM comprehension limit |
| ToolCall | arguments JSON | 2KB | Reasonable parameter size |
| ToolResponse | content | 1KB | LLM context limits |
| Character | TOOLS list | 10 tools max | Avoid overwhelming LLM |

### Type Constraints

| Field | Allowed Types | Notes |
|-------|---------------|-------|
| function.name | str (alphanumeric + _) | Valid Python identifier |
| function.description | str | Non-empty |
| parameters.properties | JSON Schema types | string, number, boolean, array, object |
| parameters.enum | list | Max 10 values for clarity |
| ToolResponse.content | str | Plain text, no binary data |

---

## Example: Complete Tool Definition Lifecycle

### 1. Character File Definition

```python
# In narrator.py
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "log_story_event",
            "description": "Log an important narrative event to the terminal",
            "parameters": {
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "The event"},
                    "importance": {"type": "string", "enum": ["low", "medium", "high"]}
                },
                "required": ["event"]
            }
        }
    }
]

class PromptGenerator:
    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "log_story_event":
            print(f"[EVENT] {tool_input['event']}")
            return f"Logged: {tool_input['event']}"
        raise ValueError(f"Unknown tool: {tool_name}")
```

### 2. Character Load Time

```python
# CharacterManager loads character
result = await character_manager.load_characters("characters/")

# Validation creates Pydantic model:
class LogStoryEventParams(BaseModel):
    event: str
    importance: Literal["low", "medium", "high"] = "medium"

tool_validators["log_story_event"] = LogStoryEventParams
```

### 3. LLM API Call

```python
# VLLMStream includes tools in request
response = await client.chat.completions.create(
    messages=[...],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "log_story_event",
                "description": "Log an important narrative event to the terminal",
                "parameters": {...}
            }
        }
    ]
)
```

### 4. LLM Generates Tool Call

```python
# Streamed response contains:
{
    "id": "call_xyz",
    "type": "function",
    "function": {
        "name": "log_story_event",
        "arguments": '{"event": "Plot twist revealed", "importance": "high"}'
    }
}
```

### 5. Tool Execution

```python
# System validates and executes
params = json.loads('{"event": "Plot twist revealed", "importance": "high"}')
validated = LogStoryEventParams(**params)  # Pydantic validation
result = await asyncio.to_thread(
    prompt_generator.handle_tool_call,
    "log_story_event",
    validated.model_dump()
)
# result = "Logged: Plot twist revealed"
```

### 6. Response to LLM

```python
# Add tool result to messages
messages.append({
    "role": "tool",
    "tool_call_id": "call_xyz",
    "content": "Logged: Plot twist revealed"
})

# LLM generates follow-up based on tool result
# (may acknowledge logging or continue story naturally)
```

---

## Pydantic Models (Implementation Reference)

### Character Loading

```python
# In character_loader.py

from pydantic import BaseModel, Field, create_model, field_validator
from typing import Any, Literal

class ToolFunctionDefinition(BaseModel):
    """OpenAI function definition."""
    name: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$', max_length=50)
    description: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] | None = None

    @field_validator('parameters')
    def validate_parameters_schema(cls, v):
        if v is not None:
            if v.get('type') != 'object':
                raise ValueError("Top-level parameters type must be 'object'")
            if 'properties' in v and len(v['properties']) > 10:
                raise ValueError("Maximum 10 parameters per tool")
        return v

class ToolDefinition(BaseModel):
    """OpenAI tool definition."""
    type: Literal["function"] = "function"
    function: ToolFunctionDefinition

class CharacterTools(BaseModel):
    """Character's TOOLS list with validation."""
    tools: list[ToolDefinition] = Field(max_length=10)

    @field_validator('tools')
    def validate_unique_names(cls, tools):
        names = [t.function.name for t in tools]
        if len(names) != len(set(names)):
            duplicates = {n for n in names if names.count(n) > 1}
            raise ValueError(f"Duplicate tool names: {duplicates}")
        return tools
```

### Runtime Validation

```python
# Dynamically generated from tool parameters
def create_parameter_model(tool_name: str, parameters: dict) -> Type[BaseModel]:
    """Generate Pydantic model from JSON Schema parameters."""
    if not parameters or parameters.get('type') != 'object':
        return BaseModel  # No validation needed

    fields = {}
    properties = parameters.get('properties', {})
    required = parameters.get('required', [])

    for prop_name, prop_schema in properties.items():
        field_type = json_schema_type_to_python(prop_schema)
        default = ... if prop_name in required else None
        fields[prop_name] = (field_type, default)

    return create_model(f"{tool_name}_Params", **fields)
```

---

## Summary

**Key Entities**:
1. **ToolDefinition**: Character file TOOLS variable (OpenAI schema)
2. **ToolCall**: LLM's request to invoke tool
3. **ToolResponse**: Character's execution result
4. **ToolValidator**: Pydantic model for runtime validation

**Validation Layers**:
1. **Load Time**: Schema structure, name uniqueness, method existence
2. **Runtime**: Parameter validation, timeout enforcement, error handling

**Data Flow**:
Character File → CharacterManager → LLM API → ToolCall → ToolExecutor → ToolResponse → LLM

All schemas follow OpenAI function calling standards for maximum compatibility.
