"""Tests for session orchestration module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_harness.session import (
    SessionConfig,
    SessionOrchestrator,
    SessionResult,
    run_session,
)
from agent_harness.agent import TokenUsage


class TestSessionResult:
    """Tests for SessionResult."""

    def test_failed_result(self):
        """Failed result creation."""
        result = SessionResult(
            success=False,
            session_id=1,
            error="Pre-flight failed",
        )
        assert result.success is False
        assert result.error == "Pre-flight failed"
        assert result.features_completed == []

    def test_success_result(self):
        """Successful result creation."""
        result = SessionResult(
            success=True,
            session_id=5,
            features_completed=[1, 2],
            tokens_used=TokenUsage(input_tokens=5000, output_tokens=2000),
            cost_usd=0.05,
            duration_seconds=120.5,
            message="Completed 2 features",
            verification_passed=True,
        )
        assert result.success is True
        assert result.features_completed == [1, 2]
        assert result.tokens_used.total_tokens == 7000
        assert result.verification_passed is True


class TestSessionConfig:
    """Tests for SessionConfig."""

    def test_default_config(self, tmp_path):
        """Default configuration values."""
        config = SessionConfig(project_dir=tmp_path)
        assert config.skip_preflight is False
        assert config.skip_tests is False
        assert config.skip_commit is False
        assert config.dry_run is False
        assert config.max_turns == 50

    def test_custom_config(self, tmp_path):
        """Custom configuration values."""
        config = SessionConfig(
            project_dir=tmp_path,
            skip_preflight=True,
            skip_tests=True,
            dry_run=True,
            max_turns=10,
        )
        assert config.skip_preflight is True
        assert config.dry_run is True
        assert config.max_turns == 10


class TestSessionOrchestrator:
    """Tests for SessionOrchestrator."""

    def _create_minimal_project(self, tmp_path):
        """Create a minimal valid project structure."""
        import subprocess

        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()

        # Create session state
        state = {
            "harness_version": "1.0.0",
            "schema_version": 1,
            "last_session": 0,
            "status": "complete",
            "next_prompt": "coding",
            "stuck_count": 0,
            "total_sessions": 0,
        }
        (harness_dir / "session_state.json").write_text(json.dumps(state))

        # Create features.json
        features = {
            "project": "test",
            "generated_by": "test",
            "init_mode": "new",
            "last_updated": "2024-01-01",
            "features": [
                {
                    "id": 1,
                    "category": "core",
                    "description": "Test feature",
                    "test_file": "tests/test_feature.py",
                    "verification_steps": ["Run tests"],
                    "passes": False,
                }
            ],
        }
        (tmp_path / "features.json").write_text(json.dumps(features))

        # Create actual git repo (not just .git directory)
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        return tmp_path

    def test_init_orchestrator(self, tmp_path):
        """Initialize orchestrator with project dir."""
        self._create_minimal_project(tmp_path)
        orchestrator = SessionOrchestrator(tmp_path)
        assert orchestrator.project_dir == tmp_path
        assert orchestrator.harness_dir == tmp_path / ".harness"

    async def test_session_returns_result(self, tmp_path):
        """Session run should return SessionResult."""
        self._create_minimal_project(tmp_path)
        # Make all features complete for simpler test
        features = {
            "project": "test",
            "generated_by": "test",
            "init_mode": "new",
            "last_updated": "2024-01-01",
            "features": [
                {
                    "id": 1,
                    "category": "core",
                    "description": "Test feature",
                    "test_file": "tests/test_feature.py",
                    "passes": True,  # Complete
                }
            ],
        }
        (tmp_path / "features.json").write_text(json.dumps(features))

        orchestrator = SessionOrchestrator(tmp_path)

        config = SessionConfig(
            project_dir=tmp_path,
            skip_preflight=True,
        )

        result = await orchestrator.run_session(config)

        # Should return a SessionResult
        assert isinstance(result, SessionResult)
        assert result.session_id >= 1


class TestRunSession:
    """Tests for run_session helper function."""

    def _create_minimal_project(self, tmp_path):
        """Create a minimal valid project structure."""
        import subprocess

        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()

        state = {
            "harness_version": "1.0.0",
            "schema_version": 1,
            "last_session": 0,
            "status": "complete",
            "next_prompt": "coding",
            "stuck_count": 0,
            "total_sessions": 0,
        }
        (harness_dir / "session_state.json").write_text(json.dumps(state))

        features = {
            "project": "test",
            "generated_by": "test",
            "init_mode": "new",
            "last_updated": "2024-01-01",
            "features": [
                {
                    "id": 1,
                    "category": "core",
                    "description": "Test feature",
                    "test_file": "tests/test_feature.py",
                    "passes": True,  # All complete
                }
            ],
        }
        (tmp_path / "features.json").write_text(json.dumps(features))
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        return tmp_path

    async def test_run_session_helper(self, tmp_path):
        """run_session helper should work."""
        self._create_minimal_project(tmp_path)

        result = await run_session(
            project_dir=tmp_path,
            skip_preflight=True,
        )

        assert isinstance(result, SessionResult)
        assert result.session_id >= 1

    async def test_run_session_returns_result(self, tmp_path):
        """run_session should return SessionResult."""
        self._create_minimal_project(tmp_path)

        result = await run_session(
            project_dir=tmp_path,
            skip_preflight=True,
        )

        # Should return a SessionResult (may fail due to env but should not crash)
        assert isinstance(result, SessionResult)
        assert result.session_id >= 1
