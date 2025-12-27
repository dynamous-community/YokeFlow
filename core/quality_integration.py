"""
Quality & Review Integration
=============================

Integration between orchestrator and review system.
Handles quality checks, deep reviews, and test coverage analysis.

Extracted from orchestrator.py for better organization.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable, TYPE_CHECKING
from uuid import UUID

from core.database_connection import DatabaseManager
from core.observability import SessionLogger
from review.review_metrics import analyze_session_logs, quick_quality_check, get_quality_rating

if TYPE_CHECKING:
    from core.database import TaskDatabase
    from core.orchestrator_models import SessionType
    from core.config import Config

logger = logging.getLogger(__name__)


class QualityIntegration:
    """
    Handles integration between orchestrator and quality/review systems.

    This class encapsulates all quality-related operations that run
    after sessions complete.
    """

    def __init__(self, config: "Config", event_callback: Optional[Callable] = None):
        """
        Initialize quality integration.

        Args:
            config: Configuration object (for model selection)
            event_callback: Optional async callback for events
        """
        self.config = config
        self.event_callback = event_callback

    async def run_quality_check(
        self,
        session_id: UUID,
        project_path: Path,
        session_logger: SessionLogger,
        session_status: str,
        session_type: "SessionType"
    ) -> None:
        """
        Run quick quality check on completed session (Phase 1 Review System).

        This runs after every session with zero API cost. It:
        1. Analyzes session JSONL log for metrics
        2. Checks for critical quality issues
        3. Stores results in database
        4. Triggers deep review if needed (Phase 2)

        Args:
            session_id: UUID of the completed session
            project_path: Path to project directory
            session_logger: Logger with JSONL path info
            session_status: Session end status ('continue', 'error', 'interrupted')
            session_type: Type of session (INITIALIZER or CODING)
        """
        try:
            from core.orchestrator_models import SessionType

            # Find session JSONL log
            jsonl_path = session_logger.jsonl_file

            if not jsonl_path.exists():
                logger.warning(f"Quality check skipped: JSONL log not found at {jsonl_path}")
                return

            # Extract metrics from session log
            metrics = analyze_session_logs(jsonl_path)

            # Run quick quality check (skip browser verification for initializer sessions)
            is_initializer = session_type == SessionType.INITIALIZER
            issues = quick_quality_check(metrics, is_initializer=is_initializer)

            # Separate critical issues from warnings
            critical_issues = [i for i in issues if i.startswith("❌")]
            warnings = [i for i in issues if i.startswith("⚠️")]

            # Calculate overall quality rating
            rating = get_quality_rating(metrics)

            # Store in database
            async with DatabaseManager() as db:
                check_id = await db.store_quality_check(
                    session_id=session_id,
                    metrics=metrics,
                    critical_issues=critical_issues,
                    warnings=warnings,
                    overall_rating=rating
                )

            # Log quality summary
            if critical_issues:
                logger.warning(f"Quality check (Session {session_id}): {len(critical_issues)} critical issues")
                for issue in critical_issues:
                    logger.warning(f"  {issue}")
            elif warnings:
                logger.info(f"Quality check (Session {session_id}): {len(warnings)} warnings, rating {rating}/10")
            else:
                logger.info(f"Quality check (Session {session_id}): No issues, rating {rating}/10")

            # Phase 2: Trigger deep review if needed (async, non-blocking)
            await self.maybe_trigger_deep_review(session_id, project_path, rating)

        except Exception as e:
            # Don't let quality check failures break the session
            logger.error(f"Quality check failed: {e}", exc_info=True)

    async def maybe_trigger_deep_review(
        self,
        session_id: UUID,
        project_path: Path,
        session_quality: Optional[int],
        force_final_review: bool = False
    ) -> None:
        """
        Trigger deep review if conditions are met (Phase 2 Review System).

        Deep reviews are triggered when:
        1. Every 5th session (sessions 5, 10, 15, 20, ...)
        2. Quality drops below 7/10
        3. No deep review in last 5 sessions
        4. Project completes (force_final_review=True)

        This runs asynchronously in the background and doesn't block the session flow.

        Args:
            session_id: UUID of the completed session
            project_path: Path to project directory
            session_quality: Quality rating from quick check (1-10), or None
            force_final_review: If True, trigger review regardless of interval (for project completion)
        """
        try:
            # Import here to avoid circular dependency
            from review.review_client import should_trigger_deep_review, run_deep_review

            # Get project ID and session number from session
            async with DatabaseManager() as db:
                async with db.acquire() as conn:
                    session = await conn.fetchrow(
                        "SELECT project_id, session_number FROM sessions WHERE id = $1",
                        session_id
                    )
                    if not session:
                        logger.warning(f"Session {session_id} not found for deep review trigger check")
                        return

                    project_id = session['project_id']
                    session_number = session['session_number']

            # Check if deep review should be triggered
            # If force_final_review is True (project completion), always trigger
            if force_final_review:
                should_trigger = True
                logger.info(f"🔍 Forcing final deep review for completed project (session {session_number})")
            else:
                should_trigger = await should_trigger_deep_review(project_id, session_number, session_quality)

            if not should_trigger:
                return

            # Log trigger reason
            if force_final_review:
                logger.info(f"🔍 Triggering deep review for session {session_id} (project completion)")
            elif session_quality is not None:
                logger.info(f"🔍 Triggering deep review for session {session_id} (quality: {session_quality}/10)")
            else:
                logger.info(f"🔍 Triggering deep review for session {session_id}")

            # For final reviews (project completion), wait for completion
            # For regular reviews, run in background to not block session flow
            if force_final_review:
                # Wait for final review to complete (important for project completion)
                logger.info(f"🔍 Running final deep review synchronously (project completion)")
                await self._run_deep_review_background(session_id, project_path)
            else:
                # Run deep review asynchronously (non-blocking)
                # This spawns a background task that doesn't block the session
                asyncio.create_task(self._run_deep_review_background(session_id, project_path))

        except Exception as e:
            # Don't let deep review trigger failures break the session
            logger.error(f"Failed to trigger deep review: {e}", exc_info=True)

    async def _run_deep_review_background(
        self,
        session_id: UUID,
        project_path: Path
    ) -> None:
        """
        Run deep review in background (Phase 2 Review System).

        This is executed as a background task so it doesn't block the main session flow.
        Even if the deep review takes 30-60 seconds, the session can continue or complete.

        Args:
            session_id: UUID of the session to review
            project_path: Path to project directory
        """
        try:
            from review.review_client import run_deep_review

            logger.info(f"🔍 Starting background deep review for session {session_id}")

            result = await run_deep_review(
                session_id=session_id,
                project_path=project_path,
                model=self.config.models.coding  # Use same model as coding sessions
            )

            logger.info(
                f"✅ Deep review complete for session {session_id}: "
                f"Rating {result['overall_rating']}/10"
            )

            # Notify via callback if available
            if self.event_callback:
                async with DatabaseManager() as db:
                    async with db.acquire() as conn:
                        session = await conn.fetchrow(
                            "SELECT project_id FROM sessions WHERE id = $1",
                            session_id
                        )
                        if session:
                            await self.event_callback(session['project_id'], "deep_review_complete", {
                                "session_id": str(session_id),
                                "rating": result['overall_rating']
                            })

        except Exception as e:
            logger.error(f"Deep review failed for session {session_id}: {e}", exc_info=True)

    async def run_test_coverage_analysis(
        self,
        project_id: UUID,
        db: "TaskDatabase"
    ) -> None:
        """
        Run test coverage analysis after initialization session completes.

        This analyzes the test-to-task ratio and identifies epics with poor coverage.
        Results are stored in project metadata for later review.

        Args:
            project_id: UUID of the project
            db: TaskDatabase instance (already connected)
        """
        try:
            from core.tests_coverage import analyze_test_coverage

            logger.info(f"Running test coverage analysis for project {project_id}...")

            # Analyze coverage
            coverage_data = await analyze_test_coverage(db, project_id)

            # Store in database
            await db.store_test_coverage(project_id, coverage_data)

            # Log summary
            overall = coverage_data['overall']
            logger.info(
                f"Test Coverage: {overall['tasks_with_tests']}/{overall['total_tasks']} tasks have tests "
                f"({overall['coverage_percentage']:.1f}%)"
            )

            # Log warnings if any
            if coverage_data['warnings']:
                for warning in coverage_data['warnings']:
                    logger.warning(f"Test Coverage: {warning}")

            # Log poor coverage epics
            if coverage_data['poor_coverage_epics']:
                logger.warning(
                    f"Test Coverage: {len(coverage_data['poor_coverage_epics'])} epic(s) have poor test coverage"
                )
                for epic in coverage_data['poor_coverage_epics'][:3]:  # Log first 3
                    logger.warning(
                        f"  - Epic {epic['epic_id']}: {epic['epic_name']} "
                        f"({epic['tasks_without_tests']}/{epic['total_tasks']} tasks without tests)"
                    )

        except Exception as e:
            # Don't let coverage analysis failures break the session
            logger.error(f"Test coverage analysis failed: {e}", exc_info=True)
