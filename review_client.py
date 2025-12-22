"""
Review Client - Automated Deep Session Analysis (Phase 2)
==========================================================

Claude-powered session review system that runs automatically to analyze
session quality and suggest prompt improvements.

This module integrates with the orchestrator to provide:
1. Automated trigger after every 5 sessions or when quality drops below 7
2. Deep analysis of session logs using Claude
3. Concrete prompt improvement suggestions
4. Trend analysis across multiple sessions
5. Storage of review results in database

Architecture:
- Called by orchestrator.py after session completion
- Uses Anthropic client (not Agent SDK) for review
- Stores results in session_quality_checks table
- Non-blocking: runs asynchronously, doesn't slow down sessions

Usage:
    from review_client import run_deep_review

    # Trigger deep review for a session
    await run_deep_review(
        session_id=session_uuid,
        project_path=Path("generations/my-project"),
        model="claude-sonnet-4-5-20250929"
    )
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from database_connection import DatabaseManager
from review_metrics import analyze_session_logs, quick_quality_check, get_quality_rating

logger = logging.getLogger(__name__)


def create_review_client(model: str) -> ClaudeSDKClient:
    """
    Create Claude SDK client for review sessions.

    IMPORTANT: This client prevents tool use by:
    - Setting mcp_servers={} (no tools available)
    - System prompt explicitly instructs text-only response
    - max_turns=1 (single response, no follow-up)

    Args:
        model: Claude model to use for review

    Returns:
        Configured ClaudeSDKClient for review
    """
    return ClaudeSDKClient(
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


async def run_deep_review(
    session_id: UUID,
    project_path: Path,
    model: str = "claude-sonnet-4-5-20250929"
) -> Dict[str, Any]:
    """
    Run deep review on a completed session using Claude.

    This is the main entry point for automated deep reviews (Phase 2).

    Steps:
    1. Load session logs (JSONL + TXT)
    2. Extract metrics using review_metrics
    3. Create context for Claude (prompt + metrics + logs)
    4. Call Claude for analysis
    5. Store results in database

    Args:
        session_id: UUID of the session to review
        project_path: Path to project directory
        model: Claude model to use for review

    Returns:
        Dict with review results:
        {
            'check_id': UUID,
            'overall_rating': int (1-10),
            'critical_issues': [str],
            'warnings': [str],
            'review_text': str (markdown)
        }

    Raises:
        FileNotFoundError: If session logs not found
        RuntimeError: If Claude SDK authentication not configured
    """
    logger.info(f"Starting deep review for session {session_id}")

    # Get session info from database
    async with DatabaseManager() as db:
        async with db.acquire() as conn:
            session = await conn.fetchrow(
                "SELECT * FROM sessions WHERE id = $1",
                session_id
            )

            if not session:
                raise ValueError(f"Session not found: {session_id}")

            session_number = session['session_number']
            session_type = session['type']
            project_id = session['project_id']

    # Find session logs
    logs_dir = project_path / "logs"
    jsonl_pattern = f"session_{session_number:03d}_*.jsonl"
    txt_pattern = f"session_{session_number:03d}_*.txt"

    jsonl_files = list(logs_dir.glob(jsonl_pattern))
    txt_files = list(logs_dir.glob(txt_pattern))

    if not jsonl_files:
        raise FileNotFoundError(f"No JSONL log found for session {session_number}")

    jsonl_path = jsonl_files[0]
    txt_path = txt_files[0] if txt_files else None

    logger.info(f"Analyzing logs: {jsonl_path.name}")

    # Extract metrics from JSONL log
    metrics = analyze_session_logs(jsonl_path)

    # Run quick quality check
    is_initializer = session_type == "initializer"
    issues = quick_quality_check(metrics, is_initializer=is_initializer)
    critical_issues = [i for i in issues if i.startswith("❌")]
    warnings = [i for i in issues if i.startswith("⚠️")]
    overall_rating = get_quality_rating(metrics)

    # Read session log excerpt for context
    session_log_excerpt = ""
    if txt_path and txt_path.exists():
        with open(txt_path, 'r') as f:
            # Read first 5000 chars for context
            session_log_excerpt = f.read(5000)

    # Create review context with all data
    context = _create_review_context(
        project_path=project_path,
        session_number=session_number,
        session_type=session_type,
        metrics=metrics,
        critical_issues=critical_issues,
        warnings=warnings,
        session_log_excerpt=session_log_excerpt
    )

    # Construct review prompt (DO NOT use review_prompt.md - it's for interactive tool-using agents)
    # This prompt is for automated analysis with all data provided upfront
    full_prompt = f"""# Deep Session Review - Session {session_number}

You are analyzing a completed autonomous coding agent session. All necessary data is provided below.

{context}

---

## YOUR TASK

Analyze this session and provide a comprehensive review focusing on:

### 1. Session Quality Rating (1-10)
Rate the overall session quality with justification based on:
- Browser verification usage (20 Playwright calls = good, 0 = critical issue)
- Error rate (4.7% shown above)
- Task completion quality
- Prompt adherence

### 2. Browser Verification Analysis
**Critical Quality Indicator** (r=0.98 correlation with session quality):
- How many Playwright calls were made? ({metrics.get('playwright_count', 0)} shown above)
- Were screenshots taken before AND after changes?
- Were user interactions tested (clicks, forms)?
- Was verification done BEFORE marking tests passing?

### 3. Error Pattern Analysis
- What types of errors occurred?
- Were they preventable with better prompt guidance?
- Did the agent recover efficiently?

### 4. Prompt Adherence
- Which steps from the coding prompt were followed well?
- Which were skipped or done poorly?
- What prompt guidance would have prevented issues?

### 5. Concrete Prompt Improvements
Provide specific, actionable changes to `coding_prompt.md` that would improve future sessions.

---

## OUTPUT FORMAT

**IMPORTANT:** End your review with a structured recommendations section:

## RECOMMENDATIONS

### High Priority
- [Specific actionable recommendation with before/after example]
- [Another high-priority improvement]

### Medium Priority
- [Medium-priority suggestion]

### Low Priority
- [Nice-to-have improvement]

Focus on **systematic improvements** that help ALL future sessions, not fixes for this specific application.
"""

    # Create review client
    client = create_review_client(model)

    logger.info(f"Calling Claude SDK ({model}) for deep analysis...")
    logger.info("Note: System prompt instructs Claude NOT to use tools - expecting text-only response")

    # Call Claude using Agent SDK
    try:
        async with client:
            # Send review prompt
            await client.query(full_prompt)

            # Collect response text (only TextBlocks, ignore ToolUseBlocks)
            review_text = ""
            message_count = 0
            text_block_count = 0
            tool_use_attempts = 0

            async for msg in client.receive_response():
                message_count += 1
                msg_type = type(msg).__name__

                logger.debug(f"Received message #{message_count}: {msg_type}")

                # Handle AssistantMessage
                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__
                        logger.debug(f"  Block type: {block_type}")

                        if block_type == "TextBlock" and hasattr(block, "text"):
                            text_block_count += 1
                            block_text = block.text
                            review_text += block_text
                            logger.debug(f"  Collected text block #{text_block_count} ({len(block_text)} chars)")
                        elif block_type == "ToolUseBlock":
                            tool_use_attempts += 1
                            logger.warning(f"Claude attempted to use a tool despite instruction not to (attempt #{tool_use_attempts})")
                            # Continue collecting text - don't stop on tool use

        logger.info(f"Review complete: {message_count} messages, {text_block_count} text blocks, {len(review_text)} total chars")

        if tool_use_attempts > 0:
            logger.warning(f"Claude attempted {tool_use_attempts} tool uses despite mcp_servers={{}} and explicit instruction not to")

    except Exception as e:
        logger.error(f"Claude SDK call failed: {e}")
        raise

    # Extract rating from review if present
    parsed_rating = _extract_rating_from_review(review_text)
    if parsed_rating:
        overall_rating = parsed_rating

    # Store in database (prompt_improvements extracted separately by prompt improvement system)
    async with DatabaseManager() as db:
        check_id = await db.store_deep_review(
            session_id=session_id,
            metrics=metrics,
            critical_issues=critical_issues,
            warnings=warnings,
            overall_rating=overall_rating,
            review_text=review_text,
            prompt_improvements=[],  # Extracted separately by prompt improvement system
            check_version="2.0"
        )

    logger.info(f"Deep review stored: {check_id}")

    return {
        'check_id': check_id,
        'overall_rating': overall_rating,
        'critical_issues': critical_issues,
        'warnings': warnings,
        'review_text': review_text
    }


def _create_review_context(
    project_path: Path,
    session_number: int,
    session_type: str,
    metrics: Dict[str, Any],
    critical_issues: List[str],
    warnings: List[str],
    session_log_excerpt: str
) -> str:
    """
    Create context for Claude review.

    Provides all relevant information about the session for analysis.
    """
    context = f"""# Review Context for Session {session_number}

## Project
- **Location:** {project_path}
- **Session:** {session_number}
- **Type:** {session_type}

## Session Metrics (Pre-computed)

```json
{json.dumps(metrics, indent=2)}
```

## Quick Quality Check Results

**Overall Rating:** {get_quality_rating(metrics)}/10

### Critical Issues
"""

    if critical_issues:
        for issue in critical_issues:
            context += f"\n{issue}"
    else:
        context += "\n✅ No critical issues detected"

    context += "\n\n### Warnings\n"

    if warnings:
        for warning in warnings:
            context += f"\n{warning}"
    else:
        context += "\n✅ No warnings"

    context += f"""

## Key Findings (Preliminary)

### Browser Verification
- **Playwright calls:** {metrics.get('playwright_count', 0)}
- **Screenshots:** {metrics.get('playwright_screenshot_count', 0)}
- **Navigations:** {metrics.get('playwright_navigate_count', 0)}

### Tool Usage
- **Total tools used:** {metrics.get('total_tool_uses', 0)}
- **Errors:** {metrics.get('error_count', 0)} ({metrics.get('error_rate', 0):.1%} rate)

### Most Used Tools (Top 10)
"""

    # Add top tools
    sorted_tools = sorted(
        metrics.get('tool_counts', {}).items(),
        key=lambda x: x[1],
        reverse=True
    )
    for tool, count in sorted_tools[:10]:
        context += f"\n- {tool}: {count}"

    context += f"""

## Session Log Excerpt (first 5000 chars)

```
{session_log_excerpt}
```
"""

    return context


def _parse_recommendations(review_text: str) -> List[str]:
    """
    Parse recommendations from Claude's review text.

    Looks for structured recommendations section and extracts recommendations.
    Handles multiple formats:
    - Markdown headings: "#### 1. **Title**"
    - Simple numbered: "1. Text"
    - Bullet points: "- Text"

    Fixed Dec 21, 2025: Now correctly handles heading-style recommendations
    that use #### prefix (e.g., "#### 1. **Add Feature**")
    """
    import re
    recommendations = []

    # Look for RECOMMENDATIONS section
    if "## RECOMMENDATIONS" in review_text or "## Recommendations" in review_text:
        lines = review_text.split('\n')
        in_recommendations = False
        current_recommendation = None

        for line in lines:
            # Start of recommendations section
            if "## RECOMMENDATIONS" in line.upper():
                in_recommendations = True
                continue

            # Stop at next top-level section (##) but not subsections (###, ####)
            if in_recommendations and line.startswith('## ') and not line.startswith('###') and 'RECOMMENDATION' not in line.upper():
                break

            if in_recommendations:
                # Look for heading-style numbered items: #### 1. **Title** or ### 1. **Title**
                heading_match = re.match(r'^#{2,4}\s*(\d+)\.\s+\*\*(.+?)\*\*', line)
                if heading_match:
                    title = heading_match.group(2).strip()
                    if current_recommendation:
                        recommendations.append(current_recommendation)
                    current_recommendation = title
                    continue

                # Look for simple numbered items: 1. Text (without heading prefix)
                simple_match = re.match(r'^\s*(\d+)\.\s+(.+)$', line)
                if simple_match:
                    text = simple_match.group(2).strip()
                    # Remove markdown bold if present
                    text = re.sub(r'^\*\*(.+?)\*\*$', r'\1', text)
                    # Skip Before:/After: examples
                    if not text.startswith('**Before:') and not text.startswith('**After:'):
                        if current_recommendation:
                            recommendations.append(current_recommendation)
                        current_recommendation = text
                    continue

                # Look for bullet points: - Text
                if line.strip().startswith('-'):
                    rec = line.strip()[1:].strip()
                    # Skip markdown emphasis markers and empty items
                    if rec and not rec.startswith('*'):
                        if current_recommendation:
                            recommendations.append(current_recommendation)
                        current_recommendation = rec

        # Add last recommendation if exists
        if current_recommendation:
            recommendations.append(current_recommendation)

    return recommendations


def _extract_rating_from_review(review_text: str) -> Optional[int]:
    """
    Extract numerical rating from review text.

    Looks for patterns like "Rating: 8/10" or "Quality: 7/10".
    """
    import re

    # Common patterns
    patterns = [
        r'Rating:\s*(\d+)/10',
        r'Quality:\s*(\d+)/10',
        r'Overall Rating:\s*(\d+)/10',
        r'Session Quality Rating:\s*(\d+)/10'
    ]

    for pattern in patterns:
        match = re.search(pattern, review_text, re.IGNORECASE)
        if match:
            rating = int(match.group(1))
            if 1 <= rating <= 10:
                return rating

    return None


async def should_trigger_deep_review(
    project_id: UUID,
    session_number: int,
    last_session_quality: Optional[int] = None
) -> bool:
    """
    Determine if a deep review should be triggered for a project.

    Triggers when:
    1. Every 5th CODING session (sessions 5, 10, 15, 20, ...)
    2. Quality drops below 7/10
    3. No deep review in last 5 sessions

    NOTE: Initializer sessions (session 0) are never reviewed with coding criteria.
    They have different quality standards (no browser testing required).

    Args:
        project_id: UUID of the project
        session_number: Number of the session that just completed
        last_session_quality: Quality rating of the last session (1-10)

    Returns:
        True if deep review should be triggered
    """
    async with DatabaseManager() as db:
        async with db.acquire() as conn:
            # First, check if this is an initializer session - never review those
            session_info = await conn.fetchrow(
                "SELECT type FROM sessions WHERE project_id = $1 AND session_number = $2",
                project_id, session_number
            )

            if session_info and session_info['type'] == 'initializer':
                logger.debug(f"Skipping deep review trigger for initializer session {session_number}")
                return False

            # Check if we're at a 5-session interval
            if session_number > 1 and session_number % 5 == 0:
                logger.info(f"Deep review trigger: 5-session interval (session {session_number})")
                return True

            # Check if quality dropped below threshold
            if last_session_quality is not None and last_session_quality < 7:
                logger.info(f"Deep review trigger: low quality ({last_session_quality}/10)")
                return True

            # Check when last deep review was done
            last_deep_review = await conn.fetchrow(
                """
                SELECT s.session_number
                FROM session_quality_checks q
                JOIN sessions s ON q.session_id = s.id
                WHERE s.project_id = $1 AND q.check_type = 'deep'
                ORDER BY q.created_at DESC
                LIMIT 1
                """,
                project_id
            )

            if last_deep_review:
                # Calculate sessions since last review (e.g., session 65 - session 60 = 5)
                sessions_since_last_review = session_number - last_deep_review['session_number']
                if sessions_since_last_review >= 5:
                    logger.info(f"Deep review trigger: {sessions_since_last_review} sessions since last review")
                    return True
            elif session_number >= 5:
                # No deep review yet, but we have 5+ sessions
                logger.info(f"Deep review trigger: first deep review at session {session_number}")
                return True

    return False


# Example usage and testing
if __name__ == "__main__":
    import sys

    # Test with a specific session
    if len(sys.argv) < 3:
        print("Usage: python review_client.py <project_path> <session_number>")
        sys.exit(1)

    project_path = Path(sys.argv[1])
    session_number = int(sys.argv[2])

    async def test_review():
        # Find session by number
        async with DatabaseManager() as db:
            async with db.acquire() as conn:
                session = await conn.fetchrow(
                    """
                    SELECT s.* FROM sessions s
                    JOIN projects p ON s.project_id = p.id
                    WHERE p.name = $1 AND s.session_number = $2
                    """,
                    project_path.name,
                    session_number
                )

                if not session:
                    print(f"Session {session_number} not found for project {project_path.name}")
                    sys.exit(1)

                session_id = session['id']

        # Run deep review
        result = await run_deep_review(
            session_id=session_id,
            project_path=project_path
        )

        print("\n" + "="*80)
        print(f"Deep Review Complete - Session {session_number}")
        print("="*80)
        print(f"\nQuality Rating: {result['overall_rating']}/10")
        print(f"\nCritical Issues: {len(result['critical_issues'])}")
        for issue in result['critical_issues']:
            print(f"  {issue}")
        print(f"\nFull review stored in database (check_id: {result['check_id']})")
        print("="*80)

    # Run async test
    asyncio.run(test_review())
