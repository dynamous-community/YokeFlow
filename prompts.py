"""
Prompt Loading Utilities
========================

Functions for loading prompt templates from the prompts directory.
"""

import shutil
import subprocess
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts"
SCHEMA_DIR = Path(__file__).parent / "schema"
SPECS_DIR = Path(__file__).parent / "specs"


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    return prompt_path.read_text()


def get_sandbox_preamble(sandbox_type: str = "local") -> str:
    """
    Load sandbox-specific preamble for tool selection guidance.

    DEPRECATED: Use get_initializer_prompt() or get_coding_prompt() instead.
    This function is kept for backward compatibility only.

    Args:
        sandbox_type: "docker" or "local" (default: "local")

    Returns:
        Preamble content as string
    """
    if sandbox_type == "docker":
        preamble_path = PROMPTS_DIR / "preambles" / "docker_sandbox.md"
    else:
        preamble_path = PROMPTS_DIR / "preambles" / "local_sandbox.md"

    if preamble_path.exists():
        return preamble_path.read_text()
    else:
        # Fallback for backward compatibility
        return ""


def get_initializer_prompt(sandbox_type: str = "local") -> str:
    """
    Load the initializer prompt for the specified sandbox type.

    Prompts are now split by sandbox type into separate files:
    - local: prompts/initializer_prompt_local.md
    - docker: prompts/initializer_prompt_docker.md

    Args:
        sandbox_type: "docker" or "local" (default: "local")

    Returns:
        Complete initializer prompt content as string
    """
    if sandbox_type == "docker":
        prompt_name = "initializer_prompt_docker"
    else:
        prompt_name = "initializer_prompt_local"

    return load_prompt(prompt_name)


def get_coding_prompt(sandbox_type: str = "local") -> str:
    """
    Load the coding agent prompt for the specified sandbox type.

    Prompts are now split by sandbox type into separate files:
    - local: prompts/coding_prompt_local.md
    - docker: prompts/coding_prompt_docker.md

    Args:
        sandbox_type: "docker" or "local" (default: "local")

    Returns:
        Complete coding prompt content as string
    """
    if sandbox_type == "docker":
        prompt_name = "coding_prompt_docker"
    else:
        prompt_name = "coding_prompt_local"

    return load_prompt(prompt_name)


def get_prompt_filename(session_type: str, sandbox_type: str = "local") -> str:
    """
    Get the prompt filename for logging purposes.

    Args:
        session_type: "initializer" or "coding"
        sandbox_type: "docker" or "local" (default: "local")

    Returns:
        Prompt filename (e.g., "initializer_prompt_local.md")
    """
    if session_type == "initializer":
        if sandbox_type == "docker":
            return "initializer_prompt_docker.md"
        else:
            return "initializer_prompt_local.md"
    else:  # coding
        if sandbox_type == "docker":
            return "coding_prompt_docker.md"
        else:
            return "coding_prompt_local.md"


def copy_spec_to_project(project_dir: Path, spec_source_path: Path = None) -> None:
    """
    Copy specification file(s) into the project directory for the agent to read.

    Supports multiple formats:
    - Single file: spec.txt, spec.md, README.md, etc.
    - Spec folder: directory with multiple documentation files

    Args:
        project_dir: Target project directory
        spec_source_path: Path to spec file or folder (if None, uses default from specs/)
    """
    # Determine source
    if spec_source_path is None:
        # Use default from specs/ directory
        spec_source = SPECS_DIR / "app_spec.txt"
        if not spec_source.exists():
            # Try spec.md as fallback
            spec_source = SPECS_DIR / "spec.md"
        if not spec_source.exists():
            raise FileNotFoundError(f"No default spec file found in {SPECS_DIR}")
    else:
        spec_source = Path(spec_source_path)
        if not spec_source.exists():
            raise FileNotFoundError(f"Spec source not found: {spec_source}")

    # Handle spec folder (directory with multiple files)
    if spec_source.is_dir():
        # Create spec/ subdirectory in project
        spec_dest_dir = project_dir / "spec"
        spec_dest_dir.mkdir(exist_ok=True)

        # Copy all files from spec folder
        copied_files = []
        for file in spec_source.glob("*"):
            if file.is_file():
                dest_file = spec_dest_dir / file.name
                if not dest_file.exists():
                    shutil.copy(file, dest_file)
                    copied_files.append(file.name)

        # Create a main app_spec.txt that references the spec folder
        main_spec = project_dir / "app_spec.txt"
        if not main_spec.exists():
            main_spec.write_text(
                f"# Project Specification\n\n"
                f"This project's specification is located in the `spec/` directory.\n\n"
                f"**Key files:**\n"
                + "\n".join(f"- spec/{f}" for f in sorted(copied_files))
                + "\n\n**Please read all files in the spec/ directory to understand the complete requirements.**\n"
            )

        print(f"Copied spec folder ({len(copied_files)} files) to project directory")

    # Handle single spec file
    else:
        # Determine destination filename
        spec_dest = project_dir / "app_spec.txt"

        # If source is not app_spec.txt, preserve original name and create pointer
        if spec_source.name != "app_spec.txt":
            # Copy with original name
            original_dest = project_dir / spec_source.name
            if not original_dest.exists():
                shutil.copy(spec_source, original_dest)

            # Create app_spec.txt as a pointer if needed
            if not spec_dest.exists():
                spec_dest.write_text(
                    f"# Project Specification\n\n"
                    f"The specification for this project is in: `{spec_source.name}`\n\n"
                    f"**Please read {spec_source.name} for the complete requirements.**\n"
                )
            print(f"Copied {spec_source.name} to project directory (app_spec.txt points to it)")
        else:
            # Direct copy for app_spec.txt
            if not spec_dest.exists():
                shutil.copy(spec_source, spec_dest)
                print("Copied app_spec.txt to project directory")


