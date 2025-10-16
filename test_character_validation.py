#!/usr/bin/env python3
"""Test character validation errors."""

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

from unmute.tts.character_loader import CharacterManager


async def test_missing_character_name():
    """Test that missing CHARACTER_NAME is rejected."""
    print("\n" + "=" * 60)
    print("Test: Missing CHARACTER_NAME")
    print("=" * 60)

    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        test_file = tmppath / "bad-character.py"

        # Character missing CHARACTER_NAME
        test_file.write_text("""
VOICE_SOURCE = {"source_type": "file", "path_on_server": "test.wav"}
INSTRUCTIONS = {"type": "smalltalk"}

class PromptGenerator:
    def __init__(self, instructions):
        pass
    def make_system_prompt(self):
        return "test"
""")

        manager = CharacterManager()
        result = await manager.load_characters(tmppath)

        if result.error_count == 1 and result.loaded_count == 0:
            print("✓ Missing CHARACTER_NAME correctly rejected")
            return True
        else:
            print(f"✗ Expected 1 error, got {result.error_count}")
            return False


async def test_missing_voice_source():
    """Test that missing VOICE_SOURCE is rejected."""
    print("\n" + "=" * 60)
    print("Test: Missing VOICE_SOURCE")
    print("=" * 60)

    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        test_file = tmppath / "bad-character.py"

        test_file.write_text("""
CHARACTER_NAME = "Test"
INSTRUCTIONS = {"type": "smalltalk"}

class PromptGenerator:
    def __init__(self, instructions):
        pass
    def make_system_prompt(self):
        return "test"
""")

        manager = CharacterManager()
        result = await manager.load_characters(tmppath)

        if result.error_count == 1 and result.loaded_count == 0:
            print("✓ Missing VOICE_SOURCE correctly rejected")
            return True
        else:
            print(f"✗ Expected 1 error, got {result.error_count}")
            return False


async def test_missing_instructions():
    """Test that missing INSTRUCTIONS is rejected."""
    print("\n" + "=" * 60)
    print("Test: Missing INSTRUCTIONS")
    print("=" * 60)

    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        test_file = tmppath / "bad-character.py"

        test_file.write_text("""
CHARACTER_NAME = "Test"
VOICE_SOURCE = {"source_type": "file", "path_on_server": "test.wav"}

class PromptGenerator:
    def __init__(self, instructions):
        pass
    def make_system_prompt(self):
        return "test"
""")

        manager = CharacterManager()
        result = await manager.load_characters(tmppath)

        if result.error_count == 1 and result.loaded_count == 0:
            print("✓ Missing INSTRUCTIONS correctly rejected")
            return True
        else:
            print(f"✗ Expected 1 error, got {result.error_count}")
            return False


async def test_missing_prompt_generator():
    """Test that missing PromptGenerator class is rejected."""
    print("\n" + "=" * 60)
    print("Test: Missing PromptGenerator")
    print("=" * 60)

    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        test_file = tmppath / "bad-character.py"

        test_file.write_text("""
CHARACTER_NAME = "Test"
VOICE_SOURCE = {"source_type": "file", "path_on_server": "test.wav"}
INSTRUCTIONS = {"type": "smalltalk"}
""")

        manager = CharacterManager()
        result = await manager.load_characters(tmppath)

        if result.error_count == 1 and result.loaded_count == 0:
            print("✓ Missing PromptGenerator correctly rejected")
            return True
        else:
            print(f"✗ Expected 1 error, got {result.error_count}")
            return False


async def test_character_attributes():
    """Test that loaded characters have correct attributes."""
    print("\n" + "=" * 60)
    print("Test: Character Attributes")
    print("=" * 60)

    manager = CharacterManager()
    characters_dir = Path(__file__).parent / "characters"
    result = await manager.load_characters(characters_dir)

    if result.loaded_count > 0:
        sample_char = list(manager.characters.values())[0]

        has_source_file = hasattr(sample_char, "_source_file")
        has_prompt_gen = hasattr(sample_char, "_prompt_generator")

        # Test TTS access
        tts_accessible = hasattr(sample_char.source, "path_on_server") or hasattr(
            sample_char.source, "url"
        )

        # Test LLM access
        if has_prompt_gen:
            try:
                generator = sample_char._prompt_generator(sample_char.instructions.model_dump())  # type: ignore
                llm_accessible = callable(getattr(generator, "make_system_prompt", None))
            except Exception:
                llm_accessible = False
        else:
            llm_accessible = False

        print(f"  _source_file attribute: {'✓' if has_source_file else '✗'}")
        print(f"  _prompt_generator attribute: {'✓' if has_prompt_gen else '✗'}")
        print(f"  TTS can access voice path: {'✓' if tts_accessible else '✗'}")
        print(f"  LLM can access prompt generator: {'✓' if llm_accessible else '✗'}")

        if has_source_file and has_prompt_gen and tts_accessible and llm_accessible:
            print("\n✓ All character attributes present and accessible")
            return True
        else:
            print("\n✗ Some attributes missing or inaccessible")
            return False
    else:
        print("✗ No characters loaded")
        return False


async def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Character Validation Tests")
    print("=" * 60)

    tests = [
        test_missing_character_name(),
        test_missing_voice_source(),
        test_missing_instructions(),
        test_missing_prompt_generator(),
        test_character_attributes(),
    ]

    results = await asyncio.gather(*tests)

    print("\n" + "=" * 60)
    if all(results):
        print("✓ All validation tests passed!")
        return 0
    else:
        print("✗ Some validation tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
