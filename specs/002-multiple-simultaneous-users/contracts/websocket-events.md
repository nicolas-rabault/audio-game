# WebSocket Event Contracts: Per-Session Character Management

**Feature**: 002-multiple-simultaneous-users
**Date**: 2025-10-16
**Protocol**: OpenAI Realtime API (Extended)

## Overview

This document defines the new WebSocket events for per-session character management. These events extend the existing OpenAI Realtime API protocol.

---

## Client→Server Events

### `session.characters.reload`

Requests the server to reload characters from a different directory for this session only.

**Direction**: Client → Server

**Schema**:
```json
{
  "type": "session.characters.reload",
  "directory": "<absolute_path_or_default>"
}
```

**Fields**:

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `type` | `string` | Yes | Event type identifier | `"session.characters.reload"` |
| `directory` | `string` | Yes | Absolute path to character directory or "default" | `"/home/user/custom-characters"` or `"default"` |

**Validation Rules**:
- `directory`: Must be non-empty string
- Special value `"default"` reloads the server's default `characters/` directory
- Absolute paths must start with `/` (Unix) or drive letter (Windows)

**Behavior**:
1. Server validates directory exists and is readable
2. Server clears current session's character registry
3. Server loads characters from specified directory
4. Server responds with `session.characters.reloaded` event
5. If mid-conversation, current conversation is gracefully ended

**Error Cases**:
- Directory does not exist → Error event with type "error"
- Directory not readable → Error event with type "error"
- No valid characters in directory → Error event with type "error"
- Invalid directory format → ValidationError (400-equivalent)

**Example Request**:
```json
{
  "type": "session.characters.reload",
  "directory": "/home/user/my-characters"
}
```

**Example Request (Default)**:
```json
{
  "type": "session.characters.reload",
  "directory": "default"
}
```

---

### `session.characters.list`

Requests the current list of characters available in this session.

**Direction**: Client → Server

**Schema**:
```json
{
  "type": "session.characters.list"
}
```

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `string` | Yes | Event type identifier |

**Behavior**:
1. Server returns `session.characters.listed` event with current character registry

**Example Request**:
```json
{
  "type": "session.characters.list"
}
```

---

## Server→Client Events

### `session.characters.reloaded`

Confirms that characters have been successfully reloaded.

**Direction**: Server → Client

**Schema**:
```json
{
  "type": "session.characters.reloaded",
  "directory": "<absolute_path>",
  "loaded_count": <integer>,
  "error_count": <integer>,
  "total_files": <integer>,
  "characters": [
    {
      "name": "<character_name>",
      "good": <boolean>
    }
  ]
}
```

**Fields**:

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `type` | `string` | Yes | Event type identifier | `"session.characters.reloaded"` |
| `directory` | `string` | Yes | Directory that was loaded | `"/home/user/custom-characters"` |
| `loaded_count` | `integer` | Yes | Number of successfully loaded characters | `9` |
| `error_count` | `integer` | Yes | Number of failed character loads | `1` |
| `total_files` | `integer` | Yes | Total .py files discovered | `10` |
| `characters` | `array` | Yes | List of loaded characters | `[{"name": "Charles", "good": true}, ...]` |

**Character Object**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Character display name |
| `good` | `boolean` | No | Is character production-ready (may be null) |

**Behavior**:
- Sent after successful `session.characters.reload` processing
- Includes summary statistics for client UI updates
- Client should refresh character selection UI with new list

**Example Response (Success)**:
```json
{
  "type": "session.characters.reloaded",
  "directory": "/home/user/custom-characters",
  "loaded_count": 5,
  "error_count": 0,
  "total_files": 5,
  "characters": [
    {"name": "Custom Character 1", "good": true},
    {"name": "Custom Character 2", "good": true},
    {"name": "Test Character", "good": false},
    {"name": "Experimental Bot", "good": null},
    {"name": "Demo Character", "good": true}
  ]
}
```

**Example Response (Partial Failure)**:
```json
{
  "type": "session.characters.reloaded",
  "directory": "/home/user/mixed-characters",
  "loaded_count": 8,
  "error_count": 2,
  "total_files": 10,
  "characters": [
    {"name": "Charles", "good": true},
    {"name": "Dev News", "good": true},
    ...
  ]
}
```

---

### `session.characters.listed`

Provides the current character list for this session.

**Direction**: Server → Client

**Schema**:
```json
{
  "type": "session.characters.listed",
  "directory": "<current_directory>",
  "character_count": <integer>,
  "characters": [
    {
      "name": "<character_name>",
      "good": <boolean>,
      "comment": "<optional_comment>"
    }
  ]
}
```

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `string` | Yes | Event type identifier |
| `directory` | `string` | Yes | Currently loaded directory |
| `character_count` | `integer` | Yes | Number of characters |
| `characters` | `array` | Yes | List of characters |

**Example Response**:
```json
{
  "type": "session.characters.listed",
  "directory": "/home/metab/audio-game/characters",
  "character_count": 9,
  "characters": [
    {"name": "Charles", "good": true, "comment": null},
    {"name": "Dev (news)", "good": true, "comment": null},
    {"name": "Watercooler", "good": true, "comment": "Casual chat"}
  ]
}
```

---

### `error` (Extended)

Error event for character reload failures.

**Direction**: Server → Client

**Schema** (Standard):
```json
{
  "type": "error",
  "error": {
    "type": "server_error",
    "code": "<error_code>",
    "message": "<human_readable_message>",
    "param": null
  }
}
```

**Character-Related Error Codes**:

| Code | Message | When |
|------|---------|------|
| `directory_not_found` | "Character directory not found: {path}" | Directory doesn't exist |
| `directory_not_readable` | "Character directory is not readable: {path}" | Permission denied |
| `no_valid_characters` | "No valid characters found in directory: {path}" | All character files failed validation |
| `invalid_directory_format` | "Invalid directory format: {path}" | Path format is invalid |

**Example (Directory Not Found)**:
```json
{
  "type": "error",
  "error": {
    "type": "server_error",
    "code": "directory_not_found",
    "message": "Character directory not found: /invalid/path",
    "param": null
  }
}
```

**Example (No Valid Characters)**:
```json
{
  "type": "error",
  "error": {
    "type": "server_error",
    "code": "no_valid_characters",
    "message": "No valid characters found in directory: /home/user/broken-chars",
    "param": null
  }
}
```

---

## Event Flow Diagrams

### Successful Character Reload

```
Client                          Server
  |                               |
  |─session.characters.reload──>  |
  |  {directory: "/custom"}       |
  |                               |
  |                        [Validate directory]
  |                        [Clean old modules]
  |                        [Load new characters]
  |                        [Update registry]
  |                               |
  |<─session.characters.reloaded─|
  |  {loaded_count: 5}            |
  |                               |
```

### Failed Character Reload

```
Client                          Server
  |                               |
  |─session.characters.reload──>  |
  |  {directory: "/invalid"}      |
  |                               |
  |                        [Validate directory]
  |                        [Error: not found]
  |                               |
  |<─error─────────────────────── |
  |  {code: "directory_not_found"}|
  |                               |
```

### List Characters

```
Client                          Server
  |                               |
  |─session.characters.list────>  |
  |                               |
  |                        [Read character registry]
  |                               |
  |<─session.characters.listed──  |
  |  {characters: [...]}          |
  |                               |
```

---

## Pydantic Models (Python Implementation)

### Client Events

```python
from pydantic import BaseModel, Field
from typing import Literal

class SessionCharactersReload(BaseModel):
    """Client requests to reload characters from a new directory."""
    type: Literal["session.characters.reload"] = "session.characters.reload"
    directory: str = Field(
        ...,
        description="Absolute path to character directory or 'default'"
    )

class SessionCharactersList(BaseModel):
    """Client requests current character list."""
    type: Literal["session.characters.list"] = "session.characters.list"
```

### Server Events

```python
class CharacterInfo(BaseModel):
    """Character summary for client display."""
    name: str
    good: bool | None = None
    comment: str | None = None

class SessionCharactersReloaded(BaseModel):
    """Server confirms characters reloaded."""
    type: Literal["session.characters.reloaded"] = "session.characters.reloaded"
    directory: str
    loaded_count: int
    error_count: int
    total_files: int
    characters: list[CharacterInfo]

class SessionCharactersListed(BaseModel):
    """Server provides current character list."""
    type: Literal["session.characters.listed"] = "session.characters.listed"
    directory: str
    character_count: int
    characters: list[CharacterInfo]
```

---

## Backward Compatibility

### For Clients Not Implementing These Events

- **Existing behavior preserved**: Characters load at session startup (default directory)
- **No breaking changes**: Clients can ignore new event types
- **Graceful degradation**: Users can still disconnect/reconnect to get different characters

### For Servers

- **New events are additive**: Existing OpenAI Realtime API events unchanged
- **No protocol version required**: Clients can discover support via trial (send event, check response)

---

## Security Considerations

### Path Validation

**Risks**:
- Path traversal attacks (e.g., `"../../sensitive/data"`)
- Loading code from untrusted directories
- Reading arbitrary files on server

**Mitigations**:
- Validate `directory` is absolute path (no relative paths)
- Check path exists and is readable before loading
- Restrict to pre-configured allowed directories (optional, can be added later)
- Trust character files (same trust level as current implementation)

**Future Enhancement**: Add `ALLOWED_CHARACTER_DIRECTORIES` config to whitelist permitted paths.

---

## Testing Strategy

### Unit Tests

Test Pydantic models serialize/deserialize correctly:
```python
def test_session_characters_reload_event():
    event = SessionCharactersReload(
        directory="/custom/characters"
    )
    json_str = event.model_dump_json()
    parsed = SessionCharactersReload.model_validate_json(json_str)
    assert parsed.directory == "/custom/characters"
```

### Integration Tests

Test WebSocket event handling:
1. Connect WebSocket client
2. Send `session.characters.reload` event
3. Verify `session.characters.reloaded` response
4. Verify character list updated

### Error Handling Tests

Test error cases:
1. Invalid directory → `error` event
2. Directory with no valid characters → `error` event
3. Concurrent reload requests → Second request queued or rejected

---

## Implementation Checklist

- [ ] Add Pydantic models to `openai_realtime_api_events.py`
- [ ] Update `ClientEventAdapter` to include new event types
- [ ] Add event handler in `_run_route()` for `session.characters.reload`
- [ ] Add event handler for `session.characters.list`
- [ ] Implement character reload logic in `UnmuteHandler`
- [ ] Add error handling with appropriate error codes
- [ ] Update WebSocket message routing
- [ ] Add unit tests for new events
- [ ] Add integration tests for reload flow
- [ ] Update API documentation (if exists)

---

## Summary

These WebSocket events enable:
- ✅ **Per-session character reloading** without disconnection
- ✅ **Character discovery** via list endpoint
- ✅ **Clear error feedback** for invalid operations
- ✅ **Backward compatibility** with existing clients
- ✅ **Extensible** for future character management features
