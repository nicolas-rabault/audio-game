#!/usr/bin/env python3
"""Simple test script to verify character loading functionality."""

import asyncio
import sys
from pathlib import Path

# Add unmute to path
sys.path.insert(0, str(Path(__file__).parent))

from unmute.tts.character_loader import CharacterManager


async def test_character_loading():
    """Test character loading from story_characters/ directory."""
    print("=" * 60)
    print("Testing Character Loading")
    print("=" * 60)

    manager = CharacterManager()
    characters_dir = Path(__file__).parent / "story_characters"

    print(f"\nCharacters directory: {characters_dir}")
    print(f"Directory exists: {characters_dir.exists()}")

    if characters_dir.exists():
        files = list(characters_dir.glob("*.py"))
        print(f"Character files found: {len(files)}")
        for f in files:
            print(f"  - {f.name}")

    print("\nLoading characters...")
    try:
        result = await manager.load_characters(characters_dir)

        print(f"\n✓ Load complete!")
        print(f"  Total files: {result.total_files}")
        print(f"  Loaded: {result.loaded_count}")
        print(f"  Errors: {result.error_count}")
        print(f"  Duration: {result.load_duration:.3f}s")

        print(f"\nCharacters loaded:")
        for name, character in manager.characters.items():
            print(f"  - {name}")
            print(f"    Source file: {getattr(character, '_source_file', 'N/A')}")
            print(f"    Has PromptGenerator: {hasattr(character, '_prompt_generator')}")
            print(f"    Good: {character.good}")
            print(f"    Source type: {character.source.source_type}")

            # Test prompt generation
            if hasattr(character, "_prompt_generator"):
                try:
                    generator = character._prompt_generator(character.instructions.model_dump())  # type: ignore
                    prompt = generator.make_system_prompt()
                    print(f"    Prompt length: {len(prompt)} chars")
                except Exception as e:
                    print(f"    Prompt generation failed: {e}")

        return True

    except Exception as e:
        print(f"\n✗ Loading failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_empty_directory():
    """Test loading from empty directory."""
    print("\n" + "=" * 60)
    print("Testing Empty Directory")
    print("=" * 60)

    manager = CharacterManager()
    empty_dir = Path(__file__).parent / "test_empty_characters"
    empty_dir.mkdir(exist_ok=True)

    print(f"\nEmpty directory: {empty_dir}")

    try:
        result = await manager.load_characters(empty_dir)
        print(f"\n✓ Empty directory handled gracefully!")
        print(f"  Total files: {result.total_files}")
        print(f"  Characters loaded: {len(manager.characters)}")

        # Clean up
        empty_dir.rmdir()
        return True

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        empty_dir.rmdir()
        return False


async def main():
    """Run all tests."""
    success = True

    success = await test_character_loading() and success
    success = await test_empty_directory() and success

    print("\n" + "=" * 60)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
