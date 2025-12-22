"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Awaitable
from datetime import datetime

from claude_agent_sdk import ClaudeSDKClient

from client import create_client
from database_connection import DatabaseManager
from progress import print_session_header, print_progress_summary
from prompts import get_initializer_prompt, get_coding_prompt, copy_spec_to_project
from observability import SessionLogger, QuietOutputFilter, create_session_logger


# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3


class SessionManager:
    """
    Manages graceful shutdown for agent sessions.

    Handles SIGINT (Ctrl+C) and SIGTERM signals to ensure sessions
    are properly finalized before exit.
    """

    def __init__(self, allow_exit: bool = True):
        """
        Initialize session manager.

        Args:
            allow_exit: If True, calls sys.exit() on interrupt (CLI mode).
                       If False, raises KeyboardInterrupt instead (API mode).
        """
        self.interrupted = False
        self.current_logger: Optional[SessionLogger] = None
        self._original_sigint = None
        self._original_sigterm = None
        self.allow_exit = allow_exit

    def setup_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_interrupt)
        self._original_sigterm = signal.signal(signal.SIGTERM, self._handle_interrupt)

    def restore_handlers(self):
        """Restore original signal handlers."""
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)

    def _handle_interrupt(self, signum, frame):
        """Handle interrupt signal."""
        if self.interrupted:
            # Second interrupt - force exit or raise exception
            print("\n\nForce exit (second interrupt)")
            if self.allow_exit:
                sys.exit(1)
            else:
                raise KeyboardInterrupt("Force interrupt")

        self.interrupted = True
        signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"

        print(f"\n\n{'='*70}")
        print(f"  Received {signal_name} - Shutting down gracefully...")
        print(f"{'='*70}")

        # Finalize current session if one is active
        if self.current_logger:
            try:
                print("\nFinalizing session logs...")
                self.current_logger.finalize("interrupted", "Session interrupted by user")
                print("✓ Session logs saved")
            except Exception as e:
                print(f"Warning: Could not finalize session logs: {e}")

        print("\nSession interrupted. To resume, run the same command again.")
        print(f"{'='*70}\n")

        if self.allow_exit:
            sys.exit(0)
        else:
            # Raise KeyboardInterrupt so orchestrator can catch it
            raise KeyboardInterrupt("Session interrupted")

    def set_current_logger(self, logger: Optional[SessionLogger]):
        """Set the current active logger for graceful shutdown."""
        self.current_logger = logger


async def run_agent_session(
    client: ClaudeSDKClient,
    message: str,
    project_dir: Path,
    logger: SessionLogger,
    verbose: bool = False,
    session_manager: Optional[SessionManager] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> tuple[str, str]:
    """
    Run a single agent session using Claude Agent SDK.

    Args:
        client: Claude SDK client
        message: The prompt to send
        project_dir: Project directory path
        logger: Session logger for recording events
        verbose: If True, show detailed terminal output (default: quiet mode)
        session_manager: Optional session manager for interrupt checking
        progress_callback: Optional async callback for real-time progress updates.
                          Called with event dict containing type, tool_name, timestamp, etc.

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    output_filter = QuietOutputFilter(verbose=verbose)

    if verbose:
        print("Sending prompt to Claude Agent SDK...\n")

    # Log the prompt (JSONL only for agent review, not in TXT or terminal)
    logger.log_prompt(message)

    try:
        # Send the query
        await client.query(message)

        # Collect response text and show tool use
        response_text = ""
        message_count = 0
        usage_data = None  # Will be populated by ResultMessage

        async for msg in client.receive_response():
            # Check if session was interrupted
            if session_manager and session_manager.interrupted:
                print("\n\nSession interrupted by user request")
                raise KeyboardInterrupt("Session stopped by user")

            msg_type = type(msg).__name__

            # Handle ResultMessage (final message with usage data)
            if msg_type == "ResultMessage":
                # Extract usage and cost information
                if hasattr(msg, "usage") and msg.usage:
                    usage_data = {
                        "input_tokens": msg.usage.get("input_tokens", 0),
                        "output_tokens": msg.usage.get("output_tokens", 0),
                        "cache_creation_input_tokens": msg.usage.get("cache_creation_input_tokens", 0),
                        "cache_read_input_tokens": msg.usage.get("cache_read_input_tokens", 0),
                    }

                    # Extract cost if available
                    if hasattr(msg, "total_cost_usd") and msg.total_cost_usd is not None:
                        usage_data["cost_usd"] = msg.total_cost_usd

                    # Log to JSONL
                    logger.log_result_message(usage_data)

                    if verbose:
                        print(f"\n[Usage] Input: {usage_data['input_tokens']:,} tokens, Output: {usage_data['output_tokens']:,} tokens", flush=True)
                        if "cost_usd" in usage_data:
                            print(f"[Cost] ${usage_data['cost_usd']:.4f}", flush=True)

                continue

            # Handle AssistantMessage (text and tool use)
            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        response_text += block.text

                        # Check for critical errors that should stop the session immediately
                        if "Credit balance is too low" in block.text:
                            error_msg = "Credit balance is too low - API key is being used instead of OAuth token"
                            logger.log_error(error_msg)
                            print(f"\n❌ FATAL ERROR: {error_msg}", flush=True)
                            print("   This usually means ANTHROPIC_API_KEY leaked from the generated project.", flush=True)
                            print("   Check generations/{project}/.env and remove ANTHROPIC_API_KEY if present.", flush=True)
                            raise RuntimeError(error_msg)

                        # Log assistant text
                        logger.log_assistant_text(block.text)

                        # Always show assistant text (even in quiet mode)
                        if output_filter.should_show_assistant_text():
                            # Add newline before message if this is not the first message
                            if message_count > 0:
                                print()
                            print(block.text, end="", flush=True)
                            message_count += 1

                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        tool_name = block.name
                        tool_id = getattr(block, "id", "unknown")
                        tool_input = getattr(block, "input", {})

                        # Log tool use
                        logger.log_tool_use(tool_name, tool_id, tool_input)

                        # Send progress update via callback
                        if progress_callback:
                            try:
                                await progress_callback({
                                    "type": "tool_use",
                                    "tool_name": tool_name,
                                    "tool_id": tool_id,
                                    "timestamp": datetime.now().isoformat()
                                })
                            except Exception as e:
                                # Don't fail session if callback fails
                                logger.log_error(f"Progress callback failed: {e}")

                        # Show tool use based on verbose mode
                        if output_filter.should_show_tool_use(tool_name):
                            print(f"\n[Tool: {tool_name}]", flush=True)
                            if verbose and hasattr(block, "input"):
                                input_str = str(block.input)
                                if len(input_str) > 200:
                                    print(f"   Input: {input_str[:200]}...", flush=True)
                                else:
                                    print(f"   Input: {input_str}", flush=True)

                    elif block_type == "ThinkingBlock" and hasattr(block, "thinking"):
                        # Log thinking
                        logger.log_thinking(block.thinking)

                        # Show thinking based on quiet mode
                        if output_filter.should_show_thinking():
                            print(f"\n[Thinking]\n{block.thinking[:500]}...\n", flush=True)

            # Handle UserMessage (tool results)
            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "ToolResultBlock":
                        result_content = getattr(block, "content", "")
                        is_error = getattr(block, "is_error", False)
                        tool_id = getattr(block, "tool_use_id", "unknown")

                        # Log tool result
                        logger.log_tool_result(tool_id, result_content, is_error)

                        # Send progress update via callback
                        if progress_callback:
                            try:
                                await progress_callback({
                                    "type": "tool_result",
                                    "tool_id": tool_id,
                                    "is_error": is_error,
                                    "timestamp": datetime.now().isoformat()
                                })
                            except Exception as e:
                                # Don't fail session if callback fails
                                logger.log_error(f"Progress callback failed: {e}")

                        # Show based on verbose mode
                        if output_filter.should_show_tool_result(is_error):
                            if is_error:
                                # Show errors (truncated)
                                error_str = str(result_content)[:500]
                                print(f"   [Error] {error_str}", flush=True)
                            elif verbose:
                                # Tool succeeded - show brief confirmation in verbose mode only
                                print("   [Done]", flush=True)

            # Handle SystemMessage
            elif msg_type == "SystemMessage":
                subtype = getattr(msg, "subtype", "unknown")
                message_text = str(msg)

                logger.log_system_message(subtype, message_text)

                # Check for API key usage warning (init message only)
                if subtype == "init" and hasattr(msg, "data"):
                    api_key_source = msg.data.get("apiKeySource", "none")
                    if api_key_source == "ANTHROPIC_API_KEY" and progress_callback:
                        # Send warning to UI via WebSocket
                        try:
                            await progress_callback({
                                "type": "api_key_warning",
                                "source": api_key_source,
                                "message": (
                                    "⚠️ Using ANTHROPIC_API_KEY (credit-based billing). "
                                    "This is more expensive than CLAUDE_CODE_OAUTH_TOKEN (membership plan). "
                                    "Check if ANTHROPIC_API_KEY leaked from project .env file."
                                ),
                                "timestamp": datetime.now().isoformat()
                            })
                        except Exception as e:
                            logger.log_error(f"Failed to send API key warning: {e}")

                        # Also print warning to console
                        print("\n" + "=" * 80)
                        print("⚠️  WARNING: Using ANTHROPIC_API_KEY (Credit-Based Billing)")
                        print("=" * 80)
                        print("You are using an API key instead of OAuth token (membership plan).")
                        print("This is significantly more expensive (~$3/million tokens vs included in plan).")
                        print("")
                        print("Common causes:")
                        print("  1. ANTHROPIC_API_KEY leaked from generated project's .env file")
                        print("  2. ANTHROPIC_API_KEY set in system environment")
                        print("")
                        print("To fix:")
                        print("  1. Check generations/{project}/.env and remove ANTHROPIC_API_KEY")
                        print("  2. Unset ANTHROPIC_API_KEY: unset ANTHROPIC_API_KEY")
                        print("  3. Ensure CLAUDE_CODE_OAUTH_TOKEN is set in agent's .env file")
                        print("=" * 80 + "\n")

                if verbose:
                    print(f"[System: {subtype}] {message_text}", flush=True)

        if verbose:
            print("\n" + "-" * 70 + "\n")

        # Finalize logging and get session summary
        session_summary = logger.finalize("continue", response_text, usage_data=usage_data)

        return "continue", response_text, session_summary

    except Exception as e:
        print(f"Error during agent session: {e}")

        # Log error
        logger.log_error(e)
        session_summary = logger.finalize("error", "", usage_data=usage_data)

        return "error", str(e), session_summary


async def run_autonomous_agent(
    project_dir: Path,
    initializer_model: str,
    coding_model: str,
    max_iterations: Optional[int] = None,
    verbose: bool = False,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        initializer_model: Claude model to use for initialization session
        coding_model: Claude model to use for coding sessions
        max_iterations: Maximum number of iterations (None for unlimited)
        verbose: If True, show detailed terminal output (default: quiet mode)
    """
    # Set up graceful shutdown handling
    session_manager = SessionManager()
    session_manager.setup_handlers()

    try:
        await _run_agent_loop(
            project_dir=project_dir,
            initializer_model=initializer_model,
            coding_model=coding_model,
            max_iterations=max_iterations,
            verbose=verbose,
            session_manager=session_manager,
        )
    finally:
        # Restore original signal handlers
        session_manager.restore_handlers()


async def _run_agent_loop(
    project_dir: Path,
    initializer_model: str,
    coding_model: str,
    max_iterations: Optional[int],
    verbose: bool,
    session_manager: SessionManager,
) -> None:
    """
    Internal function for the agent loop (separated for signal handling).

    Args:
        project_dir: Directory for the project
        initializer_model: Claude model to use for initialization session
        coding_model: Claude model to use for coding sessions
        max_iterations: Maximum number of iterations (None for unlimited)
        verbose: If True, show detailed terminal output
        session_manager: Session manager for graceful shutdown
    """
    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT DEMO")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print(f"Initializer model: {initializer_model}")
    print(f"Coding model: {coding_model}")
    if max_iterations:
        print(f"Max iterations: {max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    print("Task management: MCP-based (mcp__task-manager__* tools)")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Check if this is a fresh start or continuation
    # Check PostgreSQL database for epics to determine if initialization is needed
    project_name = project_dir.name
    is_first_run = False

    async with DatabaseManager() as db:
        project = await db.get_project_by_name(project_name)
        if project:
            # Project exists - check if it has epics (initialization complete)
            epics = await db.list_epics(project['id'])
            is_first_run = len(epics) == 0
        else:
            # Project doesn't exist in database - this is a fresh start
            is_first_run = True

    if is_first_run:
        print("Fresh start - will use initializer agent")
        print()
        print("=" * 70)
        print("  NOTE: First session (initialization) will set up the database")
        print("  and create the hierarchical task structure. This may take a few minutes.")
        print("  The agent will stop after initialization is complete.")
        print("=" * 70)
        print()
        # Copy the app spec to project directory
        copy_spec_to_project(project_dir)
    else:
        print("Continuing existing project")
        print_progress_summary(project_dir)

    # Main loop
    # Note: iteration is for the current script run, session number is global across all runs
    iteration = 0

    while True:
        iteration += 1

        # Check max iterations
        if max_iterations and iteration > max_iterations:
            print(f"\nReached max iterations ({max_iterations})")
            print("To continue, run the script again without --max-iterations")
            break

        # Print session header
        print_session_header(iteration, is_first_run)

        # Determine session type and model to use
        session_type = "initializer" if is_first_run else "coding"
        current_model = initializer_model if is_first_run else coding_model

        # Create session logger (always enabled)
        # Pass 0 to auto-determine session number from existing logs
        logger = create_session_logger(project_dir, 0, session_type, current_model)

        # Register logger with session manager for graceful shutdown
        session_manager.set_current_logger(logger)

        if verbose:
            print(f"Session log: {logger.jsonl_file.relative_to(project_dir)}")
            print(f"Using model: {current_model}")
            print()

        # Create client (fresh context) with appropriate model
        client = create_client(project_dir, current_model)

        # Choose prompt based on session type
        if is_first_run:
            prompt = get_initializer_prompt()
            was_initializer = True
            is_first_run = False  # Only use initializer once
        else:
            prompt = get_coding_prompt()
            was_initializer = False

        # Run session with async context manager
        async with client:
            status, response = await run_agent_session(
                client, prompt, project_dir, logger=logger, verbose=verbose
            )

        # Clear the logger from session manager (session is complete)
        session_manager.set_current_logger(None)

        # Stop after initializer completes
        if was_initializer:
            print("\n" + "=" * 70)
            print("  INITIALIZATION COMPLETE")
            print("=" * 70)
            print("\nThe task database has been set up successfully.")
            print("Run the script again to start the coding sessions.")
            print("\nTask management is handled via MCP tools.")
            print("The agent uses mcp__task-manager__* tools to interact with tasks.")
            print("=" * 70)
            break

        # Handle status for coding sessions
        if status == "continue":
            print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(project_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        elif status == "error":
            print("\n" + "=" * 70)
            print("  SESSION ENDED DUE TO ERROR")
            print("=" * 70)
            print("\nThe session encountered an error and has been terminated.")
            print("Session logs have been saved.")
            print("\nTo retry, run the same command again.")
            print("The agent will resume from where it left off.")
            print("=" * 70)
            break  # Exit the loop on error instead of retrying

        # Small delay between sessions (only if continuing)
        if status == "continue" and (max_iterations is None or iteration < max_iterations):
            print("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    # Print instructions for running the generated application
    print("\n" + "-" * 70)
    print("  TO RUN THE GENERATED APPLICATION:")
    print("-" * 70)
    print(f"\n  cd {project_dir.resolve()}")
    print("  ./init.sh           # Run the setup script")
    print("  # Or manually:")
    print("  npm install && npm run dev")
    print("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
    print("-" * 70)

    print("\nDone!")
