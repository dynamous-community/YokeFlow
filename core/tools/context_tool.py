"""
Context Tool
============

Tool for retrieving context files on-demand during agent sessions.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Tool definition for Claude
CONTEXT_TOOL_DEFINITION = {
    "name": "get_context_file",
    "description": "Retrieve a project context file by name. Use this to access SQL schemas, API documentation, style guides, and other project context. Call this whenever you need detailed information from a context file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The exact filename to retrieve (e.g., 'schema.sql', 'api_guide.md')"
            }
        },
        "required": ["filename"]
    }
}


def get_context_file(project_path: Path, filename: str) -> Dict[str, Any]:
    """
    Retrieve a context file's content.
    
    Args:
        project_path: Path to the project directory
        filename: Name of the context file to retrieve
    
    Returns:
        Dict with success status and content or error
    """
    context_dir = project_path / ".yokeflow" / "context"
    
    if not context_dir.exists():
        return {
            "success": False,
            "error": f"Context directory not found at {context_dir}"
        }
    
    file_path = context_dir / filename
    
    # Security check: ensure file is within context directory
    try:
        file_path.resolve().relative_to(context_dir.resolve())
    except ValueError:
        return {
            "success": False,
            "error": f"Invalid filename: {filename}. Path traversal not allowed."
        }
    
    if not file_path.exists():
        # List available files
        available = [f.name for f in context_dir.glob("*") if f.is_file() and f.name != "manifest.json"]
        return {
            "success": False,
            "error": f"File '{filename}' not found in context directory.",
            "available_files": available
        }
    
    try:
        content = file_path.read_text(encoding='utf-8')
        logger.info(f"Retrieved context file: {filename} ({len(content)} bytes)")
        return {
            "success": True,
            "filename": filename,
            "content": content,
            "size_bytes": len(content)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read file: {str(e)}"
        }


def handle_context_tool_call(
    tool_input: Dict[str, Any],
    project_path: Path
) -> str:
    """
    Handle a context tool call from the agent.
    
    Args:
        tool_input: The input from Claude's tool call
        project_path: Path to the project
    
    Returns:
        String response to return to Claude
    """
    filename = tool_input.get("filename", "")
    
    if not filename:
        return "Error: No filename provided. Please specify which context file you need."
    
    result = get_context_file(project_path, filename)
    
    if result["success"]:
        return f"# {result['filename']}\n\n{result['content']}"
    else:
        error_msg = result["error"]
        if "available_files" in result:
            error_msg += f"\n\nAvailable files: {', '.join(result['available_files'])}"
        return f"Error: {error_msg}"
