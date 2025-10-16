#!/usr/bin/env python3
"""
Migration script to convert voices.yaml to self-contained character files.

This script reads the existing voices.yaml file and generates individual Python
character files in the characters/ directory. Each character file contains
all the necessary data (name, voice source, instructions, metadata) and prompt
generation logic in a single, self-contained file.
"""

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parents[1]))

from ruamel.yaml import YAML

# Prompt generator templates for each instruction type
PROMPT_GENERATOR_TEMPLATES = {
    "constant": """class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import ConstantInstructions

        inst = ConstantInstructions(
            text=self.instructions.get("text", ""),
            language=self.instructions.get("language"),
        )
        return inst.make_system_prompt()""",
    "smalltalk": """class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import SmalltalkInstructions

        inst = SmalltalkInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()""",
    "quiz_show": """class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import QuizShowInstructions

        inst = QuizShowInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()""",
    "news": """class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import NewsInstructions

        inst = NewsInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()""",
    "guess_animal": """class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import GuessAnimalInstructions

        inst = GuessAnimalInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()""",
    "unmute_explanation": """class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import UnmuteExplanationInstructions

        inst = UnmuteExplanationInstructions()
        return inst.make_system_prompt()""",
}

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """
    Convert character name to valid Python filename.

    Args:
        name: Character name

    Returns:
        Sanitized filename with .py extension
    """
    # Convert to lowercase, replace spaces with hyphens
    filename = name.lower().replace(" ", "-")

    # Remove any characters that aren't alphanumeric, hyphens, or underscores
    filename = "".join(c for c in filename if c.isalnum() or c in "-_")

    return filename + ".py"


def generate_character_file(voice: dict, output_dir: Path, name_counts: dict) -> tuple[str, str]:
    """
    Generate a character file from a voice dictionary.

    Args:
        voice: Voice data from voices.yaml
        output_dir: Directory to write character files
        name_counts: Dict tracking name occurrences for duplicate handling

    Returns:
        Tuple of (filename, file_content)
    """
    name = voice.get("name", "Unknown")

    # Handle duplicate names
    if name in name_counts:
        name_counts[name] += 1
        original_name = name
        name = f"{name} {name_counts[name]}"
        logger.warning(
            f"Duplicate character name '{original_name}' found. "
            f"Renaming to '{name}' (occurrence #{name_counts[original_name]})"
        )
    else:
        name_counts[name] = 1

    filename = sanitize_filename(name)

    # Extract data
    instructions = voice.get("instructions", {})
    instruction_type = instructions.get("type", "constant")
    source = voice.get("source", {})
    good = voice.get("good")
    comment = voice.get("comment")

    # Build file content
    content_parts = []

    # Docstring
    content_parts.append(f'"""Character: {name}')
    if comment:
        content_parts.append(f" - {comment}")
    content_parts.append('"""\n')

    # CHARACTER_NAME
    content_parts.append(f'CHARACTER_NAME = "{name}"\n')

    # VOICE_SOURCE
    content_parts.append(f"VOICE_SOURCE = {source!r}\n")

    # INSTRUCTIONS
    content_parts.append(f"INSTRUCTIONS = {instructions!r}\n")

    # METADATA
    metadata = {"good": good, "comment": comment}
    content_parts.append(f"METADATA = {metadata!r}\n")

    # PromptGenerator
    template = PROMPT_GENERATOR_TEMPLATES.get(instruction_type)
    if template:
        content_parts.append(f"\n{template}\n")
    else:
        logger.warning(
            f"Unknown instruction type '{instruction_type}' for character '{name}'. "
            f"Using 'constant' template."
        )
        content_parts.append(f"\n{PROMPT_GENERATOR_TEMPLATES['constant']}\n")

    content = "\n".join(content_parts)

    return filename, content


def migrate_voices(
    yaml_path: Path, output_dir: Path, dry_run: bool = False
) -> tuple[int, int, int]:
    """
    Migrate voices from YAML file to individual Python files.

    Args:
        yaml_path: Path to voices.yaml file
        output_dir: Directory to write character files
        dry_run: If True, don't write files (just preview)

    Returns:
        Tuple of (files_created, files_skipped, errors)
    """
    logger.info(f"Reading voices from {yaml_path}")

    # Load YAML
    yaml = YAML()
    with yaml_path.open() as f:
        voices = yaml.load(f)

    if not voices:
        logger.warning("No voices found in YAML file")
        return 0, 0, 0

    logger.info(f"Found {len(voices)} voices in YAML file")

    # Track statistics
    files_created = 0
    files_skipped = 0
    errors = 0
    name_counts: dict[str, int] = {}

    # Create output directory if needed
    if not dry_run and not output_dir.exists():
        output_dir.mkdir(parents=True)
        logger.info(f"Created output directory: {output_dir}")

    # Generate files
    for i, voice in enumerate(voices, 1):
        try:
            name = voice.get("name", f"character_{i}")
            filename, content = generate_character_file(voice, output_dir, name_counts)
            file_path = output_dir / filename

            if dry_run:
                logger.info(f"[DRY RUN] Would create: {filename}")
                logger.debug(f"Content preview:\n{content[:200]}...")
            else:
                file_path.write_text(content)
                logger.info(f"Created: {filename}")

            files_created += 1

        except Exception as e:
            logger.error(f"Failed to migrate voice #{i}: {e}")
            errors += 1

    return files_created, files_skipped, errors


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate voices.yaml to self-contained character files"
    )
    parser.add_argument(
        "--yaml-path",
        type=Path,
        default=Path("voices.yaml"),
        help="Path to voices.yaml file (default: voices.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("characters"),
        help="Output directory for character files (default: characters)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview files without writing them",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    # Also log to file
    log_file = Path("migration.log")
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(file_handler)

    logger.info("=" * 60)
    logger.info("Voice Migration Script")
    logger.info("=" * 60)
    logger.info(f"YAML file: {args.yaml_path}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 60)

    # Check if YAML file exists
    if not args.yaml_path.exists():
        logger.error(f"YAML file not found: {args.yaml_path}")
        return 1

    # Run migration
    try:
        files_created, files_skipped, errors = migrate_voices(
            args.yaml_path, args.output_dir, args.dry_run
        )

        logger.info("=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        logger.info(f"Files created: {files_created}")
        logger.info(f"Files skipped: {files_skipped}")
        logger.info(f"Errors: {errors}")
        logger.info(f"Migration log: {log_file.absolute()}")
        logger.info("=" * 60)

        if errors > 0:
            logger.warning("Migration completed with errors")
            return 1
        else:
            logger.info("✓ Migration completed successfully!")
            return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
