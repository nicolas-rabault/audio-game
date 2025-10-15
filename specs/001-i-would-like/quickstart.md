# Quickstart: Self-Contained Character Management System

**Feature Branch**: `001-i-would-like`
**Date**: 2025-10-15

## Overview

This quickstart guide helps developers understand and work with the self-contained character management system. After implementation, characters will be defined in individual Python files in the `story_characters/` directory.

## For Developers: Creating a New Character

### Step 1: Create Character File

Create a new file in `story_characters/` directory. Use lowercase, hyphen-separated naming:

```bash
touch story_characters/my-character.py
```

### Step 2: Define Character Structure

Copy this template into your character file:

```python
"""Character: [Character Name] - [Brief Description]"""

# Required: Character display name (must be unique)
CHARACTER_NAME = "My Character"

# Required: Voice source (file or freesound)
VOICE_SOURCE = {
    "source_type": "file",  # or "freesound"
    "path_on_server": "path/to/voice.wav",
    "description": "Optional description",
    "description_link": "https://optional-link.com"
}

# Required: Instruction configuration
INSTRUCTIONS = {
    "type": "smalltalk"  # or constant, quiz_show, news, guess_animal, unmute_explanation
    # For constant type, add: "text": "Your custom instruction here"
    # For language control, add: "language": "en" (or "fr", "en/fr", "fr/en")
}

# Optional: Metadata
METADATA = {
    "good": True,  # Set to True when character is production-ready
    "comment": "Any notes about this character"
}

# Required: Prompt generator class
class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import SmalltalkInstructions
        inst = SmalltalkInstructions(
            language=self.instructions.get("language")
        )
        return inst.make_system_prompt()
```

### Step 3: Customize Instruction Type

Choose the appropriate instruction type and adjust the `PromptGenerator`:

#### For Constant Instructions (Custom Text)
```python
INSTRUCTIONS = {
    "type": "constant",
    "text": "You are a helpful assistant who speaks in pirate slang.",
    "language": "en"
}

class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import ConstantInstructions
        inst = ConstantInstructions(
            text=self.instructions.get("text"),
            language=self.instructions.get("language")
        )
        return inst.make_system_prompt()
```

#### For Smalltalk (Casual Conversation)
```python
INSTRUCTIONS = {"type": "smalltalk"}

class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import SmalltalkInstructions
        inst = SmalltalkInstructions(
            language=self.instructions.get("language")
        )
        return inst.make_system_prompt()
```

#### For Quiz Show
```python
INSTRUCTIONS = {"type": "quiz_show"}

class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import QuizShowInstructions
        inst = QuizShowInstructions(
            language=self.instructions.get("language")
        )
        return inst.make_system_prompt()
```

### Step 4: Configure Voice Source

#### Option A: File-Based Voice
```python
VOICE_SOURCE = {
    "source_type": "file",
    "path_on_server": "unmute-prod-website/my-voice.wav",
    "description": "Description of voice source",
    "description_link": "https://source-link.com"
}
```

#### Option B: Freesound Voice
```python
VOICE_SOURCE = {
    "source_type": "freesound",
    "url": "https://freesound.org/people/username/sounds/123456/",
    "sound_instance": {
        "id": 123456,
        "name": "Sound name",
        "username": "freesound_user",
        "license": "https://creativecommons.org/licenses/by/4.0/"
    },
    "path_on_server": "unmute-prod-website/freesound/123456_sound-name.mp3"
}
```

### Step 5: Test Your Character

1. Save the file
2. Restart the server
3. Check logs for loading errors:
   ```bash
   grep "character" logs/server.log
   ```
4. Verify character appears in API:
   ```bash
   curl http://localhost:8000/v1/voices | jq '.[] | select(.name=="My Character")'
   ```

---

## For Operators: Migrating from voices.yaml

### Step 1: Run Migration Script

```bash
cd /home/metab/audio-game
python scripts/migrate_voices_yaml.py
```

**Options**:
- `--dry-run`: Preview files without creating them
- `--output-dir PATH`: Specify output directory (default: `story_characters/`)

### Step 2: Review Generated Files

```bash
ls -la story_characters/
```

Check a few files to ensure proper migration:
```bash
cat story_characters/watercooler.py
```

### Step 3: Test Loading

```bash
# Start server
uvicorn unmute.main_websocket:app --reload

# In another terminal, test API
curl http://localhost:8000/v1/voices | jq length
```

Compare count with original `voices.yaml`:
```bash
grep "^- name:" voices.yaml | wc -l
```

### Step 4: Deploy

1. Commit generated files to git:
   ```bash
   git add story_characters/
   git commit -m "Migrate characters to self-contained format"
   ```

2. Deploy to production

3. Monitor metrics:
   ```bash
   curl http://localhost:8000/metrics | grep character
   ```

4. After 1 week of stable operation, remove `voices.yaml`:
   ```bash
   git rm voices.yaml
   git commit -m "Remove deprecated voices.yaml"
   ```

---

## For System Administrators: Troubleshooting

### Character Not Loading

**Check 1: File syntax errors**
```bash
python -m py_compile story_characters/my-character.py
```

**Check 2: Missing required attributes**
```bash
python -c "
import sys
sys.path.insert(0, '.')
import importlib.util
spec = importlib.util.spec_from_file_location('test', 'story_characters/my-character.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print('CHARACTER_NAME:', getattr(module, 'CHARACTER_NAME', 'MISSING'))
print('VOICE_SOURCE:', getattr(module, 'VOICE_SOURCE', 'MISSING'))
print('INSTRUCTIONS:', getattr(module, 'INSTRUCTIONS', 'MISSING'))
print('PromptGenerator:', getattr(module, 'PromptGenerator', 'MISSING'))
"
```

**Check 3: Server logs**
```bash
tail -f logs/server.log | grep -i "character\|error"
```

**Check 4: Metrics**
```bash
curl http://localhost:8000/metrics | grep character_load_errors
```

### Duplicate Character Names

**Identify duplicates**:
```bash
python -c "
from pathlib import Path
import importlib.util

names = {}
for file in Path('story_characters').glob('*.py'):
    spec = importlib.util.spec_from_file_location('test', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    name = getattr(module, 'CHARACTER_NAME', None)
    if name:
        names.setdefault(name, []).append(file.name)

for name, files in names.items():
    if len(files) > 1:
        print(f'Duplicate: {name} in {files}')
"
```

**Resolution**: Rename one of the characters and restart server.

### Performance Issues

**Check load time**:
```bash
curl http://localhost:8000/metrics | grep character_load_duration
```

**Expected**: <5s for 50 characters, <10s for 100 characters

**If slow**:
1. Check file count: `ls story_characters/*.py | wc -l`
2. Check file sizes: `du -sh story_characters/*.py | sort -h`
3. Look for large files (>10KB): investigate complexity

**Optimization**:
- Remove unused characters (set `good: False` or delete file)
- Simplify complex `PromptGenerator` classes
- Profile with: `python -m cProfile -s cumtime scripts/test_character_loading.py`

---

## Common Patterns

### Pattern 1: Character with Multiple Languages

```python
INSTRUCTIONS = {
    "type": "constant",
    "text": "You are a bilingual assistant.",
    "language": "en/fr"  # Speaks both English and French
}
```

### Pattern 2: Character with Freesound Attribution

```python
VOICE_SOURCE = {
    "source_type": "freesound",
    "url": "https://freesound.org/people/InspectorJ/sounds/519189/",
    "sound_instance": {
        "id": 519189,
        "name": "Request #42 - Hmm, I don't know.wav",
        "username": "InspectorJ",
        "license": "https://creativecommons.org/licenses/by/4.0/"
    },
    "path_on_server": "unmute-prod-website/freesound/519189_request.mp3"
}
```

### Pattern 3: Development Character (Not Production-Ready)

```python
METADATA = {
    "good": False,  # Will not appear in /v1/voices response
    "comment": "Work in progress - voice quality needs improvement"
}
```

### Pattern 4: Custom Prompt Logic

For advanced use cases, implement custom prompt generation:

```python
class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        # Custom logic here
        base_prompt = "You are a creative storyteller."

        if self.instructions.get("genre"):
            base_prompt += f" Your stories are in the {self.instructions['genre']} genre."

        return base_prompt
```

---

## Quick Reference

### File Naming Convention
- Lowercase letters
- Hyphens for spaces
- `.py` extension
- Example: `quiz-show.py`, `my-character.py`

### Required Attributes
- `CHARACTER_NAME` (str): Unique name
- `VOICE_SOURCE` (dict): Voice reference
- `INSTRUCTIONS` (dict): Instruction config
- `PromptGenerator` (class): Prompt generation logic

### Optional Attributes
- `METADATA` (dict): `good` (bool), `comment` (str)

### Instruction Types
1. `constant`: Custom instruction text
2. `smalltalk`: Casual conversation
3. `quiz_show`: Quiz game host
4. `news`: Tech news discussion
5. `guess_animal`: Animal guessing game
6. `unmute_explanation`: System explanation

### Voice Source Types
1. `file`: Local/server file path
2. `freesound`: Freesound.org download

---

## Next Steps

After creating characters:

1. **Test locally**: Verify character loads and responds correctly
2. **Review PR**: Get code review from team
3. **Monitor metrics**: Check Prometheus for load errors
4. **Document**: Add character to project documentation if notable
5. **Share**: Consider adding to character examples for others

---

## Resources

- **Data Model**: See `specs/001-i-would-like/data-model.md`
- **API Contracts**: See `specs/001-i-would-like/contracts/api-endpoints.md`
- **Research**: See `specs/001-i-would-like/research.md`
- **Existing Characters**: Browse `story_characters/` for examples
- **System Prompt Classes**: See `unmute/llm/system_prompt.py`
- **Voice Models**: See `unmute/tts/voices.py`

---

## Support

For issues or questions:
1. Check server logs: `tail -f logs/server.log`
2. Check metrics: `curl http://localhost:8000/metrics | grep character`
3. Review this guide's troubleshooting section
4. Consult team documentation or ask for help

---

**Last Updated**: 2025-10-15
**Feature Branch**: `001-i-would-like`
