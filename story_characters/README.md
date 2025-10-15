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

# Required: Instruction configuration
INSTRUCTIONS = {
    "type": "smalltalk"  # or constant, quiz_show, news, guess_animal, unmute_explanation
    # Optional fields depend on type:
    # "text": "Custom instructions" (for type: constant)
    # "language": "en" (or "fr", "en/fr", "fr/en")
}

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
        # Import the appropriate instruction class
        from unmute.llm.system_prompt import SmalltalkInstructions

        # Create instruction instance
        inst = SmalltalkInstructions(
            language=self.instructions.get("language")
        )

        # Return generated prompt
        return inst.make_system_prompt()
```

## Required Attributes

Every character file must define:

1. **`CHARACTER_NAME`** (str): Unique name for the character
2. **`VOICE_SOURCE`** (dict): Voice configuration (file or freesound type)
3. **`INSTRUCTIONS`** (dict): LLM behavior configuration
4. **`PromptGenerator`** (class): Class with `__init__(instructions)` and `make_system_prompt() -> str` methods

## Optional Attributes

- **`METADATA`** (dict): Additional metadata like `good` (bool) and `comment` (str)

## Instruction Types

The `INSTRUCTIONS` dict must have a `type` field with one of these values:

1. **`constant`**: Custom instruction text
   - Required: `text` (str) - custom instruction text
   - Optional: `language` (str) - language code

2. **`smalltalk`**: Casual conversation
   - Optional: `language` (str)

3. **`quiz_show`**: Quiz game host
   - Optional: `language` (str)

4. **`news`**: Tech news discussion
   - Optional: `language` (str)

5. **`guess_animal`**: Animal guessing game
   - Optional: `language` (str)

6. **`unmute_explanation`**: System explanation
   - No additional fields

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

1. Create a new `.py` file in `story_characters/`
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
- Invalid instruction type
- Duplicate character names

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
