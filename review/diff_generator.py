"""
Diff Generator for Prompt Improvements
========================================

Uses Claude to generate precise diffs for proposed prompt changes.
"""

import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DiffGenerator:
    """
    Generates precise diffs for prompt improvement proposals using Claude.

    Takes a general proposal and the current prompt file, then uses AI
    to identify specific sections and generate exact changes.
    """

    def __init__(self):
        """Initialize the diff generator."""
        self.prompt_dir = Path(__file__).parent.parent / 'prompts'

    async def generate_improved_prompt(
        self,
        prompt_file: str,
        improvement_guidance: str,
        theme: str
    ) -> Dict[str, Any]:
        """
        Generate a complete improved version of the prompt file.

        This is the main method for prompt improvements - it takes consolidated
        guidance from multiple review sessions and generates a complete new prompt.

        Args:
            prompt_file: Filename (e.g., 'coding_prompt_docker.md')
            improvement_guidance: Consolidated guidance from pattern analysis
            theme: Theme category for context

        Returns:
            Dict with:
                - original_prompt: Full original prompt text
                - improved_prompt: Full improved prompt text
                - changes: List of {section, description} for each change made
                - summary: Overall description of improvements
                - confidence: 1-10 confidence score
        """
        # Read current prompt file
        prompt_path = self.prompt_dir / prompt_file
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        original_content = prompt_path.read_text()

        # Build prompt for Claude to generate improved version
        improvement_prompt = self._build_improvement_prompt(
            original_content,
            improvement_guidance,
            theme
        )

        # Call Claude to generate complete improved prompt
        result = await self._call_claude_for_improvement(improvement_prompt)

        # Add original prompt to result
        result['original_prompt'] = original_content

        return result

    def _build_improvement_prompt(
        self,
        current_content: str,
        improvement_guidance: str,
        theme: str
    ) -> str:
        """Build the prompt for Claude to generate improved prompt file."""

        return f"""You are helping to improve a coding agent's prompt file based on issues identified across multiple sessions.

## Current Prompt File

```markdown
{current_content}
```

## Improvement Guidance (Theme: {theme})

{improvement_guidance}

## Your Task

Generate a COMPLETE improved version of the prompt file that addresses the issues described in the improvement guidance.

**Requirements:**
1. Output the ENTIRE improved prompt (not just the changed sections)
2. Maintain the overall structure and formatting of the original prompt
3. Incorporate ALL improvements from the guidance
4. Preserve any sections that don't need changes
5. Keep the same markdown formatting and section headers

**Output Format:**

Return a JSON object with this structure:

```json
{{
  "confidence": 8,
  "summary": "Brief overview of all improvements made",
  "changes": [
    {{
      "section": "Section name that was modified",
      "description": "What was changed and why"
    }}
  ],
  "improved_prompt": "THE COMPLETE IMPROVED PROMPT FILE TEXT HERE"
}}
```

**Important:**
- The `improved_prompt` field must contain the FULL, COMPLETE prompt file
- Include ALL sections from the original, even unchanged ones
- Apply changes where needed based on the guidance
- Maintain exact markdown formatting (headers, code blocks, lists, etc.)
- Ensure the improved prompt is ready to use as-is
"""

    async def _call_claude_for_improvement(self, prompt: str) -> Dict[str, Any]:
        """
        Call Claude to generate the complete improved prompt.

        Uses claude_agent_sdk for consistency with rest of system.
        Uses Opus by default for better reasoning on this critical task.
        """
        from review.review_client import create_review_client
        import json
        import re

        # Use prompt improvement model (defaults to Opus for better performance)
        model = os.getenv('DEFAULT_PROMPT_IMPROVEMENT_MODEL', 'claude-opus-4-5-20251101')
        client = create_review_client(model=model)

        logger.info(f"Generating improved prompt using model: {model}")

        try:
            async with client:
                # Send prompt
                await client.query(prompt)

                # Collect response text (only TextBlocks)
                response_text = ""
                async for msg in client.receive_response():
                    msg_type = type(msg).__name__

                    # Handle AssistantMessage
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            block_type = type(block).__name__

                            if block_type == "TextBlock" and hasattr(block, "text"):
                                response_text += block.text

                # Log full response for debugging (first 500 chars)
                logger.debug(f"Claude improvement response (first 500 chars): {response_text[:500]}")

                # Parse JSON from response
                # Look for ```json or just JSON object
                json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(1)
                else:
                    # Try to find JSON object directly
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        json_text = json_match.group(0)
                    else:
                        raise ValueError("Could not find JSON in Claude's response")

                result = json.loads(json_text)

                # Validate structure
                if 'improved_prompt' not in result:
                    raise ValueError("Response missing 'improved_prompt' field")

                if 'changes' not in result:
                    result['changes'] = []

                if 'summary' not in result:
                    result['summary'] = "Prompt improvements applied"

                if 'confidence' not in result:
                    result['confidence'] = 7

                # Log the result
                logger.info(f"Claude improvement complete: confidence={result.get('confidence')}, changes={len(result.get('changes', []))}, new prompt length={len(result.get('improved_prompt', ''))}")

                return result

        except Exception as e:
            logger.error(f"Failed to generate improved prompt with Claude: {e}")
            # Return a fallback result
            return {
                "confidence": 0,
                "summary": f"Error generating improved prompt: {str(e)}",
                "changes": [],
                "improved_prompt": ""
            }

    async def generate_diff(
        self,
        prompt_file: str,
        proposal_text: str,
        rationale: str,
        section_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a specific diff for a proposed change.

        Args:
            prompt_file: Filename (e.g., 'coding_prompt_docker.md')
            proposal_text: The proposed change text from review
            rationale: Why this change is needed
            section_hint: Optional hint about which section (theme name)

        Returns:
            Dict with:
                - sections: List of sections to modify
                - changes: List of {original, proposed, line_start, line_end}
                - summary: Brief description of changes
                - confidence: 1-10 how confident the AI is
        """
        # Read current prompt file
        prompt_path = self.prompt_dir / prompt_file
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        current_content = prompt_path.read_text()

        # Build prompt for Claude
        diff_prompt = self._build_diff_prompt(
            current_content,
            proposal_text,
            rationale,
            section_hint
        )

        # Call Claude to generate diff
        diff_result = await self._call_claude_for_diff(diff_prompt)

        return diff_result

    def _build_diff_prompt(
        self,
        current_content: str,
        proposal_text: str,
        rationale: str,
        section_hint: Optional[str]
    ) -> str:
        """Build the prompt for Claude to generate the diff."""

        section_context = f"\n\nHint: This likely relates to the '{section_hint}' section." if section_hint else ""

        return f"""You are helping to improve a coding agent's prompt file. You need to identify which specific section(s) of the current prompt should be modified and generate precise changes.

## Current Prompt File

```markdown
{current_content}
```

## Proposed Improvement

{proposal_text}

## Rationale

{rationale}{section_context}

## Your Task

Analyze the current prompt and the proposed improvement. Then:

1. **Identify** which section(s) of the prompt need to be modified
2. **Extract** the exact original text that should be changed
3. **Generate** the specific replacement text
4. **Explain** briefly what you're changing and why

Output your response in this JSON format:

```json
{{
  "confidence": 8,
  "summary": "Brief description of what you're changing",
  "changes": [
    {{
      "section": "Section name from the prompt",
      "original": "Exact text to be replaced",
      "proposed": "Exact replacement text",
      "explanation": "Why this specific change implements the improvement"
    }}
  ]
}}
```

**Important:**
- Be precise - extract the EXACT text that needs changing
- If the improvement applies to multiple sections, include all of them
- If you're unsure about a section, still include it but mention uncertainty in explanation
- Keep original formatting (indentation, bullet points, etc.)
- Only include text that actually exists in the current prompt
"""

    async def _call_claude_for_diff(self, prompt: str) -> Dict[str, Any]:
        """
        Call Claude to generate the diff.

        Uses claude_agent_sdk for consistency with rest of system.
        """
        from review.review_client import create_review_client
        import json
        import re

        # Create a review client (same model as deep reviews)
        model = os.getenv('DEFAULT_REVIEW_MODEL', 'claude-sonnet-4-5-20250929')
        client = create_review_client(model=model)

        try:
            async with client:
                # Send prompt
                await client.query(prompt)

                # Collect response text (only TextBlocks)
                response_text = ""
                async for msg in client.receive_response():
                    msg_type = type(msg).__name__

                    # Handle AssistantMessage
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            block_type = type(block).__name__

                            if block_type == "TextBlock" and hasattr(block, "text"):
                                response_text += block.text

                # Log full response for debugging
                logger.debug(f"Claude raw response (first 500 chars): {response_text[:500]}")

                # Parse JSON from response
                # Look for ```json or just JSON object
                json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(1)
                else:
                    # Try to find JSON object directly
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        json_text = json_match.group(0)
                    else:
                        raise ValueError("Could not find JSON in Claude's response")

                result = json.loads(json_text)

                # Log the result for debugging
                logger.info(f"Claude diff response: confidence={result.get('confidence', 'N/A')}, changes={len(result.get('changes', []))}")
                if result.get('changes'):
                    logger.debug(f"First change: {result['changes'][0]}")

                # Validate structure
                if 'changes' not in result:
                    raise ValueError("Response missing 'changes' field")

                return result

        except Exception as e:
            logger.error(f"Failed to generate diff with Claude: {e}")
            # Return a fallback result
            return {
                "confidence": 0,
                "summary": f"Error generating diff: {str(e)}",
                "changes": []
            }


# Convenience function
async def generate_diff_for_proposal(
    prompt_file: str,
    proposal_text: str,
    rationale: str,
    section_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a diff for a proposal.

    Args:
        prompt_file: Prompt filename (e.g., 'coding_prompt_docker.md')
        proposal_text: The proposed change text
        rationale: Why this change is needed
        section_hint: Optional section hint (theme name)

    Returns:
        Diff result with changes
    """
    generator = DiffGenerator()
    return await generator.generate_diff(
        prompt_file,
        proposal_text,
        rationale,
        section_hint
    )
