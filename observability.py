"""
Observability and Logging for Autonomous Coding Agent
======================================================

This module provides comprehensive logging for agent sessions including:
- Session lifecycle (start, completion, errors)
- Message processing (text, tool use, tool results)
- Performance metrics
- Structured logs for AI analysis

Log Structure:
- Session logs: logs/session_{iteration}_{timestamp}.jsonl
- Human-readable summaries: logs/session_{iteration}_{timestamp}.txt

Session metrics are stored in the PostgreSQL database for querying and analysis.
Each session gets its own log files for easy debugging and analysis.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Optional


def format_duration(seconds: float) -> str:
    """
    Format duration as human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string (e.g., "45s", "2m 30s", "1h 15m")
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = int(seconds / 3600)
        remaining_minutes = int((seconds % 3600) / 60)
        return f"{hours}h {remaining_minutes}m"


class SessionLogger:
    """
    Logs a single agent session to both JSONL (for AI analysis) and TXT (for humans).

    Creates two files per session:
    - session_{iteration}_{timestamp}.jsonl: Structured data for AI parsing
    - session_{iteration}_{timestamp}.txt: Human-readable narrative
    """

    def __init__(self, log_dir: Path, session_number: int, session_type: str, model: str = None, prompt_file: str = None, event_callback=None):
        """
        Initialize session logger.

        Args:
            log_dir: Directory to store logs
            session_number: Session iteration number
            session_type: "initializer" or "coding"
            model: Claude model being used (e.g., "claude-opus-4-5-20251101")
            prompt_file: Prompt file used (e.g., "initializer_prompt_local.md")
            event_callback: Optional callback function(event_type, data) for real-time events
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)

        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"session_{session_number:03d}_{timestamp}"

        self.jsonl_file = self.log_dir / f"{base_name}.jsonl"
        self.txt_file = self.log_dir / f"{base_name}.txt"

        self.session_number = session_number
        self.session_type = session_type
        self.model = model
        self.prompt_file = prompt_file
        self.start_time = time.time()
        self.message_count = 0
        self.tool_use_count = 0
        self.tool_errors = 0
        self.event_callback = event_callback

        # Track session metrics for analysis
        self.tasks_completed = 0
        self.tests_passed = 0
        self.browser_verifications = 0

        # Track token usage (estimated from character counts)
        # Rough estimate: 1 token ≈ 4 characters for English text
        # This is an approximation since we don't have direct API access
        self.input_chars = 0   # Prompt + tool results
        self.output_chars = 0  # Assistant responses

        # Track tool_id -> (tool_name, tool_input) mapping for event emission
        self.tool_map = {}

        # Initialize files
        self._init_files()

    def _init_files(self):
        """Initialize log files with headers."""
        # JSONL: Write session start
        session_data = {
            "event": "session_start",
            "timestamp": datetime.now().isoformat(),
            "session_number": self.session_number,
            "session_type": self.session_type,
            "model": self.model
        }
        if self.prompt_file:
            session_data["prompt_file"] = self.prompt_file
        self._write_jsonl(session_data)

        # TXT: Write human-readable header
        with open(self.txt_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write(f"AUTONOMOUS CODING AGENT - SESSION {self.session_number}\n")
            f.write("=" * 80 + "\n")
            f.write(f"Session Type: {self.session_type.upper()}\n")
            if self.model:
                f.write(f"Model: {self.model}\n")
            if self.prompt_file:
                f.write(f"Prompt File: {self.prompt_file}\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

    def _write_jsonl(self, data: dict):
        """Write a line to the JSONL log file."""
        with open(self.jsonl_file, "a") as f:
            json.dump(data, f)
            f.write("\n")

    def _write_txt(self, text: str):
        """Write text to the human-readable log file."""
        with open(self.txt_file, "a") as f:
            f.write(text)

    def _emit_event(self, event_type: str, data: dict):
        """
        Emit event via callback if configured.

        Args:
            event_type: Type of event (e.g., "assistant_message", "tool_use")
            data: Event data dictionary
        """
        if self.event_callback:
            try:
                self.event_callback(event_type, data)
            except Exception as e:
                # Don't let callback errors break logging
                pass

    def log_prompt(self, prompt: str):
        """Log the initial prompt sent to the agent (JSONL only, not TXT or terminal)."""
        # Track input tokens (prompt is input)
        self.input_chars += len(prompt)

        self._write_jsonl({
            "event": "prompt",
            "timestamp": datetime.now().isoformat(),
            "prompt_length": len(prompt),
            "prompt": prompt
        })
        # Note: Prompt is intentionally NOT logged to TXT file
        # It's too verbose for human review but useful for agent analysis

    def log_assistant_text(self, text: str):
        """Log assistant text output."""
        self.message_count += 1
        timestamp = datetime.now().isoformat()

        # Track output tokens (assistant text is output)
        self.output_chars += len(text)

        self._write_jsonl({
            "event": "assistant_text",
            "timestamp": timestamp,
            "message_number": self.message_count,
            "text": text
        })

        self._write_txt(f"[Assistant Message {self.message_count}]\n")
        self._write_txt(text + "\n\n")

        # Emit WebSocket event
        self._emit_event("assistant_message", {
            "session_number": self.session_number,
            "message_number": self.message_count,
            "text": text,
            "timestamp": timestamp
        })

    def log_tool_use(self, tool_name: str, tool_id: str, tool_input: Any):
        """Log tool use."""
        self.tool_use_count += 1
        timestamp = datetime.now().isoformat()

        self._write_jsonl({
            "event": "tool_use",
            "timestamp": timestamp,
            "tool_number": self.tool_use_count,
            "tool_name": tool_name,
            "tool_id": tool_id,
            "input": tool_input
        })

        self._write_txt(f"[Tool Use #{self.tool_use_count}: {tool_name}]\n")
        self._write_txt(f"Tool ID: {tool_id}\n")

        # Format input nicely
        if isinstance(tool_input, dict):
            for key, value in tool_input.items():
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 500:
                    value_str = value_str[:500] + "...[truncated]"
                self._write_txt(f"  {key}: {value_str}\n")
        else:
            self._write_txt(f"  Input: {tool_input}\n")
        self._write_txt("\n")

        # Store tool_id -> (tool_name, tool_input) mapping for later event emission
        self.tool_map[tool_id] = (tool_name, tool_input)

        # Emit WebSocket event for tool use count
        self._emit_event("tool_use", {
            "session_number": self.session_number,
            "tool_name": tool_name,
            "tool_count": self.tool_use_count,
            "timestamp": timestamp
        })

    def log_tool_result(self, tool_id: str, content: Any, is_error: bool):
        """Log tool result."""
        if is_error:
            self.tool_errors += 1

        self._write_jsonl({
            "event": "tool_result",
            "timestamp": datetime.now().isoformat(),
            "tool_id": tool_id,
            "is_error": is_error,
            "content": str(content)[:1000] if not is_error else str(content)  # Full error text
        })

        # Human-readable log
        if is_error:
            self._write_txt(f"[Tool Result - ERROR]\n")
            self._write_txt(f"{content}\n\n")
        else:
            # Success - just note it briefly in TXT (full content in JSONL)
            content_str = str(content)
            if len(content_str) > 200:
                self._write_txt(f"[Tool Result - Success] ({len(content_str)} chars)\n\n")
            else:
                self._write_txt(f"[Tool Result - Success]\n{content_str}\n\n")

        # Emit real-time events for MCP task/test updates
        if not is_error and tool_id in self.tool_map:
            tool_name, tool_input = self.tool_map[tool_id]

            # Emit event for task status updates
            if tool_name == "mcp__task-manager__update_task_status":
                # Increment tasks_completed if task is marked as done
                if tool_input.get("done"):
                    self.tasks_completed += 1

                self._emit_event("task_updated", {
                    "task_id": tool_input.get("task_id"),
                    "done": tool_input.get("done"),
                    "timestamp": datetime.now().isoformat()
                })

            # Emit event for test result updates
            elif tool_name == "mcp__task-manager__update_test_result":
                # Increment tests_passed if test passes
                if tool_input.get("passes"):
                    self.tests_passed += 1

                self._emit_event("test_updated", {
                    "test_id": tool_input.get("test_id"),
                    "passes": tool_input.get("passes"),
                    "timestamp": datetime.now().isoformat()
                })

            # Track Playwright browser verifications
            elif tool_name.startswith("mcp__playwright__"):
                self.browser_verifications += 1

    def log_thinking(self, thinking: str):
        """Log extended thinking blocks."""
        self._write_jsonl({
            "event": "thinking",
            "timestamp": datetime.now().isoformat(),
            "thinking": thinking
        })

        self._write_txt("[Thinking]\n")
        self._write_txt(thinking + "\n\n")

    def log_system_message(self, subtype: str, message: str):
        """Log system messages."""
        self._write_jsonl({
            "event": "system_message",
            "timestamp": datetime.now().isoformat(),
            "subtype": subtype,
            "message": message
        })

        self._write_txt(f"[System: {subtype}]\n")
        self._write_txt(message + "\n\n")

    def log_error(self, error: Exception):
        """Log an error that occurred during the session."""
        self._write_jsonl({
            "event": "error",
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error)
        })

        self._write_txt(f"[ERROR: {type(error).__name__}]\n")
        self._write_txt(f"{error}\n\n")

    def log_result_message(self, usage_data: dict):
        """Log ResultMessage with token usage and cost data (JSONL only)."""
        self._write_jsonl({
            "event": "result_message",
            "timestamp": datetime.now().isoformat(),
            "usage": usage_data
        })

    def finalize(self, status: str, response_text: str = "", usage_data: dict = None):
        """
        Finalize the session and write summary.

        Args:
            status: "continue" or "error"
            response_text: Full response text from assistant
            usage_data: Optional dict with token usage and cost data from ResultMessage
        """
        duration = time.time() - self.start_time

        # Session end event
        session_summary = {
            "event": "session_end",
            "timestamp": datetime.now().isoformat(),
            "session_number": self.session_number,
            "session_type": self.session_type,
            "model": self.model,
            "status": status,
            "duration_seconds": duration,
            "message_count": self.message_count,
            "tool_use_count": self.tool_use_count,
            "tool_errors": self.tool_errors,
            "tasks_completed": self.tasks_completed,
            "tests_passed": self.tests_passed,
            "browser_verifications": self.browser_verifications,
            "response_length": len(response_text)
        }

        # Add token usage and cost if available
        if usage_data:
            session_summary["tokens_input"] = usage_data.get("input_tokens", 0)
            session_summary["tokens_output"] = usage_data.get("output_tokens", 0)
            session_summary["tokens_cache_creation"] = usage_data.get("cache_creation_input_tokens", 0)
            session_summary["tokens_cache_read"] = usage_data.get("cache_read_input_tokens", 0)
            if "cost_usd" in usage_data:
                session_summary["cost_usd"] = usage_data["cost_usd"]

        self._write_jsonl(session_summary)

        # Human-readable summary
        self._write_txt("=" * 80 + "\n")
        self._write_txt("SESSION SUMMARY\n")
        self._write_txt("=" * 80 + "\n")
        if self.model:
            self._write_txt(f"Model: {self.model}\n")
        self._write_txt(f"Status: {status.upper()}\n")
        self._write_txt(f"Duration: {format_duration(duration)}\n")
        self._write_txt(f"Messages: {self.message_count}\n")
        self._write_txt(f"Tool Uses: {self.tool_use_count}\n")
        self._write_txt(f"Tool Errors: {self.tool_errors}\n")

        # Add token usage and cost if available
        if usage_data:
            total_tokens = usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0)
            self._write_txt(f"Tokens: {total_tokens:,} (input: {usage_data.get('input_tokens', 0):,}, output: {usage_data.get('output_tokens', 0):,})\n")
            if usage_data.get("cache_read_input_tokens", 0) > 0:
                self._write_txt(f"Cache Read: {usage_data.get('cache_read_input_tokens', 0):,} tokens\n")
            if "cost_usd" in usage_data:
                self._write_txt(f"Cost: ${usage_data['cost_usd']:.4f}\n")

        self._write_txt("=" * 80 + "\n")

        # Note: Session summary is now stored in PostgreSQL database
        # (sessions table with metrics JSONB field)
        return session_summary


class QuietOutputFilter:
    """
    Filter for controlling terminal output verbosity.

    Quiet mode (default) shows:
    - Assistant text messages
    - [Tool: Bash] notifications
    - [Error] messages

    Verbose mode shows everything:
    - All tool uses and inputs
    - Tool results
    - Thinking blocks
    - System messages
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.in_assistant_message = False

    def should_show_assistant_text(self) -> bool:
        """Always show assistant text."""
        return True

    def should_show_tool_use(self, tool_name: str) -> bool:
        """In quiet mode, only show Bash tool uses. In verbose mode, show all."""
        if self.verbose:
            return True
        return tool_name == "Bash"

    def should_show_tool_result(self, is_error: bool) -> bool:
        """In quiet mode, only show errors. In verbose mode, show all."""
        if self.verbose:
            return True
        return is_error

    def should_show_thinking(self) -> bool:
        """Only show thinking in verbose mode."""
        return self.verbose


def get_next_session_number(project_dir: Path) -> int:
    """
    Get the next session number by counting existing session logs.

    This ensures session numbers persist across script restarts.

    Args:
        project_dir: Project directory

    Returns:
        Next session number (1 if no logs exist)
    """
    log_dir = project_dir / "logs"
    if not log_dir.exists():
        return 1

    # Count existing session log files
    import glob
    session_files = glob.glob(str(log_dir / "session_*.jsonl"))

    if not session_files:
        return 1

    # Extract session numbers from filenames
    session_numbers = []
    for filepath in session_files:
        filename = os.path.basename(filepath)
        # Format: session_NNN_TIMESTAMP.jsonl
        try:
            parts = filename.split('_')
            if len(parts) >= 2:
                session_num = int(parts[1])
                session_numbers.append(session_num)
        except (ValueError, IndexError):
            continue

    if not session_numbers:
        return 1

    # Return max + 1
    return max(session_numbers) + 1


def create_session_logger(
    project_dir: Path,
    session_number: int,
    session_type: str,
    model: str = None,
    sandbox_type: str = "local",
    event_callback=None
) -> SessionLogger:
    """
    Create a session logger.

    Logging is always enabled and creates log files in the project's logs/ directory.

    Args:
        project_dir: Project directory
        session_number: Session iteration number (will be auto-determined if 0)
        session_type: "initializer" or "coding"
        model: Claude model being used (e.g., "claude-opus-4-5-20251101")
        sandbox_type: Sandbox type ("docker" or "local", default: "local")
        event_callback: Optional callback function(event_type, data) for real-time events

    Returns:
        SessionLogger instance
    """
    log_dir = project_dir / "logs"

    # Determine prompt file based on session and sandbox type
    from prompts import get_prompt_filename
    prompt_file = get_prompt_filename(session_type, sandbox_type)

    # Note: session_number can be 0 (initialization session) in 0-based numbering
    # We should trust the caller to provide the correct number from the database
    # Legacy auto-detection removed - database is the source of truth

    return SessionLogger(log_dir, session_number, session_type, model, prompt_file, event_callback)
