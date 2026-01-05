"""
Session Checkpoint Manager for YokeFlow
========================================

Manages session checkpoints for failure recovery and resumption.
Enables sessions to be resumed from the last successful state after crashes or errors.

Key Features:
- Automatic checkpointing after task completion
- Full conversation history preservation
- State validation before resumption
- Recovery attempt tracking
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from uuid import UUID
from pathlib import Path

from core.database_connection import DatabaseManager

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages session checkpoints for recovery and resumption.

    Checkpoints are created at key points during session execution:
    - After each task completion (automatic)
    - After epic completion (automatic)
    - On manual request (manual)
    - Before error handling (error)
    """

    def __init__(self, session_id: str, project_id: str):
        """
        Initialize checkpoint manager for a session.

        Args:
            session_id: UUID of the current session
            project_id: UUID of the project
        """
        self.session_id = UUID(session_id)
        self.project_id = UUID(project_id)
        self.checkpoint_count = 0
        self.last_checkpoint_id: Optional[UUID] = None

    async def create_checkpoint(
        self,
        checkpoint_type: str,
        conversation_history: List[Dict],
        current_task_id: Optional[int] = None,
        current_epic_id: Optional[int] = None,
        message_count: int = 0,
        iteration_count: int = 0,
        tool_results_cache: Optional[Dict] = None,
        completed_tasks: Optional[List[int]] = None,
        in_progress_tasks: Optional[List[int]] = None,
        blocked_tasks: Optional[List[int]] = None,
        metrics_snapshot: Optional[Dict] = None,
        files_modified: Optional[List[str]] = None,
        git_commit_sha: Optional[str] = None,
        resume_notes: Optional[str] = None
    ) -> UUID:
        """
        Create a checkpoint of the current session state.

        Args:
            checkpoint_type: Type of checkpoint (task_completion, epic_completion, manual, error)
            conversation_history: Full conversation history (list of message dicts)
            current_task_id: ID of current task being worked on
            current_epic_id: ID of current epic
            message_count: Number of messages in conversation
            iteration_count: Number of iterations completed
            tool_results_cache: Recent tool results for context
            completed_tasks: List of completed task IDs
            in_progress_tasks: List of in-progress task IDs
            blocked_tasks: List of blocked task IDs
            metrics_snapshot: Current metrics (tokens, cost, etc.)
            files_modified: List of files modified in session
            git_commit_sha: Latest git commit SHA
            resume_notes: Optional notes about how to resume

        Returns:
            UUID of the created checkpoint
        """
        async with DatabaseManager() as db:
            checkpoint_id = await db.create_checkpoint(
                session_id=self.session_id,
                project_id=self.project_id,
                checkpoint_type=checkpoint_type,
                current_task_id=current_task_id,
                current_epic_id=current_epic_id,
                message_count=message_count,
                iteration_count=iteration_count,
                conversation_history=conversation_history,
                tool_results_cache=tool_results_cache or {},
                completed_tasks=completed_tasks or [],
                in_progress_tasks=in_progress_tasks or [],
                blocked_tasks=blocked_tasks or [],
                metrics_snapshot=metrics_snapshot or {},
                files_modified=files_modified or [],
                git_commit_sha=git_commit_sha,
                resume_notes=resume_notes
            )

        self.checkpoint_count += 1
        self.last_checkpoint_id = checkpoint_id

        logger.info(
            f"Created checkpoint {self.checkpoint_count} for session {self.session_id}: "
            f"type={checkpoint_type}, task={current_task_id}, messages={message_count}"
        )

        return checkpoint_id

    async def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest checkpoint for this session.

        Returns:
            Checkpoint data or None if no checkpoints exist
        """
        async with DatabaseManager() as db:
            return await db.get_latest_checkpoint(self.session_id)

    async def get_resumable_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest resumable checkpoint for this session.

        Returns:
            Checkpoint data or None if no resumable checkpoints exist
        """
        async with DatabaseManager() as db:
            return await db.get_resumable_checkpoint(self.session_id)

    async def invalidate_checkpoints(self, reason: str) -> int:
        """
        Invalidate all checkpoints for this session.

        Use when state has changed in a way that makes old checkpoints unsafe to resume from.

        Args:
            reason: Reason for invalidation

        Returns:
            Number of checkpoints invalidated
        """
        async with DatabaseManager() as db:
            count = await db.invalidate_checkpoints(self.session_id, reason)

        logger.warning(
            f"Invalidated {count} checkpoints for session {self.session_id}: {reason}"
        )

        return count


class CheckpointRecoveryManager:
    """
    Manages recovery from checkpoints.

    Handles the process of restoring session state from a checkpoint,
    validating the restoration, and tracking recovery attempts.
    """

    def __init__(self):
        """Initialize recovery manager."""
        self.current_recovery_id: Optional[UUID] = None

    async def start_recovery(
        self,
        checkpoint_id: str,
        recovery_method: str = "automatic",
        new_session_id: Optional[str] = None
    ) -> UUID:
        """
        Start a checkpoint recovery attempt.

        Args:
            checkpoint_id: UUID of the checkpoint to recover from
            recovery_method: Method of recovery (automatic, manual, partial)
            new_session_id: Optional UUID of new session for recovery

        Returns:
            UUID of the recovery record
        """
        async with DatabaseManager() as db:
            recovery_id = await db.start_checkpoint_recovery(
                checkpoint_id=UUID(checkpoint_id),
                recovery_method=recovery_method,
                new_session_id=UUID(new_session_id) if new_session_id else None
            )

        self.current_recovery_id = recovery_id

        logger.info(
            f"Started recovery from checkpoint {checkpoint_id}: "
            f"method={recovery_method}, recovery_id={recovery_id}"
        )

        return recovery_id

    async def complete_recovery(
        self,
        recovery_id: str,
        status: str,
        recovery_notes: Optional[str] = None,
        error_message: Optional[str] = None,
        state_differences: Optional[Dict] = None
    ) -> bool:
        """
        Mark a recovery attempt as completed.

        Args:
            recovery_id: UUID of the recovery record
            status: Status (success, failed)
            recovery_notes: Optional notes about the recovery
            error_message: Optional error message if failed
            state_differences: Optional dict of state differences detected

        Returns:
            True if recovery was marked complete successfully
        """
        async with DatabaseManager() as db:
            success = await db.complete_checkpoint_recovery(
                recovery_id=UUID(recovery_id),
                status=status,
                recovery_notes=recovery_notes,
                error_message=error_message,
                state_differences=state_differences or {}
            )

        logger.info(
            f"Completed recovery {recovery_id}: status={status}"
        )

        return success

    async def restore_from_checkpoint(
        self,
        checkpoint_id: str
    ) -> Dict[str, Any]:
        """
        Restore session state from a checkpoint.

        Args:
            checkpoint_id: UUID of the checkpoint to restore from

        Returns:
            Restored state dictionary with:
            - conversation_history: Full conversation to restore
            - current_task_id: Task to resume
            - completed_tasks: Tasks already completed
            - metrics: Metrics at checkpoint
            - resume_prompt: Suggested prompt for resumption
        """
        async with DatabaseManager() as db:
            checkpoint = await db.get_checkpoint(UUID(checkpoint_id))

            if not checkpoint:
                raise ValueError(f"Checkpoint not found: {checkpoint_id}")

            if checkpoint.get("invalidated"):
                raise ValueError(
                    f"Checkpoint {checkpoint_id} is invalidated: "
                    f"{checkpoint.get('invalidation_reason')}"
                )

            if not checkpoint.get("can_resume_from"):
                raise ValueError(f"Checkpoint {checkpoint_id} cannot be resumed from")

        # Build restore state
        restore_state = {
            "checkpoint_id": checkpoint_id,
            "session_id": str(checkpoint["session_id"]),
            "project_id": str(checkpoint["project_id"]),
            "checkpoint_number": checkpoint["checkpoint_number"],
            "checkpoint_type": checkpoint["checkpoint_type"],

            # Conversation state
            "conversation_history": checkpoint.get("conversation_history", []),
            "message_count": checkpoint.get("message_count", 0),
            "iteration_count": checkpoint.get("iteration_count", 0),

            # Task state
            "current_task_id": checkpoint.get("current_task_id"),
            "current_epic_id": checkpoint.get("current_epic_id"),
            "completed_tasks": checkpoint.get("completed_tasks", []),
            "in_progress_tasks": checkpoint.get("in_progress_tasks", []),
            "blocked_tasks": checkpoint.get("blocked_tasks", []),

            # Context
            "tool_results_cache": checkpoint.get("tool_results_cache", {}),
            "metrics": checkpoint.get("metrics_snapshot", {}),

            # File state
            "files_modified": checkpoint.get("files_modified", []),
            "git_commit_sha": checkpoint.get("git_commit_sha"),

            # Resume info
            "resume_notes": checkpoint.get("resume_notes"),
            "created_at": checkpoint.get("created_at"),
            "recovery_count": checkpoint.get("recovery_count", 0)
        }

        # Generate resume prompt
        restore_state["resume_prompt"] = self._generate_resume_prompt(checkpoint)

        logger.info(
            f"Restored state from checkpoint {checkpoint_id}: "
            f"task={restore_state['current_task_id']}, "
            f"messages={restore_state['message_count']}"
        )

        return restore_state

    def _generate_resume_prompt(self, checkpoint: Dict) -> str:
        """
        Generate a prompt for resuming from a checkpoint.

        Args:
            checkpoint: Checkpoint data

        Returns:
            Resume prompt string
        """
        parts = [
            "## Session Resumed from Checkpoint",
            f"**Checkpoint**: #{checkpoint['checkpoint_number']} ({checkpoint['checkpoint_type']})",
            f"**Created**: {checkpoint['created_at']}",
        ]

        if checkpoint.get("resume_notes"):
            parts.append(f"\n**Notes**: {checkpoint['resume_notes']}")

        if checkpoint.get("current_task_id"):
            parts.append(f"\n**Resuming Task**: #{checkpoint['current_task_id']}")

        completed = checkpoint.get("completed_tasks", [])
        if completed:
            parts.append(f"\n**Completed Tasks**: {len(completed)} tasks completed")

        parts.extend([
            "\n## Instructions",
            "1. Review the conversation history to understand current context",
            "2. Continue with the current task if not completed",
            "3. Follow the same quality standards and coding practices",
            "4. Document any issues encountered during recovery"
        ])

        if checkpoint.get("recovery_count", 0) > 0:
            parts.append(
                f"\n⚠️ This checkpoint has been resumed {checkpoint['recovery_count']} times. "
                "Verify state carefully before proceeding."
            )

        return "\n".join(parts)

    async def validate_checkpoint_state(
        self,
        checkpoint_id: str,
        actual_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Validate that a checkpoint's state matches actual state.

        Args:
            checkpoint_id: UUID of checkpoint to validate
            actual_state: Current actual state to compare against

        Returns:
            Tuple of (is_valid, differences_dict)
        """
        async with DatabaseManager() as db:
            checkpoint = await db.get_checkpoint(UUID(checkpoint_id))

        if not checkpoint:
            return False, {"error": "Checkpoint not found"}

        differences = {}

        # Compare file states
        checkpoint_files = set(checkpoint.get("files_modified", []))
        actual_files = set(actual_state.get("files_modified", []))

        if checkpoint_files != actual_files:
            differences["files_modified"] = {
                "checkpoint": list(checkpoint_files),
                "actual": list(actual_files),
                "added": list(actual_files - checkpoint_files),
                "removed": list(checkpoint_files - actual_files)
            }

        # Compare git state
        if checkpoint.get("git_commit_sha") != actual_state.get("git_commit_sha"):
            differences["git_commit_sha"] = {
                "checkpoint": checkpoint.get("git_commit_sha"),
                "actual": actual_state.get("git_commit_sha")
            }

        # Compare task state
        checkpoint_tasks = set(checkpoint.get("completed_tasks", []))
        actual_tasks = set(actual_state.get("completed_tasks", []))

        if checkpoint_tasks != actual_tasks:
            differences["completed_tasks"] = {
                "checkpoint": list(checkpoint_tasks),
                "actual": list(actual_tasks),
                "checkpoint_only": list(checkpoint_tasks - actual_tasks),
                "actual_only": list(actual_tasks - checkpoint_tasks)
            }

        is_valid = len(differences) == 0

        if not is_valid:
            logger.warning(
                f"Checkpoint {checkpoint_id} validation failed: {len(differences)} differences found"
            )

        return is_valid, differences if not is_valid else None


# Utility functions

async def get_resumable_sessions(project_id: Optional[str] = None) -> List[Dict]:
    """
    Get all sessions that can be resumed from checkpoints.

    Args:
        project_id: Optional project UUID to filter by

    Returns:
        List of resumable session info dicts
    """
    async with DatabaseManager() as db:
        return await db.get_resumable_sessions(
            project_id=UUID(project_id) if project_id else None
        )


async def get_checkpoint_recovery_history(
    project_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """
    Get history of checkpoint recoveries.

    Args:
        project_id: Optional project UUID to filter by
        limit: Maximum number of records

    Returns:
        List of recovery history dicts
    """
    async with DatabaseManager() as db:
        return await db.get_checkpoint_recovery_history(
            project_id=UUID(project_id) if project_id else None,
            limit=limit
        )
