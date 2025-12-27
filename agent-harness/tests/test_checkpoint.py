"""Tests for checkpoint.py - Checkpoint system."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from git import Repo

from agent_harness.checkpoint import (
    Checkpoint,
    RollbackResult,
    create_checkpoint,
    rollback_to_checkpoint,
    get_checkpoint,
    list_checkpoints,
    list_checkpoints_for_session,
    cleanup_old_checkpoints,
    delete_checkpoint,
    verify_checkpoint,
    get_latest_checkpoint,
    get_checkpoint_count,
)
from agent_harness.exceptions import StateError


@pytest.fixture
def project_with_files(tmp_path):
    """Create a project directory with harness files."""
    # Create .harness directory
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()

    # Create features.json
    features_path = tmp_path / "features.json"
    features_path.write_text('{"project": "test", "features": []}')

    # Create claude-progress.txt
    progress_path = tmp_path / "claude-progress.txt"
    progress_path.write_text("# Claude Progress Log\n")

    # Create session state
    state_path = harness_dir / "session_state.json"
    state_path.write_text('{"session": 1, "status": "complete"}')

    return tmp_path


@pytest.fixture
def git_project(tmp_path):
    """Create a project with git repository."""
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create initial files
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()

    features_path = tmp_path / "features.json"
    features_path.write_text('{"project": "test", "features": []}')

    # Initial commit
    repo.index.add(["features.json"])
    repo.index.commit("Initial commit")

    return tmp_path


class TestCreateCheckpoint:
    """Tests for create_checkpoint function."""

    def test_create_basic_checkpoint(self, project_with_files):
        """Test creating a basic checkpoint."""
        checkpoint = create_checkpoint(
            project_with_files,
            session=1,
            reason="Before risky operation",
        )

        assert checkpoint.id.startswith("checkpoint-1-")
        assert checkpoint.session == 1
        assert checkpoint.reason == "Before risky operation"
        assert "features.json" in checkpoint.files_backed_up
        assert "claude-progress.txt" in checkpoint.files_backed_up
        assert "session_state.json" in checkpoint.files_backed_up

    def test_create_checkpoint_saves_files(self, project_with_files):
        """Test that checkpoint saves backup files."""
        checkpoint = create_checkpoint(
            project_with_files,
            session=1,
            reason="Test",
        )

        checkpoint_path = project_with_files / ".harness" / "checkpoints" / checkpoint.id
        assert checkpoint_path.exists()
        assert (checkpoint_path / "features.json").exists()
        assert (checkpoint_path / "claude-progress.txt").exists()
        assert (checkpoint_path / "checkpoint.json").exists()

    def test_create_checkpoint_with_git(self, git_project):
        """Test that checkpoint captures git ref."""
        checkpoint = create_checkpoint(
            git_project,
            session=1,
            reason="Test",
        )

        assert checkpoint.git_ref
        assert len(checkpoint.git_ref) == 40  # Full SHA

    def test_create_checkpoint_computes_hashes(self, project_with_files):
        """Test that checkpoint computes file hashes."""
        checkpoint = create_checkpoint(
            project_with_files,
            session=1,
            reason="Test",
        )

        assert checkpoint.features_json_hash
        assert checkpoint.progress_file_hash
        assert checkpoint.session_state_hash


class TestRollbackToCheckpoint:
    """Tests for rollback_to_checkpoint function."""

    def test_rollback_restores_files(self, project_with_files):
        """Test that rollback restores files."""
        # Create checkpoint
        checkpoint = create_checkpoint(
            project_with_files,
            session=1,
            reason="Before changes",
        )

        # Modify files
        features_path = project_with_files / "features.json"
        original_content = features_path.read_text()
        features_path.write_text('{"modified": true}')

        # Rollback
        result = rollback_to_checkpoint(
            project_with_files,
            checkpoint.id,
            restore_git=False,
        )

        assert result.success
        assert "features.json" in result.files_restored
        assert features_path.read_text() == original_content

    def test_rollback_to_missing_checkpoint_raises(self, project_with_files):
        """Test rollback to nonexistent checkpoint raises error."""
        with pytest.raises(StateError, match="not found"):
            rollback_to_checkpoint(project_with_files, "nonexistent-id")

    def test_rollback_with_git(self, git_project):
        """Test rollback restores git state."""
        repo = Repo(git_project)
        features_path = git_project / "features.json"

        # Create checkpoint
        checkpoint = create_checkpoint(git_project, session=1, reason="Test")

        # Make changes and commit
        features_path.write_text('{"modified": true}')
        repo.index.add(["features.json"])
        repo.index.commit("Modified")

        # Rollback
        result = rollback_to_checkpoint(git_project, checkpoint.id)

        assert result.git_restored
        assert repo.head.commit.hexsha == checkpoint.git_ref


class TestGetCheckpoint:
    """Tests for get_checkpoint function."""

    def test_get_existing_checkpoint(self, project_with_files):
        """Test getting an existing checkpoint."""
        created = create_checkpoint(project_with_files, session=1, reason="Test")
        retrieved = get_checkpoint(project_with_files, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.session == created.session

    def test_get_nonexistent_checkpoint(self, project_with_files):
        """Test getting nonexistent checkpoint returns None."""
        result = get_checkpoint(project_with_files, "nonexistent")
        assert result is None


class TestListCheckpoints:
    """Tests for list_checkpoints function."""

    def test_list_checkpoints_empty(self, project_with_files):
        """Test listing checkpoints when none exist."""
        checkpoints = list_checkpoints(project_with_files)
        assert checkpoints == []

    def test_list_checkpoints_multiple(self, project_with_files):
        """Test listing multiple checkpoints."""
        create_checkpoint(project_with_files, session=1, reason="First")
        create_checkpoint(project_with_files, session=2, reason="Second")
        create_checkpoint(project_with_files, session=3, reason="Third")

        checkpoints = list_checkpoints(project_with_files)

        assert len(checkpoints) == 3
        # Should be sorted newest first
        assert checkpoints[0].session == 3
        assert checkpoints[2].session == 1

    def test_list_checkpoints_for_session(self, project_with_files):
        """Test listing checkpoints for specific session."""
        create_checkpoint(project_with_files, session=1, reason="First")
        create_checkpoint(project_with_files, session=2, reason="Second")
        create_checkpoint(project_with_files, session=2, reason="Third")

        checkpoints = list_checkpoints_for_session(project_with_files, session=2)

        assert len(checkpoints) == 2
        assert all(c.session == 2 for c in checkpoints)


class TestCleanupCheckpoints:
    """Tests for cleanup_old_checkpoints function."""

    def test_cleanup_old_checkpoints(self, project_with_files):
        """Test cleaning up old checkpoints."""
        # Create checkpoints
        create_checkpoint(project_with_files, session=1, reason="Old")
        create_checkpoint(project_with_files, session=2, reason="New")

        # Manually age the first checkpoint
        checkpoints = list_checkpoints(project_with_files)
        old_checkpoint = [c for c in checkpoints if c.session == 1][0]
        checkpoint_path = project_with_files / ".harness" / "checkpoints" / old_checkpoint.id
        metadata_path = checkpoint_path / "checkpoint.json"

        with open(metadata_path) as f:
            data = json.load(f)

        # Set timestamp to 10 days ago
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        data["timestamp"] = old_time.isoformat().replace("+00:00", "Z")

        with open(metadata_path, "w") as f:
            json.dump(data, f)

        # Cleanup with 7 day max age
        deleted = cleanup_old_checkpoints(
            project_with_files,
            max_age_days=7,
            keep_per_session=0,
        )

        assert deleted == 1
        assert get_checkpoint_count(project_with_files) == 1


class TestDeleteCheckpoint:
    """Tests for delete_checkpoint function."""

    def test_delete_checkpoint(self, project_with_files):
        """Test deleting a checkpoint."""
        checkpoint = create_checkpoint(project_with_files, session=1, reason="Test")

        result = delete_checkpoint(project_with_files, checkpoint.id)

        assert result is True
        assert get_checkpoint(project_with_files, checkpoint.id) is None

    def test_delete_nonexistent_checkpoint(self, project_with_files):
        """Test deleting nonexistent checkpoint returns False."""
        result = delete_checkpoint(project_with_files, "nonexistent")
        assert result is False


class TestVerifyCheckpoint:
    """Tests for verify_checkpoint function."""

    def test_verify_valid_checkpoint(self, project_with_files):
        """Test verifying a valid checkpoint."""
        checkpoint = create_checkpoint(project_with_files, session=1, reason="Test")

        result = verify_checkpoint(project_with_files, checkpoint.id)

        assert result["valid"] is True
        assert "features.json" in result["files"]
        assert result["files"]["features.json"]["exists"] is True

    def test_verify_nonexistent_checkpoint(self, project_with_files):
        """Test verifying nonexistent checkpoint."""
        result = verify_checkpoint(project_with_files, "nonexistent")

        assert result["valid"] is False
        assert "not found" in result["error"]


class TestGetLatestCheckpoint:
    """Tests for get_latest_checkpoint function."""

    def test_get_latest_checkpoint(self, project_with_files):
        """Test getting latest checkpoint."""
        create_checkpoint(project_with_files, session=1, reason="First")
        create_checkpoint(project_with_files, session=2, reason="Second")
        latest_created = create_checkpoint(project_with_files, session=3, reason="Latest")

        latest = get_latest_checkpoint(project_with_files)

        assert latest is not None
        assert latest.id == latest_created.id

    def test_get_latest_checkpoint_none(self, project_with_files):
        """Test getting latest checkpoint when none exist."""
        latest = get_latest_checkpoint(project_with_files)
        assert latest is None


class TestGetCheckpointCount:
    """Tests for get_checkpoint_count function."""

    def test_get_checkpoint_count(self, project_with_files):
        """Test counting checkpoints."""
        assert get_checkpoint_count(project_with_files) == 0

        create_checkpoint(project_with_files, session=1, reason="First")
        assert get_checkpoint_count(project_with_files) == 1

        create_checkpoint(project_with_files, session=2, reason="Second")
        assert get_checkpoint_count(project_with_files) == 2
