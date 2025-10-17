"""
Character loading module for self-contained character management system.

This module handles:
- Discovery of character files in the characters/ directory
- Dynamic module loading using importlib
- Character validation and error handling
- Prometheus metrics for character loading
"""

import asyncio
import importlib.util
import inspect
import logging
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from unmute.metrics import (
    CHARACTER_LOAD_COUNT,
    CHARACTER_LOAD_DURATION,
    CHARACTER_LOAD_ERRORS,
    CHARACTERS_LOADED,
)
from unmute.tts.voices import VoiceSample

logger = logging.getLogger(__name__)

# Required attributes in character files
REQUIRED_ATTRIBUTES = ["CHARACTER_NAME", "VOICE_SOURCE", "INSTRUCTIONS"]


# ========================================
# Pydantic Models for Tool Validation
# ========================================


class ToolFunctionDefinition(BaseModel):
    """OpenAI function definition schema."""

    name: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$", max_length=50)
    description: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] | None = None

    @field_validator("parameters")
    @classmethod
    def validate_parameters_schema(cls, v):
        """Validate that parameters follow JSON Schema object format."""
        if v is not None:
            if v.get("type") != "object":
                raise ValueError("Top-level parameters type must be 'object'")
            if "properties" in v and len(v["properties"]) > 10:
                raise ValueError("Maximum 10 parameters per tool")
        return v


class ToolDefinition(BaseModel):
    """OpenAI tool definition schema."""

    type: Literal["function"] = "function"
    function: ToolFunctionDefinition


class CharacterTools(BaseModel):
    """Character's TOOLS list with validation."""

    tools: list[ToolDefinition] = Field(max_length=10)

    @field_validator("tools")
    @classmethod
    def validate_unique_names(cls, tools):
        """Ensure tool names are unique within character."""
        names = [t.function.name for t in tools]
        if len(names) != len(set(names)):
            duplicates = {n for n in names if names.count(n) > 1}
            raise ValueError(f"Duplicate tool names: {duplicates}")
        return tools


@dataclass
class CharacterLoadResult:
    """Result of loading all character files."""

    characters: Dict[str, VoiceSample]  # Keyed by character name
    total_files: int
    loaded_count: int
    error_count: int
    load_duration: float


def _load_character_file_sync(file_path: Path, module_prefix: str) -> Dict[str, Any]:
    """
    Synchronously load a character file and extract its attributes.
    This function is wrapped by asyncio.to_thread() to avoid blocking.

    Args:
        file_path: Path to character .py file
        module_prefix: Session-unique module prefix (e.g., "session_abc12345.characters")

    Returns:
        Dict with character attributes

    Raises:
        ImportError: If module cannot be loaded
        AttributeError: If required attributes are missing
    """
    # Ensure the session-specific characters package is in sys.modules
    # This is needed for imports like "from characters.shared_constants import ..."
    # Note: We still need the base 'characters' module for relative imports to work
    if 'characters' not in sys.modules:
        import characters
        sys.modules['characters'] = characters

    # Create session-specific module name (e.g., "session_abc12345.characters.charles")
    module_name = f"{module_prefix}.{file_path.stem}"

    # Load module using importlib
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec from {file_path}")

    module = importlib.util.module_from_spec(spec)

    # Register the module in sys.modules before executing to support internal imports
    sys.modules[module_name] = module

    spec.loader.exec_module(module)

    # Check for required attributes
    missing = [attr for attr in REQUIRED_ATTRIBUTES if not hasattr(module, attr)]
    if missing:
        raise AttributeError(f"Missing required attributes: {', '.join(missing)}")

    # Check for PromptGenerator class
    if not hasattr(module, "PromptGenerator"):
        raise AttributeError("Missing required class: PromptGenerator")

    # Extract attributes
    return {
        "name": getattr(module, "CHARACTER_NAME"),
        "voice_source": getattr(module, "VOICE_SOURCE"),
        "instructions": getattr(module, "INSTRUCTIONS"),
        "metadata": getattr(module, "METADATA", {}),
        "prompt_generator": getattr(module, "PromptGenerator"),
        "tools": getattr(module, "TOOLS", None),  # Optional TOOLS variable
    }


async def _validate_character_data(
    raw_data: Dict[str, Any], file_path: Path
) -> VoiceSample | None:
    """
    Validate character data and create VoiceSample instance.

    Args:
        raw_data: Raw data extracted from character file
        file_path: Path to character file (for error reporting)

    Returns:
        VoiceSample instance if valid, None if invalid
    """
    try:
        # Validate PromptGenerator interface
        prompt_generator_class = raw_data["prompt_generator"]

        # Check __init__ method signature
        if not hasattr(prompt_generator_class, "__init__"):
            logger.error(
                f"{file_path.name}: PromptGenerator class missing __init__ method"
            )
            CHARACTER_LOAD_ERRORS.labels(error_type="MissingInit").inc()
            return None

        # Check make_system_prompt method
        if not hasattr(prompt_generator_class, "make_system_prompt"):
            logger.error(
                f"{file_path.name}: PromptGenerator class missing make_system_prompt method"
            )
            CHARACTER_LOAD_ERRORS.labels(error_type="MissingMethod").inc()
            return None

        # Verify make_system_prompt returns string
        if hasattr(prompt_generator_class, "make_system_prompt"):
            method = getattr(prompt_generator_class, "make_system_prompt")
            sig = inspect.signature(method)
            # Method should have return annotation of str
            if sig.return_annotation not in (str, inspect.Signature.empty):
                logger.warning(
                    f"{file_path.name}: make_system_prompt should return str (found {sig.return_annotation})"
                )

        # T008: Validate TOOLS variable structure (if present)
        tools_list = raw_data.get("tools")
        tool_validators: Dict[str, Any] = {}

        if tools_list is not None:
            # Validate TOOLS format
            try:
                if not isinstance(tools_list, list):
                    logger.error(
                        f"{file_path.name}: TOOLS must be a list, got {type(tools_list).__name__}"
                    )
                    CHARACTER_LOAD_ERRORS.labels(error_type="InvalidToolsFormat").inc()
                    return None

                # Validate using Pydantic model
                validated_tools = CharacterTools(tools=tools_list)

                # T010: Verify handle_tool_call method exists when TOOLS defined
                if not hasattr(prompt_generator_class, "handle_tool_call"):
                    logger.error(
                        f"{file_path.name}: TOOLS defined but PromptGenerator missing handle_tool_call method"
                    )
                    CHARACTER_LOAD_ERRORS.labels(
                        error_type="MissingToolHandler"
                    ).inc()
                    return None

                # T009: Generate tool validators from parameter schemas
                from unmute.llm.tool_executor import create_parameter_model

                for tool in validated_tools.tools:
                    tool_name = tool.function.name
                    parameters = tool.function.parameters
                    validator_model = create_parameter_model(tool_name, parameters)
                    tool_validators[tool_name] = validator_model

                logger.info(
                    f"{file_path.name}: Loaded with {len(validated_tools.tools)} tools: "
                    f"{[t.function.name for t in validated_tools.tools]}"
                )

            except ValidationError as e:
                logger.error(f"{file_path.name}: TOOLS validation failed - {e}")
                CHARACTER_LOAD_ERRORS.labels(error_type="ToolValidationError").inc()
                return None

        # Create VoiceSample with Pydantic validation
        # Note: instructions are NOT part of VoiceSample schema - they are attached as internal attributes
        character = VoiceSample(
            name=raw_data["name"],
            source=raw_data["voice_source"],
            **raw_data.get("metadata", {}),
        )

        # Attach internal fields (not persisted)
        character._source_file = file_path.name  # type: ignore
        character._instructions = raw_data["instructions"]  # type: ignore
        character._prompt_generator = prompt_generator_class  # type: ignore
        character._tools = tools_list  # type: ignore
        character._tool_validators = tool_validators  # type: ignore

        logger.debug(
            f"{file_path.name}: Attached _instructions={raw_data['instructions']}, "
            f"_tools={len(tools_list) if tools_list else 0} tools"
        )

        return character

    except ValidationError as e:
        logger.error(f"{file_path.name}: Validation failed - {e}")
        CHARACTER_LOAD_ERRORS.labels(error_type="ValidationError").inc()
        return None
    except Exception as e:
        logger.error(f"{file_path.name}: Unexpected error during validation - {e}")
        CHARACTER_LOAD_ERRORS.labels(error_type=type(e).__name__).inc()
        return None


async def _load_single_character(file_path: Path, module_prefix: str) -> VoiceSample | None:
    """
    Load and validate a single character file.

    Args:
        file_path: Path to character .py file
        module_prefix: Session-unique module prefix

    Returns:
        VoiceSample if successful, None if failed
    """
    try:
        # Load file (run in thread to avoid blocking event loop)
        raw_data = await asyncio.to_thread(_load_character_file_sync, file_path, module_prefix)

        # Validate data
        character = await _validate_character_data(raw_data, file_path)

        return character

    except ImportError as e:
        logger.error(f"{file_path.name}: Import failed - {e}")
        CHARACTER_LOAD_ERRORS.labels(error_type="ImportError").inc()
        return None
    except AttributeError as e:
        logger.error(f"{file_path.name}: {e}")
        CHARACTER_LOAD_ERRORS.labels(error_type="MissingAttribute").inc()
        return None
    except Exception as e:
        logger.error(
            f"{file_path.name}: Unexpected error - {type(e).__name__}: {e}"
        )
        CHARACTER_LOAD_ERRORS.labels(error_type=type(e).__name__).inc()
        return None


class CharacterManager:
    """Manager for loading and accessing characters from Python files.

    Each CharacterManager instance is scoped to a session, enabling
    multiple simultaneous users to load different character sets independently.

    Args:
        session_id: Optional session identifier. If not provided, generates a unique ID.
                   Used to create isolated module namespaces in sys.modules.
    """

    def __init__(self, session_id: str | None = None):
        # Generate unique session ID if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]  # Short 8-char ID for readability

        self.session_id = session_id
        # Create session-unique module prefix (e.g., "session_abc12345.characters")
        self.module_prefix = f"session_{self.session_id}.characters"

        self.characters: Dict[str, VoiceSample] = {}
        self._load_result: CharacterLoadResult | None = None
        self._current_directory: Path | None = None

        logger.debug(f"CharacterManager initialized with session_id={self.session_id}, module_prefix={self.module_prefix}")

    def _cleanup_character_modules(self) -> None:
        """
        Remove all session-specific character modules from sys.modules.
        This ensures a clean reload without stale imports.
        """
        # Find all modules in this session's namespace (e.g., "session_abc12345.characters.*")
        prefix = f"{self.module_prefix}."
        character_modules = [
            module_name
            for module_name in sys.modules.keys()
            if module_name.startswith(prefix)
        ]

        # Remove them from sys.modules
        for module_name in character_modules:
            del sys.modules[module_name]
            logger.debug(f"Cleaned up session module: {module_name}")

    async def reload_characters(self, characters_dir: Path) -> CharacterLoadResult:
        """
        Reload characters from a new directory, clearing all previously loaded characters.

        This method:
        1. Cleans up old character modules from sys.modules
        2. Loads new characters from the specified directory
        3. Updates the character registry

        WARNING: This will break active sessions using old characters.
        Sessions should be terminated/reconnected after calling this method.

        Args:
            characters_dir: Path to the new characters directory

        Returns:
            CharacterLoadResult with loaded characters and metrics

        Raises:
            FileNotFoundError: If characters_dir does not exist
        """
        logger.info(f"Reloading characters from: {characters_dir}")

        # Step 1: Clean up old modules
        self._cleanup_character_modules()

        # Step 2: Clear old characters
        old_count = len(self.characters)
        self.characters = {}
        logger.info(f"Cleared {old_count} previously loaded characters")

        # Step 3: Load new characters
        result = await self.load_characters(characters_dir)

        logger.info(
            f"Reload complete: {result.loaded_count} characters loaded from {characters_dir}"
        )

        return result

    async def load_characters(self, characters_dir: Path) -> CharacterLoadResult:
        """
        Load all character files from the specified directory.

        Args:
            characters_dir: Path to characters/ directory

        Returns:
            CharacterLoadResult with loaded characters and metrics

        Raises:
            FileNotFoundError: If characters_dir does not exist
        """
        if not characters_dir.exists():
            raise FileNotFoundError(f"Character directory not found: {characters_dir}")

        start_time = time.time()

        # Files to skip (utility modules, not character definitions)
        # Only skip __init__.py; resources/ subdirectory is excluded separately
        SKIP_FILES = {
            "__init__.py",
        }

        # Discover all .py files (sorted for deterministic order)
        # Skip files in SKIP_FILES and anything in the resources/ subdirectory
        all_py_files = sorted(characters_dir.glob("*.py"))
        character_files = [
            f for f in all_py_files
            if f.name not in SKIP_FILES
        ]
        total_files = len(character_files)

        if total_files == 0:
            logger.warning(
                f"No character files found in {characters_dir}. System will start with empty character list."
            )

        # Load all characters concurrently with session-specific module prefix
        loaded_characters = await asyncio.gather(
            *[_load_single_character(file_path, self.module_prefix) for file_path in character_files]
        )

        # Build character dictionary with duplicate detection
        characters: Dict[str, VoiceSample] = {}
        loaded_count = 0
        error_count = 0

        for character in loaded_characters:
            if character is None:
                error_count += 1
                continue

            # Check for duplicate names (first-loaded-wins)
            if character.name in characters:
                existing_file = characters[character.name]._source_file  # type: ignore
                logger.error(
                    f"{character._source_file}: Duplicate character name '{character.name}' "  # type: ignore
                    f"(first defined in {existing_file}). Skipping."
                )
                CHARACTER_LOAD_ERRORS.labels(error_type="DuplicateName").inc()
                error_count += 1
                continue

            characters[character.name] = character
            loaded_count += 1
            CHARACTER_LOAD_COUNT.inc()

        load_duration = time.time() - start_time

        # Update instance state
        self.characters = characters
        self._current_directory = characters_dir
        self._load_result = CharacterLoadResult(
            characters=characters,
            total_files=total_files,
            loaded_count=loaded_count,
            error_count=error_count,
            load_duration=load_duration,
        )

        # Emit metrics
        CHARACTER_LOAD_DURATION.observe(load_duration)
        CHARACTERS_LOADED.set(loaded_count)

        return self._load_result

    def get_character(self, name_or_voice_path: str) -> VoiceSample | None:
        """
        Get a character by name or voice path.

        Args:
            name_or_voice_path: Character name (e.g., "Fabieng") or voice path (e.g., "unmute-prod-website/fabieng-enhanced-v2.wav")

        Returns:
            VoiceSample if found, None otherwise
        """
        # First try direct name lookup
        character = self.characters.get(name_or_voice_path)
        if character:
            return character

        # If not found, try matching by voice path
        for char in self.characters.values():
            voice_path = char.source.model_dump().get('path_on_server')
            if voice_path == name_or_voice_path:
                return char

        return None

    def cleanup_session_modules(self) -> None:
        """
        Clean up all session-specific modules from sys.modules.

        This should be called when a session ends to prevent memory leaks.
        It removes all character modules loaded for this session from the global
        module registry.

        Called by UnmuteHandler.__aexit__() during session cleanup.
        """
        self._cleanup_character_modules()
        logger.info(f"Session {self.session_id} modules cleaned up")
