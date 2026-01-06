"""
App Spec Generator
==================

Generates app_spec.md files from natural language descriptions using Claude.
Produces structured markdown output with section markers for agent consumption.

Usage:
    from core.spec_generator import generate_spec_stream

    # In an async context (FastAPI endpoint)
    async for event in generate_spec_stream(description="Build a task app..."):
        # Handle SSE events
        pass
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any

from dotenv import load_dotenv
from core.context_strategy import analyze_context_strategy

logger = logging.getLogger(__name__)


# ============================================================================
# JSON Schema for Claude's Output
# ============================================================================

SPEC_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "project_name": {
            "type": "string",
            "description": "Project name in lowercase with hyphens (e.g., 'task-manager')"
        },
        "overview": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "One paragraph describing what the app does, who it's for, and core problem it solves"
                },
                "success_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 measurable success criteria"
                },
                "constraints": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "constraint": {"type": "string"}
                        }
                    },
                    "description": "Timeline, compliance, compatibility constraints"
                },
                "out_of_scope": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Features explicitly out of scope for MVP"
                }
            },
            "required": ["summary", "success_criteria"]
        },
        "tech_stack": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "layer": {"type": "string"},
                    "technology": {"type": "string"},
                    "version": {"type": "string"}
                }
            },
            "description": "Tech stack as layer/technology/version tuples"
        },
        "frontend": {
            "type": "object",
            "properties": {
                "framework": {"type": "string"},
                "styling": {"type": "string"},
                "state_management": {"type": "string"},
                "routing": {"type": "string"},
                "build_tool": {"type": "string"},
                "key_dependencies": {"type": "object"},
                "directory_structure": {"type": "string"}
            }
        },
        "backend": {
            "type": "object",
            "properties": {
                "framework": {"type": "string"},
                "python_version": {"type": "string"},
                "orm": {"type": "string"},
                "validation": {"type": "string"},
                "auth": {"type": "string"},
                "key_dependencies": {"type": "array", "items": {"type": "string"}},
                "directory_structure": {"type": "string"}
            }
        },
        "database": {
            "type": "object",
            "properties": {
                "engine": {"type": "string"},
                "driver": {"type": "string"},
                "migrations": {"type": "string"},
                "conventions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "convention": {"type": "string"},
                            "rule": {"type": "string"}
                        }
                    }
                }
            }
        },
        "environment": {
            "type": "object",
            "properties": {
                "prerequisites": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string"},
                            "version": {"type": "string"}
                        }
                    }
                },
                "env_variables": {"type": "array", "items": {"type": "string"}}
            }
        }
    },
    "required": ["project_name", "overview", "tech_stack"]
}


# ============================================================================
# Markdown Conversion
# ============================================================================

def spec_to_markdown(spec: Dict[str, Any]) -> str:
    """
    Convert a spec dictionary to clean markdown format.
    
    Uses standard markdown headers. Section boundaries are implicit.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    project_name = spec.get("project_name", "Untitled Project")
    
    lines = []
    
    # Header
    lines.append(f"# App Specification: {project_name}")
    lines.append("")
    lines.append(f"> **Generated**: {timestamp}")
    lines.append("> **Status**: Pending Validation")
    lines.append("> **Version**: 1.0")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Overview Section
    lines.append("## Overview")
    lines.append("")
    
    overview = spec.get("overview", {})
    if isinstance(overview, str):
        # Handle old format
        lines.append("### Project Summary")
        lines.append("")
        lines.append(overview)
    else:
        lines.append("### Project Summary")
        lines.append("")
        lines.append(overview.get("summary", ""))
        lines.append("")
        
        # Success Criteria
        if overview.get("success_criteria"):
            lines.append("### Success Criteria")
            lines.append("")
            for criterion in overview["success_criteria"]:
                lines.append(f"- {criterion}")
            lines.append("")
        
        # Constraints
        if overview.get("constraints"):
            lines.append("### Constraints")
            lines.append("")
            lines.append("| Type | Constraint |")
            lines.append("|------|------------|")
            for constraint in overview["constraints"]:
                if isinstance(constraint, dict):
                    lines.append(f"| {constraint.get('type', '')} | {constraint.get('constraint', '')} |")
                else:
                    lines.append(f"| General | {constraint} |")
            lines.append("")
        
        # Out of Scope
        if overview.get("out_of_scope"):
            lines.append("### Out of Scope (MVP)")
            lines.append("")
            for item in overview["out_of_scope"]:
                lines.append(f"- {item}")
            lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # Tech Stack Summary
    lines.append("## Tech Stack")
    lines.append("")
    tech_stack = spec.get("tech_stack", [])
    if tech_stack:
        lines.append("| Layer | Technology | Version |")
        lines.append("|-------|------------|---------|")
        for item in tech_stack:
            if isinstance(item, dict):
                lines.append(f"| {item.get('layer', '')} | {item.get('technology', '')} | {item.get('version', '')} |")
            else:
                lines.append(f"| General | {item} | latest |")
        lines.append("")
    lines.append("---")
    lines.append("")
    
    # Frontend Section
    frontend = spec.get("frontend", {})
    lines.append("## Frontend")
    lines.append("")
    lines.append("### Technology Choices")
    lines.append("")
    if frontend:
        lines.append(f"- **Framework**: {frontend.get('framework', 'React 18.x with TypeScript')}")
        lines.append(f"- **Styling**: {frontend.get('styling', 'Tailwind CSS 3.x')}")
        lines.append(f"- **State Management**: {frontend.get('state_management', 'Zustand for client state, React Query for server state')}")
        lines.append(f"- **Routing**: {frontend.get('routing', 'React Router 6.x')}")
        lines.append(f"- **Build Tool**: {frontend.get('build_tool', 'Vite')}")
    else:
        lines.append("- **Framework**: React 18.x with TypeScript (strict mode)")
        lines.append("- **Styling**: Tailwind CSS 3.x")
        lines.append("- **State Management**: Zustand for client state, React Query for server state")
        lines.append("- **Routing**: React Router 6.x")
        lines.append("- **Build Tool**: Vite")
    lines.append("")
    
    # Frontend directory structure
    lines.append("### Directory Structure")
    lines.append("")
    lines.append("```")
    if frontend.get("directory_structure"):
        lines.append(frontend["directory_structure"])
    else:
        lines.append("""frontend/
├── src/
│   ├── components/
│   │   ├── ui/              # Base components (Button, Input, Modal, etc.)
│   │   └── features/        # Feature-specific components
│   ├── pages/               # Route-level components
│   ├── hooks/               # Custom React hooks
│   ├── store/               # Zustand stores
│   ├── services/            # API client functions
│   ├── types/               # TypeScript type definitions
│   └── utils/               # Helper functions
├── public/
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts""")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Backend Section
    backend = spec.get("backend", {})
    lines.append("## Backend")
    lines.append("")
    lines.append("### Technology Choices")
    lines.append("")
    if backend:
        lines.append(f"- **Framework**: {backend.get('framework', 'FastAPI 0.104+')}")
        lines.append(f"- **Python Version**: {backend.get('python_version', '3.11+')}")
        lines.append(f"- **ORM**: {backend.get('orm', 'SQLAlchemy 2.0 with async support')}")
        lines.append(f"- **Validation**: {backend.get('validation', 'Pydantic v2')}")
        lines.append(f"- **Auth**: {backend.get('auth', 'JWT with python-jose')}")
    else:
        lines.append("- **Framework**: FastAPI 0.104+")
        lines.append("- **Python Version**: 3.11+")
        lines.append("- **ORM**: SQLAlchemy 2.0 with async support")
        lines.append("- **Validation**: Pydantic v2")
        lines.append("- **Auth**: JWT with python-jose")
    lines.append("")
    
    # Backend dependencies
    if backend.get("key_dependencies"):
        lines.append("### Key Dependencies")
        lines.append("")
        lines.append("```txt")
        lines.append("# requirements.txt")
        for dep in backend["key_dependencies"]:
            lines.append(dep)
        lines.append("```")
        lines.append("")
    
    # Backend directory structure
    lines.append("### Directory Structure")
    lines.append("")
    lines.append("```")
    if backend.get("directory_structure"):
        lines.append(backend["directory_structure"])
    else:
        lines.append("""backend/
├── src/
│   ├── api/
│   │   └── routes/          # API route handlers
│   ├── core/
│   │   ├── config.py        # Settings with pydantic-settings
│   │   ├── database.py      # Async engine and session
│   │   ├── auth.py          # JWT utilities
│   │   └── exceptions.py    # Custom exceptions
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   └── utils/               # Helper functions
├── tests/
├── alembic/
├── main.py
└── requirements.txt""")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Database Section
    database = spec.get("database", {})
    lines.append("## Database")
    lines.append("")
    lines.append("### Technology Choices")
    lines.append("")
    if database:
        lines.append(f"- **Engine**: {database.get('engine', 'PostgreSQL 15+')}")
        lines.append(f"- **ORM**: {database.get('orm', 'SQLAlchemy 2.0 with async support')}")
        lines.append(f"- **Migrations**: {database.get('migrations', 'Alembic')}")
        lines.append(f"- **Driver**: {database.get('driver', 'asyncpg')}")
    else:
        lines.append("- **Engine**: PostgreSQL 15+")
        lines.append("- **ORM**: SQLAlchemy 2.0 with async support")
        lines.append("- **Migrations**: Alembic")
        lines.append("- **Driver**: asyncpg")
    lines.append("")
    
    # Database conventions
    lines.append("### Schema Conventions")
    lines.append("")
    lines.append("| Convention | Rule |")
    lines.append("|------------|------|")
    if database.get("conventions"):
        for conv in database["conventions"]:
            if isinstance(conv, dict):
                lines.append(f"| {conv.get('convention', '')} | {conv.get('rule', '')} |")
    else:
        lines.append("| Primary keys | UUID, generated with uuid4 |")
        lines.append("| Foreign keys | Named with `_id` suffix |")
        lines.append("| Timestamps | `created_at` and `updated_at` on all tables |")
        lines.append("| Soft deletes | `is_deleted` boolean + `deleted_at` timestamp |")
        lines.append("| String limits | Always specify max length |")
        lines.append("| Indexes | On foreign keys and frequently queried fields |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Testing Section
    lines.append("## Testing")
    lines.append("")
    lines.append("### Backend Testing (pytest)")
    lines.append("")
    lines.append("- Use `pytest` with `pytest-asyncio` for async tests")
    lines.append("- Create test database for isolation")
    lines.append("- Use factories for test data generation")
    lines.append("")
    lines.append("### Frontend Testing (Vitest + React Testing Library)")
    lines.append("")
    lines.append("- Unit test components with `@testing-library/react`")
    lines.append("- Mock stores and API calls")
    lines.append("- Use `data-testid` attributes for reliable selectors")
    lines.append("")
    lines.append("### E2E Testing (Playwright)")
    lines.append("")
    lines.append("- Test complete user flows")
    lines.append("- Use page object pattern")
    lines.append("- Run against test database")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Standards Section
    lines.append("## Coding Standards")
    lines.append("")
    lines.append("### General Rules")
    lines.append("")
    lines.append("- All code must pass linting without warnings")
    lines.append("- No hardcoded secrets or credentials")
    lines.append("- Environment variables for all configuration")
    lines.append("- Meaningful variable and function names")
    lines.append("- Comments for non-obvious logic only")
    lines.append("")
    lines.append("### TypeScript / Frontend")
    lines.append("")
    lines.append("| Rule | Example |")
    lines.append("|------|---------|")
    lines.append("| Strict mode enabled | `\"strict\": true` in tsconfig |")
    lines.append("| Explicit return types | `function getName(): string` |")
    lines.append("| No `any` type | Use `unknown` or proper types |")
    lines.append("| Components under 200 lines | Extract sub-components |")
    lines.append("| `data-testid` on interactive elements | `data-testid=\"submit-button\"` |")
    lines.append("")
    lines.append("### Python / Backend")
    lines.append("")
    lines.append("| Rule | Example |")
    lines.append("|------|---------|")
    lines.append("| Type hints on all signatures | `def create(self, data: TaskCreate) -> Task:` |")
    lines.append("| Docstrings on public functions | Triple-quoted description |")
    lines.append("| Async for I/O operations | `async def fetch_data():` |")
    lines.append("| No bare `except:` | Always specify exception type |")
    lines.append("| Max function length: 50 lines | Extract helper functions |")
    lines.append("")
    lines.append("### Git Conventions")
    lines.append("")
    lines.append("**Commit message format:**")
    lines.append("```")
    lines.append("<type>(<scope>): <description>")
    lines.append("")
    lines.append("Types: feat, fix, refactor, test, docs, chore")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Environment Section
    environment = spec.get("environment", {})
    lines.append("## Environment Setup")
    lines.append("")
    lines.append("### Prerequisites")
    lines.append("")
    lines.append("| Tool | Version |")
    lines.append("|------|---------|")
    if environment.get("prerequisites"):
        for prereq in environment["prerequisites"]:
            if isinstance(prereq, dict):
                lines.append(f"| {prereq.get('tool', '')} | {prereq.get('version', '')} |")
    else:
        lines.append("| Node.js | 18+ |")
        lines.append("| Python | 3.11+ |")
        lines.append("| Docker | 24+ |")
        lines.append("| Docker Compose | 2.0+ |")
    lines.append("")
    
    # Environment variables
    if environment.get("env_variables"):
        lines.append("### Environment Variables")
        lines.append("")
        lines.append("Create a `.env` file in the project root:")
        lines.append("")
        lines.append("```bash")
        for var in environment["env_variables"]:
            lines.append(var)
        lines.append("```")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # Validation Checklist
    lines.append("## Validation Checklist")
    lines.append("")
    lines.append("Before approving this specification, please verify:")
    lines.append("")
    lines.append("- [ ] Project overview accurately describes your goals")
    lines.append("- [ ] Tech stack matches your requirements")
    lines.append("- [ ] Code patterns align with your team's style")
    lines.append("- [ ] All constraints are captured")
    lines.append("- [ ] Nothing critical is missing from features")
    lines.append("")
    lines.append("**To approve**: Confirm this specification is complete and accurate.")
    lines.append("**To request changes**: Note specific modifications needed.")
    lines.append("")
    
    return "\n".join(lines)


# ============================================================================
# Prompt Generation
# ============================================================================

SPEC_GENERATION_PROMPT = """
# Project Specification Generator

You are creating a project specification that will be used by an autonomous AI coding agent.
The agent will use this specification to build a complete, production-ready application
autonomously over multiple coding sessions.

IMPORTANT: The project name should reflect the USER'S application, not the tool generating it.
Do NOT prefix the project name with "yokeflow" or any tool-related names.

## User's Project Description

{description}

{context_section}

{tech_preferences_section}

## Your Task

Create a comprehensive specification following this JSON structure. The output will be converted
to a markdown document with section markers for selective agent reading.

### 1. project_name
- Lowercase with hyphens (e.g., "task-manager", "route-planner")
- Concise but descriptive
- No spaces or special characters

### 2. overview (object with these fields)
- **summary**: One paragraph (3-5 sentences) describing what the app does, target users, and value proposition
- **success_criteria**: Array of 3-5 measurable success criteria
- **constraints**: Array of objects with "type" and "constraint" fields (timeline, compliance, compatibility)
- **out_of_scope**: Array of features explicitly out of scope for MVP

### 3. tech_stack
Array of objects with:
- **layer**: Frontend, Backend, Database, Cache, Testing, etc.
- **technology**: Specific technology name (React, FastAPI, PostgreSQL)
- **version**: Version requirement (e.g., "18.x", "0.104+", "15+")

### 4. frontend (object)
- **framework**: e.g., "React 18.x with TypeScript (strict mode)"
- **styling**: e.g., "Tailwind CSS 3.x"
- **state_management**: e.g., "Zustand for client state, React Query for server state"
- **routing**: e.g., "React Router 6.x"
- **build_tool**: e.g., "Vite"

### 5. backend (object)
- **framework**: e.g., "FastAPI 0.104+"
- **python_version**: e.g., "3.11+"
- **orm**: e.g., "SQLAlchemy 2.0 with async support"
- **validation**: e.g., "Pydantic v2"
- **auth**: e.g., "JWT with python-jose"
- **key_dependencies**: Array of requirement lines (e.g., "fastapi>=0.104.0")

### 6. database (object)
- **engine**: e.g., "PostgreSQL 15+"
- **driver**: e.g., "asyncpg"
- **migrations**: e.g., "Alembic"
- **conventions**: Array of objects with "convention" and "rule" fields

### 7. environment (object)
- **prerequisites**: Array of objects with "tool" and "version" fields
- **env_variables**: Array of environment variable lines (e.g., "DATABASE_URL=postgresql+asyncpg://...")

## Critical Guidelines

- Be SPECIFIC. The agent needs actionable details, not vague descriptions.
- Cover ALL features from the user's description. Nothing should be omitted.
- Include enough detail that the agent can implement without clarification.
- If the user didn't specify tech stack, recommend appropriate modern technologies.
- The specification should be complete enough to build a production-ready MVP.

## Output Format

You MUST output a valid JSON object wrapped in ```json ... ``` code blocks.
The JSON must match this structure:

```json
{{
  "project_name": "string",
  "overview": {{
    "summary": "string",
    "success_criteria": ["string", ...],
    "constraints": [{{"type": "string", "constraint": "string"}}, ...],
    "out_of_scope": ["string", ...]
  }},
  "tech_stack": [
    {{"layer": "Frontend", "technology": "React + TypeScript", "version": "18.x"}},
    ...
  ],
  "frontend": {{ ... }},
  "backend": {{ ... }},
  "database": {{ ... }},
  "environment": {{ ... }}
}}
```

Output ONLY the JSON. No explanatory text before or after the JSON block.
"""


def build_generation_prompt(
    description: str,
    context_files_summary: Optional[str] = None,
    technology_preferences: Optional[str] = None
) -> str:
    """Build the complete prompt for spec generation."""

    # Context section
    if context_files_summary:
        context_section = f"""
## Context Files Provided

The user has provided the following context files for reference:

{context_files_summary}

Use these files to:
- Understand the desired code style and patterns
- Identify specific technologies or frameworks to use
- Extract detailed requirements from existing documentation
"""
    else:
        context_section = ""

    # Tech preferences section
    if technology_preferences:
        tech_preferences_section = f"""
## User's Technology Preferences

The user has specified they prefer: {technology_preferences}

Incorporate these preferences into your technology stack recommendations.
"""
    else:
        tech_preferences_section = ""

    return SPEC_GENERATION_PROMPT.format(
        description=description,
        context_section=context_section,
        tech_preferences_section=tech_preferences_section
    )


# ============================================================================
# JSON Extraction
# ============================================================================

def extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from Claude's response text.

    Handles:
    - JSON wrapped in ```json ... ``` code blocks
    - Raw JSON objects
    - JSON with surrounding text

    Returns:
        Parsed JSON dict or None if extraction fails
    """
    # Try to extract from code block first
    code_block_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
    matches = re.findall(code_block_pattern, text)

    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try to find raw JSON object
    # Look for { ... } pattern
    brace_start = text.find('{')
    if brace_start != -1:
        # Find matching closing brace
        depth = 0
        for i, char in enumerate(text[brace_start:], brace_start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i+1])
                    except json.JSONDecodeError:
                        break

    return None


# ============================================================================
# Spec Generation with Streaming
# ============================================================================

async def generate_spec_stream(
    description: str,
    project_name: Optional[str] = None,
    context_files: Optional[List[Any]] = None,  # List of UploadFile
    technology_preferences: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Generate app_spec.md using Claude SDK with streaming.

    Yields SSE-formatted events:
    - data: {"type": "spec_progress", "content": "...", "phase": "..."}
    - data: {"type": "spec_complete", "markdown": "...", "project_name": "..."}
    - data: {"type": "spec_error", "error": "..."}

    Args:
        description: Natural language project description
        project_name: Optional suggested project name
        context_files: Optional list of UploadFile objects for context
        technology_preferences: Optional technology preferences string
    """
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    # Ensure authentication is configured
    agent_root = Path(__file__).parent.parent
    agent_env_file = agent_root / ".env"
    load_dotenv(dotenv_path=agent_env_file)

    # CRITICAL: Remove any leaked ANTHROPIC_API_KEY first
    os.environ.pop("ANTHROPIC_API_KEY", None)

    oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
    if not oauth_token:
        yield format_sse_event("spec_error", {"error": "CLAUDE_CODE_OAUTH_TOKEN not configured in .env"})
        return

    # Set OAuth token for SDK
    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token

    # Create temp directory for context files if provided
    temp_dir = None
    context_summary = None

    try:
        if context_files:
            temp_dir = tempfile.mkdtemp(prefix="yokeflow_spec_")
            context_parts = []

            for file in context_files:
                # Save file to temp directory
                file_path = Path(temp_dir) / file.filename
                content = await file.read()
                file_path.write_bytes(content)
                await file.seek(0)  # Reset for potential re-read

                # Build summary
                try:
                    text_content = content.decode('utf-8')
                    # Truncate if too long (reduced to prevent timeout)
                    if len(text_content) > 2000:
                        text_content = text_content[:2000] + "\n... (truncated for spec generation, full file available later)"
                    context_parts.append(f"### {file.filename}\n```\n{text_content}\n```")
                except UnicodeDecodeError:
                    context_parts.append(f"### {file.filename}\n(binary file, {len(content)} bytes)")

            context_summary = "\n\n".join(context_parts)

        # Build the prompt
        prompt = build_generation_prompt(
            description=description,
            context_files_summary=context_summary,
            technology_preferences=technology_preferences
        )

        # Add project name hint if provided
        if project_name:
            prompt += f"\n\n**Note:** The user suggests the project name '{project_name}'. Use this if appropriate, or suggest a better name."

        yield format_sse_event("spec_progress", {
            "content": "Starting specification generation...",
            "phase": "initializing"
        })

        # Create Claude SDK client
        # No tools needed - we just want text generation
        working_dir = temp_dir if temp_dir else str(Path.cwd())

        client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model="claude-sonnet-4-5-20250929",  # Fast model for spec generation
                system_prompt="You are an expert software architect creating detailed project specifications. Output only valid JSON.",
                permission_mode="default",
                max_turns=10,  # Should complete in 1-2 turns
                cwd=working_dir,
            )
        )

        yield format_sse_event("spec_progress", {
            "content": "Analyzing requirements and designing specification...",
            "phase": "analyzing"
        })

        # Collect response
        response_text = ""
        
        # Track timing for progress feedback
        import asyncio
        import time
        start_time = time.time()
        last_heartbeat = start_time
        HEARTBEAT_INTERVAL = 5  # seconds
        MAX_GENERATION_TIME = 300  # 5 minutes timeout (increased for large context)

        async with client:
            # Send the query (this starts the generation)
            query_task = asyncio.create_task(client.query(prompt))
            
            # Wait for query with periodic heartbeats
            while not query_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(query_task), timeout=HEARTBEAT_INTERVAL)
                except asyncio.TimeoutError:
                    # Query still running, send heartbeat
                    elapsed = int(time.time() - start_time)
                    
                    # Check for timeout
                    if elapsed > MAX_GENERATION_TIME:
                        query_task.cancel()
                        yield format_sse_event("spec_error", {
                            "error": f"Generation timed out after {elapsed}s. Please try again with fewer context files."
                        })
                        return
                    
                    # Send simple, honest heartbeat
                    yield format_sse_event("spec_progress", {
                        "content": f"Generating specification... ({elapsed}s)",
                        "phase": "generating",
                        "elapsed_seconds": elapsed
                    })
            
            # Check if query raised an exception
            if query_task.exception():
                raise query_task.exception()

            # Receive streaming response with heartbeats
            # Use async iterator with timeout to send heartbeats while waiting
            yield format_sse_event("spec_progress", {
                "content": "Receiving response...",
                "phase": "receiving",
                "elapsed_seconds": int(time.time() - start_time)
            })
            
            # Create async iterator from receive_response
            response_iter = client.receive_response().__aiter__()
            response_complete = False
            pending_next = None  # Track pending __anext__ call
            
            while not response_complete:
                try:
                    # Create or reuse pending __anext__ call
                    if pending_next is None:
                        pending_next = asyncio.ensure_future(response_iter.__anext__())
                    
                    # Try to get next message with timeout
                    msg = await asyncio.wait_for(
                        asyncio.shield(pending_next),
                        timeout=HEARTBEAT_INTERVAL
                    )
                    pending_next = None  # Clear after successful receive
                    
                    msg_type = type(msg).__name__

                    # Handle AssistantMessage (text content)
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            block_type = type(block).__name__

                            if block_type == "TextBlock" and hasattr(block, "text"):
                                response_text += block.text

                                # Send progress updates (truncated)
                                preview = block.text[:100].replace('\n', ' ')
                                if preview:
                                    yield format_sse_event("spec_progress", {
                                        "content": preview + "..." if len(block.text) > 100 else preview,
                                        "phase": "generating",
                                        "elapsed_seconds": int(time.time() - start_time)
                                    })
                                    
                            elif block_type == "ThinkingBlock":
                                # Claude is thinking - show thinking indicator
                                yield format_sse_event("spec_progress", {
                                    "content": "Claude is thinking...",
                                    "phase": "thinking",
                                    "elapsed_seconds": int(time.time() - start_time)
                                })

                    # Handle ResultMessage (completion)
                    elif msg_type == "ResultMessage":
                        elapsed = int(time.time() - start_time)
                        yield format_sse_event("spec_progress", {
                            "content": f"Completed in {elapsed}s",
                            "phase": "complete",
                            "elapsed_seconds": elapsed
                        })
                        logger.info(f"Spec generation completed in {elapsed}s")
                        response_complete = True
                        
                except asyncio.TimeoutError:
                    # No message received in HEARTBEAT_INTERVAL, send heartbeat
                    elapsed = int(time.time() - start_time)
                    
                    # Check for overall timeout
                    if elapsed > MAX_GENERATION_TIME:
                        yield format_sse_event("spec_error", {
                            "error": f"Generation timed out after {elapsed}s. Please try again."
                        })
                        return
                    
                    # Send simple, honest heartbeat
                    yield format_sse_event("spec_progress", {
                        "content": f"Generating specification... ({elapsed}s)",
                        "phase": "generating",
                        "elapsed_seconds": elapsed
                    })
                    
                except StopAsyncIteration:
                    # Iterator exhausted
                    response_complete = True

        # Parse JSON from response
        spec_data = extract_json_from_response(response_text)

        if spec_data:
            # Convert to Markdown with section markers
            markdown_content = spec_to_markdown(spec_data)

            # Analyze context strategy
            context_strategy_result = analyze_context_strategy(context_files or [], markdown_content)
            logger.info(f"Context strategy: {context_strategy_result['strategy']} - {context_strategy_result['reason']}")

            yield format_sse_event("spec_complete", {
                "markdown": markdown_content,
                "project_name": spec_data.get("project_name", ""),
                "context_strategy": context_strategy_result
            })
        else:
            # If JSON extraction failed, log the response for debugging
            logger.error(f"Failed to extract JSON from response: {response_text[:500]}")
            yield format_sse_event("spec_error", {
                "error": "Failed to parse specification from Claude's response. Please try again."
            })

    except Exception as e:
        logger.exception("Error during spec generation")
        yield format_sse_event("spec_error", {"error": str(e)})

    finally:
        # Cleanup temp directory
        if temp_dir:
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format data as an SSE event string."""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"


# ============================================================================
# Synchronous wrapper for testing
# ============================================================================

def generate_spec_sync(
    description: str,
    project_name: Optional[str] = None,
    technology_preferences: Optional[str] = None
) -> str:
    """
    Synchronous wrapper for generate_spec_stream.
    Returns the final markdown spec or raises an exception.
    """
    import asyncio

    async def run():
        markdown_result = None
        error = None

        async for event in generate_spec_stream(
            description=description,
            project_name=project_name,
            technology_preferences=technology_preferences
        ):
            # Parse SSE event
            if event.startswith("data: "):
                data = json.loads(event[6:].strip())
                if data["type"] == "spec_complete":
                    markdown_result = data["markdown"]
                elif data["type"] == "spec_error":
                    error = data["error"]

        if error:
            raise RuntimeError(error)
        if not markdown_result:
            raise RuntimeError("No specification generated")

        return markdown_result

    return asyncio.run(run())
