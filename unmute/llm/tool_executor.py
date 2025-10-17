"""
Tool execution module for character function calling.

This module handles:
- Tool parameter validation using Pydantic models
- Tool execution with timeout enforcement
- Error handling and result formatting
- Prometheus metrics for tool usage
"""

import asyncio
import json
import logging
from typing import Any, Type

from prometheus_client import Counter, Histogram
from pydantic import BaseModel, ValidationError, create_model

from unmute.timer import Stopwatch

logger = logging.getLogger(__name__)


# ========================================
# Prometheus Metrics
# ========================================

CHARACTER_TOOL_CALLS = Counter(
    "character_tool_calls_total",
    "Total number of tool invocations by character and tool name",
    ["character_name", "tool_name"],
)

CHARACTER_TOOL_ERRORS = Counter(
    "character_tool_errors_total",
    "Total number of tool execution errors by error type",
    ["error_type"],
)

CHARACTER_TOOL_LATENCY = Histogram(
    "character_tool_latency_seconds",
    "Tool execution duration in seconds",
    ["tool_name"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25],  # 1ms to 250ms
)


# ========================================
# JSON Schema to Pydantic Conversion
# ========================================


def _json_schema_type_to_python(prop_schema: dict[str, Any]) -> Type:
    """
    Convert JSON Schema type to Python type annotation.

    Args:
        prop_schema: JSON Schema property definition

    Returns:
        Python type for Pydantic field
    """
    json_type = prop_schema.get("type", "string")

    # Handle enum constraints (use Literal if possible, else constrained string)
    if "enum" in prop_schema:
        # For simplicity, just validate enum as string and check in validator
        return str

    type_mapping = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    return type_mapping.get(json_type, str)


def create_parameter_model(tool_name: str, parameters: dict[str, Any] | None) -> Type[BaseModel]:
    """
    Generate Pydantic model from JSON Schema parameters.

    This converts OpenAI function calling parameter schemas into Pydantic
    models for runtime validation.

    Args:
        tool_name: Name of the tool (used for model class name)
        parameters: JSON Schema parameters object (type: "object")

    Returns:
        Pydantic model class for validating tool parameters

    Example:
        >>> params = {
        ...     "type": "object",
        ...     "properties": {
        ...         "event": {"type": "string"},
        ...         "importance": {"type": "string", "enum": ["low", "medium", "high"]}
        ...     },
        ...     "required": ["event"]
        ... }
        >>> Model = create_parameter_model("log_event", params)
        >>> validated = Model(event="test", importance="high")
        >>> validated.event
        'test'
    """
    # If no parameters or not an object schema, return empty BaseModel
    if not parameters or parameters.get("type") != "object":
        return BaseModel

    fields: dict[str, Any] = {}
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    for prop_name, prop_schema in properties.items():
        # Convert JSON Schema type to Python type
        field_type = _json_schema_type_to_python(prop_schema)

        # Determine if field is required (default = ...)
        # or optional (default = None)
        if prop_name in required:
            default = ...  # Required field marker
        else:
            default = None

        fields[prop_name] = (field_type | None, default)

    # Create dynamic Pydantic model
    model_name = f"{tool_name.title().replace('_', '')}Params"
    return create_model(model_name, **fields)


# ========================================
# Tool Execution
# ========================================


async def execute_tool(
    prompt_generator: Any,
    tool_name: str,
    tool_input_json: str,
    tool_validators: dict[str, Type[BaseModel]],
    character_name: str,
) -> str:
    """
    Execute a character tool with full validation and error handling.

    This function:
    1. Parses JSON arguments from LLM
    2. Validates parameters using Pydantic model
    3. Executes tool via character's handle_tool_call() method
    4. Enforces 100ms timeout
    5. Handles all errors gracefully
    6. Emits metrics and logs

    Args:
        prompt_generator: Character's PromptGenerator instance
        tool_name: Name of the tool to execute
        tool_input_json: JSON string of tool arguments from LLM
        tool_validators: Dict mapping tool names to Pydantic validator models
        character_name: Character name (for metrics)

    Returns:
        Tool result string (success or error message)

    Example:
        >>> result = await execute_tool(
        ...     prompt_generator,
        ...     "log_event",
        ...     '{"event": "User revealed backstory"}',
        ...     {"log_event": LogEventParams},
        ...     "Narrator"
        ... )
        >>> result
        'Logged: User revealed backstory'
    """
    # Step 1: Parse JSON arguments
    try:
        tool_input = json.loads(tool_input_json)
    except json.JSONDecodeError as e:
        CHARACTER_TOOL_ERRORS.labels(error_type="json_parse").inc()
        error_msg = f"Error: Invalid JSON arguments - {e}"
        logger.error(f"Tool {tool_name} JSON parse error: {e}")
        return error_msg

    # Step 2: Validate parameters
    validator = tool_validators.get(tool_name)
    if validator:
        try:
            validated_input = validator(**tool_input)
            tool_input = validated_input.model_dump(exclude_none=True)
        except ValidationError as e:
            CHARACTER_TOOL_ERRORS.labels(error_type="validation").inc()
            # Extract first error message
            error_details = e.errors()[0]
            field = error_details.get("loc", ["unknown"])[0]
            msg = error_details.get("msg", "Invalid parameter")
            error_msg = f"Error: Invalid parameter '{field}' - {msg}"
            logger.error(f"Tool {tool_name} validation error: {error_msg}")
            return error_msg

    # Step 3: Execute tool with timeout and metrics
    try:
        # Start timing
        timer = Stopwatch()

        # Run in thread pool to avoid blocking event loop
        # Enforce 100ms timeout
        result = await asyncio.wait_for(
            asyncio.to_thread(
                prompt_generator.handle_tool_call, tool_name, tool_input
            ),
            timeout=0.1,  # 100ms maximum
        )

        # Record metrics
        execution_time = timer.time()
        CHARACTER_TOOL_CALLS.labels(
            character_name=character_name, tool_name=tool_name
        ).inc()
        CHARACTER_TOOL_LATENCY.labels(tool_name=tool_name).observe(execution_time)

        # Log successful execution
        logger.info(
            f"Tool executed: {character_name}.{tool_name}({tool_input}) -> {result[:100]} "
            f"({execution_time*1000:.1f}ms)"
        )

        # Warn if approaching timeout
        if execution_time > 0.08:  # 80ms warning threshold
            logger.warning(
                f"Tool {tool_name} took {execution_time*1000:.1f}ms (approaching 100ms timeout)"
            )

        return str(result)

    except asyncio.TimeoutError:
        CHARACTER_TOOL_ERRORS.labels(error_type="timeout").inc()
        error_msg = "Error: Tool execution timed out (exceeded 100ms)"
        logger.error(f"Tool {tool_name} timeout after 100ms")
        return error_msg

    except Exception as e:
        CHARACTER_TOOL_ERRORS.labels(error_type="execution").inc()
        error_msg = f"Error: {type(e).__name__} - {str(e)}"
        logger.error(f"Tool {tool_name} execution error: {e}", exc_info=True)
        return error_msg
