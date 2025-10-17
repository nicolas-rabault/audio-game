# Character Files

This directory contains self-contained character definition files. Each character is defined in a single Python file with complete configuration including name, voice source, instructions, metadata, and prompt generation logic.

## Character File Format

Each character file must follow this structure:

```python
"""Character: [Name] - [Optional Description]"""

# Required: Unique character name
CHARACTER_NAME = "Character Name"

# Required: Voice source configuration
VOICE_SOURCE = {
    "source_type": "file",  # or "freesound"
    "path_on_server": "path/to/voice.wav",
    # Optional fields:
    "description": "Voice description",
    "description_link": "https://source-link.com"
}

# Required: Instruction configuration (embedded format)
INSTRUCTIONS = {
    "instruction_prompt": "Your character's behavior description",
    "language": "en"  # Optional: "en", "fr", "en/fr", or "fr/en"
}

# Optional: Tool definitions for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "What the tool does (for LLM understanding)",
            "parameters": {
                "type": "object",
                "properties": {
                    "param_name": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param_name"]
            }
        }
    }
]

# Optional: Metadata
METADATA = {
    "good": True,  # Set to True for production-ready characters
    "comment": "Optional comment"
}

# Required: Prompt generator class
class PromptGenerator:
    """Generate system prompts for this character."""

    def __init__(self, instructions: dict):
        """
        Initialize with instructions from character file.

        Args:
            instructions: The INSTRUCTIONS dict from this character file
        """
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        """
        Generate the system prompt for the LLM.

        Returns:
            System prompt string
        """
        # Import shared prompt utilities
        from unmute.llm.system_prompt import (
            _SYSTEM_PROMPT_TEMPLATE,
            _SYSTEM_PROMPT_BASICS,
            LANGUAGE_CODE_TO_INSTRUCTIONS,
            get_readable_llm_name,
        )

        # Build your custom instructions
        additional_instructions = self.instructions.get('instruction_prompt', '')

        # Use the template
        return _SYSTEM_PROMPT_TEMPLATE.format(
            _SYSTEM_PROMPT_BASICS=_SYSTEM_PROMPT_BASICS,
            additional_instructions=additional_instructions,
            language_instructions=LANGUAGE_CODE_TO_INSTRUCTIONS.get(
                self.instructions.get('language')
            ),
            llm_name=get_readable_llm_name(),
        )

    def get_tools(self) -> list[dict] | None:
        """
        Return tool definitions for LLM (optional).

        Returns:
            TOOLS list if defined, None otherwise
        """
        return globals().get('TOOLS')

    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """
        Execute a tool and return result (required if TOOLS defined).

        Args:
            tool_name: Name of the tool to execute
            tool_input: Validated parameters dict

        Returns:
            Tool result as string
        """
        # Implement tool execution logic
        if tool_name == "tool_name":
            result = do_something(tool_input["param_name"])
            return f"Success: {result}"

        raise ValueError(f"Unknown tool: {tool_name}")
```

## Required Attributes

Every character file must define:

1. **`CHARACTER_NAME`** (str): Unique name for the character
2. **`VOICE_SOURCE`** (dict): Voice configuration (file or freesound type)
3. **`INSTRUCTIONS`** (dict): LLM behavior configuration
4. **`PromptGenerator`** (class): Class with `__init__(instructions)` and `make_system_prompt() -> str` methods

## Optional Attributes

- **`METADATA`** (dict): Additional metadata like `good` (bool) and `comment` (str)
- **`TOOLS`** (list): Tool definitions for LLM function calling (requires `get_tools()` and `handle_tool_call()` methods)

## Character Format

All characters use the **embedded format** where prompt generation logic is embedded directly in the `PromptGenerator.make_system_prompt()` method. This provides maximum flexibility for character-specific behavior.

### Tool Support (Optional)

Characters can optionally define tools that the LLM can invoke during conversations. Tools enable:
- Logging story events
- Performing calculations
- Looking up information
- Managing game state

If you define `TOOLS`, you must also implement:
- `get_tools()` method: Returns the TOOLS list to the LLM
- `handle_tool_call()` method: Executes tool calls and returns results

**See [quickstart.md](../specs/003-on-characters-i/quickstart.md) for detailed tool documentation.**

## Voice Source Types

### File-based Voice

```python
VOICE_SOURCE = {
    "source_type": "file",
    "path_on_server": "unmute-prod-website/voice.wav",
    "description": "Optional description",
    "description_link": "https://optional-link.com"
}
```

### Freesound Voice

```python
VOICE_SOURCE = {
    "source_type": "freesound",
    "url": "https://freesound.org/people/username/sounds/123456/",
    "sound_instance": {
        "id": 123456,
        "name": "Sound name",
        "username": "freesound_username",
        "license": "https://creativecommons.org/licenses/by/4.0/"
    },
    "path_on_server": "unmute-prod-website/freesound/123456_sound.mp3"
}
```

## File Naming Convention

- Use lowercase letters
- Replace spaces with hyphens
- Use `.py` extension
- Examples: `watercooler.py`, `quiz-show.py`, `my-character.py`

## Creating a New Character

1. Create a new `.py` file in `characters/`
2. Copy the template above
3. Fill in all required fields
4. Choose appropriate instruction type
5. Implement PromptGenerator class
6. Test locally before committing

## Validation

Characters are validated at startup. Invalid files are logged and skipped. Common validation errors:

- Missing required attribute (CHARACTER_NAME, VOICE_SOURCE, INSTRUCTIONS)
- Missing PromptGenerator class
- Invalid voice source format
- Invalid TOOLS format (must be list of dicts with OpenAI function calling schema)
- Missing `handle_tool_call()` method when TOOLS is defined
- Duplicate character names
- Duplicate tool names within character

## Loading Behavior

- Characters load automatically at server startup
- Invalid characters are skipped with error logging
- Duplicate names: first-loaded-wins (alphabetical order)
- Empty directory: server starts with warning
- Characters with `good: False` are hidden from API

## Migration from voices.yaml

To migrate existing characters from `voices.yaml`:

```bash
python scripts/migrate_voices_yaml.py --dry-run  # Preview
python scripts/migrate_voices_yaml.py            # Migrate
```

See `scripts/migrate_voices_yaml.py --help` for more options.

## Examples

See existing character files in this directory for complete examples of each instruction type.

## Troubleshooting

For detailed troubleshooting, see [quickstart.md](../specs/001-i-would-like/quickstart.md).
