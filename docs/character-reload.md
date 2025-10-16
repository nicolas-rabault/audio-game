# Dynamic Character Reloading

This document describes how to dynamically reload characters from different directories without restarting the server.

## Overview

The character reload feature allows you to:
- Switch between different character sets on a running server
- Load characters from any directory on the filesystem
- Return to the default `characters/` directory
- Automatically terminate active sessions when reloading

## How It Works

### Architecture

1. **CharacterManager.reload_characters()**: Core method that:
   - Cleans up old character modules from `sys.modules`
   - Clears the previous character registry
   - Loads all `.py` files from the new directory
   - Validates and registers new characters

2. **HTTP Endpoint**: `POST /v1/characters/reload`
   - Accepts a directory path or "default"
   - Triggers the reload process
   - Terminates all active WebSocket sessions
   - Returns reload statistics

3. **Session Management**:
   - All active WebSocket connections are tracked
   - On reload, sessions receive a graceful disconnect message
   - Clients must reconnect to use new characters

### Session Impact

**WARNING**: Reloading characters will forcibly disconnect all active WebSocket sessions.

- Active conversations will be terminated
- Clients will receive a fatal error message: "Characters reloaded from {path}. Please reconnect."
- WebSocket close code: 1012 (Service Restart)
- Clients must reconnect to establish a new session with the new character set

## Usage

### HTTP API

#### Endpoint: `POST /v1/characters/reload`

**Request Body**:
```json
{
  "directory": "/absolute/path/to/characters"
}
```

Or to reload the default directory:
```json
{
  "directory": "default"
}
```

**Success Response** (200):
```json
{
  "success": true,
  "directory": "/home/user/my-characters",
  "total_files": 10,
  "loaded_count": 9,
  "error_count": 1,
  "load_duration": 0.45,
  "message": "Successfully loaded 9 characters from /home/user/my-characters"
}
```

**Error Responses**:
- **404**: Directory not found
- **400**: Path is not a directory
- **500**: Unexpected error during reload

### Command-Line Script

A convenience script is provided at [scripts/reload_characters.py](../scripts/reload_characters.py).

#### Basic Usage

```bash
# Reload from a custom directory
python scripts/reload_characters.py /path/to/my-characters

# Reload the default characters/ directory
python scripts/reload_characters.py default

# With custom server URL
python scripts/reload_characters.py /path/to/characters --url http://localhost:8080
```

#### Example Output

```
Sending reload request to http://localhost:8000/v1/characters/reload
Payload: {
  "directory": "/home/user/my-characters"
}

✓ Characters reloaded successfully!
  Directory: /home/user/my-characters
  Loaded: 9/10 characters
  Errors: 1
  Duration: 0.45s

  Successfully loaded 9 characters from /home/user/my-characters
```

### Using curl

```bash
# Reload from custom directory
curl -X POST http://localhost:8000/v1/characters/reload \
  -H "Content-Type: application/json" \
  -d '{"directory": "/home/user/my-characters"}'

# Reload default directory
curl -X POST http://localhost:8000/v1/characters/reload \
  -H "Content-Type: application/json" \
  -d '{"directory": "default"}'
```

## Use Cases

### 1. Multiple Character Sets

Organize characters into different directories for different purposes:

```
/home/user/characters-production/    # Production characters
/home/user/characters-testing/       # Test characters
/home/user/characters-experimental/  # Experimental characters
```

Switch between them as needed:

```bash
python scripts/reload_characters.py /home/user/characters-testing
# Test your new characters...
python scripts/reload_characters.py default  # Back to production
```

### 2. Hot Character Development

Develop characters in a separate directory and reload without server restart:

```bash
# Edit characters in ~/dev/my-new-character/
# When ready to test:
python scripts/reload_characters.py ~/dev/my-new-character

# Continue editing and reload as needed
```

### 3. Context-Specific Character Sets

Load different character sets based on context:
- Educational characters for training sessions
- Gaming characters for game mode
- Professional characters for business use

## Path Validation

The reload endpoint accepts:
- **Absolute paths**: e.g., `/home/user/my-characters`, `/opt/characters`
- **"default" keyword**: Reloads the default `characters/` directory

**Requirements**:
- Path must exist and be a directory
- Directory must be readable by the server process
- Character files must be valid Python modules (`.py` files)

**No restrictions** on which directories can be loaded - trust is placed in the caller.

## Character File Requirements

Character files in the new directory must follow the standard format:

**Required attributes**:
- `CHARACTER_NAME` (str)
- `VOICE_SOURCE` (dict)
- `INSTRUCTIONS` (dict)
- `PromptGenerator` class with:
  - `__init__(self, instructions)` method
  - `make_system_prompt(self) -> str` method

**Optional attributes**:
- `METADATA` (dict) - e.g., `{"good": True, "comment": "..."}`

See [characters/README.md](../characters/README.md) for full character format documentation.

## Technical Details

### Module Cleanup

When reloading:
1. All modules in the `characters.*` namespace are removed from `sys.modules`
2. This ensures clean imports without stale references
3. New character files are loaded fresh using `importlib`

### Concurrent Loading

Character files are loaded concurrently using `asyncio.gather()` for performance.

### Error Handling

- Individual character loading errors are logged but don't block others
- Prometheus metrics track errors by type (ImportError, ValidationError, etc.)
- Duplicate character names: first-loaded-wins strategy
- Failed character files are excluded from the final character set

### Metrics

The following Prometheus metrics are updated during reload:
- `CHARACTER_LOAD_COUNT`: Total successfully loaded characters
- `CHARACTER_LOAD_ERRORS`: Count by error type
- `CHARACTER_LOAD_DURATION`: Time to load all characters (histogram)
- `CHARACTERS_LOADED`: Current number of loaded characters (gauge)

## Troubleshooting

### Characters not loading

Check server logs for errors:
```bash
grep "character" logs/server.log
```

Common issues:
- Missing required attributes (CHARACTER_NAME, VOICE_SOURCE, etc.)
- Syntax errors in character files
- Import errors (missing dependencies)
- Invalid PromptGenerator class

### WebSocket clients not reconnecting

Ensure clients handle WebSocket close code 1012 (Service Restart) and automatically reconnect.

The error message sent before disconnect: "Characters reloaded from {path}. Please reconnect."

### Permission denied

Ensure the server process has read access to the character directory and files:
```bash
ls -la /path/to/characters
```

## Security Considerations

- **No path restrictions**: Any absolute path can be loaded
- **Trust required**: Assumes the caller is authorized to reload characters
- **Code execution**: Character files are Python modules that execute on import
- **Recommendation**: Add authentication to the `/v1/characters/reload` endpoint in production

## Future Enhancements

Possible improvements for future versions:

1. **Path whitelist**: Restrict reloading to pre-configured directories
2. **Authentication**: Require API key or auth token for reload endpoint
3. **Graceful session handling**: Option to preserve active sessions
4. **Character hot-reload**: Reload individual characters without affecting others
5. **WebSocket reload command**: Trigger reload via WebSocket message (for characters with function calling)
6. **Reload history**: Track reload events and allow rollback

## Related Documentation

- [Character File Format](../characters/README.md)
- [Character Creation Guide](../specs/003-i-want-the/quickstart.md) (if exists)
- [API Documentation](../README.md)
