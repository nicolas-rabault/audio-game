# Research: Self-Contained Character Management System

**Feature Branch**: `001-i-would-like`
**Date**: 2025-10-15

## Overview

This document captures research findings and design decisions for implementing a self-contained character management system using Python files as the storage format.

## Research Questions & Findings

### 1. Python File Format for Executable Code + Structured Metadata

**Question**: How do we store both executable prompt generation logic AND parseable metadata in a single Python file?

**Decision**: Use module-level constants and classes with a standardized naming convention.

**Rationale**:
- Python modules can contain both data (constants, dictionaries) and executable code (classes, functions)
- Module-level constants are easily inspectable via `getattr()` after import
- Pydantic models can validate the metadata structure
- Classes can provide the prompt generation logic

**Pattern**:
```python
# story_characters/watercooler.py

# Metadata as module constants (parseable)
CHARACTER_NAME = "Watercooler"
VOICE_SOURCE = {
    "source_type": "file",
    "path_on_server": "unmute-prod-website/p329_022.wav",
    "description": "From the Device Recorded VCTK dataset."
}
INSTRUCTIONS = {
    "type": "smalltalk"
}
METADATA = {
    "good": True,
    "comment": None
}

# Prompt generation logic (executable)
class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        # Character-specific logic here
        return "..."
```

**Alternatives Considered**:
- **Docstrings with YAML/TOML**: Rejected - requires parsing and doesn't support executable code cleanly
- **Separate .py + .json files**: Rejected - violates self-contained requirement
- **Python dataclasses with methods**: Considered - but module-level constants are simpler for metadata inspection

### 2. Dynamic Module Loading Patterns

**Question**: How do we safely load Python files from `story_characters/` directory at runtime?

**Decision**: Use `importlib.util.spec_from_file_location()` with error isolation per file.

**Rationale**:
- `importlib.util` provides safe, sandboxed module loading
- Each file can be loaded independently with try/except isolation
- Module spec allows validation before execution
- Supports async loading with `asyncio.to_thread()`

**Pattern**:
```python
import importlib.util
from pathlib import Path

async def load_character_file(file_path: Path) -> dict:
    def _load_sync():
        spec = importlib.util.spec_from_file_location(
            f"story_characters.{file_path.stem}",
            file_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec from {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Extract standardized attributes
        return {
            "name": getattr(module, "CHARACTER_NAME"),
            "voice_source": getattr(module, "VOICE_SOURCE"),
            "instructions": getattr(module, "INSTRUCTIONS"),
            "metadata": getattr(module, "METADATA", {}),
            "prompt_generator": getattr(module, "PromptGenerator")
        }

    return await asyncio.to_thread(_load_sync)
```

**Alternatives Considered**:
- **`exec()` with file read**: Rejected - less secure, harder to debug, no module isolation
- **`__import__()` with sys.path manipulation**: Rejected - pollutes sys.path, harder to clean up
- **Plugin frameworks (pluggy, stevedore)**: Rejected - overkill for this use case

### 3. Character File Validation Strategies

**Question**: How do we validate character files and handle errors gracefully?

**Decision**: Two-phase validation - structure check + Pydantic validation.

**Rationale**:
- Phase 1: Check for required module attributes (CHARACTER_NAME, VOICE_SOURCE, etc.) - fast fail
- Phase 2: Validate data types using existing Pydantic models (VoiceSample, Instructions)
- Errors are logged with file path and specific issue, file is skipped
- Validation happens during load, not at import time

**Pattern**:
```python
REQUIRED_ATTRIBUTES = ["CHARACTER_NAME", "VOICE_SOURCE", "INSTRUCTIONS"]

async def validate_and_load_character(file_path: Path) -> VoiceSample | None:
    try:
        raw_data = await load_character_file(file_path)

        # Phase 1: Structure validation
        missing = [attr for attr in REQUIRED_ATTRIBUTES if attr not in raw_data]
        if missing:
            logger.error(f"{file_path.name}: Missing required attributes: {missing}")
            return None

        # Phase 2: Pydantic validation
        character = VoiceSample(
            name=raw_data["name"],
            source=raw_data["voice_source"],
            instructions=raw_data["instructions"],
            **raw_data.get("metadata", {})
        )

        # Store prompt generator reference
        character._prompt_generator = raw_data["prompt_generator"]

        return character

    except Exception as e:
        logger.error(f"{file_path.name}: Validation failed - {e}")
        CHARACTER_LOAD_ERRORS.labels(error_type=type(e).__name__).inc()
        return None
```

**Alternatives Considered**:
- **JSON Schema validation**: Rejected - doesn't help with executable code validation
- **AST parsing before execution**: Considered - too complex, performance overhead
- **Fail-fast on first error**: Rejected - violates graceful degradation requirement (FR-009)

### 4. Migration Patterns from YAML to Python Files

**Question**: How do we migrate existing `voices.yaml` entries to individual Python character files?

**Decision**: One-time migration script that generates Python files from YAML structure.

**Rationale**:
- YAML structure already maps to Pydantic models (VoiceSample)
- Each YAML entry becomes one Python file
- Instruction type determines which PromptGenerator template to use
- Script is run once manually, not part of runtime system

**Pattern**:
```python
# scripts/migrate_voices_yaml.py

PROMPT_GENERATOR_TEMPLATES = {
    "constant": """
class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import ConstantInstructions
        inst = ConstantInstructions(
            text=self.instructions.get("text", ""),
            language=self.instructions.get("language")
        )
        return inst.make_system_prompt()
""",
    "smalltalk": """
class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import SmalltalkInstructions
        inst = SmalltalkInstructions(
            language=self.instructions.get("language")
        )
        return inst.make_system_prompt()
""",
    # ... other instruction types
}

def migrate_character(voice: VoiceSample, output_dir: Path):
    filename = voice.name.lower().replace(" ", "-") + ".py"
    file_path = output_dir / filename

    # Generate Python file content
    content = f'''"""Character: {voice.name}"""

CHARACTER_NAME = "{voice.name}"

VOICE_SOURCE = {voice.source.model_dump()}

INSTRUCTIONS = {voice.instructions.model_dump()}

METADATA = {{
    "good": {voice.good},
    "comment": {repr(voice.comment)}
}}

{PROMPT_GENERATOR_TEMPLATES[voice.instructions.type]}
'''

    file_path.write_text(content)
```

**Alternatives Considered**:
- **Runtime YAML fallback**: Rejected - violates FR-006 (no backward compatibility)
- **Automatic migration on startup**: Rejected - creates uncertainty about data source
- **Manual file-by-file rewrite**: Rejected - error-prone, time-consuming for 50+ characters

### 5. Duplicate Name Handling

**Question**: How do we enforce unique character names when loading multiple files?

**Decision**: First-loaded-wins with explicit error logging for duplicates.

**Rationale**:
- Simple deterministic behavior (alphabetical file order)
- Duplicate detection during load phase
- Clear error messages for operators
- Matches clarification in spec (FR-014)

**Pattern**:
```python
async def load_all_characters(characters_dir: Path) -> dict[str, VoiceSample]:
    characters = {}
    files = sorted(characters_dir.glob("*.py"))  # Deterministic order

    for file_path in files:
        character = await validate_and_load_character(file_path)
        if character is None:
            continue

        if character.name in characters:
            logger.error(
                f"{file_path.name}: Duplicate character name '{character.name}' "
                f"(first defined in {characters[character.name]._source_file}). Skipping."
            )
            CHARACTER_LOAD_ERRORS.labels(error_type="DuplicateName").inc()
            continue

        character._source_file = file_path.name
        characters[character.name] = character

    return characters
```

## Technology Stack Summary

**Core Technologies**:
- **Python 3.12**: Language version (existing project constraint)
- **importlib.util**: Dynamic module loading
- **Pydantic**: Data validation (already in use)
- **Prometheus client**: Metrics (already in use)
- **ruamel.yaml**: Migration script only (already in use)

**No New Dependencies Required**: All chosen technologies are already in the project or part of Python stdlib.

## Performance Considerations

**Estimated Performance**:
- Module import: ~1-5ms per file (Python import overhead)
- Validation: ~0.1ms per character (Pydantic)
- Target: 50 characters in 5s = 100ms per character budget (well within estimates)
- Actual bottleneck: File I/O, mitigated by `asyncio.to_thread()`

**Optimization Strategy**:
- Load files concurrently using `asyncio.gather()`
- Cache loaded characters in memory (no re-loading during runtime)
- Lazy initialization of prompt generators (only create when needed)

## Security Considerations

**Risks**:
- **Arbitrary code execution**: Character files are Python code
- **Malicious file inclusion**: Directory traversal attacks

**Mitigations**:
- Character files must be in designated `story_characters/` directory only
- File permissions should restrict write access to admins
- No user-uploaded character files (admin/dev-controlled only)
- Module loading uses importlib (safer than exec)
- Each file loads in isolation (errors don't cascade)

**Acceptable Risk**: This is an internal system where character files are version-controlled and reviewed before deployment. Not a user-facing upload feature.

## Open Questions & Decisions Deferred

None - all NEEDS CLARIFICATION items from Technical Context have been resolved.

## References

- Python importlib documentation: https://docs.python.org/3/library/importlib.html
- Pydantic discriminated unions: https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions
- Existing codebase: `unmute/tts/voices.py`, `unmute/llm/system_prompt.py`
