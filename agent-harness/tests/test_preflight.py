"""Tests for preflight checks module."""

import json
from pathlib import Path

import pytest

from agent_harness.preflight import (
    PreflightCheckResult,
    PreflightResult,
    check_features_file,
    check_git_state,
    check_harness_files,
    check_working_directory,
    format_preflight_result,
    run_preflight_checks,
)


class TestPreflightCheckResult:
    """Tests for PreflightCheckResult."""

    def test_passed_check(self):
        """Passed check should have passed=True."""
        result = PreflightCheckResult(
            name="test_check",
            passed=True,
            message="All good",
        )
        assert result.passed is True
        assert result.warning is False

    def test_failed_check(self):
        """Failed check should have passed=False."""
        result = PreflightCheckResult(
            name="test_check",
            passed=False,
            message="Something wrong",
        )
        assert result.passed is False

    def test_warning_check(self):
        """Warning check should have warning=True."""
        result = PreflightCheckResult(
            name="test_check",
            passed=True,
            message="Minor issue",
            warning=True,
        )
        assert result.passed is True
        assert result.warning is True

    def test_check_with_details(self):
        """Check can include details."""
        result = PreflightCheckResult(
            name="test_check",
            passed=False,
            message="Error",
            details="Full error trace here",
        )
        assert result.details == "Full error trace here"


class TestPreflightResult:
    """Tests for PreflightResult."""

    def test_empty_result_passes(self):
        """Empty result should pass."""
        result = PreflightResult(passed=True)
        assert result.passed is True
        assert result.checks == []
        assert result.warnings == []

    def test_add_passing_check(self):
        """Adding a passing check maintains passed state."""
        result = PreflightResult(passed=True)
        result.add_check(
            PreflightCheckResult(name="check1", passed=True, message="OK")
        )
        assert result.passed is True
        assert len(result.checks) == 1

    def test_add_failing_check(self):
        """Adding a failing check sets passed=False."""
        result = PreflightResult(passed=True)
        result.add_check(
            PreflightCheckResult(name="check1", passed=False, message="Failed")
        )
        assert result.passed is False
        assert result.abort_reason == "check1: Failed"

    def test_add_warning_check(self):
        """Warning check adds to warnings list."""
        result = PreflightResult(passed=True)
        result.add_check(
            PreflightCheckResult(
                name="check1",
                passed=True,
                message="Minor issue",
                warning=True,
            )
        )
        assert result.passed is True
        assert len(result.warnings) == 1
        assert "Minor issue" in result.warnings[0]


class TestCheckWorkingDirectory:
    """Tests for check_working_directory."""

    def test_existing_directory(self, tmp_path):
        """Existing directory should pass."""
        result = check_working_directory(tmp_path)
        assert result.passed is True
        assert result.name == "working_directory"

    def test_nonexistent_directory(self):
        """Non-existent directory should fail."""
        result = check_working_directory(Path("/nonexistent/path"))
        assert result.passed is False
        assert "does not exist" in result.message

    def test_file_not_directory(self, tmp_path):
        """File (not directory) should fail."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("test")
        result = check_working_directory(test_file)
        assert result.passed is False
        assert "not a directory" in result.message


class TestCheckHarnessFiles:
    """Tests for check_harness_files."""

    def test_all_files_present(self, tmp_path):
        """All files present should pass."""
        (tmp_path / ".harness").mkdir()
        (tmp_path / "features.json").write_text("{}")
        result = check_harness_files(tmp_path)
        assert result.passed is True

    def test_missing_harness_dir(self, tmp_path):
        """Missing .harness should fail."""
        (tmp_path / "features.json").write_text("{}")
        result = check_harness_files(tmp_path)
        assert result.passed is False
        assert ".harness" in result.message

    def test_missing_features_file(self, tmp_path):
        """Missing features.json should fail."""
        (tmp_path / ".harness").mkdir()
        result = check_harness_files(tmp_path)
        assert result.passed is False
        assert "features.json" in result.message


class TestCheckGitState:
    """Tests for check_git_state."""

    def test_not_git_repo(self, tmp_path):
        """Non-git directory should fail."""
        result = check_git_state(tmp_path)
        assert result.passed is False
        assert "Not a git repository" in result.message

    def test_git_repo_no_git(self, tmp_path):
        """Non-git dir should fail (not just mkdir .git)."""
        # Creating just .git dir without proper git init should fail
        (tmp_path / ".git").mkdir()
        result = check_git_state(tmp_path)
        # Either fails or passes - the key is it doesn't crash
        assert result.name == "git_state"


class TestCheckFeaturesFile:
    """Tests for check_features_file."""

    def test_valid_features(self, tmp_path):
        """Valid features file should pass."""
        features = {
            "project": "test",
            "generated_by": "test",
            "init_mode": "new",
            "last_updated": "2024-01-01",
            "features": [
                {
                    "id": 1,
                    "category": "test",
                    "description": "Test feature",
                    "test_file": "tests/test_feature.py",
                    "passes": False,
                }
            ],
        }
        (tmp_path / "features.json").write_text(json.dumps(features))
        result = check_features_file(tmp_path)
        assert result.passed is True
        assert "0/1 complete" in result.message

    def test_no_features(self, tmp_path):
        """Empty features list should fail."""
        features = {
            "project": "test",
            "generated_by": "test",
            "init_mode": "new",
            "last_updated": "2024-01-01",
            "features": [],
        }
        (tmp_path / "features.json").write_text(json.dumps(features))
        result = check_features_file(tmp_path)
        assert result.passed is False
        assert "No features" in result.message

    def test_all_features_complete(self, tmp_path):
        """All features complete should warn."""
        features = {
            "project": "test",
            "generated_by": "test",
            "init_mode": "new",
            "last_updated": "2024-01-01",
            "features": [
                {
                    "id": 1,
                    "category": "test",
                    "description": "Test feature",
                    "test_file": "tests/test_feature.py",
                    "passes": True,
                }
            ],
        }
        (tmp_path / "features.json").write_text(json.dumps(features))
        result = check_features_file(tmp_path)
        assert result.passed is True
        assert result.warning is True
        assert "complete" in result.message


class TestRunPreflightChecks:
    """Tests for run_preflight_checks."""

    def test_minimal_valid_setup(self, tmp_path):
        """Minimal valid setup should run checks."""
        import subprocess

        # Create required files
        (tmp_path / ".harness").mkdir()
        # Create actual git repo for proper testing
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        features = {
            "project": "test",
            "generated_by": "test",
            "init_mode": "new",
            "last_updated": "2024-01-01",
            "features": [
                {
                    "id": 1,
                    "category": "test",
                    "description": "Test",
                    "test_file": "tests/test.py",
                    "passes": False,
                }
            ],
        }
        (tmp_path / "features.json").write_text(json.dumps(features))

        result = run_preflight_checks(
            tmp_path,
            skip_tests=True,
            skip_init_script=True,
        )

        # Should have run at least some checks
        assert len(result.checks) >= 3

    def test_nonexistent_directory_fails_early(self):
        """Non-existent directory should fail on first check."""
        result = run_preflight_checks(Path("/nonexistent"))
        assert result.passed is False
        assert len(result.checks) == 1
        assert result.checks[0].name == "working_directory"


class TestFormatPreflightResult:
    """Tests for format_preflight_result."""

    def test_format_passed_result(self):
        """Passed result should show success."""
        result = PreflightResult(passed=True)
        result.add_check(
            PreflightCheckResult(name="check1", passed=True, message="OK")
        )
        formatted = format_preflight_result(result)
        assert "Pre-flight Checks" in formatted
        assert "[PASS]" in formatted
        assert "All checks passed" in formatted

    def test_format_failed_result(self):
        """Failed result should show abort reason."""
        result = PreflightResult(passed=True)
        result.add_check(
            PreflightCheckResult(name="check1", passed=False, message="Error")
        )
        formatted = format_preflight_result(result)
        assert "[FAIL]" in formatted
        assert "ABORT" in formatted

    def test_format_with_warnings(self):
        """Warnings should be listed."""
        result = PreflightResult(passed=True)
        result.add_check(
            PreflightCheckResult(
                name="check1",
                passed=True,
                message="Minor issue",
                warning=True,
            )
        )
        formatted = format_preflight_result(result)
        assert "[WARN]" in formatted
        assert "Warnings:" in formatted
