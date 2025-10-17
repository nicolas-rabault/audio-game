# Quickstart Guide: Character Tools

**Feature**: Optional TOOLS Variable for Character Function Calling
**Audience**: Character developers
**Prerequisites**: Familiarity with character file format (embedded format)

## Table of Contents

1. [Overview](#overview)
2. [Adding Tools to Existing Characters](#adding-tools-to-existing-characters)
3. [Creating Tool-Enabled Characters from Scratch](#creating-tool-enabled-characters-from-scratch)
4. [Tool Implementation Best Practices](#tool-implementation-best-practices)
5. [Testing Your Tools](#testing-your-tools)
6. [Debugging](#debugging)
7. [Examples](#examples)
8. [FAQ](#faq)

---

## Overview

Character tools enable LLM-triggered function calling, allowing characters to perform actions beyond generating text. Common use cases:

- **Logging**: Track story events, user preferences, conversation metrics
- **Calculations**: Perform math, generate random numbers
- **Data Retrieval**: Look up information from external sources (future)
- **State Management**: Update game state, track scores (future)

**Key Concepts**:
- **TOOLS variable**: Optional list of tool definitions in character file
- **get_tools()**: PromptGenerator method that returns tools to LLM
- **handle_tool_call()**: PromptGenerator method that executes tools
- **OpenAI Format**: Standard function calling schema for LLM compatibility

---

## Adding Tools to Existing Characters

### Step 1: Define TOOLS Variable

Add a `TOOLS` list at the top of your character file (after INSTRUCTIONS):

```python
# In your_character.py

CHARACTER_NAME = "Your Character"
VOICE_SOURCE = {...}
INSTRUCTIONS = {...}

# NEW: Add TOOLS variable
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "your_tool_name",
            "description": "Clear description for LLM",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "What param1 does"
                    }
                },
                "required": ["param1"]
            }
        }
    }
]
```

**TOOLS Format Rules**:
- Must be a list (even for single tool)
- Each tool must have `type: "function"`
- `function.name`: Alphanumeric + underscores, unique within character
- `function.description`: <200 chars, clear enough for LLM to understand when to use
- `function.parameters`: JSON Schema format (optional)

### Step 2: Add get_tools() Method

Update your `PromptGenerator` class:

```python
class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        # ... your existing code ...
        pass

    # NEW: Add get_tools() method
    def get_tools(self) -> list[dict] | None:
        """Return tool definitions for LLM."""
        return globals().get('TOOLS')
```

**Note**: `globals().get('TOOLS')` safely checks if TOOLS is defined in the module.

### Step 3: Add handle_tool_call() Method

Implement tool execution logic:

```python
class PromptGenerator:
    # ... existing methods ...

    # NEW: Add handle_tool_call() method
    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Execute tool and return result."""
        if tool_name == "your_tool_name":
            # Access parameters
            param1 = tool_input["param1"]

            # Perform action
            result = do_something(param1)

            # Return confirmation
            return f"Success: {result}"

        # Handle unknown tools
        raise ValueError(f"Unknown tool: {tool_name}")
```

**handle_tool_call() Rules**:
- **Input**: `tool_name` (str), `tool_input` (dict with validated parameters)
- **Output**: String result or error message
- **Errors**: Raise exceptions for unknown tools (system catches and returns to LLM)
- **Timeout**: Must complete in <100ms

### Step 4: Test Your Character

```bash
# Restart server to reload character
python -m unmute.main_websocket

# Connect and test
# Trigger tool by having conversation that uses it
```

---

## Creating Tool-Enabled Characters from Scratch

### Minimal Example: Narrator with Logging Tool

```python
"""Character: Narrator with story event logging."""

CHARACTER_NAME = "Narrator"

VOICE_SOURCE = {
    'source_type': 'file',
    'path_on_server': 'path/to/voice.wav',
    'description': 'Narrator voice'
}

INSTRUCTIONS = {
    'instruction_prompt': 'You are a storytelling narrator. You describe scenes, characters, and events in an engaging narrative style. When important story moments happen, log them using your tool.',
    'language': 'en'
}

# Define tool
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
                        "description": "The story event to log (e.g., 'User revealed their motivation')"
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
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import (
            _SYSTEM_PROMPT_TEMPLATE,
            _SYSTEM_PROMPT_BASICS,
            LANGUAGE_CODE_TO_INSTRUCTIONS,
            get_readable_llm_name,
        )

        additional_instructions = self.instructions.get('instruction_prompt', '')

        return _SYSTEM_PROMPT_TEMPLATE.format(
            _SYSTEM_PROMPT_BASICS=_SYSTEM_PROMPT_BASICS,
            additional_instructions=additional_instructions,
            language_instructions=LANGUAGE_CODE_TO_INSTRUCTIONS.get(
                self.instructions.get('language')
            ),
            llm_name=get_readable_llm_name(),
        )

    def get_tools(self) -> list[dict] | None:
        """Return tool definitions for LLM."""
        return globals().get('TOOLS')

    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Execute tool and return result."""
        if tool_name == "log_story_event":
            event = tool_input["event"]
            importance = tool_input.get("importance", "medium")

            # Log to terminal
            print(f"[NARRATOR EVENT] [{importance.upper()}] {event}")

            # Return confirmation
            return f"Logged story event: {event}"

        raise ValueError(f"Unknown tool: {tool_name}")
```

---

## Tool Implementation Best Practices

### DO ✓

1. **Keep Tools Fast** (<100ms execution time)
   ```python
   # Good: Simple calculation
   def handle_tool_call(self, tool_name, tool_input):
       if tool_name == "calculate_sum":
           result = tool_input["a"] + tool_input["b"]
           return f"Sum: {result}"
   ```

2. **Return Descriptive Messages**
   ```python
   # Good: Clear confirmation
   return "Logged event: User revealed backstory"

   # Bad: Vague response
   return "OK"
   ```

3. **Use Clear Parameter Names**
   ```python
   # Good: Self-explanatory
   "parameters": {
       "event": {"type": "string", "description": "The event to log"},
       "importance": {"type": "string", "enum": ["low", "medium", "high"]}
   }

   # Bad: Ambiguous
   "parameters": {
       "data": {"type": "string"},
       "level": {"type": "number"}
   }
   ```

4. **Validate Inputs**
   ```python
   # Good: Check constraints
   def handle_tool_call(self, tool_name, tool_input):
       if tool_name == "set_volume":
           volume = tool_input["level"]
           if not 0 <= volume <= 100:
               raise ValueError("Volume must be between 0 and 100")
           # ... proceed ...
   ```

5. **Log Important Actions**
   ```python
   # Good: Debug visibility
   def handle_tool_call(self, tool_name, tool_input):
       print(f"[TOOL] {tool_name} called with {tool_input}")
       result = perform_action(tool_input)
       print(f"[TOOL] {tool_name} completed: {result}")
       return result
   ```

### DON'T ✗

1. **Don't Make Blocking Network Requests**
   ```python
   # Bad: Blocks event loop
   def handle_tool_call(self, tool_name, tool_input):
       response = requests.get("https://api.example.com/data")  # SLOW!
       return response.text

   # Better: Document as anti-pattern, use async in future
   ```

2. **Don't Access Mutable Global State**
   ```python
   # Bad: Thread-safety issues
   conversation_state = {}  # Global variable

   def handle_tool_call(self, tool_name, tool_input):
       conversation_state["last_event"] = tool_input["event"]  # UNSAFE!
   ```

3. **Don't Return Large Data**
   ```python
   # Bad: Wastes LLM context
   def handle_tool_call(self, tool_name, tool_input):
       return "\n".join([f"Item {i}" for i in range(1000)])  # TOO LONG!

   # Good: Summarize
   def handle_tool_call(self, tool_name, tool_input):
       items = get_items()
       return f"Found {len(items)} items"
   ```

4. **Don't Raise Generic Exceptions Without Messages**
   ```python
   # Bad: Unhelpful error
   raise Exception()

   # Good: Descriptive error
   raise ValueError("Invalid importance level: must be low, medium, or high")
   ```

---

## Testing Your Tools

### Manual Testing

1. **Start server** with your character loaded:
   ```bash
   python -m unmute.main_websocket
   ```

2. **Check logs** for character loading:
   ```
   [INFO] Character Narrator loaded with 1 tools: ['log_story_event']
   ```

3. **Connect via WebSocket** and select your character

4. **Trigger tool** through conversation:
   - Say something that should prompt tool use
   - Watch terminal for tool execution logs
   - Verify LLM receives and processes result

### Example Test Conversation

```
User: "Tell me a story about a brave knight."

LLM: "Once upon a time, there was a brave knight named Sir Galahad..."
     [Internally calls log_story_event with "Story begun: Knight tale", importance: "medium"]

Terminal Output:
[NARRATOR EVENT] [MEDIUM] Story begun: Knight tale

User: "What was his motivation?"

LLM: "Sir Galahad sought the Holy Grail to prove his worth..."
     [Internally calls log_story_event with "User asked about motivation", importance: "high"]

Terminal Output:
[NARRATOR EVENT] [HIGH] User asked about motivation
```

### Automated Testing (Future)

```python
# In tests/test_narrator_tools.py
import pytest
from characters.narrator import PromptGenerator, TOOLS

def test_log_story_event():
    """Test logging tool executes correctly."""
    pg = PromptGenerator({'instruction_prompt': 'test'})

    result = pg.handle_tool_call(
        "log_story_event",
        {"event": "Test event", "importance": "high"}
    )

    assert "Logged story event: Test event" in result

def test_invalid_tool():
    """Test unknown tool raises error."""
    pg = PromptGenerator({'instruction_prompt': 'test'})

    with pytest.raises(ValueError, match="Unknown tool"):
        pg.handle_tool_call("nonexistent_tool", {})
```

---

## Debugging

### Common Issues

#### 1. Character Fails to Load

**Symptom**: Error on server startup
```
[ERROR] Character YourCharacter tool validation failed: Missing method: handle_tool_call
```

**Solution**: Add `handle_tool_call()` method to `PromptGenerator` class

#### 2. Tool Never Gets Called

**Possible Causes**:
- LLM doesn't understand when to use tool (improve description)
- Tool not included in API request (check `get_tools()` returns TOOLS)
- LLM model doesn't support function calling (check vLLM config)

**Debug Steps**:
```python
# Add logging to get_tools()
def get_tools(self):
    tools = globals().get('TOOLS')
    print(f"[DEBUG] get_tools() returning: {tools}")
    return tools
```

#### 3. Parameter Validation Errors

**Symptom**: LLM receives error message
```
Error: Missing required parameter: event
```

**Solution**: Check parameter names in TOOLS match what LLM sends

**Debug**: Add logging to handle_tool_call():
```python
def handle_tool_call(self, tool_name, tool_input):
    print(f"[DEBUG] Tool: {tool_name}, Input: {tool_input}")
    # ... rest of code ...
```

#### 4. Tool Timeout

**Symptom**: Error after 100ms
```
Error: Tool execution timed out
```

**Solution**: Optimize tool to run faster, or mark as anti-pattern for future async implementation

### Metrics & Monitoring

**Prometheus Metrics** (view at `/metrics` endpoint):
- `character_tool_calls_total{character_name, tool_name}` - Tool invocation count
- `character_tool_errors_total{error_type}` - Error count by type
- `character_tool_latency_seconds{tool_name}` - Execution duration histogram

**Check Metrics**:
```bash
curl http://localhost:8000/metrics | grep character_tool
```

---

## Examples

### Example 1: Random Number Generator

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Roll dice for game mechanics (e.g., 2d6 means roll two 6-sided dice)",
            "parameters": {
                "type": "object",
                "properties": {
                    "num_dice": {
                        "type": "integer",
                        "description": "Number of dice to roll",
                        "minimum": 1,
                        "maximum": 10
                    },
                    "num_sides": {
                        "type": "integer",
                        "description": "Number of sides per die",
                        "enum": [4, 6, 8, 10, 12, 20, 100]
                    }
                },
                "required": ["num_dice", "num_sides"]
            }
        }
    }
]

def handle_tool_call(self, tool_name, tool_input):
    if tool_name == "roll_dice":
        import random
        rolls = [
            random.randint(1, tool_input["num_sides"])
            for _ in range(tool_input["num_dice"])
        ]
        total = sum(rolls)
        return f"Rolled {tool_input['num_dice']}d{tool_input['num_sides']}: {rolls} (total: {total})"

    raise ValueError(f"Unknown tool: {tool_name}")
```

### Example 2: Simple Calculator

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Perform basic arithmetic calculations",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "Math operation to perform"
                    },
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["operation", "a", "b"]
            }
        }
    }
]

def handle_tool_call(self, tool_name, tool_input):
    if tool_name == "calculate":
        ops = {
            "add": lambda a, b: a + b,
            "subtract": lambda a, b: a - b,
            "multiply": lambda a, b: a * b,
            "divide": lambda a, b: a / b if b != 0 else "Error: Division by zero"
        }

        op = tool_input["operation"]
        result = ops[op](tool_input["a"], tool_input["b"])

        if isinstance(result, str):  # Error case
            return result

        return f"{tool_input['a']} {op} {tool_input['b']} = {result}"

    raise ValueError(f"Unknown tool: {tool_name}")
```

### Example 3: Multiple Tools (Quiz Character)

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_answer",
            "description": "Check if user's answer to quiz question is correct",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "user_answer": {"type": "string"}
                },
                "required": ["question_id", "user_answer"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_score",
            "description": "Update user's quiz score",
            "parameters": {
                "type": "object",
                "properties": {
                    "points": {"type": "integer", "description": "Points to add (positive) or subtract (negative)"}
                },
                "required": ["points"]
            }
        }
    }
]

def handle_tool_call(self, tool_name, tool_input):
    if tool_name == "check_answer":
        # Simplified: check against hardcoded answers
        correct_answers = {"q1": "Paris", "q2": "42"}
        correct = correct_answers.get(tool_input["question_id"], "").lower() == tool_input["user_answer"].lower()
        return f"Answer is {'correct' if correct else 'incorrect'}"

    elif tool_name == "update_score":
        # Log score update (future: persist to database)
        print(f"[SCORE] +{tool_input['points']} points")
        return f"Score updated: +{tool_input['points']} points"

    raise ValueError(f"Unknown tool: {tool_name}")
```

---

## FAQ

### Q: When should I use tools vs. prompt engineering?

**A**: Use tools when you need:
- External side effects (logging, state updates)
- Precise calculations (math, random numbers)
- Deterministic behavior (not relying on LLM to format output correctly)

Use prompt engineering when:
- Pure text generation is sufficient
- Behavior can be controlled via system prompt
- No external actions needed

### Q: Can tools call other tools?

**A**: Not directly. Each tool invocation is independent. If you need multi-step logic:
1. LLM calls first tool
2. First tool returns result
3. LLM processes result and decides to call second tool

### Q: How do I handle tool errors gracefully?

**A**: Raise exceptions with descriptive messages. The system catches them and returns to LLM:
```python
if invalid_input:
    raise ValueError("Input must be between 1 and 100")
```

LLM receives: `"Error: Input must be between 1 and 100"` and can explain to user.

### Q: Can I make async tools?

**A**: Not in the current version. Tools must be synchronous and complete <100ms. Future versions may support async tools for longer operations.

### Q: Do I need to update existing characters?

**A**: No. Tools are optional. Characters without TOOLS variable work exactly as before.

### Q: What happens if I define TOOLS but forget get_tools()?

**A**: Character loads successfully but tools aren't sent to LLM. Add `get_tools()` method to enable tools.

### Q: What happens if I define TOOLS but forget handle_tool_call()?

**A**: **Character loading fails** at startup with clear error message. You must implement both `get_tools()` and `handle_tool_call()` if TOOLS is defined.

### Q: Can different characters share tools?

**A**: Not directly. Each character's tools are independent. If you need shared logic, create a helper module and import in multiple character files.

---

## Next Steps

1. **Add tools to existing character**: Follow [Adding Tools to Existing Characters](#adding-tools-to-existing-characters)
2. **Test with narrator.py**: Try the logging tool example
3. **Read data-model.md**: Understand tool schemas in depth
4. **Check contracts/tool-schema.json**: Validate your TOOLS against JSON Schema
5. **Report issues**: File bugs or feature requests in project tracker

## Further Reading

- [data-model.md](data-model.md) - Detailed schema specifications
- [research.md](research.md) - Technical decisions and alternatives
- [plan.md](plan.md) - Implementation architecture
- OpenAI Function Calling Guide: https://platform.openai.com/docs/guides/function-calling
