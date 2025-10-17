# Testing Guide: Character Tools Feature

**Feature**: Optional TOOLS Variable for Character Function Calling
**Status**: ✅ Complete - Ready for Testing

## Quick Start Testing

### 1. Start the Server

```bash
cd /home/metab/audio-game
python -m unmute.main_websocket
```

**Expected startup logs**:
```
[INFO] Character Narrator loaded with 1 tools: ['log_story_event']
[INFO] System prompt updated: You are a storytelling narrator...
```

### 2. Manual Tool Execution Test

Test the narrator character's tool directly:

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/metab/audio-game')

from characters.narrator import PromptGenerator, TOOLS

# 1. Verify TOOLS defined
print("✓ TOOLS variable:", TOOLS[0]['function']['name'])

# 2. Test get_tools()
pg = PromptGenerator({'instruction_prompt': 'test', 'language': 'en'})
tools = pg.get_tools()
print("✓ get_tools() returns:", len(tools), "tools")

# 3. Test handle_tool_call()
result = pg.handle_tool_call('log_story_event', {
    'event': 'Test story event',
    'importance': 'high'
})
print("✓ handle_tool_call() result:", result)
EOF
```

**Expected output**:
```
✓ TOOLS variable: log_story_event
✓ get_tools() returns: 1 tools
[NARRATOR EVENT] [HIGH] Test story event
✓ handle_tool_call() result: Logged story event: Test story event
```

### 3. Character Loading Test

Verify character loads correctly with tools:

```bash
python3 << 'EOF'
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, '/home/metab/audio-game')

from unmute.tts.character_loader import CharacterManager

async def test_loading():
    cm = CharacterManager()
    result = await cm.load_characters(Path('/home/metab/audio-game/characters'))

    narrator = cm.get_character('Narrator')
    if narrator:
        print("✓ Character loaded:", narrator.name)
        print("✓ Has tools:", hasattr(narrator, '_tools'))
        print("✓ Tools count:", len(narrator._tools) if narrator._tools else 0)
        print("✓ Tool validators:", list(narrator._tool_validators.keys()) if hasattr(narrator, '_tool_validators') else [])
    else:
        print("✗ Character not found")

asyncio.run(test_loading())
EOF
```

**Expected output**:
```
✓ Character loaded: Narrator
✓ Has tools: True
✓ Tools count: 1
✓ Tool validators: ['log_story_event']
```

### 4. Tool Execution Engine Test

Test the tool executor directly:

```bash
python3 << 'EOF'
import sys
import asyncio
sys.path.insert(0, '/home/metab/audio-game')

from unmute.llm.tool_executor import execute_tool, create_parameter_model
from characters.narrator import PromptGenerator

async def test_executor():
    # Setup
    pg = PromptGenerator({'instruction_prompt': 'test'})
    tool_name = 'log_story_event'
    tool_input_json = '{"event": "Executor test", "importance": "medium"}'

    # Create validator
    params = {
        "type": "object",
        "properties": {
            "event": {"type": "string"},
            "importance": {"type": "string", "enum": ["low", "medium", "high"]}
        },
        "required": ["event"]
    }
    validator = create_parameter_model(tool_name, params)
    validators = {tool_name: validator}

    # Execute
    result = await execute_tool(pg, tool_name, tool_input_json, validators, "Narrator")
    print("✓ Tool execution result:", result)

asyncio.run(test_executor())
EOF
```

**Expected output**:
```
[NARRATOR EVENT] [MEDIUM] Executor test
✓ Tool execution result: Logged story event: Executor test
```

### 5. Integration Test (End-to-End)

This requires a running LLM server and WebSocket client.

**Prerequisites**:
- LLM server running (vLLM with function calling support)
- WebSocket client connected

**Test Scenario**:
1. Connect to WebSocket server
2. Send: `{"type": "session_update", "session": {"voice": "Narrator"}}`
3. Send: `{"type": "user_message", "message": "Tell me a story about a dragon"}`
4. **Expected**:
   - LLM generates narrative
   - Tool `log_story_event` called automatically (if LLM decides)
   - Terminal shows: `[NARRATOR EVENT] [MEDIUM] Story begun: Dragon tale`
   - LLM continues with full response

**Check logs**:
```bash
tail -f logs/server.log | grep -E "tool|Tool|NARRATOR EVENT"
```

## Validation Checklist

### Character Loading
- [ ] Server starts without errors
- [ ] Narrator character loads successfully
- [ ] Log shows: "Loaded with 1 tools: ['log_story_event']"
- [ ] No validation errors in logs

### Tool Execution
- [ ] Direct handle_tool_call() works
- [ ] Terminal logging appears correctly
- [ ] Tool returns success message
- [ ] No exceptions raised

### Tool Validation
- [ ] Valid parameters accepted
- [ ] Invalid parameters rejected with clear errors
- [ ] Required parameters enforced
- [ ] Enum constraints work (importance: low/medium/high)

### Error Handling
- [ ] Invalid JSON → "Error: Invalid JSON..."
- [ ] Missing required param → "Error: Invalid parameter..."
- [ ] Unknown tool → "Error: Unknown tool..."
- [ ] Timeout (if tool takes >100ms) → "Error: Tool execution timed out"

### Metrics
- [ ] Metrics endpoint accessible: `curl http://localhost:8000/metrics`
- [ ] `character_tool_calls_total` present
- [ ] `character_tool_errors_total` present
- [ ] `character_tool_latency_seconds` present

## Performance Testing

### Baseline (No Tools)

```bash
# Create a test character without tools
cp characters/narrator.py characters/narrator_no_tools.py
# Remove TOOLS, get_tools(), handle_tool_call() from narrator_no_tools.py

# Run loadtest
python -m unmute.loadtest.loadtest_client \
    --character Narrator \
    --n-workers 4 \
    --duration 60

# Record p50, p95, p99 latencies
```

### With Tools

```bash
# Run loadtest with tool-enabled narrator
python -m unmute.loadtest.loadtest_client \
    --character Narrator \
    --n-workers 4 \
    --duration 60

# Record p50, p95, p99 latencies
# Compare with baseline - should be <10% increase
```

## Debugging

### Check Character Loading Errors

```bash
grep -i "error.*character\|narrator" logs/server.log
```

### Check Tool Execution

```bash
grep -i "tool.*execut\|executing tool" logs/server.log
```

### Check Tool Call Detection

```bash
grep -i "detected.*tool call" logs/server.log
```

### Monitor Metrics

```bash
# Real-time tool metrics
watch -n 1 'curl -s http://localhost:8000/metrics | grep character_tool'
```

## Common Issues

### Issue: Character doesn't load

**Symptoms**: No log about tools, character not available

**Solutions**:
- Check file exists: `ls -la characters/narrator.py`
- Check syntax: `python3 -m py_compile characters/narrator.py`
- Check logs: `grep "narrator" logs/server.log`

### Issue: Tools not called

**Symptoms**: Conversation works but no tool execution

**Possible Causes**:
- LLM doesn't support function calling (check vLLM model)
- Tools not passed to LLM (check "Using X tools for LLM" log)
- LLM chooses not to call tool (this is normal - not all responses need tools)

**Debug**:
- Check VLLMStream receives tools: Add debug logging
- Try prompts that clearly need tool: "Log this important event: User asked about dragons"

### Issue: Tool execution fails

**Symptoms**: Error messages in response or logs

**Solutions**:
- Check handle_tool_call() implementation
- Verify tool_name matches TOOLS definition
- Check parameters match schema
- Ensure execution completes in <100ms

## Success Criteria

✅ **Feature is working** if:
1. Character loads with tools (log message)
2. Direct tool execution works (manual test)
3. LLM can call tools (integration test)
4. Tool results appear in conversation
5. Metrics are collected
6. No crashes or errors

## Next Steps After Testing

1. **If all tests pass**:
   - Document actual performance metrics
   - Deploy to staging environment
   - Monitor metrics in production
   - Gather user feedback

2. **If tests fail**:
   - Review error logs
   - Check specific failure point
   - Consult [FINAL_IMPLEMENTATION_SUMMARY.md](FINAL_IMPLEMENTATION_SUMMARY.md)
   - File bug report with reproduction steps

## Contact

For issues or questions, see:
- [quickstart.md](quickstart.md) - Developer guide
- [CLAUDE.md](../../CLAUDE.md) - Examples and guidelines
- [FINAL_IMPLEMENTATION_SUMMARY.md](FINAL_IMPLEMENTATION_SUMMARY.md) - Complete implementation details
