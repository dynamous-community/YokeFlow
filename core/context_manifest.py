"""
Context Manifest Generation
============================

Creates a manifest of context files with summaries for efficient context injection.
Uses batch summarization to minimize API calls.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Size threshold for summarization (bytes)
LARGE_FILE_THRESHOLD = 5000  # 5KB
# Preview length
PREVIEW_LENGTH = 200
# Max content to send for summarization per file
SUMMARIZATION_CONTENT_LIMIT = 2000


async def create_context_manifest(
    context_files: List[Dict[str, str]],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a manifest of context files with metadata and summaries.
    
    Args:
        context_files: List of dicts with {"filename": str, "content": str}
        api_key: Optional Anthropic API key (uses env var if not provided)
    
    Returns:
        Manifest dict with file metadata and summaries
    """
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "total_files": len(context_files),
        "total_size_kb": 0,
        "files": []
    }
    
    large_files = []
    large_file_indices = []
    
    for idx, cf in enumerate(context_files):
        content = cf.get("content", "")
        size_bytes = len(content)
        size_kb = round(size_bytes / 1024, 2)
        manifest["total_size_kb"] += size_kb
        
        # Create file entry
        entry = {
            "filename": cf["filename"],
            "size_kb": size_kb,
            "preview": content[:PREVIEW_LENGTH] + ("..." if len(content) > PREVIEW_LENGTH else ""),
            "summary": None  # Will be filled for large files
        }
        manifest["files"].append(entry)
        
        # Track large files for summarization
        if size_bytes > LARGE_FILE_THRESHOLD:
            large_files.append(cf)
            large_file_indices.append(idx)
    
    # Batch summarize large files (one API call)
    if large_files:
        try:
            summaries = await summarize_files_batch(large_files, api_key)
            for idx, summary in zip(large_file_indices, summaries):
                manifest["files"][idx]["summary"] = summary
        except Exception as e:
            logger.warning(f"Failed to generate summaries: {e}")
            # Fallback: use first line of content as summary
            for idx in large_file_indices:
                content = context_files[idx]["content"]
                first_line = content.split('\n')[0][:100]
                manifest["files"][idx]["summary"] = f"(Auto-summary failed) {first_line}"
    
    manifest["total_size_kb"] = round(manifest["total_size_kb"], 2)
    return manifest


async def summarize_files_batch(
    files: List[Dict[str, str]],
    api_key: Optional[str] = None
) -> List[str]:
    """
    Summarize multiple files in a single API call.
    
    Args:
        files: List of dicts with {"filename": str, "content": str}
        api_key: Optional Anthropic API key
    
    Returns:
        List of summaries, one per file
    """
    import os
    
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found")
    
    # Build prompt with all files
    prompt = """Summarize each of the following files in 1-2 sentences. 
Focus on what the file contains and its purpose. 
Return ONLY the summaries, one per line, prefixed with the filename.

Format:
filename1.ext: Summary of file 1.
filename2.ext: Summary of file 2.

Files to summarize:

"""
    
    for f in files:
        content_preview = f["content"][:SUMMARIZATION_CONTENT_LIMIT]
        prompt += f"## {f['filename']}\n```\n{content_preview}\n```\n\n"
    
    # Single API call - lazy import to avoid module-level dependency
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse response
    response_text = response.content[0].text
    summaries = parse_summaries(response_text, [f["filename"] for f in files])
    
    return summaries


def parse_summaries(response_text: str, filenames: List[str]) -> List[str]:
    """
    Parse summaries from Claude's response.
    
    Args:
        response_text: Claude's response
        filenames: List of filenames in order
    
    Returns:
        List of summaries matching filenames order
    """
    summaries = []
    lines = response_text.strip().split('\n')
    
    # Create a map of filename to summary
    summary_map = {}
    for line in lines:
        line = line.strip()
        if ':' in line:
            # Try to match filename: summary format
            parts = line.split(':', 1)
            fname = parts[0].strip()
            summary = parts[1].strip() if len(parts) > 1 else ""
            summary_map[fname] = summary
    
    # Return summaries in order of filenames
    for fname in filenames:
        if fname in summary_map:
            summaries.append(summary_map[fname])
        else:
            # Fallback: look for partial match
            found = False
            for key, val in summary_map.items():
                if fname in key or key in fname:
                    summaries.append(val)
                    found = True
                    break
            if not found:
                summaries.append("(Summary not available)")
    
    return summaries


def save_manifest(manifest: Dict[str, Any], context_dir: Path) -> Path:
    """
    Save manifest to the context directory.
    
    Args:
        manifest: Manifest dict
        context_dir: Path to .yokeflow/context directory
    
    Returns:
        Path to saved manifest file
    """
    manifest_path = context_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    logger.info(f"Saved manifest with {manifest['total_files']} files to {manifest_path}")
    return manifest_path


def load_manifest(context_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Load manifest from the context directory.
    
    Args:
        context_dir: Path to .yokeflow/context directory
    
    Returns:
        Manifest dict if exists, None otherwise
    """
    manifest_path = context_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    
    with open(manifest_path, 'r') as f:
        return json.load(f)


def manifest_to_prompt(manifest: Dict[str, Any]) -> str:
    """
    Convert manifest to a prompt-friendly string.
    
    Args:
        manifest: Manifest dict
    
    Returns:
        Formatted string for injection into system prompt
    """
    lines = [
        "## Available Context Files",
        f"Total: {manifest['total_files']} files ({manifest['total_size_kb']}KB)",
        "",
        "**To read a file, use:** `cat .yokeflow/context/<filename>`",
        "",
        "Only read files when you need them for your current task.",
        ""
    ]
    
    for f in manifest["files"]:
        lines.append(f"### {f['filename']} ({f['size_kb']}KB)")
        if f.get("summary"):
            lines.append(f"  {f['summary']}")
        else:
            lines.append(f"  Preview: {f['preview']}")
        lines.append("")
    
    return "\n".join(lines)
