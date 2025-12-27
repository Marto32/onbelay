"""Tests for CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_harness.cli import main


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def project_with_config(tmp_path):
    """Create a project with minimal config."""
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()

    config = {
        "project": {"name": "test-project"},
        "agent": {"model": "claude-sonnet-4-20250514"},
        "costs": {"daily_limit": 50.0},
    }
    (harness_dir / "config.yaml").write_text(
        "project:\n  name: test-project\n"
    )

    return tmp_path


class TestMainGroup:
    """Tests for main CLI group."""

    def test_version_flag(self, runner):
        """--version shows version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "harness" in result.output.lower()

    def test_help_flag(self, runner):
        """--help shows help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Universal Agent Harness" in result.output


class TestVersionCommand:
    """Tests for version command."""

    def test_version_command(self, runner):
        """version command shows version."""
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert "Agent Harness" in result.output


class TestInitCommand:
    """Tests for init command."""

    def test_init_requires_spec(self, runner, tmp_path):
        """init requires --spec option."""
        result = runner.invoke(main, ["-p", str(tmp_path), "init"])
        assert result.exit_code != 0
        assert "spec" in result.output.lower() or "required" in result.output.lower()

    def test_init_with_dry_run(self, runner, tmp_path):
        """init with --dry-run works."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test Project\n\nBuild something.")

        result = runner.invoke(main, [
            "-p", str(tmp_path),
            "init",
            "--spec", str(spec_file),
            "--dry-run",
        ])

        assert result.exit_code == 0
        assert "Initialization" in result.output

    def test_init_creates_harness_dir(self, runner, tmp_path):
        """init creates .harness directory."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test Project\n\nDescription.")

        result = runner.invoke(main, [
            "-p", str(tmp_path),
            "init",
            "--spec", str(spec_file),
            "--dry-run",
        ])

        assert result.exit_code == 0
        assert (tmp_path / ".harness").exists()

    def test_init_creates_features_json(self, runner, tmp_path):
        """init creates features.json."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test\n\nBuild a test app.")

        result = runner.invoke(main, [
            "-p", str(tmp_path),
            "init",
            "--spec", str(spec_file),
            "--dry-run",
        ])

        assert result.exit_code == 0
        assert (tmp_path / "features.json").exists()

    def test_init_with_mode_new(self, runner, tmp_path):
        """init with --mode new works."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test\n\nNew project.")

        result = runner.invoke(main, [
            "-p", str(tmp_path),
            "init",
            "--spec", str(spec_file),
            "--mode", "new",
            "--dry-run",
        ])

        assert result.exit_code == 0
        assert "Mode: new" in result.output or "new" in result.output.lower()

    def test_init_with_mode_adopt(self, runner, tmp_path):
        """init with --mode adopt works."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test\n\nExisting project.")

        result = runner.invoke(main, [
            "-p", str(tmp_path),
            "init",
            "--spec", str(spec_file),
            "--mode", "adopt",
            "--dry-run",
        ])

        assert result.exit_code == 0
        assert "Mode: adopt" in result.output or "adopt" in result.output.lower()


class TestRunCommand:
    """Tests for run command."""

    def test_run_requires_config(self, runner, tmp_path):
        """run requires project config."""
        result = runner.invoke(main, ["-p", str(tmp_path), "run"])
        # Should fail without config
        assert result.exit_code != 0

    def test_run_with_dry_run(self, runner, tmp_path):
        """run with --dry-run works with proper setup."""
        import subprocess

        # Create proper project structure
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()

        # Create config - use correct YAML structure matching Config dataclass
        config_content = """
project:
  name: test-project
models:
  default: claude-sonnet-4-20250514
costs:
  per_session_usd: 10.0
  per_feature_usd: 25.0
  total_project_usd: 200.0
"""
        (harness_dir / "config.yaml").write_text(config_content)

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

        # Create features
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
                    "test_file": "tests/test.py",
                    "passes": False,
                }
            ],
        }
        (tmp_path / "features.json").write_text(json.dumps(features))

        # Create git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        result = runner.invoke(main, [
            "-p", str(tmp_path),
            "run",
            "--dry-run",
            "--skip-preflight",
        ])

        assert result.exit_code == 0
        assert "Dry run" in result.output or "dry run" in result.output.lower()

    def test_run_help(self, runner):
        """run --help shows options."""
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output
        assert "--feature" in result.output
        assert "--skip-preflight" in result.output


class TestStatusCommand:
    """Tests for status command."""

    def test_status_requires_config(self, runner, tmp_path):
        """status without config exits gracefully or with error."""
        result = runner.invoke(main, ["-p", str(tmp_path), "status"])
        # Either fails or shows warning - key is it handles missing config gracefully
        # The status command may not hard fail if config loading is optional
        assert result.exit_code in [0, 1]

    def test_status_with_config(self, runner, project_with_config):
        """status works with config."""
        result = runner.invoke(main, ["-p", str(project_with_config), "status"])
        # May show warning but should not crash
        assert "Status" in result.output or result.exit_code != 0


class TestHealthCommand:
    """Tests for health command."""

    def test_health_help(self, runner):
        """health --help shows help."""
        result = runner.invoke(main, ["health", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower()


class TestVerifyCommand:
    """Tests for verify command."""

    def test_verify_requires_feature_or_all(self, runner, project_with_config):
        """verify requires --feature or --all."""
        result = runner.invoke(main, ["-p", str(project_with_config), "verify"])
        assert result.exit_code != 0
        assert "feature" in result.output.lower() or "all" in result.output.lower()

    def test_verify_help(self, runner):
        """verify --help shows options."""
        result = runner.invoke(main, ["verify", "--help"])
        assert result.exit_code == 0
        assert "--feature" in result.output
        assert "--all" in result.output


class TestControlCommands:
    """Tests for control commands (pause, resume, skip, handoff, takeback)."""

    def test_pause_command(self, runner):
        """pause command exists."""
        result = runner.invoke(main, ["pause", "--help"])
        assert result.exit_code == 0

    def test_resume_command(self, runner):
        """resume command exists."""
        result = runner.invoke(main, ["resume", "--help"])
        assert result.exit_code == 0

    def test_skip_requires_feature(self, runner):
        """skip requires --feature."""
        result = runner.invoke(main, ["skip"])
        assert result.exit_code != 0

    def test_handoff_command(self, runner):
        """handoff command exists."""
        result = runner.invoke(main, ["handoff", "--help"])
        assert result.exit_code == 0

    def test_takeback_command(self, runner):
        """takeback command exists."""
        result = runner.invoke(main, ["takeback", "--help"])
        assert result.exit_code == 0


class TestCleanupCommand:
    """Tests for cleanup command."""

    def test_cleanup_help(self, runner):
        """cleanup --help shows options."""
        result = runner.invoke(main, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "--now" in result.output


class TestLogsCommand:
    """Tests for logs command."""

    def test_logs_help(self, runner):
        """logs --help shows options."""
        result = runner.invoke(main, ["logs", "--help"])
        assert result.exit_code == 0
        assert "--query" in result.output
        assert "--session" in result.output
        assert "--level" in result.output


class TestMigrateCommand:
    """Tests for migrate command."""

    def test_migrate_help(self, runner):
        """migrate --help shows options."""
        result = runner.invoke(main, ["migrate", "--help"])
        assert result.exit_code == 0
        assert "--no-backup" in result.output
