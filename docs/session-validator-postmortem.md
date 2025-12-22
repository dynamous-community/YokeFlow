# Session Validator Post-Mortem

## Date
December 22, 2024

## Summary
Attempted to add session validators to prevent issues seen in Session 18 (wrong tool usage, context compaction). The implementation had a critical bug in message counting that caused false emergency stops.

## What We Tried

### Recommendation 1: Docker Mode Tool Validator ✅
**Status**: Worked correctly

Blocked `Bash` tool usage in Docker mode, forcing use of `mcp__task-manager__bash_docker`.

**Implementation**:
- Hook registered with `matcher="*"`
- Checked `is_docker_mode()` and `tool_name == "Bash"`
- Returned `{"decision": "block"}` with clear error message

**Result**: This part worked correctly. No issues detected.

### Recommendation 2: Message Count Validator ❌
**Status**: FAILED - False positives

Tracked message count to warn at 35/45 and block at 55 messages.

**Implementation**:
- Global counter in `session_validators.py`
- Incremented in `agent.py` when `AssistantMessage` received
- Hook checked count and warned/blocked

**Problem**: Counter incremented too fast
- Session 019: 18 actual messages, but fired at 45 and 55
- Session 021: 23 actual messages, but fired at 55 (multiple times)
- Ratio: ~2.4x too many increments

**Root Cause**: UNKNOWN
- Only one `increment_message_count()` call in code (agent.py:188)
- Called once per `AssistantMessage` (outside the block loop)
- Yet counter reached 55 when only 23 messages sent
- Possible causes:
  1. SDK sends multiple `AssistantMessage` events per turn?
  2. Event loop re-processes messages?
  3. Some other code path calling increment?
  4. Race condition with async hooks?

### Recommendation 3: Context Compaction Detector ✅
**Status**: Worked correctly (not triggered)

Detected `compact_boundary` SystemMessage and showed warning.

**Result**: No compaction events occurred (sessions stopped earlier), so couldn't fully test, but implementation was correct.

## What Went Wrong

### The False Emergency Stops

**Session 021 example**:
```
Actual messages: 23
Validator count: 55+
Result: "⛔ EMERGENCY STOP: 55 messages exceeded!"
Tools blocked, session couldn't continue
```

**Impact**:
- Sessions blocked from doing legitimate work
- Agent confused by contradictory error messages
- Worse UX than before the validators

### Why Message Counting Failed

**Expected behavior**:
```python
async for msg in client.receive_response():
    if msg_type == "AssistantMessage":
        increment_message_count()  # Once per message
        # Process content blocks...
```

**Actual behavior** (inferred from logs):
- Counter incremented ~2.4x more than expected
- 23 messages → counter reached 55
- Something is calling increment multiple times OR
- AssistantMessage events are duplicated in the stream

**Unable to diagnose** because:
- Code only has one increment call
- Async event stream is black box
- No logging of increment calls
- SDK internals not visible

## Lessons Learned

### 1. Don't Trust Global State in Async Hooks

**Problem**: Global counter shared across async event processing

**Better approach**: Use the logger's existing `message_count`
```python
# Instead of global counter in session_validators.py
# Use logger.message_count from observability.py
# It's already tracking messages correctly!
```

### 2. The Real Solution Was Already There

**Observation**: `logger.message_count` was CORRECT (23 messages)

**We should have**:
- Read `logger.message_count` instead of maintaining parallel counter
- Added warnings based on logger count, not global state
- Trusted existing, proven infrastructure

### 3. Test in Isolation Before Integration

**What we did**: Wrote unit tests, but they tested validator logic in isolation

**What we missed**: Integration test with actual SDK event stream

**Should have**:
1. Run one test session with verbose logging
2. Count increments vs actual messages
3. Debug the 2.4x multiplier before deploying

### 4. Hooks Are Not the Right Place for State

**Hooks are for**:
- Validation (check and allow/block)
- Transformation (modify input_data)
- One-time checks

**Hooks are NOT for**:
- Maintaining session-wide state
- Counting events
- Complex logic with side effects

**Better design**:
- Track state in `agent.py` (where events are processed)
- Use hooks only for validation checks
- Pass state to hooks via context if needed

## What Actually Caused Session 18 to Stop

Re-reading Session 18 analysis:

**Primary issue**: Agent used `Bash` instead of `bash_docker` at message 66
**Secondary issue**: Session ran to 66 messages (should stop at ~45)

**Root causes**:
1. Context compaction at ~157K tokens removed Docker guidance
2. No automated enforcement of message limits
3. No tool validation

## Better Approach (Future)

### For Tool Validation
✅ **Keep the Docker mode validator** - It worked correctly

```python
# This part was good!
async def docker_mode_tool_validator(input_data, ...):
    if is_docker_mode() and tool_name == "Bash":
        return {"decision": "block", "systemMessage": "..."}
    return {}
```

### For Message Count Limits

❌ **Don't use global counter in hooks**

✅ **Use logger's existing count in agent.py**:

```python
# In agent.py, after logging assistant text
if msg_type == "AssistantMessage":
    for block in msg.content:
        if block_type == "TextBlock":
            logger.log_assistant_text(block.text)

            # Check logger's count (already correct!)
            if logger.message_count == 35:
                print("⚠️ 35 messages - wrap up soon")
            elif logger.message_count == 45:
                print("🛑 45 messages - STOP NOW")
            elif logger.message_count >= 55:
                # Force session end
                raise RuntimeError("Emergency stop: 55 messages exceeded")
```

**Why this works**:
- `logger.message_count` already proven accurate
- No global state shared with hooks
- Direct, synchronous increment
- Simple to reason about

### For Context Compaction

✅ **Keep the SystemMessage detector**:

```python
# In agent.py SystemMessage handler
if msg_type == "SystemMessage":
    if getattr(msg, "subtype", None) == "compact_boundary":
        print("⚠️ CONTEXT COMPACTION DETECTED")
        logger.log_error("Context compaction occurred")
```

## Recommendation

**DO NOT** re-implement session validators using global state and hooks.

**DO** implement message limits directly in `agent.py` using `logger.message_count`.

**KEEP** Docker mode tool validator (it worked correctly).

**Simple fix for Session 18 issue**:
```python
# agent.py, in AssistantMessage handler
logger.log_assistant_text(block.text)

# Add these lines:
if logger.message_count >= 50:
    raise RuntimeError(
        f"Session exceeded safe message limit ({logger.message_count} messages). "
        f"Approaching context compaction threshold. Stopping to preserve Docker guidance."
    )
```

That's it. No hooks, no global state, no complexity. Just check the logger's count and hard-stop at 50.

## Files to Clean Up

- ❌ `session_validators.py` - Delete (broken message counting)
- ❌ `tests/test_session_validators.py` - Delete (tests broken implementation)
- ❌ `docs/session-18-improvements.md` - Archive (implementation was flawed)
- ✅ `docs/session-validator-postmortem.md` - Keep (this document)

## Status

- ✅ Broken code reverted (feature branch deleted)
- ✅ Main branch clean (only has .env.local fix)
- ✅ Lessons documented
- ⏸️ Session validators postponed until better approach designed

---

**Bottom line**: The idea was good, the implementation was flawed. Use the logger's existing message count instead of creating parallel state. Keep it simple.
