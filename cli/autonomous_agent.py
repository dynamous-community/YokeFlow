#!/usr/bin/env python3
"""
Autonomous Coding Agent
=======================

A harness for long-running autonomous coding with Claude.
This script implements the two-agent pattern (initializer + coding agent) and
incorporates all the strategies from the long-running agents guide.

Example Usage:
    python autonomous_agent.py --project-dir ./my_project
    python autonomous_agent.py --project-dir ./my_project --max-iterations 5
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from orchestrator import run_autonomous_agent_via_orchestrator


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent - Long-running agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start fresh project (uses Opus for initialization, Sonnet for coding)
  python autonomous_agent.py --project-dir ./my_project

  # Override model for both initializer and coding sessions
  python autonomous_agent.py --project-dir ./my_project --model claude-opus-4-5-20251101

  # Override just the initializer model (use Sonnet for planning)
  python autonomous_agent.py --project-dir ./my_project --initializer-model claude-sonnet-4-5-20250929

  # Override just the coding model (use Opus for implementation)
  python autonomous_agent.py --project-dir ./my_project --coding-model claude-opus-4-5-20251101

  # Limit iterations for testing
  python autonomous_agent.py --project-dir ./my_project --max-iterations 3

  # Use verbose mode (show detailed terminal output)
  python autonomous_agent.py --project-dir ./my_project --verbose

  # Continue existing project (runs in quiet mode by default)
  python autonomous_agent.py --project-dir ./my_project
        """,
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("./autonomous_demo_project"),
        help="Directory for the project (default: generations/autonomous_demo_project). Relative paths automatically placed in generations/ directory.",
    )

    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help="Path to specification file or folder (supports .txt, .md, or directory with multiple files). If not provided, uses default from specs/app_spec.txt",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Claude model to use for both initializer and coding (overrides defaults)",
    )

    parser.add_argument(
        "--initializer-model",
        type=str,
        default=None,
        help="Claude model for initialization session (overrides config file)",
    )

    parser.add_argument(
        "--coding-model",
        type=str,
        default=None,
        help="Claude model for coding sessions (overrides config file)",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to configuration file (default: auto-detect .autonomous-coding.yaml)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed terminal output (default is quiet mode; logs always capture everything)",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load configuration
    if args.config:
        config = Config.load_from_file(args.config)
        print(f"Loaded configuration from: {args.config}")
    else:
        config = Config.load_default()
        # Check if we loaded from a file
        if Path('.autonomous-coding.yaml').exists():
            print("Loaded configuration from: .autonomous-coding.yaml (current directory)")
        elif (Path.home() / '.autonomous-coding.yaml').exists():
            print(f"Loaded configuration from: {Path.home() / '.autonomous-coding.yaml'}")
        else:
            print("Using default configuration (no config file found)")


    if os.environ.get("ANTHROPIC_API_KEY"):
        print("Warning: Your ANTHROPIC_API_KEY environment variable is set")
        print("\nYou probably want to unset it to avoid unexpected charges and use your OAUTH_TOKEN instead.")
        return

    # Determine which models to use (CLI args override config file)
    # Priority: --model flag > --initializer/coding-model flags > config file > defaults
    if args.model:
        # --model overrides everything
        initializer_model = args.model
        coding_model = args.model
    else:
        # Use specific model flags if provided, otherwise use config
        initializer_model = args.initializer_model if args.initializer_model else config.models.initializer
        coding_model = args.coding_model if args.coding_model else config.models.coding

    # Use max_iterations from CLI if provided, otherwise from config
    max_iterations = args.max_iterations if args.max_iterations is not None else config.project.max_iterations

    # Automatically place projects in configured directory unless already specified
    project_dir = args.project_dir
    generations_dir = config.project.default_generations_dir

    if not str(project_dir).startswith(f"{generations_dir}/"):
        # Convert relative paths to be under configured generations directory
        if project_dir.is_absolute():
            # If absolute path, use as-is
            pass
        else:
            # Prepend generations directory to relative paths
            project_dir = Path(generations_dir) / project_dir

    # Run the agent via orchestrator
    # Note: Graceful shutdown (Ctrl+C) is now handled by SessionManager in orchestrator
    try:
        asyncio.run(
            run_autonomous_agent_via_orchestrator(
                project_dir=project_dir,
                initializer_model=initializer_model,
                coding_model=coding_model,
                _spec_source=args.spec,
                max_iterations=max_iterations,
                verbose=args.verbose,
            )
        )
    except KeyboardInterrupt:
        # This should rarely be reached now that SessionManager handles SIGINT
        # But keep as a fallback
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
