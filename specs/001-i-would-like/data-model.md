# Data Model: Self-Contained Character Management System

**Feature Branch**: `001-i-would-like`
**Date**: 2025-10-15

## Overview

This document defines the data structures and relationships for the self-contained character management system. The model extends existing Pydantic models while adding new concepts for file-based character loading.

## Entity Definitions

### Character (VoiceSample)

**Description**: Complete definition of a conversational agent with voice, instructions, and metadata.

**Existing Model** (in `unmute/tts/voices.py`): `VoiceSample`

**Fields**:
| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `name` | `str` | Yes | Character display name | Must be unique across all loaded characters; non-empty |
| `source` | `FreesoundVoiceSource \| FileVoiceSource` | Yes | Voice audio reference | Must be valid discriminated union |
| `instructions` | `Instructions` | Yes | LLM behavior configuration | Must be valid discriminated union |
| `good` | `bool \| None` | No | Quality flag for character | None = undecided |
| `comment` | `str \| None` | No | Character notes/attribution | Free text |

**New Fields** (added during loading, not persisted):
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_source_file` | `str` | Yes | Filename character was loaded from (for error reporting) |
| `_prompt_generator` | `type[PromptGenerator]` | Yes | Class reference for generating system prompts |

**State Transitions**: None (immutable after loading)

**Relationships**:
- Has one `VoiceSource` (either `FreesoundVoiceSource` or `FileVoiceSource`)
- Has one `Instructions` (one of 6 instruction types)
- Has one `PromptGenerator` class (embedded in character file)

**Example**:
```python
VoiceSample(
    name="Watercooler",
    source=FileVoiceSource(
        source_type="file",
        path_on_server="unmute-prod-website/p329_022.wav",
        description="From Device Recorded VCTK dataset"
    ),
    instructions=SmalltalkInstructions(type="smalltalk", language=None),
    good=True,
    comment=None,
    _source_file="watercooler.py",
    _prompt_generator=<class 'PromptGenerator'>
)
```

---

### VoiceSource (Abstract)

**Description**: Reference to audio sample for TTS voice cloning.

**Discriminator**: `source_type` field (either "file" or "freesound")

#### FileVoiceSource

**Fields**:
| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `source_type` | `Literal["file"]` | Yes | Discriminator value | Must be "file" |
| `path_on_server` | `str` | Yes | Relative path to audio file on TTS server | Non-empty string |
| `description` | `str \| None` | No | Human-readable description | Free text |
| `description_link` | `str \| None` | No | URL with more info | Valid URL or None |

**Example**:
```python
FileVoiceSource(
    source_type="file",
    path_on_server="unmute-prod-website/p329_022.wav",
    description="From the Device Recorded VCTK dataset.",
    description_link="https://datashare.ed.ac.uk/handle/10283/3038"
)
```

#### FreesoundVoiceSource

**Fields**:
| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `source_type` | `Literal["freesound"]` | Yes | Discriminator value | Must be "freesound" |
| `url` | `str` | Yes | Freesound.org URL | Must be valid freesound.org URL |
| `sound_instance` | `dict` | Yes | Freesound API metadata | Must contain id, name, username, license |
| `path_on_server` | `str \| None` | No | Path after download | Set during download process |

**Example**:
```python
FreesoundVoiceSource(
    source_type="freesound",
    url="https://freesound.org/people/InspectorJ/sounds/519189/",
    sound_instance={
        "id": 519189,
        "name": "Request #42 - Hmm, I don't know.wav",
        "username": "InspectorJ",
        "license": "https://creativecommons.org/licenses/by/4.0/"
    },
    path_on_server="unmute-prod-website/freesound/519189_request-42.mp3"
)
```

---

### Instructions (Abstract)

**Description**: Configuration for LLM behavior and personality.

**Discriminator**: `type` field (one of: constant, smalltalk, quiz_show, news, guess_animal, unmute_explanation)

**Existing Models** (in `unmute/llm/system_prompt.py`): All instruction classes already exist

#### Common Fields (All Instruction Types)
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `Literal[...]` | Yes | Discriminator identifying instruction type |
| `language` | `LanguageCode \| None` | Varies | Language preference ("en", "fr", "en/fr", "fr/en") |

#### ConstantInstructions
**Fields**:
- `type`: `Literal["constant"]`
- `text`: `str` (custom instruction text)
- `language`: `LanguageCode | None`

**Example**:
```python
ConstantInstructions(
    type="constant",
    text="Offer life advice. Be kind and sympathetic. Your name is Gertrude.",
    language="en"
)
```

#### SmalltalkInstructions
**Fields**:
- `type`: `Literal["smalltalk"]`
- `language`: `LanguageCode | None`

#### QuizShowInstructions
**Fields**:
- `type`: `Literal["quiz_show"]`
- `language`: `LanguageCode | None`

#### NewsInstructions
**Fields**:
- `type`: `Literal["news"]`
- `language`: `LanguageCode | None`

#### GuessAnimalInstructions
**Fields**:
- `type`: `Literal["guess_animal"]`
- `language`: `LanguageCode | None`

#### UnmuteExplanationInstructions
**Fields**:
- `type`: `Literal["unmute_explanation"]`
- (No language field - always English)

---

### PromptGenerator (New Concept)

**Description**: Character-specific class that generates system prompts from instructions. Embedded within character Python files.

**Interface** (expected methods):
```python
class PromptGenerator:
    def __init__(self, instructions: dict):
        """Initialize with instructions data from character file."""
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        """Generate the system prompt string for the LLM."""
        # Character-specific implementation
        pass
```

**Validation Rules**:
- Must have `__init__(self, instructions)` method
- Must have `make_system_prompt(self) -> str` method
- Must be importable from character file
- Can use `unmute.llm.system_prompt` classes internally but not required

**Example** (from character file):
```python
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

---

### CharacterLoadResult (New Model)

**Description**: Internal model representing the result of loading all character files.

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `characters` | `dict[str, VoiceSample]` | Successfully loaded characters (keyed by name) |
| `total_files` | `int` | Total .py files found in directory |
| `loaded_count` | `int` | Number successfully loaded |
| `error_count` | `int` | Number that failed to load |
| `load_duration` | `float` | Total load time in seconds |

**Usage**: Returned by character loader, used for metrics and logging.

---

## Relationships Diagram

```
CharacterLoadResult
    │
    └──> characters: dict[str, VoiceSample]
            │
            └──> VoiceSample (Character)
                    ├──> source: VoiceSource (discriminated union)
                    │     ├──> FileVoiceSource
                    │     └──> FreesoundVoiceSource
                    │
                    ├──> instructions: Instructions (discriminated union)
                    │     ├──> ConstantInstructions
                    │     ├──> SmalltalkInstructions
                    │     ├──> QuizShowInstructions
                    │     ├──> NewsInstructions
                    │     ├──> GuessAnimalInstructions
                    │     └──> UnmuteExplanationInstructions
                    │
                    └──> _prompt_generator: type[PromptGenerator]
```

## File-to-Model Mapping

**Character File Structure** → **VoiceSample Model**

```python
# story_characters/example.py

# Module-level constants (metadata)
CHARACTER_NAME = "..."          → VoiceSample.name
VOICE_SOURCE = {...}            → VoiceSample.source (validated against VoiceSource models)
INSTRUCTIONS = {...}            → VoiceSample.instructions (validated against Instructions models)
METADATA = {                    → VoiceSample fields:
    "good": bool,               →   .good
    "comment": str              →   .comment
}

# Class definition (prompt generation logic)
class PromptGenerator:          → VoiceSample._prompt_generator
    def make_system_prompt():  →   (callable at runtime)
        ...
```

## Validation Rules Summary

### Character Loading Validation
1. **File Discovery**: Only `.py` files in `story_characters/` directory
2. **Module Attributes**: Must have `CHARACTER_NAME`, `VOICE_SOURCE`, `INSTRUCTIONS`
3. **Name Uniqueness**: Duplicate names rejected (first-loaded-wins)
4. **Pydantic Validation**: All data validated against existing Pydantic models
5. **PromptGenerator Validation**: Must have required methods (`__init__`, `make_system_prompt`)

### Data Type Validation (via Pydantic)
- `VoiceSample.name`: Non-empty string
- `VoiceSource`: Discriminated union (validated by `source_type`)
- `Instructions`: Discriminated union (validated by `type`)
- `FileVoiceSource.path_on_server`: Non-empty string
- `FreesoundVoiceSource.url`: Valid URL format

### Business Rules
- **BR-001**: Character names must be unique (enforced at load time)
- **BR-002**: Invalid character files are logged and skipped (no system failure)
- **BR-003**: All existing instruction types must be supported (6 types: constant, smalltalk, quiz_show, news, guess_animal, unmute_explanation)
- **BR-004**: Voice sources must reference accessible audio files (validation deferred to TTS service)
- **BR-005**: Prompt generators must return valid system prompt strings (validated at runtime)

## Migration Mapping

**From `voices.yaml` Entry** → **To Character File**

```yaml
# voices.yaml
- name: Watercooler
  good: true
  instructions:
    type: smalltalk
  source:
    source_type: file
    path_on_server: unmute-prod-website/p329_022.wav
    description: From VCTK dataset
```

**Becomes**:

```python
# story_characters/watercooler.py
CHARACTER_NAME = "Watercooler"

VOICE_SOURCE = {
    "source_type": "file",
    "path_on_server": "unmute-prod-website/p329_022.wav",
    "description": "From VCTK dataset"
}

INSTRUCTIONS = {
    "type": "smalltalk"
}

METADATA = {
    "good": True,
    "comment": None
}

class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import SmalltalkInstructions
        inst = SmalltalkInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()
```

## Constraints & Invariants

### Invariants
1. **Character names are unique**: No two loaded characters can have the same name
2. **All loaded characters are valid**: Invalid characters are excluded from the loaded set
3. **Prompt generators are callable**: All `_prompt_generator` references can be instantiated and called
4. **Source files are tracked**: Every loaded character knows which file it came from

### Constraints
- Maximum file size: 10KB per character file (soft limit for performance)
- Maximum characters: 1000+ (no hard limit, but performance target is 100 in <10s)
- Character names: Must be valid Python identifiers when converted to filenames (lowercase, hyphens)
- File encoding: UTF-8 (Python default)

## Performance Implications

- **Load Time**: O(n) where n = number of character files (parallel loading mitigates)
- **Memory**: O(n * avg_character_size) - all characters kept in memory
- **Lookup Time**: O(1) - characters stored in dict keyed by name
- **Validation Time**: O(1) per character - Pydantic validation is fast

## Future Extensions (Out of Scope)

- Versioned character files
- Character dependencies/inheritance
- Dynamic reload without restart
- Multiple character bank directories
- Character marketplace/sharing
