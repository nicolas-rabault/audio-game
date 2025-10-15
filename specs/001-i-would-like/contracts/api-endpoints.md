# API Contracts: Character Management System

**Feature Branch**: `001-i-would-like`
**Date**: 2025-10-15

## Overview

This document defines the API contracts affected by the self-contained character management system. The primary contract is the existing `/v1/voices` endpoint, which must remain backward compatible.

## Affected Endpoints

### GET /v1/voices

**Purpose**: Returns list of available characters/voices for selection in the UI.

**Contract Status**: **MUST NOT CHANGE** - Existing clients depend on this endpoint.

**Current Implementation**: `unmute/main_websocket.py:200-210`

#### Request

```
GET /v1/voices HTTP/1.1
Host: unmute.sh
```

**Query Parameters**: None

**Headers**: None required

#### Response

**Status Code**: `200 OK`

**Content-Type**: `application/json`

**Response Body** (JSON Array):
```json
[
  {
    "name": "Watercooler",
    "instructions": {
      "type": "smalltalk"
    },
    "source": {
      "source_type": "file",
      "path_on_server": "unmute-prod-website/p329_022.wav",
      "description": "From the Device Recorded VCTK dataset.",
      "description_link": "https://datashare.ed.ac.uk/handle/10283/3038"
    },
    "good": true
  },
  {
    "name": "Quiz show",
    "instructions": {
      "type": "quiz_show"
    },
    "source": {
      "source_type": "freesound",
      "url": "https://freesound.org/people/InspectorJ/sounds/519189/",
      "sound_instance": {
        "id": 519189,
        "name": "Request #42 - Hmm, I don't know.wav",
        "username": "InspectorJ",
        "license": "https://creativecommons.org/licenses/by/4.0/"
      },
      "path_on_server": "unmute-prod-website/freesound/519189_request-42.mp3"
    },
    "good": true
  }
]
```

**Response Schema**:
```typescript
type VoicesResponse = Array<{
  name: string;
  good: boolean;
  instructions: Instructions;
  source: VoiceSource;
  // Note: 'comment' field is excluded from response
}>

type Instructions =
  | { type: "constant", text: string, language?: LanguageCode }
  | { type: "smalltalk", language?: LanguageCode }
  | { type: "quiz_show", language?: LanguageCode }
  | { type: "news", language?: LanguageCode }
  | { type: "guess_animal", language?: LanguageCode }
  | { type: "unmute_explanation" }

type LanguageCode = "en" | "fr" | "en/fr" | "fr/en"

type VoiceSource = FileVoiceSource | FreesoundVoiceSource

type FileVoiceSource = {
  source_type: "file";
  path_on_server: string;
  description?: string;
  description_link?: string;
}

type FreesoundVoiceSource = {
  source_type: "freesound";
  url: string;
  sound_instance: {
    id: number;
    name: string;
    username: string;
    license: string;
  };
  path_on_server?: string;
}
```

#### Implementation Changes

**Before** (current implementation):
```python
@app.get("/v1/voices")
@cache
def voices():
    voice_list = VoiceList()  # Reads voices.yaml
    good_voices = [
        voice.model_dump(exclude={"comment"})
        for voice in voice_list.voices
        if voice.good
    ]
    return good_voices
```

**After** (new implementation):
```python
@app.get("/v1/voices")
@cache
def voices():
    character_manager = get_character_manager()  # Loads from story_characters/
    good_voices = [
        voice.model_dump(exclude={"comment", "_source_file", "_prompt_generator"})
        for voice in character_manager.characters.values()
        if voice.good
    ]
    return good_voices
```

**Contract Guarantees**:
- Response structure remains identical
- Only `good=True` characters are returned
- `comment` field is excluded
- Internal fields (`_source_file`, `_prompt_generator`) are excluded
- Alphabetical or load-order sorting (implementation detail, not guaranteed)

**Caching Behavior**:
- Endpoint uses `@cache` decorator
- Cache populated at first request after startup
- Character changes require server restart to take effect
- No runtime reload of characters

---

### POST /v1/voices

**Purpose**: Upload voice file for cloning (unrelated to character management).

**Contract Status**: **NO CHANGES** - This endpoint is for voice cloning, not character management.

**Implementation**: No changes required.

---

## Internal Service Contracts

### Character Manager Interface

**Purpose**: Internal API for loading and accessing characters.

**Module**: `unmute/tts/character_loader.py` (new)

#### CharacterManager.load_characters()

**Signature**:
```python
async def load_characters(characters_dir: Path) -> CharacterLoadResult
```

**Parameters**:
- `characters_dir`: Path to `story_characters/` directory

**Returns**:
```python
@dataclass
class CharacterLoadResult:
    characters: dict[str, VoiceSample]  # Keyed by character name
    total_files: int
    loaded_count: int
    error_count: int
    load_duration: float
```

**Behavior**:
- Loads all `.py` files from directory concurrently
- Validates each character file
- Skips invalid files with error logging
- Enforces unique character names (first-loaded-wins)
- Emits Prometheus metrics
- Returns loaded characters in dict

**Error Handling**:
- Invalid files: Logged, skipped, counter incremented
- Duplicate names: Logged, duplicate skipped
- Missing directory: Raises `FileNotFoundError`
- Import errors: Logged, file skipped

#### CharacterManager.get_character()

**Signature**:
```python
def get_character(name: str) -> VoiceSample | None
```

**Parameters**:
- `name`: Character name to retrieve

**Returns**:
- `VoiceSample` if found
- `None` if not found

**Behavior**:
- O(1) lookup in internal dict
- Returns character with `_prompt_generator` attached

---

### Character File Contract

**Purpose**: Defines the interface that character files must implement.

**Location**: `story_characters/*.py`

#### Required Module Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `CHARACTER_NAME` | `str` | Yes | Unique character name |
| `VOICE_SOURCE` | `dict` | Yes | Voice source specification (FileVoiceSource or FreesoundVoiceSource) |
| `INSTRUCTIONS` | `dict` | Yes | Instruction configuration |
| `METADATA` | `dict` | No | Optional metadata (good, comment) |
| `PromptGenerator` | `class` | Yes | Class with prompt generation logic |

#### PromptGenerator Interface

**Required Methods**:
```python
class PromptGenerator:
    def __init__(self, instructions: dict):
        """Initialize with instructions from character file."""
        pass

    def make_system_prompt(self) -> str:
        """Generate system prompt for LLM."""
        pass
```

**Contract**:
- `__init__` must accept single `instructions` parameter (dict)
- `make_system_prompt` must return non-empty string
- Class can import from `unmute.llm.system_prompt` but not required
- Class must be instantiable without external dependencies

#### Example Character File

```python
"""Character: Watercooler - Casual conversation partner"""

CHARACTER_NAME = "Watercooler"

VOICE_SOURCE = {
    "source_type": "file",
    "path_on_server": "unmute-prod-website/p329_022.wav",
    "description": "From the Device Recorded VCTK dataset.",
    "description_link": "https://datashare.ed.ac.uk/handle/10283/3038"
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
        inst = SmalltalkInstructions(
            language=self.instructions.get("language")
        )
        return inst.make_system_prompt()
```

---

## Prometheus Metrics Contract

### New Metrics (added to `unmute/metrics.py`)

#### CHARACTER_LOAD_COUNT
**Type**: Counter
**Name**: `worker_character_load_count`
**Description**: Total number of character files successfully loaded
**Labels**: None
**Usage**: Incremented once per successfully loaded character file

#### CHARACTER_LOAD_ERRORS
**Type**: Counter
**Name**: `worker_character_load_errors`
**Description**: Number of character file loading errors
**Labels**: `error_type` (e.g., "ImportError", "ValidationError", "DuplicateName", "MissingAttribute")
**Usage**: Incremented for each failed character file load

#### CHARACTER_LOAD_DURATION
**Type**: Histogram
**Name**: `worker_character_load_duration`
**Description**: Time taken to load all character files (seconds)
**Buckets**: `[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]`
**Usage**: Observed once per startup with total load duration

#### CHARACTERS_LOADED
**Type**: Gauge
**Name**: `worker_characters_loaded`
**Description**: Number of characters currently loaded
**Labels**: None
**Usage**: Set once after loading completes

---

## Migration Script Contract

### Script: scripts/migrate_voices_yaml.py

**Purpose**: One-time migration from `voices.yaml` to `story_characters/*.py`

**Usage**:
```bash
python scripts/migrate_voices_yaml.py [--dry-run] [--output-dir story_characters]
```

**Behavior**:
- Reads `voices.yaml` from repository root
- Generates one `.py` file per character in `story_characters/`
- Filename: `{character-name}.py` (lowercase, spaces→hyphens)
- Preserves all data: name, source, instructions, metadata
- Generates appropriate `PromptGenerator` based on instruction type
- `--dry-run`: Print files without writing
- Logs summary: files created, skipped, errors

**Output**:
- Character files in `story_characters/` directory
- Log file: `migration.log`
- Exit code 0 on success

**Error Handling**:
- Invalid YAML: Exit with error
- Duplicate names: Log warning, suffix with `_2`, `_3`, etc.
- Invalid characters: Skip with warning

---

## Backward Compatibility

### Guarantee: No Breaking Changes to /v1/voices

**Verification Checklist**:
- [ ] Response JSON structure unchanged
- [ ] Field types unchanged (str, bool, dict remain same types)
- [ ] Field names unchanged
- [ ] Only `good=True` characters returned
- [ ] `comment` field still excluded
- [ ] Response is JSON array of objects

### Migration Path

1. **Phase 1**: Implement character loader, test with sample characters
2. **Phase 2**: Run migration script, generate `story_characters/` files
3. **Phase 3**: Update `/v1/voices` endpoint to use new loader
4. **Phase 4**: Test endpoint returns identical data
5. **Phase 5**: Deploy, keep `voices.yaml` as backup (do not delete immediately)
6. **Phase 6**: Monitor for regressions, remove `voices.yaml` after 1 week

### Rollback Plan

If issues arise:
1. Revert code changes to `/v1/voices` endpoint
2. System falls back to `voices.yaml` automatically
3. No data loss (both systems coexist during migration)

---

## Testing Contracts

### Integration Test: /v1/voices Endpoint

**Test Case**: Verify endpoint returns expected structure
```python
async def test_v1_voices_endpoint():
    response = client.get("/v1/voices")
    assert response.status_code == 200

    voices = response.json()
    assert isinstance(voices, list)
    assert len(voices) > 0

    for voice in voices:
        assert "name" in voice
        assert "instructions" in voice
        assert "source" in voice
        assert "good" in voice
        assert voice["good"] is True  # Only good voices
        assert "comment" not in voice  # Excluded field
        assert "_source_file" not in voice  # Internal field
```

### Unit Test: Character Loading

**Test Case**: Verify character file validation
```python
async def test_load_valid_character_file(tmp_path):
    char_file = tmp_path / "test.py"
    char_file.write_text(VALID_CHARACTER_CONTENT)

    result = await load_character_file(char_file)

    assert result.name == "Test Character"
    assert result.good is True
    assert result._prompt_generator is not None
```

**Test Case**: Verify duplicate name handling
```python
async def test_duplicate_character_names(tmp_path):
    (tmp_path / "char1.py").write_text(CHARACTER_WITH_NAME_X)
    (tmp_path / "char2.py").write_text(CHARACTER_WITH_NAME_X)

    result = await load_all_characters(tmp_path)

    assert len(result.characters) == 1  # Only first loaded
    assert result.error_count == 1  # Duplicate logged as error
```

---

## Documentation Updates Required

### Files to Update
- `README.md`: Add character management section
- `unmute/main_websocket.py`: Update docstrings
- `unmute/tts/voices.py`: Add deprecation warnings to VoiceList
- API documentation (if exists): No changes (contract unchanged)

### New Documentation
- `story_characters/README.md`: Guide for creating character files
- `docs/character-format.md`: Character file format specification
- Migration guide: Step-by-step YAML→Python migration

---

## Summary

**Key Contracts**:
1. `/v1/voices` endpoint: **NO BREAKING CHANGES**
2. Character file format: New contract defined (required attributes + PromptGenerator interface)
3. Prometheus metrics: 4 new metrics added
4. Internal CharacterManager API: New interface for loading/accessing characters

**Compatibility**:
- ✅ Existing API clients: Unaffected
- ✅ Existing services (LLM, TTS, STT): Unaffected
- ✅ Existing character data: Migrated via script
- ✅ Rollback: Supported (keep voices.yaml during migration)
