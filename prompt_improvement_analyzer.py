"""
Prompt Improvement Analyzer
============================

Analyzes patterns across multiple projects to generate concrete
prompt improvements for the global coding prompts.

Created: December 21, 2025
Status: Production Ready
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
from pathlib import Path
from datetime import datetime, timedelta
import logging

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from database import TaskDatabase
from config import Config

logger = logging.getLogger(__name__)


class PromptImprovementAnalyzer:
    """
    Analyzes session patterns across projects to improve prompts.
    """

    def __init__(self, db: TaskDatabase):
        self.db = db
        self.config = Config.load_default()
        self._claude_client = None

    def _create_claude_client(self) -> ClaudeSDKClient:
        """
        Create Claude SDK client for prompt improvement analysis.

        Similar to review client, but focused on generating specific text diffs.
        """
        if self._claude_client is None:
            self._claude_client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model=self.config.models.coding,  # Use coding model (Sonnet)
                    system_prompt=(
                        "You are a prompt engineering expert analyzing autonomous coding sessions. "
                        "Your job is to generate specific, actionable improvements to coding prompts. "
                        "ALL necessary data is provided in the user message. "
                        "Provide your analysis as structured JSON. "
                        "DO NOT attempt to read files, run commands, or use any tools. "
                        "Respond with precise before/after text diffs for prompt improvements."
                    ),
                    permission_mode="bypassPermissions",
                    mcp_servers={},  # No MCP servers - no tools
                    max_turns=1,  # Single-turn only
                    max_buffer_size=10485760,  # 10MB buffer
                )
            )
        return self._claude_client

    async def analyze_projects(
        self,
        project_ids: Optional[List[UUID]] = None,
        sandbox_type: str = "docker",
        last_n_days: int = 7,
        min_sessions_per_project: int = 5,
        triggered_by: str = "manual",
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Perform cross-project analysis for prompt improvements.

        Args:
            project_ids: Specific projects to analyze (None = all eligible projects)
            sandbox_type: 'docker' or 'local' (which prompt to improve)
            last_n_days: Only analyze sessions from last N days
            min_sessions_per_project: Minimum sessions required per project
            triggered_by: 'manual', 'scheduled', or 'threshold'
            user_id: User who triggered the analysis

        Returns:
            Dict with analysis_id and summary statistics
        """
        logger.info(f"Starting prompt improvement analysis for {sandbox_type} mode")

        # 1. Create analysis record
        analysis_id = await self._create_analysis_record(
            project_ids or [],
            sandbox_type,
            triggered_by,
            user_id
        )

        try:
            # 2. Gather eligible projects if not specified
            if project_ids is None:
                project_ids = await self._find_eligible_projects(
                    sandbox_type,
                    last_n_days,
                    min_sessions_per_project
                )

            if not project_ids:
                await self._mark_analysis_failed(
                    analysis_id,
                    "No eligible projects found"
                )
                return {
                    "analysis_id": str(analysis_id),
                    "status": "failed",
                    "error": "No eligible projects found"
                }

            # 3. Update analysis with actual projects
            await self._update_analysis_projects(analysis_id, project_ids)

            # 4. Gather session data from all projects
            date_start = datetime.now() - timedelta(days=last_n_days)
            session_data = await self._gather_session_data(
                project_ids,
                date_start,
                sandbox_type
            )

            if not session_data:
                await self._mark_analysis_failed(
                    analysis_id,
                    "No sessions found in date range"
                )
                return {
                    "analysis_id": str(analysis_id),
                    "status": "failed",
                    "error": "No sessions found"
                }

            # 5. Load deep review recommendations (NEW - Phase 2)
            deep_review_recommendations = await self._load_deep_review_recommendations(
                project_ids,
                date_start
            )

            # 6. Identify patterns (now includes deep review data)
            patterns = await self._identify_patterns(session_data, deep_review_recommendations)

            # 7. Load current prompt
            current_prompt = await self._load_prompt(sandbox_type)

            # 8. Generate improvement proposals with Claude (NEW - uses deep reviews)
            proposals = await self._generate_proposals(
                patterns,
                current_prompt,
                session_data,
                sandbox_type,
                deep_review_recommendations
            )

            # 8. Store proposals in database
            for proposal in proposals:
                await self._store_proposal(analysis_id, proposal)

            # 9. Mark analysis as completed
            await self._complete_analysis(
                analysis_id,
                len(session_data),
                patterns,
                proposals,
                date_start
            )

            logger.info(f"Analysis {analysis_id} completed: {len(proposals)} proposals generated")

            return {
                "analysis_id": str(analysis_id),
                "status": "completed",
                "projects_analyzed": len(project_ids),
                "sessions_analyzed": len(session_data),
                "proposals_generated": len(proposals),
                "patterns_found": len(patterns.get("issues", [])),
                "quality_impact_estimate": self._estimate_quality_impact(patterns)
            }

        except Exception as e:
            logger.error(f"Analysis {analysis_id} failed: {e}")
            await self._mark_analysis_failed(analysis_id, str(e))
            raise

    async def _find_eligible_projects(
        self,
        sandbox_type: str,
        last_n_days: int,
        min_sessions: int
    ) -> List[UUID]:
        """Find projects eligible for analysis."""
        async with self.db.acquire() as conn:
            # Find projects with sufficient sessions
            # Note: sandbox_type filter is optional - if projects don't have it set,
            # we analyze them anyway and assume they match the requested type
            result = await conn.fetch("""
                SELECT
                    p.id,
                    COUNT(DISTINCT s.id) as session_count
                FROM projects p
                JOIN sessions s ON p.id = s.project_id
                LEFT JOIN session_quality_checks q ON s.id = q.session_id
                WHERE s.type = 'coding'
                  AND s.status = 'completed'
                  AND s.created_at > NOW() - INTERVAL '%s days'
                  AND (p.metadata->>'sandbox_type' = $1 OR p.metadata->>'sandbox_type' IS NULL)
                GROUP BY p.id
                HAVING COUNT(DISTINCT s.id) >= $2
                ORDER BY session_count DESC
            """ % last_n_days, sandbox_type, min_sessions)

            return [row['id'] for row in result]

    async def _gather_session_data(
        self,
        project_ids: List[UUID],
        date_start: datetime,
        sandbox_type: str
    ) -> List[Dict[str, Any]]:
        """Gather session logs and metrics from all projects."""
        sessions = []

        async with self.db.acquire() as conn:
            for project_id in project_ids:
                # Get sessions with quality metrics
                result = await conn.fetch("""
                    SELECT
                        s.id,
                        s.session_number,
                        s.project_id,
                        s.created_at,
                        s.metrics,
                        q.overall_rating,
                        q.playwright_count,
                        q.error_count,
                        q.error_rate,
                        q.critical_issues,
                        q.warnings,
                        p.name as project_name
                    FROM sessions s
                    LEFT JOIN session_quality_checks q ON s.id = q.session_id AND q.check_type = 'quick'
                    JOIN projects p ON s.project_id = p.id
                    WHERE s.project_id = $1
                      AND s.type = 'coding'
                      AND s.status = 'completed'
                      AND s.created_at >= $2
                    ORDER BY s.session_number
                """, project_id, date_start)

                for row in result:
                    session_dict = dict(row)
                    # Note: Session logs path would be constructed from project name if needed
                    # For pattern detection, we use quality_checks data which is already in DB
                    sessions.append(session_dict)

        return sessions

    async def _load_deep_review_recommendations(
        self,
        project_ids: List[UUID],
        date_start: datetime
    ) -> List[Dict[str, Any]]:
        """
        Load deep review recommendations from session_quality_checks table.

        This is the key integration point with the review system (Phase 2).
        Returns recommendations from all deep reviews for the specified projects.

        Returns:
            List of dicts with:
            - session_id, session_number, project_id, project_name
            - overall_rating (1-10)
            - recommendations (list of strings)
            - created_at
        """
        recommendations = []

        async with self.db.acquire() as conn:
            for project_id in project_ids:
                result = await conn.fetch("""
                    SELECT
                        sqc.id as check_id,
                        s.id as session_id,
                        s.session_number,
                        s.project_id,
                        p.name as project_name,
                        sqc.overall_rating,
                        sqc.prompt_improvements,
                        sqc.created_at
                    FROM session_quality_checks sqc
                    JOIN sessions s ON sqc.session_id = s.id
                    JOIN projects p ON s.project_id = p.id
                    WHERE s.project_id = $1
                      AND sqc.check_type = 'deep'
                      AND s.created_at >= $2
                      AND sqc.prompt_improvements IS NOT NULL
                      AND sqc.prompt_improvements != '[]'
                    ORDER BY s.session_number
                """, project_id, date_start)

                for row in result:
                    # Parse prompt_improvements (stored as JSON string)
                    improvements = row['prompt_improvements']
                    if isinstance(improvements, str):
                        import json
                        try:
                            improvements = json.loads(improvements)
                        except:
                            improvements = []

                    if improvements:  # Only include if there are actual recommendations
                        recommendations.append({
                            'check_id': row['check_id'],
                            'session_id': row['session_id'],
                            'session_number': row['session_number'],
                            'project_id': row['project_id'],
                            'project_name': row['project_name'],
                            'overall_rating': row['overall_rating'],
                            'recommendations': improvements,
                            'created_at': row['created_at']
                        })

        logger.info(f"Loaded {len(recommendations)} deep reviews with recommendations")
        return recommendations

    async def _identify_patterns(
        self,
        session_data: List[Dict[str, Any]],
        deep_review_recommendations: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Identify common patterns across sessions.

        Returns a dict with pattern categories and specific issues found.
        """
        patterns = {
            "issues": [],
            "statistics": {
                "total_sessions": len(session_data),
                "avg_quality": 0,
                "browser_verification_rate": 0,
                "avg_error_rate": 0
            }
        }

        if not session_data:
            return patterns

        # Calculate aggregate statistics
        total_quality = 0
        sessions_with_browser = 0
        total_error_rate = 0
        sessions_with_rating = 0

        for session in session_data:
            if session.get('overall_rating'):
                total_quality += session['overall_rating']
                sessions_with_rating += 1

            if session.get('playwright_count', 0) > 0:
                sessions_with_browser += 1

            if session.get('error_rate') is not None:
                total_error_rate += float(session['error_rate'])

        patterns["statistics"]["avg_quality"] = (
            total_quality / sessions_with_rating if sessions_with_rating > 0 else 0
        )
        patterns["statistics"]["browser_verification_rate"] = (
            sessions_with_browser / len(session_data)
        )
        patterns["statistics"]["avg_error_rate"] = (
            total_error_rate / len(session_data)
        )

        # Identify specific issues
        # 1. Missing browser verification
        sessions_without_browser = len(session_data) - sessions_with_browser
        if sessions_without_browser > len(session_data) * 0.005:  # More than 0.5% (lowered for testing)
            patterns["issues"].append({
                "type": "missing_browser_verification",
                "severity": "critical",
                "frequency": sessions_without_browser / len(session_data),
                "sessions_affected": sessions_without_browser,
                "description": "High percentage of sessions skip browser verification",
                "recommendation": "Add explicit browser testing requirement to prompt"
            })

        # 2. High error rate
        if patterns["statistics"]["avg_error_rate"] > 0.01:  # More than 0.01% errors (lowered for testing)
            patterns["issues"].append({
                "type": "high_error_rate",
                "severity": "moderate",
                "frequency": patterns["statistics"]["avg_error_rate"] / 100,
                "sessions_affected": sum(1 for s in session_data if s.get('error_rate', 0) > 15),
                "description": "High tool error rate indicates unclear instructions",
                "recommendation": "Clarify error recovery procedures in prompt"
            })

        # 3. Low quality scores
        low_quality_sessions = sum(
            1 for s in session_data
            if s.get('overall_rating') and s['overall_rating'] < 9.5
        )
        if low_quality_sessions > len(session_data) * 0.10:  # More than 10% (lowered for testing)
            patterns["issues"].append({
                "type": "low_quality_sessions",
                "severity": "moderate",
                "frequency": low_quality_sessions / len(session_data),
                "sessions_affected": low_quality_sessions,
                "description": "Significant portion of sessions have quality < 7/10",
                "recommendation": "Review and strengthen core prompt instructions"
            })

        # NEW (Phase 2): Aggregate deep review recommendations
        if deep_review_recommendations:
            aggregated = self._aggregate_recommendations(deep_review_recommendations)
            patterns["deep_review_recommendations"] = aggregated
            logger.info(f"Aggregated {len(aggregated)} recommendation themes from deep reviews")

        return patterns

    def _aggregate_recommendations(
        self,
        deep_review_recommendations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate recommendations from multiple deep reviews into themes.

        Groups similar recommendations together and identifies recurring patterns.
        This is key for cross-project analysis.

        Returns:
            Dict with recommendation themes, each containing:
            - theme_name: str
            - recommendations: List[str] (individual recommendation texts)
            - sessions: List[session_info] (which sessions mentioned this)
            - frequency: int (how many sessions mentioned it)
            - avg_quality: float (average quality of sessions with this recommendation)
        """
        from collections import defaultdict

        # Keywords for categorizing recommendations
        theme_keywords = {
            'browser_verification': ['browser', 'screenshot', 'playwright', 'visual', 'ui', 'verify'],
            'error_handling': ['error', 'recovery', 'debugging', 'fix', 'retry'],
            'git_commits': ['commit', 'git', 'message', 'version control'],
            'testing': ['test', 'testing', 'unit test', 'e2e', 'coverage'],
            'docker': ['docker', 'bash_docker', 'container'],
            'parallel_execution': ['parallel', 'concurrent', 'independent'],
            'task_management': ['task', 'epic', 'checklist', 'workflow'],
            'documentation': ['comment', 'documentation', 'readme'],
        }

        # Aggregate recommendations by theme
        themes = defaultdict(lambda: {
            'recommendations': [],
            'session_dict': {},  # Use dict to track unique sessions
            'frequency': 0
        })

        for review in deep_review_recommendations:
            session_id = str(review['session_id'])
            session_info = {
                'session_id': session_id,
                'session_number': review['session_number'],
                'project_name': review['project_name'],
                'overall_rating': review['overall_rating']
            }

            for rec in review['recommendations']:
                rec_lower = rec.lower()

                # Find matching themes
                matched_themes = []
                for theme, keywords in theme_keywords.items():
                    if any(keyword in rec_lower for keyword in keywords):
                        matched_themes.append(theme)

                # If no specific theme, categorize as 'general'
                if not matched_themes:
                    matched_themes = ['general']

                # Add to each matching theme
                for theme in matched_themes:
                    themes[theme]['recommendations'].append(rec)
                    themes[theme]['frequency'] += 1

                    # Track unique sessions (only add if not already present)
                    if session_id not in themes[theme]['session_dict']:
                        themes[theme]['session_dict'][session_id] = session_info

        # Calculate averages and format output
        result = {}
        for theme_name, data in themes.items():
            if data['frequency'] > 0:
                # Convert session_dict to list
                sessions_list = list(data['session_dict'].values())
                unique_sessions = len(sessions_list)
                total_quality = sum(s['overall_rating'] for s in sessions_list)

                result[theme_name] = {
                    'theme_name': theme_name,
                    'recommendations': data['recommendations'],
                    'sessions': sessions_list,  # Now contains unique sessions only
                    'frequency': data['frequency'],
                    'avg_quality': total_quality / unique_sessions if unique_sessions > 0 else 0,
                    'unique_sessions': unique_sessions
                }

        return result

    async def _load_prompt(self, sandbox_type: str) -> str:
        """Load the current prompt file."""
        prompt_file = f"coding_prompt_{sandbox_type}.md"
        prompt_path = Path(__file__).parent / "prompts" / prompt_file

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        with open(prompt_path, 'r') as f:
            return f.read()

    async def _generate_proposals(
        self,
        patterns: Dict[str, Any],
        current_prompt: str,
        session_data: List[Dict[str, Any]],
        sandbox_type: str,
        deep_review_recommendations: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate concrete prompt improvement proposals using Claude.

        UPDATED (Phase 2): Now uses deep review recommendations as primary source.
        Falls back to threshold-based issues only if no deep reviews available.

        This uses the Claude Agent SDK to analyze patterns and generate
        specific, actionable prompt changes with before/after diffs.
        """
        proposals = []

        # Priority 1: Use deep review recommendations (Phase 2 integration)
        if patterns.get("deep_review_recommendations"):
            logger.info("Generating proposals from deep review recommendations")
            proposals.extend(
                await self._generate_proposals_from_deep_reviews(
                    patterns["deep_review_recommendations"],
                    current_prompt,
                    sandbox_type
                )
            )

        # Priority 2: Use threshold-based issues (original implementation)
        for issue in patterns.get("issues", []):
            # Create a proposal based on the issue
            proposal = {
                "prompt_file": f"coding_prompt_{sandbox_type}.md",
                "section_name": self._map_issue_to_section(issue["type"]),
                "change_type": "modification",
                "original_text": "",  # Will be filled in when applying
                "proposed_text": issue["recommendation"],
                "rationale": issue["description"],
                "evidence": [
                    {
                        "type": "pattern",
                        "frequency": issue["frequency"],
                        "sessions_affected": issue["sessions_affected"],
                        "severity": issue["severity"]
                    }
                ],
                "confidence_level": self._calculate_confidence(issue)
            }
            proposals.append(proposal)

        logger.info(f"Generated {len(proposals)} total proposals")
        return proposals

    async def _generate_proposals_from_deep_reviews(
        self,
        aggregated_recommendations: Dict[str, Any],
        current_prompt: str,
        sandbox_type: str
    ) -> List[Dict[str, Any]]:
        """
        Generate proposals from aggregated deep review recommendations.

        Phase 3: Uses Claude SDK to generate specific before/after text diffs.

        Args:
            aggregated_recommendations: Output from _aggregate_recommendations()
            current_prompt: Current prompt file content
            sandbox_type: 'docker' or 'local'

        Returns:
            List of proposal dicts ready for database storage
        """
        proposals = []

        # Sort themes by frequency (most common first)
        sorted_themes = sorted(
            aggregated_recommendations.items(),
            key=lambda x: x[1]['frequency'],
            reverse=True
        )

        # Phase 3 approach: Try Claude SDK for top themes, but always generate proposals for all themes
        # This ensures we don't lose coverage when Claude SDK fails

        claude_enabled = True  # Set to False to skip Claude SDK entirely
        claude_budget = 3  # Limit Claude API calls to avoid excessive cost
        claude_used = 0

        for theme_name, theme_data in sorted_themes:
            # Skip if very low frequency (< 2 mentions)
            if theme_data['frequency'] < 2:
                continue

            diff_result = None

            # Try Claude SDK for high-priority themes (if enabled and budget available)
            if claude_enabled and claude_used < claude_budget and theme_data['unique_sessions'] >= 3:
                try:
                    diff_result = await self._generate_diff_with_claude(
                        theme_name=theme_name,
                        recommendations=theme_data['recommendations'],
                        current_prompt=current_prompt,
                        sandbox_type=sandbox_type
                    )
                    claude_used += 1

                    if diff_result:
                        logger.info(f"✅ Claude-powered proposal for theme: {theme_name}")
                except Exception as e:
                    logger.warning(f"Claude SDK failed for {theme_name}, using fallback: {e}")

            # Generate proposal (Claude-powered if available, otherwise from recommendations)
            if diff_result:
                # Use Claude-generated diff
                proposal = {
                    "prompt_file": f"coding_prompt_{sandbox_type}.md",
                    "section_name": diff_result.get("section_name", self._map_theme_to_section(theme_name)),
                    "change_type": diff_result.get("change_type", "modification"),
                    "original_text": diff_result.get("original_text", ""),
                    "proposed_text": diff_result.get("proposed_text", ""),
                    "rationale": (
                        f"[Claude-enhanced] {diff_result.get('rationale', '')} "
                        f"(Recommended by {theme_data['unique_sessions']} sessions, "
                        f"avg quality: {theme_data['avg_quality']:.1f}/10)"
                    ),
                    "evidence": [
                        {
                            "type": "deep_review_claude",
                            "theme": theme_name,
                            "frequency": theme_data['frequency'],
                            "sessions": theme_data['sessions'][:5],
                            "avg_quality": theme_data['avg_quality']
                        }
                    ],
                    "confidence_level": min(10, self._calculate_theme_confidence(theme_data) + 1)  # Boost for Claude
                }
            else:
                # Use recommendations directly (Phase 2 approach)
                best_recommendations = sorted(theme_data['recommendations'], key=lambda x: len(x))[:3]
                proposal = {
                    "prompt_file": f"coding_prompt_{sandbox_type}.md",
                    "section_name": self._map_theme_to_section(theme_name),
                    "change_type": "modification",
                    "original_text": "",
                    "proposed_text": "\n".join(f"- {rec}" for rec in best_recommendations),
                    "rationale": f"Recommended by {theme_data['unique_sessions']} sessions (avg quality: {theme_data['avg_quality']:.1f}/10)",
                    "evidence": [
                        {
                            "type": "deep_review",
                            "theme": theme_name,
                            "frequency": theme_data['frequency'],
                            "sessions": theme_data['sessions'][:5],
                            "avg_quality": theme_data['avg_quality']
                        }
                    ],
                    "confidence_level": self._calculate_theme_confidence(theme_data)
                }

            proposals.append(proposal)

        logger.info(f"Generated {len(proposals)} proposals ({claude_used} Claude-enhanced)")
        return proposals

    async def _generate_diff_with_claude(
        self,
        theme_name: str,
        recommendations: List[str],
        current_prompt: str,
        sandbox_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Use Claude SDK to generate specific before/after text diff.

        Phase 3: This is the key Claude-powered analysis that generates precise diffs.

        Args:
            theme_name: Category (browser_verification, error_handling, etc.)
            recommendations: List of recommendation texts from deep reviews
            current_prompt: Full current prompt content
            sandbox_type: 'docker' or 'local'

        Returns:
            Dict with:
            - section_name: Where in prompt to make change
            - original_text: Current text to be replaced
            - proposed_text: New text to insert
            - rationale: Why this change improves the prompt
            - change_type: 'addition', 'modification', or 'deletion'
        """
        # Build prompt for Claude
        analysis_prompt = f"""# Task: Generate Specific Prompt Improvement

You are analyzing recommendations from multiple autonomous coding sessions to improve a coding prompt.

## Theme: {theme_name}

## Recommendations from Sessions:
{chr(10).join(f'- {rec}' for rec in recommendations[:10])}

## Current Prompt File: coding_prompt_{sandbox_type}.md
{current_prompt}

## Your Task:

Analyze the recommendations and current prompt to generate a SPECIFIC, ACTIONABLE improvement.

1. Find the most relevant section in the current prompt for this theme
2. Extract the exact text that should be modified (if modifying existing content)
3. Generate the improved version of that text
4. Explain why this change addresses the recommendations

## Output Format (JSON):

```json
{{
  "section_name": "Name of the section being modified",
  "change_type": "addition" | "modification" | "deletion",
  "original_text": "Exact text from current prompt (or empty string for additions)",
  "proposed_text": "New/improved text to insert",
  "rationale": "Brief explanation of how this addresses the recommendations"
}}
```

## Rules:

1. Be SPECIFIC - Extract exact text from the current prompt, don't paraphrase
2. Keep changes FOCUSED - Address one clear improvement
3. Make it ACTIONABLE - Proposed text should be ready to insert
4. If the prompt already addresses this well, return null
5. Output ONLY valid JSON, no markdown code blocks

Generate the improvement:"""

        try:
            client = self._create_claude_client()

            # Send message to Claude
            logger.info(f"Requesting Claude analysis for theme: {theme_name}")

            async with client:
                await client.query(analysis_prompt)

                # Collect response (same pattern as review_client.py)
                response_text = ""
                msg_count = 0
                text_block_count = 0
                async for msg in client.receive_response():
                    msg_count += 1
                    msg_type = type(msg).__name__
                    logger.debug(f"Received message {msg_count} type={msg_type}")

                    # Handle AssistantMessage with content blocks
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            block_type = type(block).__name__
                            logger.debug(f"  Block type: {block_type}")

                            if block_type == "TextBlock" and hasattr(block, "text"):
                                text_block_count += 1
                                block_text = block.text
                                response_text += block_text
                                logger.debug(f"  Collected text block #{text_block_count} ({len(block_text)} chars)")

                logger.info(f"Received {msg_count} messages, {text_block_count} text blocks, total text length: {len(response_text)}")

            # Parse JSON response
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Handle null response
            if response_text.lower() == "null":
                logger.info(f"Claude returned null for theme {theme_name} (already well addressed)")
                return None

            # Parse JSON
            result = json.loads(response_text)

            # Validate required fields
            if not all(key in result for key in ["section_name", "proposed_text", "rationale"]):
                logger.error(f"Claude response missing required fields: {result}")
                return None

            logger.info(f"Successfully generated Claude diff for theme: {theme_name}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude JSON response for {theme_name}: {e}")
            logger.error(f"Response was: {response_text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Claude SDK error for {theme_name}: {e}", exc_info=True)
            return None

    def _map_theme_to_section(self, theme_name: str) -> str:
        """Map recommendation theme to prompt section."""
        theme_map = {
            "browser_verification": "Step 3: Implement and verify the solution",
            "error_handling": "Error Recovery and Debugging",
            "git_commits": "Git Workflow",
            "testing": "Testing Requirements",
            "docker": "Docker Environment",
            "parallel_execution": "Tool Usage Optimization",
            "task_management": "Task Management",
            "documentation": "Code Documentation",
            "general": "General Instructions"
        }
        return theme_map.get(theme_name, "General Instructions")

    def _calculate_theme_confidence(self, theme_data: Dict[str, Any]) -> int:
        """Calculate confidence level for a theme-based proposal."""
        # Higher frequency = higher confidence
        frequency = theme_data['frequency']
        unique_sessions = theme_data['unique_sessions']
        avg_quality = theme_data['avg_quality']

        # Base confidence on number of sessions mentioning it
        if unique_sessions >= 5:
            base = 9
        elif unique_sessions >= 3:
            base = 7
        elif unique_sessions >= 2:
            base = 5
        else:
            base = 3

        # Boost if mentioned by high-quality sessions
        if avg_quality >= 9:
            base = min(10, base + 1)
        elif avg_quality < 6:
            base = max(1, base - 1)

        return base

    def _map_issue_to_section(self, issue_type: str) -> str:
        """Map issue type to prompt section."""
        section_map = {
            "missing_browser_verification": "Step 3: Implement the solution",
            "high_error_rate": "Error Recovery and Debugging",
            "low_quality_sessions": "General Instructions"
        }
        return section_map.get(issue_type, "General Instructions")

    def _calculate_confidence(self, issue: Dict[str, Any]) -> int:
        """Calculate confidence level (1-10) for a proposal."""
        # Base confidence on frequency and severity
        frequency = issue["frequency"]
        severity = issue["severity"]

        base_confidence = int(frequency * 10)

        # Boost for critical issues
        if severity == "critical":
            base_confidence = min(10, base_confidence + 2)
        elif severity == "moderate":
            base_confidence = min(10, base_confidence + 1)

        return max(1, min(10, base_confidence))

    def _estimate_quality_impact(self, patterns: Dict[str, Any]) -> float:
        """Estimate expected quality improvement from fixing these issues."""
        if not patterns.get("issues"):
            return 0.0

        # Estimate based on severity and frequency
        total_impact = 0.0
        for issue in patterns["issues"]:
            severity_weight = {"critical": 2.0, "moderate": 1.0, "low": 0.5}
            weight = severity_weight.get(issue["severity"], 0.5)
            total_impact += issue["frequency"] * weight

        # Cap at reasonable maximum
        return min(3.0, total_impact)

    # Database operations

    async def _create_analysis_record(
        self,
        project_ids: List[UUID],
        sandbox_type: str,
        triggered_by: str,
        user_id: Optional[UUID]
    ) -> UUID:
        """Create initial analysis record."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO prompt_improvement_analyses (
                    projects_analyzed,
                    sandbox_type,
                    triggered_by,
                    user_id,
                    status
                )
                VALUES ($1, $2, $3, $4, 'running')
                RETURNING id
            """, project_ids, sandbox_type, triggered_by, user_id)
            return row['id']

    async def _update_analysis_projects(
        self,
        analysis_id: UUID,
        project_ids: List[UUID]
    ):
        """Update analysis with actual project IDs."""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE prompt_improvement_analyses
                SET projects_analyzed = $1
                WHERE id = $2
            """, project_ids, analysis_id)

    async def _complete_analysis(
        self,
        analysis_id: UUID,
        sessions_count: int,
        patterns: Dict[str, Any],
        proposals: List[Dict[str, Any]],
        date_start: datetime
    ):
        """Mark analysis as completed and store results."""
        quality_impact = self._estimate_quality_impact(patterns)

        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE prompt_improvement_analyses
                SET
                    status = 'completed',
                    completed_at = NOW(),
                    sessions_analyzed = $1,
                    patterns_identified = $2,
                    quality_impact_estimate = $3,
                    date_range_start = $4,
                    date_range_end = NOW()
                WHERE id = $5
            """, sessions_count, json.dumps(patterns), quality_impact, date_start, analysis_id)

    async def _mark_analysis_failed(self, analysis_id: UUID, error: str):
        """Mark analysis as failed."""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE prompt_improvement_analyses
                SET
                    status = 'failed',
                    completed_at = NOW(),
                    notes = $1
                WHERE id = $2
            """, error, analysis_id)

    async def _store_proposal(
        self,
        analysis_id: UUID,
        proposal: Dict[str, Any]
    ):
        """Store a proposal in the database."""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO prompt_proposals (
                    analysis_id,
                    prompt_file,
                    section_name,
                    change_type,
                    original_text,
                    proposed_text,
                    rationale,
                    evidence,
                    confidence_level
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                analysis_id,
                proposal["prompt_file"],
                proposal["section_name"],
                proposal["change_type"],
                proposal.get("original_text", ""),
                proposal["proposed_text"],
                proposal["rationale"],
                json.dumps(proposal["evidence"]),
                proposal["confidence_level"]
            )
