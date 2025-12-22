"""
Review Metrics - Session Quality Analysis
==========================================

Lightweight session quality metrics extraction and analysis.
Extracted from review_agent.py for integration into core platform.

This module provides:
1. Session log analysis (JSONL parsing for metrics)
2. Quick quality checks (no API calls, instant feedback)
3. Browser verification tracking (r=0.98 correlation with quality)

Usage:
    from review_metrics import analyze_session_logs, quick_quality_check

    # Extract metrics from JSONL log
    metrics = analyze_session_logs(Path("logs/session_001_timestamp.jsonl"))

    # Run quality gate check
    issues = quick_quality_check(metrics)
    if issues:
        print(f"Quality issues: {issues}")
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


def analyze_session_logs(jsonl_path: Path) -> Dict[str, Any]:
    """
    Extract key metrics from session JSONL log.

    Parses the complete event stream to extract:
    - Tool usage counts by type
    - Error statistics
    - Browser verification metrics (Playwright)
    - Session timing

    Args:
        jsonl_path: Path to session JSONL log file

    Returns:
        Dict with comprehensive session metrics:
        {
            'tool_counts': {tool_name: count},
            'total_tool_uses': int,
            'error_count': int,
            'error_rate': float (0.0-1.0),
            'playwright_count': int,
            'playwright_screenshot_count': int,
            'playwright_navigate_count': int,
            'playwright_tools_used': [tool_names],
            'session_start': ISO timestamp,
            'session_end': ISO timestamp
        }

    Note:
        Browser verification (playwright_count) correlates r=0.98 with
        session quality. This is the #1 quality indicator.
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
                # Skip malformed lines
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


def quick_quality_check(session_metrics: Dict[str, Any], is_initializer: bool = False) -> List[str]:
    """
    Lightweight quality gate check based on key metrics.

    Returns list of quality issues found (empty list = no issues).

    Critical Quality Indicators:
    1. Browser verification (r=0.98 correlation with quality)
       - 0 Playwright calls = CRITICAL ISSUE (for coding sessions only)
       - Playwright used but no screenshots = WARNING

    2. Error rate
       - >15% = WARNING (target: <5%)

    3. Tool usage patterns
       - <5 tool uses = possible incomplete session

    Args:
        session_metrics: Metrics dict from analyze_session_logs()
        is_initializer: True if this is an initialization session (skips browser verification check)

    Returns:
        List of issue strings (e.g., ["❌ CRITICAL: No browser verification"])
        Empty list if no issues found

    Example:
        >>> metrics = analyze_session_logs(log_path)
        >>> issues = quick_quality_check(metrics, is_initializer=False)
        >>> if issues:
        ...     print("Quality gate failed:")
        ...     for issue in issues:
        ...         print(f"  {issue}")
    """
    issues = []

    # Critical: Browser verification present? (Skip for initialization sessions)
    if not is_initializer:
        playwright_count = session_metrics.get('playwright_count', 0)
        playwright_screenshot_count = session_metrics.get('playwright_screenshot_count', 0)

        if playwright_count == 0:
            issues.append("❌ CRITICAL: No browser verification detected (0 Playwright calls)")
        elif playwright_screenshot_count == 0:
            issues.append("⚠️ WARNING: Playwright used but no screenshots taken")

    # Error rate acceptable?
    error_rate = session_metrics.get('error_rate', 0)
    if error_rate > 0.15:
        issues.append(f"⚠️ High error rate: {error_rate:.1%} (target: <15%)")

    # Reasonable tool usage?
    total_tools = session_metrics.get('total_tool_uses', 0)
    if total_tools < 5:
        issues.append(f"⚠️ Very few tool uses: {total_tools} (possible incomplete session?)")

    return issues


def get_quality_rating(session_metrics: Dict[str, Any]) -> int:
    """
    Calculate overall quality rating (1-10) based on metrics.

    Rating criteria:
    - 9-10: Excellent (50+ Playwright calls, <5% errors)
    - 7-8: Good (10-49 Playwright calls, <10% errors)
    - 5-6: Fair (1-9 Playwright calls, <15% errors)
    - 3-4: Poor (0 Playwright calls or high error rate)
    - 1-2: Critical (multiple quality issues)

    Args:
        session_metrics: Metrics dict from analyze_session_logs()

    Returns:
        Integer rating from 1-10
    """
    playwright_count = session_metrics.get('playwright_count', 0)
    error_rate = session_metrics.get('error_rate', 0)
    issues = quick_quality_check(session_metrics)

    # Start with base score
    score = 10

    # Browser verification (most critical metric)
    if playwright_count == 0:
        score -= 6  # Massive penalty for no browser testing
    elif playwright_count < 10:
        score -= 3  # Significant penalty for minimal testing
    elif playwright_count < 30:
        score -= 1  # Minor penalty for moderate testing

    # Error rate
    if error_rate > 0.20:
        score -= 3  # High error rate
    elif error_rate > 0.15:
        score -= 2  # Elevated error rate
    elif error_rate > 0.10:
        score -= 1  # Moderate error rate

    # Critical issues
    critical_issues = [i for i in issues if i.startswith("❌")]
    score -= len(critical_issues)

    # Ensure score stays in valid range
    return max(1, min(10, score))


def format_quality_summary(session_metrics: Dict[str, Any]) -> str:
    """
    Format a human-readable quality summary.

    Args:
        session_metrics: Metrics dict from analyze_session_logs()

    Returns:
        Formatted string summary

    Example output:
        Quality Rating: 8/10
        ✅ Browser verification: 42 Playwright calls (12 screenshots)
        ✅ Error rate: 5.2% (3 errors in 58 tool uses)
        ⚠️ WARNING: High error rate: 18.0%
    """
    rating = get_quality_rating(session_metrics)
    issues = quick_quality_check(session_metrics)

    lines = [f"Quality Rating: {rating}/10"]

    # Browser verification
    playwright_count = session_metrics.get('playwright_count', 0)
    screenshot_count = session_metrics.get('playwright_screenshot_count', 0)

    if playwright_count > 0:
        lines.append(f"✅ Browser verification: {playwright_count} Playwright calls ({screenshot_count} screenshots)")
    else:
        lines.append("❌ No browser verification")

    # Error rate
    error_count = session_metrics.get('error_count', 0)
    total_tools = session_metrics.get('total_tool_uses', 0)
    error_rate = session_metrics.get('error_rate', 0)

    if error_rate < 0.05:
        lines.append(f"✅ Error rate: {error_rate:.1%} ({error_count} errors in {total_tools} tool uses)")
    else:
        lines.append(f"⚠️ Error rate: {error_rate:.1%} ({error_count} errors in {total_tools} tool uses)")

    # Issues
    if issues:
        lines.append("\nIssues:")
        for issue in issues:
            lines.append(f"  {issue}")

    return "\n".join(lines)


def find_session_log(project_dir: Path, session_number: int) -> Optional[Path]:
    """
    Find JSONL log file for a specific session.

    Args:
        project_dir: Project directory path
        session_number: Session number (e.g., 0 for initialization, 1+ for coding)

    Returns:
        Path to JSONL log file, or None if not found
    """
    logs_dir = project_dir / "logs"

    if not logs_dir.exists():
        return None

    # Session numbers are now 0-based (0 = initialization)
    pattern = f"session_{session_number:03d}_*.jsonl"
    files = list(logs_dir.glob(pattern))

    return files[0] if files else None


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python review_metrics.py <path/to/session.jsonl>")
        sys.exit(1)

    log_path = Path(sys.argv[1])

    if not log_path.exists():
        print(f"Error: Log file not found: {log_path}")
        sys.exit(1)

    print(f"Analyzing {log_path.name}...\n")

    # Extract metrics
    metrics = analyze_session_logs(log_path)

    # Display summary
    print(format_quality_summary(metrics))

    print(f"\nTop 10 Tools Used:")
    sorted_tools = sorted(metrics['tool_counts'].items(), key=lambda x: x[1], reverse=True)
    for tool, count in sorted_tools[:10]:
        print(f"  {tool}: {count}")
