"""
App Spec Generator
==================

Generates app_spec.txt files from natural language descriptions using Claude.
Produces structured XML output matching YokeFlow's specification format.

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class RoadmapPhase:
    """A phase in the implementation roadmap."""
    phase: str
    status: str  # Always "pending" for new projects
    description: str


@dataclass
class ImplementedFeature:
    """A feature that has been implemented (empty for new projects)."""
    name: str
    description: str
    file_locations: Optional[List[str]] = None


@dataclass
class SpecOutput:
    """Structured output for project specification."""
    project_name: str
    overview: str
    technology_stack: List[str]
    core_capabilities: List[str]
    implemented_features: List[Dict[str, Any]] = field(default_factory=list)
    additional_requirements: Optional[List[str]] = None
    development_guidelines: Optional[List[str]] = None
    implementation_roadmap: Optional[List[Dict[str, str]]] = None


# JSON Schema for Claude's structured output
SPEC_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "project_name": {
            "type": "string",
            "description": "Project name in lowercase with hyphens (e.g., 'task-manager')"
        },
        "overview": {
            "type": "string",
            "description": "Comprehensive description of the project's purpose, users, and goals"
        },
        "technology_stack": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of technologies, frameworks, and tools to use"
        },
        "core_capabilities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Main feature areas the application must provide"
        },
        "implemented_features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "file_locations": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["name", "description"]
            },
            "description": "Features already implemented (leave empty for new projects)"
        },
        "additional_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Non-functional requirements like performance, security, deployment"
        },
        "development_guidelines": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Coding standards and practices to follow"
        },
        "implementation_roadmap": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "description": "Name of the implementation phase"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                        "description": "Current status (use 'pending' for new projects)"
                    },
                    "description": {
                        "type": "string",
                        "description": "What this phase involves"
                    }
                },
                "required": ["phase", "status", "description"]
            },
            "description": "Implementation phases ordered by dependency"
        }
    },
    "required": [
        "project_name",
        "overview",
        "technology_stack",
        "core_capabilities",
        "implemented_features"
    ],
    "additionalProperties": False
}


# ============================================================================
# XML Conversion
# ============================================================================

def escape_xml(text: str) -> str:
    """Escape special XML characters."""
    if not text:
        return ""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def spec_to_xml(spec: Dict[str, Any]) -> str:
    """
    Convert a SpecOutput dictionary to XML format.

    Matches the format in generations/opti-route/app_spec.txt:
    - 2-space indentation
    - Proper XML escaping
    - All sections in order
    """
    indent = "  "

    # Start XML document
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<project_specification>',
        f'{indent}<project_name>{escape_xml(spec["project_name"])}</project_name>',
        '',
        f'{indent}<overview>',
        f'{indent}{indent}{escape_xml(spec["overview"])}',
        f'{indent}</overview>',
        ''
    ]

    # Technology stack
    xml_parts.append(f'{indent}<technology_stack>')
    for tech in spec.get("technology_stack", []):
        xml_parts.append(f'{indent}{indent}<technology>{escape_xml(tech)}</technology>')
    xml_parts.append(f'{indent}</technology_stack>')
    xml_parts.append('')

    # Core capabilities
    xml_parts.append(f'{indent}<core_capabilities>')
    for cap in spec.get("core_capabilities", []):
        xml_parts.append(f'{indent}{indent}<capability>{escape_xml(cap)}</capability>')
    xml_parts.append(f'{indent}</core_capabilities>')
    xml_parts.append('')

    # Implemented features (usually empty for new projects)
    xml_parts.append(f'{indent}<implemented_features>')
    for feature in spec.get("implemented_features", []):
        xml_parts.append(f'{indent}{indent}<feature>')
        xml_parts.append(f'{indent}{indent}{indent}<name>{escape_xml(feature.get("name", ""))}</name>')
        xml_parts.append(f'{indent}{indent}{indent}<description>{escape_xml(feature.get("description", ""))}</description>')
        if feature.get("file_locations"):
            xml_parts.append(f'{indent}{indent}{indent}<file_locations>')
            for loc in feature["file_locations"]:
                xml_parts.append(f'{indent}{indent}{indent}{indent}<location>{escape_xml(loc)}</location>')
            xml_parts.append(f'{indent}{indent}{indent}</file_locations>')
        xml_parts.append(f'{indent}{indent}</feature>')
    xml_parts.append(f'{indent}</implemented_features>')

    # Additional requirements (optional)
    if spec.get("additional_requirements"):
        xml_parts.append('')
        xml_parts.append(f'{indent}<additional_requirements>')
        for req in spec["additional_requirements"]:
            xml_parts.append(f'{indent}{indent}<requirement>{escape_xml(req)}</requirement>')
        xml_parts.append(f'{indent}</additional_requirements>')

    # Development guidelines (optional)
    if spec.get("development_guidelines"):
        xml_parts.append('')
        xml_parts.append(f'{indent}<development_guidelines>')
        for guideline in spec["development_guidelines"]:
            xml_parts.append(f'{indent}{indent}<guideline>{escape_xml(guideline)}</guideline>')
        xml_parts.append(f'{indent}</development_guidelines>')

    # Implementation roadmap (optional)
    if spec.get("implementation_roadmap"):
        xml_parts.append('')
        xml_parts.append(f'{indent}<implementation_roadmap>')
        for phase in spec["implementation_roadmap"]:
            xml_parts.append(f'{indent}{indent}<phase>')
            xml_parts.append(f'{indent}{indent}{indent}<name>{escape_xml(phase.get("phase", ""))}</name>')
            xml_parts.append(f'{indent}{indent}{indent}<status>{escape_xml(phase.get("status", "pending"))}</status>')
            xml_parts.append(f'{indent}{indent}{indent}<description>{escape_xml(phase.get("description", ""))}</description>')
            xml_parts.append(f'{indent}{indent}</phase>')
        xml_parts.append(f'{indent}</implementation_roadmap>')

    # Close root element
    xml_parts.append('</project_specification>')

    return '\n'.join(xml_parts)


# ============================================================================
# Prompt Generation
# ============================================================================

SPEC_GENERATION_PROMPT = """
# YokeFlow Project Specification Generator

You are creating a project specification for YokeFlow, an autonomous AI coding platform.
The specification you generate will be used by an AI agent to build a complete,
production-ready application autonomously over multiple coding sessions.

## User's Project Description

{description}

{context_section}

{tech_preferences_section}

## Your Task

Create a comprehensive specification with these sections:

### 1. project_name
- Lowercase with hyphens (e.g., "task-manager", "route-planner")
- Concise but descriptive
- No spaces or special characters

### 2. overview
A comprehensive paragraph (3-5 sentences) covering:
- What the application does and its purpose
- Target users and primary use cases
- Key goals and value proposition
- Important constraints or scope boundaries

### 3. technology_stack
List 5-10 specific technologies. Consider:
- User's stated preferences (if any)
- Project requirements (database needs, real-time features, etc.)
- Agent-friendly technologies (Node.js, TypeScript, Python, React work well)
- Include: framework, database, testing tools, key libraries
- Be specific: "PostgreSQL" not just "database", "React" not just "frontend"

### 4. core_capabilities
5-10 main feature areas the application must provide.
- Be specific: "User authentication with email/password and OAuth" not just "authentication"
- Each capability should be a distinct, implementable feature area
- These become the high-level epics for implementation

### 5. implemented_features
Leave as an empty array [] (the agent populates this during development)

### 6. additional_requirements
5-10 non-functional requirements:
- Performance expectations (response times, concurrent users)
- Security requirements (authentication, data protection)
- Integration constraints (APIs, external services)
- Deployment considerations (containerization, hosting)
- Any "must have" technical requirements from the user's description

### 7. development_guidelines
5-8 coding standards the agent should follow:
- Error handling expectations
- Testing requirements (unit tests, integration tests)
- Code quality standards (TypeScript strict mode, linting)
- Specific patterns to use or avoid
- Documentation requirements

### 8. implementation_roadmap
6-10 phases ordered by DEPENDENCY (foundational first):
1. Project setup and infrastructure (always first)
2. Database/data layer setup
3. Core backend/API development
4. Core frontend components
5. Main features (in dependency order)
6. Secondary features
7. Testing and polish (always last)

Each phase needs:
- phase: Name of the phase
- status: Always "pending" for new projects
- description: What this phase involves (1-2 sentences)

## Critical Guidelines

- Be SPECIFIC. The agent needs actionable details, not vague descriptions.
- Cover ALL features from the user's description. Nothing should be omitted.
- Order the roadmap by dependency. Database before API, API before UI.
- Include enough detail that the agent can implement without clarification.
- If the user didn't specify tech stack, recommend appropriate modern technologies.
- The specification should be complete enough to build a production-ready MVP.

## Output Format

You MUST output a valid JSON object wrapped in ```json ... ``` code blocks.
The JSON must match this exact structure:

```json
{{
  "project_name": "string",
  "overview": "string",
  "technology_stack": ["string", ...],
  "core_capabilities": ["string", ...],
  "implemented_features": [],
  "additional_requirements": ["string", ...],
  "development_guidelines": ["string", ...],
  "implementation_roadmap": [
    {{
      "phase": "string",
      "status": "pending",
      "description": "string"
    }},
    ...
  ]
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
    Generate app_spec.txt using Claude SDK with streaming.

    Yields SSE-formatted events:
    - data: {"type": "spec_progress", "content": "...", "phase": "..."}
    - data: {"type": "spec_complete", "xml": "...", "project_name": "..."}
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
                    # Truncate if too long
                    if len(text_content) > 5000:
                        text_content = text_content[:5000] + "\n... (truncated)"
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

        async with client:
            # Send the query
            await client.query(prompt)

            # Receive streaming response
            async for msg in client.receive_response():
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
                                    "phase": "generating"
                                })

                # Handle ResultMessage (completion)
                elif msg_type == "ResultMessage":
                    logger.info("Spec generation completed")

        # Parse JSON from response
        spec_data = extract_json_from_response(response_text)

        if spec_data:
            # Ensure implemented_features is empty for new projects
            spec_data["implemented_features"] = []

            # Convert to XML
            xml_content = spec_to_xml(spec_data)

            yield format_sse_event("spec_complete", {
                "xml": xml_content,
                "project_name": spec_data.get("project_name", "")
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
    Returns the final XML spec or raises an exception.
    """
    import asyncio

    async def run():
        xml_result = None
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
                    xml_result = data["xml"]
                elif data["type"] == "spec_error":
                    error = data["error"]

        if error:
            raise RuntimeError(error)
        if not xml_result:
            raise RuntimeError("No specification generated")

        return xml_result

    return asyncio.run(run())
