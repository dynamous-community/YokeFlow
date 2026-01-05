"""
Tests for Session Checkpoint System
====================================

Comprehensive tests for checkpoint creation, recovery, and restoration including:
- Checkpoint creation with full state
- Checkpoint recovery from failures
- State validation
- Resume prompt generation
- Database persistence
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4, UUID
from datetime import datetime

from core.checkpoint import (
    CheckpointManager,
    CheckpointRecoveryManager,
    get_resumable_sessions,
    get_checkpoint_recovery_history
)


class TestCheckpointManager:
    """Test the CheckpointManager class."""

    @pytest.mark.asyncio
    async def test_create_checkpoint_basic(self):
        """Test basic checkpoint creation."""
        session_id = str(uuid4())
        project_id = str(uuid4())

        manager = CheckpointManager(session_id, project_id)

        conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            checkpoint_id = uuid4()
            mock_db.create_checkpoint = AsyncMock(return_value=checkpoint_id)

            # Create checkpoint
            result = await manager.create_checkpoint(
                checkpoint_type="task_completion",
                conversation_history=conversation,
                current_task_id=123,
                message_count=2
            )

            # Verify
            assert result == checkpoint_id
            assert manager.checkpoint_count == 1
            assert manager.last_checkpoint_id == checkpoint_id

            # Check call arguments
            call_args = mock_db.create_checkpoint.call_args
            assert call_args.kwargs['session_id'] == UUID(session_id)
            assert call_args.kwargs['project_id'] == UUID(project_id)
            assert call_args.kwargs['checkpoint_type'] == "task_completion"
            assert call_args.kwargs['current_task_id'] == 123
            assert call_args.kwargs['message_count'] == 2

    @pytest.mark.asyncio
    async def test_create_checkpoint_with_full_state(self):
        """Test checkpoint creation with full state information."""
        session_id = str(uuid4())
        project_id = str(uuid4())

        manager = CheckpointManager(session_id, project_id)

        conversation = [{"role": "user", "content": "Test"}]
        tool_cache = {"last_result": "success"}
        metrics = {"tokens": 1000, "cost": 0.05}
        completed_tasks = [1, 2, 3]
        in_progress_tasks = [4]
        files_modified = ["src/app.py", "tests/test_app.py"]

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            checkpoint_id = uuid4()
            mock_db.create_checkpoint = AsyncMock(return_value=checkpoint_id)

            result = await manager.create_checkpoint(
                checkpoint_type="epic_completion",
                conversation_history=conversation,
                current_task_id=4,
                current_epic_id=1,
                message_count=10,
                iteration_count=5,
                tool_results_cache=tool_cache,
                completed_tasks=completed_tasks,
                in_progress_tasks=in_progress_tasks,
                blocked_tasks=[],
                metrics_snapshot=metrics,
                files_modified=files_modified,
                git_commit_sha="abc123",
                resume_notes="Completed epic 1"
            )

            # Verify all state was passed
            call_args = mock_db.create_checkpoint.call_args
            assert call_args.kwargs['checkpoint_type'] == "epic_completion"
            assert call_args.kwargs['current_epic_id'] == 1
            assert call_args.kwargs['iteration_count'] == 5
            assert call_args.kwargs['tool_results_cache'] == tool_cache
            assert call_args.kwargs['completed_tasks'] == completed_tasks
            assert call_args.kwargs['metrics_snapshot'] == metrics
            assert call_args.kwargs['git_commit_sha'] == "abc123"

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self):
        """Test getting latest checkpoint."""
        session_id = str(uuid4())
        project_id = str(uuid4())

        manager = CheckpointManager(session_id, project_id)

        checkpoint_data = {
            "id": uuid4(),
            "checkpoint_number": 5,
            "checkpoint_type": "task_completion"
        }

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_latest_checkpoint = AsyncMock(return_value=checkpoint_data)

            result = await manager.get_latest_checkpoint()

            assert result == checkpoint_data
            mock_db.get_latest_checkpoint.assert_called_once_with(UUID(session_id))

    @pytest.mark.asyncio
    async def test_get_resumable_checkpoint(self):
        """Test getting resumable checkpoint."""
        session_id = str(uuid4())
        project_id = str(uuid4())

        manager = CheckpointManager(session_id, project_id)

        checkpoint_data = {
            "id": uuid4(),
            "can_resume_from": True,
            "invalidated": False
        }

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_resumable_checkpoint = AsyncMock(return_value=checkpoint_data)

            result = await manager.get_resumable_checkpoint()

            assert result == checkpoint_data

    @pytest.mark.asyncio
    async def test_invalidate_checkpoints(self):
        """Test invalidating checkpoints."""
        session_id = str(uuid4())
        project_id = str(uuid4())

        manager = CheckpointManager(session_id, project_id)

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.invalidate_checkpoints = AsyncMock(return_value=3)

            count = await manager.invalidate_checkpoints("State changed")

            assert count == 3
            mock_db.invalidate_checkpoints.assert_called_once_with(
                UUID(session_id),
                "State changed"
            )


class TestCheckpointRecoveryManager:
    """Test the CheckpointRecoveryManager class."""

    @pytest.mark.asyncio
    async def test_start_recovery(self):
        """Test starting a recovery attempt."""
        manager = CheckpointRecoveryManager()

        checkpoint_id = str(uuid4())
        new_session_id = str(uuid4())

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            recovery_id = uuid4()
            mock_db.start_checkpoint_recovery = AsyncMock(return_value=recovery_id)

            result = await manager.start_recovery(
                checkpoint_id=checkpoint_id,
                recovery_method="automatic",
                new_session_id=new_session_id
            )

            assert result == recovery_id
            assert manager.current_recovery_id == recovery_id

            call_args = mock_db.start_checkpoint_recovery.call_args
            assert call_args.kwargs['checkpoint_id'] == UUID(checkpoint_id)
            assert call_args.kwargs['recovery_method'] == "automatic"
            assert call_args.kwargs['new_session_id'] == UUID(new_session_id)

    @pytest.mark.asyncio
    async def test_complete_recovery_success(self):
        """Test completing a successful recovery."""
        manager = CheckpointRecoveryManager()

        recovery_id = str(uuid4())

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.complete_checkpoint_recovery = AsyncMock(return_value=True)

            success = await manager.complete_recovery(
                recovery_id=recovery_id,
                status="success",
                recovery_notes="Successfully resumed from checkpoint"
            )

            assert success is True

            call_args = mock_db.complete_checkpoint_recovery.call_args
            assert call_args.kwargs['recovery_id'] == UUID(recovery_id)
            assert call_args.kwargs['status'] == "success"

    @pytest.mark.asyncio
    async def test_complete_recovery_failed(self):
        """Test completing a failed recovery."""
        manager = CheckpointRecoveryManager()

        recovery_id = str(uuid4())

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.complete_checkpoint_recovery = AsyncMock(return_value=True)

            success = await manager.complete_recovery(
                recovery_id=recovery_id,
                status="failed",
                error_message="State validation failed",
                state_differences={"files": ["diff1.py"]}
            )

            assert success is True

            call_args = mock_db.complete_checkpoint_recovery.call_args
            assert call_args.kwargs['status'] == "failed"
            assert call_args.kwargs['error_message'] == "State validation failed"

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_success(self):
        """Test successful restore from checkpoint."""
        manager = CheckpointRecoveryManager()

        checkpoint_id = str(uuid4())
        session_id = uuid4()
        project_id = uuid4()

        checkpoint_data = {
            "id": UUID(checkpoint_id),
            "session_id": session_id,
            "project_id": project_id,
            "checkpoint_number": 3,
            "checkpoint_type": "task_completion",
            "conversation_history": [{"role": "user", "content": "Test"}],
            "message_count": 5,
            "iteration_count": 2,
            "current_task_id": 10,
            "current_epic_id": 2,
            "completed_tasks": [1, 2, 3],
            "in_progress_tasks": [4],
            "blocked_tasks": [],
            "tool_results_cache": {"last": "result"},
            "metrics_snapshot": {"tokens": 1000},
            "files_modified": ["app.py"],
            "git_commit_sha": "abc123",
            "resume_notes": "Test resume",
            "created_at": datetime.now(),
            "recovery_count": 0,
            "can_resume_from": True,
            "invalidated": False
        }

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_checkpoint = AsyncMock(return_value=checkpoint_data)

            state = await manager.restore_from_checkpoint(checkpoint_id)

            # Verify restored state
            assert state["checkpoint_id"] == checkpoint_id
            assert state["session_id"] == str(session_id)
            assert state["project_id"] == str(project_id)
            assert state["checkpoint_number"] == 3
            assert state["current_task_id"] == 10
            assert state["message_count"] == 5
            assert state["completed_tasks"] == [1, 2, 3]
            assert "resume_prompt" in state

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_not_found(self):
        """Test restore fails when checkpoint not found."""
        manager = CheckpointRecoveryManager()

        checkpoint_id = str(uuid4())

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_checkpoint = AsyncMock(return_value=None)

            with pytest.raises(ValueError, match="Checkpoint not found"):
                await manager.restore_from_checkpoint(checkpoint_id)

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_invalidated(self):
        """Test restore fails when checkpoint is invalidated."""
        manager = CheckpointRecoveryManager()

        checkpoint_id = str(uuid4())

        checkpoint_data = {
            "id": UUID(checkpoint_id),
            "invalidated": True,
            "invalidation_reason": "State diverged"
        }

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_checkpoint = AsyncMock(return_value=checkpoint_data)

            with pytest.raises(ValueError, match="is invalidated"):
                await manager.restore_from_checkpoint(checkpoint_id)

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_cannot_resume(self):
        """Test restore fails when checkpoint cannot be resumed from."""
        manager = CheckpointRecoveryManager()

        checkpoint_id = str(uuid4())

        checkpoint_data = {
            "id": UUID(checkpoint_id),
            "invalidated": False,
            "can_resume_from": False
        }

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_checkpoint = AsyncMock(return_value=checkpoint_data)

            with pytest.raises(ValueError, match="cannot be resumed from"):
                await manager.restore_from_checkpoint(checkpoint_id)

    @pytest.mark.asyncio
    async def test_validate_checkpoint_state_valid(self):
        """Test checkpoint state validation succeeds."""
        manager = CheckpointRecoveryManager()

        checkpoint_id = str(uuid4())

        checkpoint_data = {
            "files_modified": ["app.py", "test.py"],
            "git_commit_sha": "abc123",
            "completed_tasks": [1, 2, 3]
        }

        actual_state = {
            "files_modified": ["app.py", "test.py"],
            "git_commit_sha": "abc123",
            "completed_tasks": [1, 2, 3]
        }

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_checkpoint = AsyncMock(return_value=checkpoint_data)

            is_valid, differences = await manager.validate_checkpoint_state(
                checkpoint_id,
                actual_state
            )

            assert is_valid is True
            assert differences is None

    @pytest.mark.asyncio
    async def test_validate_checkpoint_state_files_differ(self):
        """Test checkpoint validation detects file differences."""
        manager = CheckpointRecoveryManager()

        checkpoint_id = str(uuid4())

        checkpoint_data = {
            "files_modified": ["app.py"],
            "git_commit_sha": "abc123",
            "completed_tasks": [1, 2]
        }

        actual_state = {
            "files_modified": ["app.py", "new_file.py"],
            "git_commit_sha": "abc123",
            "completed_tasks": [1, 2]
        }

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_checkpoint = AsyncMock(return_value=checkpoint_data)

            is_valid, differences = await manager.validate_checkpoint_state(
                checkpoint_id,
                actual_state
            )

            assert is_valid is False
            assert differences is not None
            assert "files_modified" in differences
            assert "new_file.py" in differences["files_modified"]["added"]

    @pytest.mark.asyncio
    async def test_validate_checkpoint_state_git_differs(self):
        """Test checkpoint validation detects git commit differences."""
        manager = CheckpointRecoveryManager()

        checkpoint_id = str(uuid4())

        checkpoint_data = {
            "files_modified": [],
            "git_commit_sha": "abc123",
            "completed_tasks": []
        }

        actual_state = {
            "files_modified": [],
            "git_commit_sha": "def456",
            "completed_tasks": []
        }

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_checkpoint = AsyncMock(return_value=checkpoint_data)

            is_valid, differences = await manager.validate_checkpoint_state(
                checkpoint_id,
                actual_state
            )

            assert is_valid is False
            assert "git_commit_sha" in differences

    def test_generate_resume_prompt(self):
        """Test resume prompt generation."""
        manager = CheckpointRecoveryManager()

        checkpoint = {
            "checkpoint_number": 3,
            "checkpoint_type": "task_completion",
            "created_at": "2024-01-01T10:00:00",
            "resume_notes": "Continue with task 5",
            "current_task_id": 5,
            "completed_tasks": [1, 2, 3, 4],
            "recovery_count": 0
        }

        prompt = manager._generate_resume_prompt(checkpoint)

        # Verify prompt contains key information
        assert "Session Resumed from Checkpoint" in prompt
        assert "#3" in prompt
        assert "task_completion" in prompt
        assert "Continue with task 5" in prompt
        assert "Resuming Task" in prompt
        assert "#5" in prompt
        assert "4 tasks completed" in prompt

    def test_generate_resume_prompt_with_recovery_count(self):
        """Test resume prompt warns about multiple recoveries."""
        manager = CheckpointRecoveryManager()

        checkpoint = {
            "checkpoint_number": 2,
            "checkpoint_type": "manual",
            "created_at": "2024-01-01T10:00:00",
            "recovery_count": 3
        }

        prompt = manager._generate_resume_prompt(checkpoint)

        # Should include warning
        assert "resumed 3 times" in prompt
        assert "Verify state carefully" in prompt


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.asyncio
    async def test_get_resumable_sessions(self):
        """Test getting resumable sessions."""
        project_id = str(uuid4())

        resumable_sessions = [
            {"session_id": uuid4(), "checkpoint_id": uuid4()},
            {"session_id": uuid4(), "checkpoint_id": uuid4()}
        ]

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_resumable_sessions = AsyncMock(return_value=resumable_sessions)

            result = await get_resumable_sessions(project_id)

            assert len(result) == 2
            assert result == resumable_sessions

    @pytest.mark.asyncio
    async def test_get_checkpoint_recovery_history(self):
        """Test getting checkpoint recovery history."""
        project_id = str(uuid4())

        history = [
            {"recovery_id": uuid4(), "status": "success"},
            {"recovery_id": uuid4(), "status": "failed"}
        ]

        with patch('core.checkpoint.DatabaseManager') as MockDB:
            mock_db = AsyncMock()
            MockDB.return_value.__aenter__.return_value = mock_db

            mock_db.get_checkpoint_recovery_history = AsyncMock(return_value=history)

            result = await get_checkpoint_recovery_history(project_id, limit=10)

            assert len(result) == 2
            assert result == history


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
