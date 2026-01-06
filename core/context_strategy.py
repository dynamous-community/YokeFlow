"""
Context Strategy Analysis
=========================

Determines optimal context injection strategy based on project complexity.
"""

from typing import Dict, List, Any


def analyze_context_strategy(
    context_files: List[Any],
    spec_content: str
) -> Dict[str, Any]:
    """
    Analyze context files and project spec to determine optimal context strategy.
    
    Args:
        context_files: List of uploaded context files (UploadFile objects or dicts)
        spec_content: Generated specification markdown
    
    Returns:
        Dict with:
        - strategy: "load_all" or "task_specific"
        - metrics: Dict of analysis metrics
        - reason: Human-readable explanation
    """
    # Calculate context metrics
    context_count = len(context_files) if context_files else 0
    total_size = 0
    
    if context_files:
        for cf in context_files:
            # Handle both UploadFile objects and dicts
            if hasattr(cf, 'size'):
                total_size += cf.size
            elif isinstance(cf, dict) and 'content' in cf:
                total_size += len(cf['content'])
    
    # Estimate project complexity from spec
    estimated_epics = estimate_epic_count(spec_content)
    
    # Decision logic
    metrics = {
        "context_file_count": context_count,
        "total_context_size_kb": round(total_size / 1024, 2),
        "estimated_epics": estimated_epics
    }
    
    # Simple projects: Load all context
    if context_count <= 5 and total_size < 100_000:  # < 100KB
        return {
            "strategy": "load_all",
            "metrics": metrics,
            "reason": "Small context set (≤5 files, <100KB) - loading all files for simplicity"
        }
    
    # Large context: Task-specific loading
    if context_count > 15 or total_size > 500_000:  # > 500KB
        return {
            "strategy": "task_specific",
            "metrics": metrics,
            "reason": f"Large context set ({context_count} files, {metrics['total_context_size_kb']}KB) - using task-specific loading for performance"
        }
    
    # Medium context: Decide based on project complexity
    if estimated_epics > 10:
        return {
            "strategy": "task_specific",
            "metrics": metrics,
            "reason": f"Complex project ({estimated_epics} estimated epics) with moderate context - using task-specific loading"
        }
    else:
        return {
            "strategy": "load_all",
            "metrics": metrics,
            "reason": f"Moderate project ({estimated_epics} estimated epics) with manageable context - loading all files"
        }


def estimate_epic_count(spec_content: str) -> int:
    """
    Estimate number of epics from spec content.
    
    Uses heuristics:
    - Count major features/components mentioned
    - Look for section complexity
    - Estimate from spec length
    
    Args:
        spec_content: Generated specification markdown
    
    Returns:
        Estimated number of epics (minimum 1)
    """
    if not spec_content:
        return 1
    
    # Count major indicators
    epic_indicators = 0
    
    # Count "## " headers (major sections)
    epic_indicators += spec_content.count('\n## ')
    
    # Count feature-related keywords
    feature_keywords = [
        'authentication', 'authorization', 'database', 'api', 
        'frontend', 'backend', 'integration', 'deployment',
        'testing', 'monitoring', 'caching', 'search'
    ]
    
    content_lower = spec_content.lower()
    for keyword in feature_keywords:
        if keyword in content_lower:
            epic_indicators += 1
    
    # Estimate based on spec length (rough heuristic)
    # Assume ~500 chars per epic on average
    length_estimate = len(spec_content) // 500
    
    # Take weighted average
    estimated = (epic_indicators + length_estimate) // 2
    
    # Clamp to reasonable range
    return max(1, min(estimated, 50))
