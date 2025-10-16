#!/usr/bin/env python3
"""
Script to reload characters from a different directory via the HTTP API.

Usage:
    # Reload from a custom directory
    python scripts/reload_characters.py /path/to/characters

    # Reload the default characters/ directory
    python scripts/reload_characters.py default

    # With custom server URL
    python scripts/reload_characters.py /path/to/characters --url http://localhost:8000
"""

import argparse
import json
import sys

import requests


def reload_characters(directory: str, server_url: str = "http://localhost:8000"):
    """
    Reload characters from a new directory.

    Args:
        directory: Path to the directory containing character files, or "default"
        server_url: Base URL of the server

    Returns:
        Response data from the server
    """
    endpoint = f"{server_url}/v1/characters/reload"

    payload = {"directory": directory}

    print(f"Sending reload request to {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(endpoint, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            print("\n✓ Characters reloaded successfully!")
            print(f"  Directory: {data['directory']}")
            print(f"  Loaded: {data['loaded_count']}/{data['total_files']} characters")
            print(f"  Errors: {data['error_count']}")
            print(f"  Duration: {data['load_duration']:.2f}s")
            print(f"\n  {data['message']}")
            return data
        else:
            print(f"\n✗ Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"  {error_data.get('detail', 'Unknown error')}")
            except json.JSONDecodeError:
                print(f"  {response.text}")
            sys.exit(1)

    except requests.exceptions.ConnectionError:
        print(f"\n✗ Connection error: Could not connect to {server_url}")
        print("  Is the server running?")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"\n✗ Timeout: Server did not respond within 30 seconds")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Reload characters from a different directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reload from custom directory
  python scripts/reload_characters.py /home/user/my-characters

  # Reload default characters/ directory
  python scripts/reload_characters.py default

  # With custom server URL
  python scripts/reload_characters.py /home/user/my-characters --url http://localhost:8080
        """,
    )

    parser.add_argument(
        "directory",
        help='Path to characters directory or "default" to reload the default characters/ directory',
    )

    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Server URL (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    reload_characters(args.directory, args.url)


if __name__ == "__main__":
    main()
