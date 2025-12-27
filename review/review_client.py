"""
Review Client - Automated Deep Session Analysis (Phase 2)
==========================================================

YokeFlow's Claude-powered session review system that runs automatically to
analyze session quality and suggest prompt improvements.

This module integrates with the orchestrator to provide:
1. Automated trigger after every 5 sessions or when quality drops below 7
2. Deep analysis of session logs using Claude
3. Concrete prompt improvement suggestions
4. Trend analysis across multiple sessions
5. Storage of review results in database

Architecture:
- Called by orchestrator.py after session completion
- Stores results in session_deep_reviews table
- Non-blocking: runs asynchronously, doesn't slow down sessions

Usage:
    from review.review_client import run_deep_review

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
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from core.database_connection import DatabaseManager


logger = logging.getLogger(__name__)

def analyze_session_logs(jsonl_path: Path) -> Dict[str, Any]:
    """
    Extract key metrics from session JSONL log.

    Parses the complete event stream to extract:
    - Tool usage counts by type
    - Error types seen (for context in reviews)
    - Enhanced context for deep reviews (REFACTORED Dec 25, 2025)

    NOTE: This now extracts enhanced data for review context optimization.
    Most aggregate metrics (tool_calls_count, errors_count) are still in database,
    but we extract detailed patterns for better prompt improvement recommendations.

    Args:
        jsonl_path: Path to session JSONL log file

    Returns:
        Dict with session metrics:
        {
            'tool_counts': {tool_name: count},
            'errors_seen': [error_message_samples],
            'enhanced_data': {
                'errors': [detailed error context],
                'task_timeline': {task_id: {...}},
                'browser_events': [timing and patterns],
                'adherence_issues': [prompt violations],
                'key_events': [important session moments]
            }
        }

    """
    tool_counts = {}
    error_types = []

    # Enhanced data for context optimization
    errors = []
    task_timeline = {}
    browser_events = []
    key_events = []
    adherence_issues = []

    # State tracking
    current_task = None
    last_tool = None
    error_messages_seen = set()
    prompt_file = 'unknown'
    prompt_version = 'unknown'
    model = 'unknown'
    commit_count = 0
    last_commit_message = ''

    with open(jsonl_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue

            try:
                event = json.loads(line)
                event_type = event.get('event')
                timestamp = event.get('timestamp', '')

                # SESSION START - Extract prompt info and model
                if event_type == 'session_start':
                    prompt_file = event.get('prompt_file', 'unknown')
                    # Extract model from session_start event
                    model = event.get('model', 'unknown')
                    # Extract version from prompt metadata if available
                    prompt_version = event.get('prompt_version', 'unknown')
                    key_events.append({
                        'time': timestamp,
                        'type': 'session_start',
                        'desc': f"Session started with {prompt_file} ({model})"
                    })

                # TOOL USE - Track for error context and patterns
                elif event_type == 'tool_use':
                    tool_name = event.get('tool_name')
                    if tool_name:
                        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                        last_tool = tool_name

                        # Get parameters - MCP tools use 'input' field, others use 'parameters'
                        params = event.get('input') or event.get('parameters') or {}

                        # Track task lifecycle
                        if tool_name == 'mcp__task-manager__start_task':
                            task_id = params.get('task_id')
                            if task_id:
                                current_task = str(task_id)
                                task_timeline[current_task] = {
                                    'start_time': timestamp,
                                    'browser_verifications': [],
                                    'tests_marked': [],
                                    'completion_time': None
                                }
                                key_events.append({
                                    'time': timestamp,
                                    'type': 'task_start',
                                    'desc': f"Started task {task_id}"
                                })

                        # Track browser verification
                        elif tool_name.startswith('mcp__playwright__'):
                            if current_task and current_task in task_timeline:
                                task_timeline[current_task]['browser_verifications'].append({
                                    'time': timestamp,
                                    'tool': tool_name
                                })
                            browser_events.append({
                                'time': timestamp,
                                'tool': tool_name,
                                'task': current_task
                            })

                        # Track test marking
                        elif tool_name == 'mcp__task-manager__update_test_result':
                            if current_task and current_task in task_timeline:
                                task_timeline[current_task]['tests_marked'].append(timestamp)

                        # Track task completion
                        elif tool_name == 'mcp__task-manager__update_task_status':
                            done_param = params.get('done')
                            if done_param and current_task and current_task in task_timeline:
                                task_timeline[current_task]['completion_time'] = timestamp
                                key_events.append({
                                    'time': timestamp,
                                    'type': 'task_complete',
                                    'desc': f"Completed task {current_task}"
                                })

                        # Check for prompt violations - Using Bash instead of bash_docker
                        elif tool_name == 'Bash':
                            # This is only a violation in Docker mode, but we'll flag it for review
                            adherence_issues.append({
                                'type': 'wrong_tool',
                                'issue': 'Used Bash tool (check if Docker mode - should use bash_docker)',
                                'timestamp': timestamp
                            })

                        # Check for /workspace/ prefix in file operations
                        elif tool_name in ['Read', 'Write', 'Edit']:
                            file_path = params.get('file_path', '')
                            if '/workspace/' in file_path:
                                adherence_issues.append({
                                    'type': 'path_error',
                                    'issue': f'{tool_name} used /workspace/ prefix (should use relative path)',
                                    'timestamp': timestamp,
                                    'path': file_path
                                })

                # TOOL RESULT - Capture errors with context
                elif event_type == 'tool_result' and event.get('is_error'):
                    error_msg = event.get('content', '')[:500]  # More than previous 100 chars
                    error_hash = hash(error_msg[:100])  # Check for duplicates

                    # Add to both old format (for compatibility) and new format
                    error_types.append(error_msg[:100])

                    errors.append({
                        'tool': last_tool,
                        'message': error_msg,
                        'timestamp': timestamp,
                        'is_repeated': error_hash in error_messages_seen,
                        'task': current_task
                    })
                    error_messages_seen.add(error_hash)

                    key_events.append({
                        'time': timestamp,
                        'type': 'error',
                        'desc': f"Error in {last_tool}: {error_msg[:80]}"
                    })

            except json.JSONDecodeError:
                # Skip malformed lines
                continue

    # Calculate browser verification patterns
    screenshot_count = sum(1 for e in browser_events if 'screenshot' in e['tool'].lower())
    console_check_count = sum(1 for e in browser_events if 'console' in e['tool'].lower())

    # Analyze screenshot timing relative to task completion
    screenshots_before = 0
    screenshots_after = 0
    for task_id, timeline in task_timeline.items():
        completion = timeline['completion_time']
        if not completion:
            continue
        for verif in timeline['browser_verifications']:
            if 'screenshot' in verif['tool'].lower():
                if verif['time'] < completion:
                    screenshots_before += 1
                else:
                    screenshots_after += 1

    total_screenshots = screenshots_before + screenshots_after
    screenshots_before_pct = screenshots_before / total_screenshots if total_screenshots > 0 else 0

    # Check for good navigation pattern (navigate followed by screenshot)
    has_good_pattern = _check_nav_screenshot_pattern(browser_events)

    return {
        'tool_counts': tool_counts,
        'errors_seen': list(set(error_types)),
        'enhanced_data': {
            'prompt_file': prompt_file,
            'prompt_version': prompt_version,
            'model': model,
            'errors': errors,
            'task_timeline': task_timeline,
            'screenshot_count': screenshot_count,
            'screenshots_before_completion': screenshots_before,
            'screenshots_after_completion': screenshots_after,
            'screenshots_before_pct': screenshots_before_pct,
            'screenshots_after_pct': 1 - screenshots_before_pct,
            'console_check_count': console_check_count,
            'has_good_nav_pattern': 'YES ✅' if has_good_pattern else 'NO ⚠️',
            'adherence_checks': adherence_issues,
            'commit_count': commit_count,
            'last_commit_message': last_commit_message,
            'key_events': key_events[:20]  # Limit to 20 most important events
        }
    }

def _check_nav_screenshot_pattern(browser_events: List[Dict]) -> bool:
    """
    Check if browser events show good Navigate → Screenshot pattern.

    A good pattern is when navigate is followed by screenshot within a reasonable time.
    """
    if len(browser_events) < 2:
        return False

    # Count navigate->screenshot pairs
    nav_screenshot_pairs = 0
    for i in range(len(browser_events) - 1):
        current = browser_events[i]
        next_event = browser_events[i + 1]

        if 'navigate' in current['tool'].lower() and 'screenshot' in next_event['tool'].lower():
            nav_screenshot_pairs += 1

    # If we have at least 2 navigate->screenshot patterns, that's good
    return nav_screenshot_pairs >= 2


def _format_duration(start_time: str, end_time: str) -> str:
    """Format duration between two ISO timestamps."""
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        duration = (end - start).total_seconds()

        if duration < 60:
            return f"{duration:.0f}s"
        elif duration < 3600:
            return f"{duration/60:.1f}m"
        else:
            return f"{duration/3600:.1f}h"
    except:
        return "unknown"


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
                "You are a code review expert analyzing YokeFlow coding agent sessions. "
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
    model: str = None
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
    # Use DEFAULT_REVIEW_MODEL from env if model not specified
    if model is None:
        model = os.getenv('DEFAULT_REVIEW_MODEL', 'claude-sonnet-4-5-20250929')

    logger.info(f"Starting deep review for session {session_id} using model {model}")

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

            session_dict = dict(session)
            # Parse metrics JSONB field (asyncpg returns it as a string)
            if 'metrics' in session_dict and isinstance(session_dict['metrics'], str):
                try:
                    session_dict['metrics'] = json.loads(session_dict['metrics'])
                except (json.JSONDecodeError, TypeError):
                    session_dict['metrics'] = {}
            session_metrics = session_dict.get('metrics', {})

            # Calculate error rate from database metrics and add to session_metrics
            error_rate = session_metrics.get('errors_count', 0) / session_metrics.get('tool_calls_count', 0) if session_metrics.get('tool_calls_count', 0) > 0 else 0
            session_metrics['error_rate'] = error_rate


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

    # Extract model from enhanced data
    model = metrics.get('enhanced_data', {}).get('model', 'unknown')

    # Create review context with all data
    context = _create_review_context(
        project_path=project_path,
        session_number=session_number,
        session_type=session_type,
        metrics=metrics,
        session_metrics=session_metrics,
    )

    # Load review prompt from external file
    # NOTE: This prompt was designed for interactive agents, but works well for automated reviews too
    # The client is configured with mcp_servers={} and max_turns=1, so no tool use will occur
    review_prompt_path = Path(__file__).parent.parent / "prompts" / "review_prompt.md"

    if not review_prompt_path.exists():
        logger.warning(f"Review prompt not found at {review_prompt_path}, using inline prompt")
        review_base_prompt = _get_fallback_review_prompt()
    else:
        logger.info(f"Loading review prompt from {review_prompt_path}")
        with open(review_prompt_path, 'r') as f:
            review_base_prompt = f.read()

    # Construct full prompt with context
    full_prompt = f"""{review_base_prompt}

---

# REVIEW DATA FOR SESSION {session_number}

{context}

---

## YOUR TASK

Analyze this session using the framework above. All necessary data is provided - DO NOT attempt to use tools.

Provide a comprehensive review focusing on:

1. **Session Quality Rating (1-10)** - Based on browser verification ({metrics.get('playwright_count', 0)} Playwright calls), error rate, task completion
2. **Browser Verification Analysis** - Critical quality indicator (r=0.98 correlation)
3. **Error Pattern Analysis** - What types, were they preventable, recovery efficiency
4. **Prompt Adherence** - Which steps followed well, which skipped
5. **Concrete Prompt Improvements** - Specific changes to `coding_prompt.md`

**IMPORTANT:** End with structured RECOMMENDATIONS section (High/Medium/Low Priority) with specific, actionable changes.

Focus on **systematic improvements** that help ALL future sessions, not fixes for this specific application.
"""

    # Create review client
    client = create_review_client(model)

    logger.info(f"Calling Claude SDK ({model}) for deep analysis...")

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

        logger.info(f"Review complete: {message_count} messages, {text_block_count} text blocks, {len(review_text)} total chars")

        if tool_use_attempts > 0:
            logger.warning(f"Claude attempted {tool_use_attempts} tool uses despite mcp_servers={{}} and explicit instruction not to")

    except Exception as e:
        logger.error(f"Claude SDK call failed: {e}")
        raise

    # Extract executive summary for structured storage
    review_summary = _extract_executive_summary(review_text)

    # Extract rating from review if present (default to 5 if not found)
    # Prefer rating from executive summary, fall back to general extraction
    overall_rating = review_summary.get('rating') or _extract_rating_from_review(review_text) or 5

    # Parse recommendations from review text
    prompt_improvements = _parse_recommendations(review_text)

    # Store in database
    async with DatabaseManager() as db:
        check_id = await db.store_deep_review(
            session_id=session_id,
            metrics=metrics,
            overall_rating=overall_rating,
            review_text=review_text,
            prompt_improvements=prompt_improvements,  # Extracted from RECOMMENDATIONS section
            review_summary=review_summary,  # Extracted from Executive Summary section
            review_version="2.0",
            model=model  # Model extracted from JSONL
        )

    logger.info(f"Deep review stored: {check_id}")

    return {
        'check_id': check_id,
        'overall_rating': overall_rating,
        'review_text': review_text
    }


def _get_fallback_review_prompt() -> str:
    """
    Fallback review prompt if external file not found.

    This is a minimal prompt - the external file has much more detail.
    """
    return """# Deep Session Review

You are analyzing a completed YokeFlow coding agent session. All necessary data is provided below.

## YOUR TASK

Analyze this session and provide a comprehensive review focusing on:

### 1. Session Quality Rating (1-10)
Rate the overall session quality based on:
- Browser verification usage (Playwright calls)
- Error rate
- Task completion quality
- Prompt adherence

### 2. Browser Verification Analysis
**Critical Quality Indicator** (r=0.98 correlation with session quality):
- How many Playwright calls were made?
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

## OUTPUT FORMAT

**IMPORTANT:** End your review with a structured recommendations section:

## RECOMMENDATIONS

### High Priority
- [Specific actionable recommendation with before/after example]

### Medium Priority
- [Medium-priority suggestion]

### Low Priority
- [Nice-to-have improvement]

Focus on **systematic improvements** that help ALL future sessions, not fixes for this specific application.
"""


def _create_review_context(
    project_path: Path,
    session_number: int,
    session_type: str,
    metrics: Dict[str, Any],
    session_metrics: Dict[str, Any],
) -> str:
    """
    Create optimized context for Claude review.

    REFACTORED Dec 25, 2025: Now uses enhanced JSONL data instead of TXT log excerpt.
    This provides 8x token reduction with better signal-to-noise ratio.

    Provides all relevant information about the session for analysis.
    """
    enhanced_data = metrics.get('enhanced_data', {})

    context = f"""# Review Context for Session

## Session Metadata
- Session: {session_number} ({session_type})
- Model: {enhanced_data.get('model', 'unknown')}
- Prompt file: {enhanced_data.get('prompt_file', 'unknown')} ({enhanced_data.get('prompt_version', 'unknown')})
- Duration: {session_metrics.get('duration_seconds', 0):.0f}s

## Session Metrics (from database)
"""
    # Format session metrics as bullet list for better readability
    for key, value in session_metrics.items():
        # Skip model since we already included it above
        if key == 'model':
            continue

        # Format the key to be more readable (e.g., tool_calls_count -> Tool Calls)
        readable_key = key.replace('_', ' ').title()

        # Format values appropriately
        if isinstance(value, float):
            if key == 'error_rate':
                formatted_value = f"{value:.1%}"
            else:
                formatted_value = f"{value:.2f}"
        elif isinstance(value, int):
            formatted_value = f"{value:,}"
        else:
            formatted_value = str(value)

        context += f"\n- **{readable_key}:** {formatted_value}"

    context += f"\n\n## Tool Usage (Top 20)\n"
    # Add top tools
    sorted_tools = sorted(
        metrics.get('tool_counts', {}).items(),
        key=lambda x: x[1],
        reverse=True
    )
    for tool, count in sorted_tools[:20]:  # Top 20 instead of all
        context += f"\n- {tool}: {count}"

    context += f"\n\n## Error Analysis (ENHANCED)\n"
    context += f"**Total errors: {session_metrics.get('errors_count', 0)} ({session_metrics.get('error_rate', 0):.1%} rate)**\n"

    # Format detailed error information
    errors = enhanced_data.get('errors', [])
    if errors:
        for i, err in enumerate(errors[:10], 1):  # Limit to first 10 errors
            repeated = " (REPEATED)" if err.get('is_repeated') else ""
            context += f"\n### Error {i}{repeated} ({err.get('tool', 'unknown')})"
            context += f"\n- Time: {err.get('timestamp', 'unknown')}"
            context += f"\n- Task: {err.get('task', 'none')}"
            context += f"\n- Message: {err.get('message', '')[:200]}..."
    else:
        context += "\n- No errors detected"

    # Browser Verification Patterns
    context += f"\n\n## Browser Verification Patterns\n"
    context += f"- Total Playwright calls: {session_metrics.get('browser_verifications', 0)}\n"
    context += f"- Screenshots taken: {enhanced_data.get('screenshot_count', 0)}\n"
    context += f"- Screenshot timing:\n"
    context += f"  - Before task completion: {enhanced_data.get('screenshots_before_completion', 0)} ({enhanced_data.get('screenshots_before_pct', 0):.0%})\n"
    context += f"  - After task completion: {enhanced_data.get('screenshots_after_completion', 0)} ({enhanced_data.get('screenshots_after_pct', 0):.0%})\n"
    context += f"- Console checks: {enhanced_data.get('console_check_count', 0)}\n"
    context += f"- Navigate → Screenshot pattern: {enhanced_data.get('has_good_nav_pattern', 'unknown')}\n"

    # Task Completion Timeline
    context += f"\n\n## Task Completion Timeline\n"
    task_timeline = enhanced_data.get('task_timeline', {})
    if task_timeline:
        for task_id, data in sorted(task_timeline.items())[:10]:  # Limit to first 10 tasks
            start = data.get('start_time', '')
            end = data.get('completion_time')
            duration = _format_duration(start, end) if end else 'Not completed'

            browser_count = len(data.get('browser_verifications', []))
            test_count = len(data.get('tests_marked', []))

            # Check if browser verification happened before completion
            verified_before = False
            if data.get('browser_verifications') and end:
                last_verif = data['browser_verifications'][-1]['time']
                verified_before = last_verif < end

            context += f"\n- **Task {task_id}**: {duration}"
            context += f"\n  - Browser verifications: {browser_count}"
            context += f"\n  - Tests marked: {test_count}"
            context += f"\n  - Verified before completion: {'YES ✅' if verified_before else 'NO ❌'}"
    else:
        context += "\n- No tasks completed this session"

    # Prompt Adherence Indicators
    context += f"\n\n## Prompt Adherence Indicators\n"
    adherence_issues = enhanced_data.get('adherence_checks', [])
    if adherence_issues:
        context += "⚠️ **Violations detected:**\n"
        for issue in adherence_issues[:10]:  # Limit to first 10
            context += f"\n- [{issue.get('timestamp', 'unknown')}] {issue.get('issue', '')}"
    else:
        context += "✅ No prompt violations detected"

    # Session Event Timeline (replaces TXT log excerpt)
    context += f"\n\n## Session Event Timeline\n"
    key_events = enhanced_data.get('key_events', [])
    if key_events:
        for event in key_events:
            emoji = {
                'session_start': '🚀',
                'task_start': '▶️',
                'task_complete': '✅',
                'error': '❌',
                'git_commit': '💾'
            }.get(event.get('type'), '•')

            time_str = event.get('time', '')
            time_only = time_str.split('T')[1][:8] if 'T' in time_str else time_str
            context += f"\n- {emoji} {time_only}: {event.get('desc', '')}"
    else:
        context += "\n- No significant events recorded"

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


def _extract_executive_summary(review_text: str) -> Dict[str, Any]:
    """
    Extract the Executive Summary section from review text.

    Returns structured summary data for the review_summary JSONB field:
    {
        'rating': int,
        'one_line': str,
        'summary': str
    }
    """
    import re

    # Find the Executive Summary section
    summary_match = re.search(
        r'## Executive Summary\s*\n\*\*Session Rating: (\d+)/10\*\* - (.+?)\n\n(.+?)(?=\n##|\Z)',
        review_text,
        re.DOTALL
    )

    if summary_match:
        rating = int(summary_match.group(1))
        one_line = summary_match.group(2).strip()
        summary_text = summary_match.group(3).strip()

        return {
            'rating': rating,
            'one_line': one_line,
            'summary': summary_text
        }

    return {}


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
                FROM session_deep_reviews dr
                JOIN sessions s ON dr.session_id = s.id
                WHERE s.project_id = $1
                ORDER BY dr.created_at DESC
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
