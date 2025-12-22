#!/usr/bin/env python3
"""
Review Agent - Automated Session Analysis (EXPERIMENTAL)
=========================================================

**Status:** Research tool for prompt engineering and quality analysis.
**Not integrated** into the main autonomous coding platform.

This is a standalone experimental script that analyzes completed coding sessions
to identify prompt improvements and quality patterns. It uses the Claude Agent SDK
with tool use disabled (text-only mode) and is designed for manual, post-session analysis.

Key findings:
- Browser verification correlates r=0.98 with session quality
- Successfully validated v4 prompt improvements (0% → 100% browser verification)
- Proven review → improve → measure cycle works

See docs/review-system.md for complete architecture and usage guide.

Usage:
    # Review a specific session
    python review_agent.py --project generations/my-project --session 5

    # Review last N sessions
    python review_agent.py --project generations/my-project --last-n 3

    # Review entire project (all sessions)
    python review_agent.py --project generations/my-project --type final

    # Quick quality check (lightweight)
    python review_agent.py --project generations/my-project --session 5 --quick

Examples:
    python review_agent.py --project generations/playwright-test --session 2
    python review_agent.py --project generations/playwright-test --last-n 5 --output review_sessions_2-6.md
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from database_connection import DatabaseManager
from config import Config


def find_session_logs(project_dir: Path, session_number: Optional[int] = None) -> List[Path]:
    """Find session log files in project directory."""
    logs_dir = project_dir / "logs"

    if not logs_dir.exists():
        print(f"❌ No logs directory found in {project_dir}")
        return []

    if session_number:
        # Find specific session
        pattern = f"session_{session_number:03d}_*.jsonl"
        files = list(logs_dir.glob(pattern))
        if not files:
            print(f"❌ No logs found for session {session_number}")
            return []
        return files
    else:
        # Find all sessions
        return sorted(logs_dir.glob("session_*.jsonl"))


def analyze_session_logs(jsonl_path: Path) -> Dict[str, Any]:
    """
    Extract key metrics from session JSONL log.

    Returns:
        Dict with tool counts, error rate, browser verification stats, etc.
    """
    tool_counts = {}
    error_count = 0
    total_tool_uses = 0
    playwright_tools = []
    session_start = None
    session_end = None

    with open(jsonl_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue

            try:
                event = json.loads(line)

                # Track session timing
                if event.get('event') == 'session_start':
                    session_start = event.get('timestamp')

                # Count tool uses
                if event.get('event') == 'tool_use':
                    tool_name = event.get('tool_name')
                    if tool_name:
                        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                        total_tool_uses += 1

                        # Track Playwright usage specifically
                        if tool_name.startswith('mcp__playwright__'):
                            playwright_tools.append(tool_name)

                # Count errors
                if event.get('event') == 'tool_result' and event.get('is_error'):
                    error_count += 1

                # Track session end
                if event.get('event') == 'session_end':
                    session_end = event.get('timestamp')

            except json.JSONDecodeError:
                continue

    # Calculate metrics
    error_rate = error_count / total_tool_uses if total_tool_uses > 0 else 0

    playwright_count = len(playwright_tools)
    playwright_screenshot_count = sum(1 for t in playwright_tools if 'screenshot' in t)
    playwright_navigate_count = sum(1 for t in playwright_tools if 'navigate' in t)

    return {
        'tool_counts': tool_counts,
        'total_tool_uses': total_tool_uses,
        'error_count': error_count,
        'error_rate': error_rate,
        'playwright_count': playwright_count,
        'playwright_screenshot_count': playwright_screenshot_count,
        'playwright_navigate_count': playwright_navigate_count,
        'playwright_tools_used': list(set(playwright_tools)),
        'session_start': session_start,
        'session_end': session_end,
    }


def quick_quality_check(session_metrics: Dict[str, Any]) -> List[str]:
    """
    Lightweight quality gate check based on key metrics.

    Returns list of issues found.
    """
    issues = []

    # Critical: Browser verification present?
    if session_metrics['playwright_count'] == 0:
        issues.append("❌ CRITICAL: No browser verification detected (0 Playwright calls)")
    elif session_metrics['playwright_screenshot_count'] == 0:
        issues.append("⚠️ WARNING: Playwright used but no screenshots taken")

    # Error rate acceptable?
    if session_metrics['error_rate'] > 0.15:
        issues.append(f"⚠️ High error rate: {session_metrics['error_rate']:.1%} (target: <15%)")

    # Reasonable tool usage?
    if session_metrics['total_tool_uses'] < 5:
        issues.append(f"⚠️ Very few tool uses: {session_metrics['total_tool_uses']} (possible incomplete session?)")

    return issues


def load_review_prompt() -> str:
    """Load the review prompt template."""
    prompt_path = Path(__file__).parent / "prompts" / "review_prompt.md"

    if not prompt_path.exists():
        print(f"❌ Review prompt not found at {prompt_path}")
        sys.exit(1)

    with open(prompt_path, 'r') as f:
        return f.read()


def create_review_context(
    project_dir: Path,
    session_number: int,
    session_metrics: Dict[str, Any]
) -> str:
    """
    Create context for review agent with all relevant information.
    """
    logs_dir = project_dir / "logs"

    # Read session logs
    jsonl_files = list(logs_dir.glob(f"session_{session_number:03d}_*.jsonl"))
    txt_files = list(logs_dir.glob(f"session_{session_number:03d}_*.txt"))
    notes_files = list(logs_dir.glob(f"session_{session_number:03d}_notes.md"))

    context = f"""# Review Context for Session {session_number}

## Project
- **Location:** {project_dir}
- **Session:** {session_number}

## Session Metrics (Pre-computed)
```json
{json.dumps(session_metrics, indent=2)}
```

## Key Findings (Preliminary)

### Browser Verification
- **Playwright calls:** {session_metrics['playwright_count']}
- **Screenshots:** {session_metrics['playwright_screenshot_count']}
- **Navigations:** {session_metrics['playwright_navigate_count']}

### Tool Usage
- **Total tools used:** {session_metrics['total_tool_uses']}
- **Errors:** {session_metrics['error_count']} ({session_metrics['error_rate']:.1%} rate)

### Most Used Tools (Top 10)
"""

    # Add top tools
    sorted_tools = sorted(session_metrics['tool_counts'].items(), key=lambda x: x[1], reverse=True)
    for tool, count in sorted_tools[:10]:
        context += f"- {tool}: {count}\n"

    context += "\n## Log Files Available\n\n"

    # List available files
    if jsonl_files:
        context += f"- JSONL log: {jsonl_files[0].name}\n"
    if txt_files:
        context += f"- TXT log: {txt_files[0].name}\n"
    if notes_files:
        context += f"- Session notes: {notes_files[0].name}\n"

    # Add app spec path
    app_spec = project_dir / "app_spec.txt"
    if app_spec.exists():
        context += f"- App spec: app_spec.txt\n"

    context += f"\n## Database\n- Type: PostgreSQL (centralized)\n- Project: {project_dir.name}\n"

    return context


async def _run_review_async(client: ClaudeSDKClient, prompt: str) -> str:
    """
    Async helper to call Claude SDK and collect response text.

    Args:
        client: Configured ClaudeSDKClient
        prompt: Review prompt to send

    Returns:
        Collected review text from Claude's response
    """
    import logging
    logger = logging.getLogger(__name__)

    async with client:
        # Send review prompt
        await client.query(prompt)

        # Collect response text (only TextBlocks, ignore ToolUseBlocks)
        review_text = ""
        message_count = 0
        text_block_count = 0
        tool_use_attempts = 0

        async for msg in client.receive_response():
            message_count += 1
            msg_type = type(msg).__name__

            # Handle AssistantMessage
            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        text_block_count += 1
                        block_text = block.text
                        review_text += block_text
                    elif block_type == "ToolUseBlock":
                        tool_use_attempts += 1
                        logger.warning(f"Claude attempted to use a tool despite instruction not to (attempt #{tool_use_attempts})")
                        # Continue collecting text - don't stop on tool use

        if tool_use_attempts > 0:
            logger.warning(f"Claude attempted {tool_use_attempts} tool uses despite mcp_servers={{}} and explicit instruction not to")

    return review_text


def run_review(
    project_dir: Path,
    session_number: int,
    model: str = "claude-sonnet-4-5-20250929",
    output_file: Optional[Path] = None,
    quick: bool = False
) -> str:
    """
    Run review agent on a specific session.

    Args:
        project_dir: Path to project directory
        session_number: Session number to review
        model: Claude model to use for review
        output_file: Optional output file path
        quick: If True, only run quick quality check

    Returns:
        Review text
    """
    print(f"📊 Analyzing session {session_number} in {project_dir.name}...")

    # Find session logs
    jsonl_files = find_session_logs(project_dir, session_number)
    if not jsonl_files:
        print(f"❌ No logs found for session {session_number}")
        sys.exit(1)

    jsonl_path = jsonl_files[0]
    print(f"📄 Reading {jsonl_path.name}...")

    # Analyze logs
    session_metrics = analyze_session_logs(jsonl_path)

    # Quick quality check
    print("\n🔍 Quick Quality Check:")
    issues = quick_quality_check(session_metrics)

    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  ✅ No major issues detected")

    if quick:
        # Only output quick check
        review_text = f"""# Quick Quality Check - Session {session_number}

**Project:** {project_dir.name}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Metrics
- Tool uses: {session_metrics['total_tool_uses']}
- Errors: {session_metrics['error_count']} ({session_metrics['error_rate']:.1%} rate)
- Playwright calls: {session_metrics['playwright_count']}
- Screenshots: {session_metrics['playwright_screenshot_count']}

## Issues
"""
        if issues:
            for issue in issues:
                review_text += f"\n{issue}"
        else:
            review_text += "\n✅ No major issues detected\n"

        review_text += f"\n\n## Top Tools Used\n\n"
        sorted_tools = sorted(session_metrics['tool_counts'].items(), key=lambda x: x[1], reverse=True)
        for tool, count in sorted_tools[:10]:
            review_text += f"- {tool}: {count}\n"

        print(f"\n📝 Quick review complete")

    else:
        # Full review with Claude
        print("\n🤖 Running full review with Claude...")

        # Load review prompt
        review_prompt = load_review_prompt()

        # Create context
        context = create_review_context(project_dir, session_number, session_metrics)

        # Create Claude SDK client for review
        # Note: This client prevents tool use by setting mcp_servers={} and max_turns=1
        client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=model,
                system_prompt=(
                    "You are a code review expert analyzing autonomous coding agent sessions. "
                    "ALL necessary data is provided in the user message - you have everything you need. "
                    "Provide your analysis as pure Markdown text. "
                    "DO NOT attempt to read files, run commands, or use any tools. "
                    "Respond with a comprehensive review report following the requested format."
                ),
                permission_mode="bypassPermissions",
                mcp_servers={},  # No MCP servers - no tools available
                max_turns=1,  # Single-turn only
                max_buffer_size=10485760,  # 10MB buffer
            )
        )

        # Read session logs to include in prompt
        txt_path = project_dir / "logs" / f"session_{session_number:03d}_*.txt"
        txt_files = list(project_dir.glob(str(txt_path).replace(str(project_dir) + "/", "")))

        session_log_excerpt = ""
        if txt_files:
            with open(txt_files[0], 'r') as f:
                # Read first 5000 chars
                session_log_excerpt = f.read(5000)

        # Construct full prompt
        full_prompt = f"""{review_prompt}

---

{context}

---

## Session Log Excerpt (first 5000 chars)

```
{session_log_excerpt}
```

---

## YOUR TASK

Analyze this session and provide:

1. **Session Quality Rating** (1-10) with justification
2. **Prompt Adherence Analysis** - Which steps were followed/skipped?
3. **Browser Verification Analysis** - Quality of testing
4. **Error Pattern Analysis** - What went wrong and why?
5. **Concrete Prompt Improvements** - Specific changes to coding_prompt.md with before/after examples

Focus on **systematic improvements** that will help ALL future sessions, not just fixes for this application.
"""

        print("⏳ Waiting for Claude's analysis...")

        # Call Claude using Agent SDK (async pattern)
        import asyncio
        review_text = asyncio.run(_run_review_async(client, full_prompt))

        print(f"✅ Review complete ({len(review_text)} chars)")

    # Save output
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(review_text)
        print(f"💾 Saved to {output_file}")
    else:
        print("\n" + "="*80)
        print(review_text)
        print("="*80)

    return review_text


def main():
    parser = argparse.ArgumentParser(
        description="Review autonomous coding sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to project directory (e.g., generations/my-project)"
    )

    parser.add_argument(
        "--session",
        type=int,
        help="Specific session number to review"
    )

    parser.add_argument(
        "--last-n",
        type=int,
        help="Review last N sessions"
    )

    parser.add_argument(
        "--type",
        choices=["session", "trends", "final"],
        default="session",
        help="Review type: session (single), trends (multiple), final (all)"
    )

    parser.add_argument(
        "--model",
        default="claude-sonnet-4-5-20250929",
        help="Claude model to use for review (default: Sonnet 4.5)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: print to stdout)"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick quality check only (no Claude call)"
    )

    args = parser.parse_args()

    # Validate project directory
    if not args.project.exists():
        print(f"❌ Project directory not found: {args.project}")
        sys.exit(1)

    # Note: With PostgreSQL, we don't check for tasks.db anymore
    # The database is centralized and accessed via DATABASE_URL

    # Determine what to review
    if args.session:
        # Single session
        run_review(
            args.project,
            args.session,
            args.model,
            args.output,
            args.quick
        )

    elif args.last_n:
        # Last N sessions
        logs_dir = args.project / "logs"
        all_sessions = sorted(logs_dir.glob("session_*.jsonl"))

        if not all_sessions:
            print(f"❌ No sessions found in {logs_dir}")
            sys.exit(1)

        # Extract session numbers
        session_numbers = []
        for log_file in all_sessions:
            # Extract session number from filename
            try:
                num = int(log_file.stem.split('_')[1])
                session_numbers.append(num)
            except (ValueError, IndexError):
                continue

        session_numbers = sorted(set(session_numbers))[-args.last_n:]

        print(f"📊 Reviewing sessions: {session_numbers}")

        for session_num in session_numbers:
            print(f"\n{'='*80}")
            run_review(
                args.project,
                session_num,
                args.model,
                None,  # No output file for multi-session
                args.quick
            )

    else:
        print("❌ Must specify --session or --last-n")
        sys.exit(1)


if __name__ == "__main__":
    main()
