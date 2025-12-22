# Buffer Overflow Issue - Playwright Snapshots (RESOLVED)

## ✅ Resolution

**Issue:** We were using the **old `claude-code-sdk`** which had a hardcoded 1MB buffer limit with no configuration option.

**Fix:** Migrated to **`claude-agent-sdk` v0.1.13** which exposes `max_buffer_size` parameter in `ClaudeAgentOptions`.

**Implementation:** Set `max_buffer_size=10485760` (10MB) in [client.py](../client.py)

## Original Problem

The old Claude Code SDK had a hardcoded 1MB (1048576 bytes) buffer limit for JSON messages:

```python
# claude_code_sdk/_internal/transport/subprocess_cli.py:24
_MAX_BUFFER_SIZE = 1024 * 1024  # 1MB buffer limit
```

When Playwright's `browser_snapshot` tool returns large HTML dumps (20KB-50KB for complex pages), the total JSON message size can exceed this limit, causing crashes:

```
Failed to decode JSON: JSON message exceeded maximum buffer size of 1048576 bytes
```

## Root Cause (Old SDK)

In `claude-code-sdk`, the buffer size was **not configurable** via `ClaudeCodeOptions`. The buffer size was an internal implementation detail in the transport layer.

**New SDK:** The `claude-agent-sdk` exposes `max_buffer_size` as a public parameter in `ClaudeAgentOptions`.

## Impact

Sessions crash when agent uses `browser_snapshot` on:
- Dashboards with many components
- Data tables with large datasets
- Complex SPAs with heavy JavaScript frameworks
- Any page where the HTML exceeds ~20-30KB

Observed in sessions:
- yahoo-docker session 11: Buffer overflow from snapshot
- yahoo-docker session 12: Buffer overflow from snapshot
- Multiple other sessions with similar errors

## Solution (Implemented)

### 1. SDK Migration

Migrated from `claude-code-sdk` → `claude-agent-sdk`:

```python
# client.py
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

return ClaudeSDKClient(
    options=ClaudeAgentOptions(
        model=model,
        max_buffer_size=10485760,  # 10MB (10x default) - prevents Playwright crashes
        # ... other options
    )
)
```

**Files modified:**
- [client.py](../client.py) - SDK import and buffer size configuration
- [agent.py](../agent.py) - SDK import
- [orchestrator.py](../orchestrator.py) - SDK import

### 2. Defense in Depth (Still Valuable)

Even with the buffer fix, we maintain **prompt engineering** best practices to prevent unnecessary large snapshots:

#### Playwright Guidance in Prompts ([prompts/coding_prompt.md](../prompts/coding_prompt.md))

```markdown
**CRITICAL - Browser Snapshot Buffer Limits:**

When using Playwright, be EXTREMELY careful with `browser_snapshot`:
- ⚠️ **Tool Output Too Large Error** - Snapshots of complex pages can exceed buffer limits
- ✅ **Prefer CSS Selectors** - Use `browser_click` / `browser_type` with specific selectors
- ❌ **Avoid Snapshots On**:
  - Dashboards (many components = 20KB-50KB HTML)
  - Data tables (large datasets)
  - Complex SPAs (React/Vue admin panels)

**If you see "Tool output too large" error:**
1. DO NOT retry the same snapshot
2. Use CSS selectors instead: `button.submit-btn` instead of snapshot → click
3. Use `browser_run_code` for complex interactions
```

#### Playwright MCP Configuration ([client.py:122](../client.py#L122))

```python
"playwright": {
    "command": "npx",
    "args": [
        "@playwright/mcp@latest",
        "--browser", "chrome",
        "--headless",
        "--snapshot-mode", "incremental"  # Reduce snapshot size
    ]
}
```

The `--snapshot-mode incremental` flag reduces snapshot size, but cannot prevent all overflows.

## Historical Workarounds (No Longer Needed)

These were considered before discovering `claude-agent-sdk` had the fix:

### ~~Option 1: Patch SDK Locally~~ (Not needed)

~~Edit the installed SDK file directly to increase buffer size~~

**Status:** Not needed - `claude-agent-sdk` has proper API

### ~~Option 2: Request SDK Enhancement~~ (Already exists!)

~~File issue with Anthropic to make buffer size configurable~~

**Status:** Already implemented in `claude-agent-sdk` v0.1.13+

## Testing

To verify if a page will trigger buffer overflow:

```python
# In browser console
const html = document.documentElement.outerHTML;
console.log(`HTML size: ${html.length} bytes`);
console.log(`JSON size estimate: ${JSON.stringify({html: html}).length} bytes`);
console.log(`Exceeds 1MB? ${JSON.stringify({html: html}).length > 1048576}`);
```

## Verification

After migration, buffer overflow errors should no longer occur for Playwright snapshots under 10MB.

**To test:**
```bash
python -c "from client import create_client; from pathlib import Path; import tempfile; tmpdir = Path(tempfile.mkdtemp()); client = create_client(tmpdir, 'claude-sonnet-4-5-20250929'); print(f'Buffer size: {client.options.max_buffer_size}')"
```

Expected output: `Buffer size: 10485760`

## Related Files

- [prompts/coding_prompt.md](../prompts/coding_prompt.md) - Agent guidance
- [client.py](../client.py) - Playwright MCP configuration
- [.claude/commands/prime.md](../.claude/commands/prime.md) - Session history

## Status

✅ **RESOLVED**
- **Migration:** `claude-code-sdk` → `claude-agent-sdk` v0.1.13
- **Configuration:** `max_buffer_size=10485760` (10MB)
- **Files updated:** client.py, agent.py, orchestrator.py
- **Testing:** Verified client creation sets 10MB buffer
- **Defense in depth:** Prompt guidance maintained for best practices
