"""Tests for progress monitor module."""

import pytest

from agent_harness.progress_monitor import (
    ProgressCheck,
    ProgressMonitor,
    ProgressSnapshot,
    StuckPattern,
    create_progress_monitor,
    format_progress_warning,
)


class TestProgressSnapshot:
    """Tests for ProgressSnapshot."""

    def test_default_values(self):
        """Default values should be zero/empty."""
        snapshot = ProgressSnapshot()
        assert snapshot.tokens_used == 0
        assert snapshot.files_modified == 0
        assert snapshot.tests_run == 0
        assert snapshot.error_count == 0

    def test_custom_values(self):
        """Custom values should be set."""
        snapshot = ProgressSnapshot(
            tokens_used=5000,
            files_modified=3,
            tests_run=10,
            tests_passed=9,
            tool_calls=5,
        )
        assert snapshot.tokens_used == 5000
        assert snapshot.files_modified == 3
        assert snapshot.tests_passed == 9


class TestProgressCheck:
    """Tests for ProgressCheck."""

    def test_making_progress(self):
        """Making progress check."""
        check = ProgressCheck(
            making_progress=True,
            message="All good",
        )
        assert check.making_progress is True
        assert check.force_stop is False
        assert check.warning_level == "none"

    def test_stuck_check(self):
        """Stuck check."""
        check = ProgressCheck(
            making_progress=False,
            message="Stuck",
            stuck_count=2,
            warning_level="high",
        )
        assert check.making_progress is False
        assert check.stuck_count == 2


class TestStuckPattern:
    """Tests for StuckPattern."""

    def test_create_pattern(self):
        """Create a stuck pattern."""
        pattern = StuckPattern(
            pattern_type="no_files",
            description="No file changes",
            severity="medium",
        )
        assert pattern.pattern_type == "no_files"
        assert pattern.severity == "medium"


class TestProgressMonitor:
    """Tests for ProgressMonitor."""

    def test_initial_state(self):
        """Initial state should be empty."""
        monitor = ProgressMonitor()
        assert len(monitor.snapshots) == 0
        assert monitor.stuck_count == 0

    def test_take_snapshot(self):
        """Taking snapshot should add to list."""
        monitor = ProgressMonitor()
        snapshot = monitor.take_snapshot(
            tokens_used=1000,
            files_modified=2,
        )
        assert len(monitor.snapshots) == 1
        assert snapshot.tokens_used == 1000
        assert snapshot.files_modified == 2

    def test_should_check(self):
        """should_check should return True at interval."""
        monitor = ProgressMonitor(check_interval_tokens=5000)
        assert monitor.should_check(0) is False
        assert monitor.should_check(4999) is False
        assert monitor.should_check(5000) is True
        assert monitor.should_check(10000) is True

    def test_check_progress_initial(self):
        """Initial check should pass (not enough data)."""
        monitor = ProgressMonitor()
        monitor.take_snapshot(tokens_used=1000)
        check = monitor.check_progress(monitor.snapshots[-1])
        assert check.making_progress is True
        assert "Initial" in check.message

    def test_check_progress_making_progress(self):
        """Making progress should pass."""
        monitor = ProgressMonitor()

        # First snapshot
        monitor.take_snapshot(
            tokens_used=1000,
            files_modified=0,
            tool_calls=0,
            tests_run=0,
        )

        # Second snapshot with progress
        monitor.take_snapshot(
            tokens_used=5000,
            files_modified=2,
            tool_calls=5,
            tests_run=3,
        )

        check = monitor.check_progress(monitor.snapshots[-1])
        assert check.making_progress is True
        assert monitor.stuck_count == 0

    def test_check_progress_no_progress(self):
        """No progress should detect stuck."""
        monitor = ProgressMonitor()

        # First snapshot
        monitor.take_snapshot(
            tokens_used=1000,
            files_modified=0,
            tool_calls=0,
            tests_run=0,
        )

        # Second snapshot with NO progress
        monitor.take_snapshot(
            tokens_used=5000,
            files_modified=0,
            tool_calls=0,
            tests_run=0,
        )

        check = monitor.check_progress(monitor.snapshots[-1])
        assert check.making_progress is False
        assert monitor.stuck_count == 1
        assert "Stuck" in check.message

    def test_stuck_threshold_warning(self):
        """Reaching stuck threshold should increase warning level."""
        monitor = ProgressMonitor(stuck_threshold=2)

        # First stuck
        monitor.take_snapshot(tokens_used=1000)
        monitor.take_snapshot(tokens_used=5000)
        check1 = monitor.check_progress(monitor.snapshots[-1])
        assert check1.warning_level == "medium"

        # Second stuck
        monitor.take_snapshot(tokens_used=10000)
        check2 = monitor.check_progress(monitor.snapshots[-1])
        assert check2.warning_level == "high"
        assert monitor.stuck_count == 2

    def test_force_stop_threshold(self):
        """Reaching force stop threshold should set force_stop."""
        monitor = ProgressMonitor(stuck_threshold=1, force_stop_threshold=2)

        # First stuck
        monitor.take_snapshot(tokens_used=1000)
        monitor.take_snapshot(tokens_used=5000)
        monitor.check_progress(monitor.snapshots[-1])

        # Second stuck - should force stop
        monitor.take_snapshot(tokens_used=10000)
        check = monitor.check_progress(monitor.snapshots[-1])
        assert check.force_stop is True
        assert check.warning_level == "critical"

    def test_progress_resets_stuck_count(self):
        """Making progress should reset stuck count."""
        monitor = ProgressMonitor()

        # Get stuck
        monitor.take_snapshot(tokens_used=1000)
        monitor.take_snapshot(tokens_used=5000)
        monitor.check_progress(monitor.snapshots[-1])
        assert monitor.stuck_count == 1

        # Make progress
        monitor.take_snapshot(
            tokens_used=10000,
            files_modified=5,
            tool_calls=10,
            tests_run=3,
        )
        check = monitor.check_progress(monitor.snapshots[-1])
        assert check.making_progress is True
        assert monitor.stuck_count == 0

    def test_get_summary(self):
        """Summary should contain key metrics."""
        monitor = ProgressMonitor()
        monitor.take_snapshot(
            tokens_used=1000,
            files_modified=0,
        )
        monitor.take_snapshot(
            tokens_used=5000,
            files_modified=3,
            tool_calls=10,
        )

        summary = monitor.get_summary()
        assert summary["snapshots_taken"] == 2
        assert summary["total_tokens"] == 5000
        assert summary["files_modified"] == 3
        assert summary["tool_calls"] == 10

    def test_reset(self):
        """Reset should clear all state."""
        monitor = ProgressMonitor()
        monitor.take_snapshot(tokens_used=1000)
        monitor.stuck_count = 2

        monitor.reset()

        assert len(monitor.snapshots) == 0
        assert monitor.stuck_count == 0
        assert monitor.last_check_tokens == 0


class TestCreateProgressMonitor:
    """Tests for create_progress_monitor factory."""

    def test_create_with_defaults(self):
        """Create with default values."""
        monitor = create_progress_monitor()
        assert monitor.check_interval_tokens == 5000
        assert monitor.stuck_threshold == 2
        assert monitor.force_stop_threshold == 3

    def test_create_with_custom_values(self):
        """Create with custom values."""
        monitor = create_progress_monitor(
            check_interval=10000,
            stuck_threshold=3,
            force_stop_threshold=5,
        )
        assert monitor.check_interval_tokens == 10000
        assert monitor.stuck_threshold == 3
        assert monitor.force_stop_threshold == 5


class TestFormatProgressWarning:
    """Tests for format_progress_warning."""

    def test_no_warning_for_progress(self):
        """No warning when making progress."""
        check = ProgressCheck(making_progress=True, message="OK")
        formatted = format_progress_warning(check)
        assert formatted == ""

    def test_warning_formatted(self):
        """Warning should be formatted."""
        check = ProgressCheck(
            making_progress=False,
            message="Stuck on tests",
            warning_level="high",
        )
        formatted = format_progress_warning(check)
        assert "PROGRESS WARNING" in formatted
        assert "Stuck on tests" in formatted
        assert "different approach" in formatted

    def test_force_stop_formatted(self):
        """Force stop should show termination message."""
        check = ProgressCheck(
            making_progress=False,
            message="Multiple stucks",
            force_stop=True,
        )
        formatted = format_progress_warning(check)
        assert "terminated" in formatted
