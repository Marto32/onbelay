"""Tests for context manager module."""

import pytest

from agent_harness.context_manager import (
    ContextManager,
    ContextStatus,
    ContextWarning,
    create_context_manager,
    get_context_window_size,
)


class TestContextStatus:
    """Tests for ContextStatus."""

    def test_create_status(self):
        """Create a context status."""
        status = ContextStatus(
            tokens_used=50000,
            context_window=200000,
            percentage_used=0.25,
            tokens_remaining=150000,
        )
        assert status.tokens_used == 50000
        assert status.percentage_used == 0.25
        assert status.warning_level == "none"

    def test_status_with_warning(self):
        """Status with warning level."""
        status = ContextStatus(
            tokens_used=160000,
            context_window=200000,
            percentage_used=0.80,
            tokens_remaining=40000,
            warning_level="warning",
            message="Consider wrapping up",
        )
        assert status.warning_level == "warning"
        assert status.message is not None


class TestContextWarning:
    """Tests for ContextWarning."""

    def test_create_warning(self):
        """Create a context warning."""
        warning = ContextWarning(
            level="warning",
            message="75% context used",
        )
        assert warning.level == "warning"
        assert warning.force_action is False

    def test_force_action_warning(self):
        """Warning with force action."""
        warning = ContextWarning(
            level="critical",
            message="90% context used",
            force_action=True,
        )
        assert warning.force_action is True


class TestContextManager:
    """Tests for ContextManager."""

    def test_initial_state(self):
        """Initial state should have zero tokens used."""
        manager = ContextManager()
        assert manager.tokens_used == 0
        assert manager.percentage_used == 0.0
        assert manager.can_continue() is True

    def test_update_usage(self):
        """Updating usage should increase tokens."""
        manager = ContextManager()
        manager.update_usage(input_tokens=1000, output_tokens=500)
        assert manager.tokens_used == 1500

        manager.update_usage(input_tokens=2000, output_tokens=1000)
        assert manager.tokens_used == 4500

    def test_percentage_used(self):
        """Percentage should be calculated correctly."""
        manager = ContextManager()
        # With 200k context and 4k reserve = 196k usable
        manager.update_usage(input_tokens=98000, output_tokens=0)
        assert manager.percentage_used == pytest.approx(0.5, rel=0.01)

    def test_tokens_remaining(self):
        """Remaining tokens should be calculated correctly."""
        manager = ContextManager()
        initial_remaining = manager.tokens_remaining
        manager.update_usage(input_tokens=10000, output_tokens=0)
        assert manager.tokens_remaining == initial_remaining - 10000

    def test_get_status_none_level(self):
        """Status should be 'none' when well under limits."""
        manager = ContextManager()
        manager.update_usage(input_tokens=10000, output_tokens=0)
        status = manager.get_status()
        assert status.warning_level == "none"
        assert status.message is None

    def test_get_status_warning_level(self):
        """Status should be 'warning' at 75%."""
        manager = ContextManager(warning_threshold=0.75)
        # Use 75% of usable context
        usable = manager.usable_tokens
        manager.update_usage(input_tokens=int(usable * 0.76), output_tokens=0)
        status = manager.get_status()
        assert status.warning_level == "warning"
        assert status.message is not None

    def test_get_status_critical_level(self):
        """Status should be 'critical' at 90%."""
        manager = ContextManager(critical_threshold=0.90)
        usable = manager.usable_tokens
        manager.update_usage(input_tokens=int(usable * 0.91), output_tokens=0)
        status = manager.get_status()
        assert status.warning_level == "critical"

    def test_get_status_exceeded_level(self):
        """Status should be 'exceeded' at 100%."""
        manager = ContextManager()
        usable = manager.usable_tokens
        manager.update_usage(input_tokens=usable + 1000, output_tokens=0)
        status = manager.get_status()
        assert status.warning_level == "exceeded"

    def test_check_and_warn_no_warning(self):
        """No warning when under threshold."""
        manager = ContextManager()
        manager.update_usage(input_tokens=10000, output_tokens=0)
        warning = manager.check_and_warn()
        assert warning is None

    def test_check_and_warn_warning(self):
        """Warning issued at threshold."""
        manager = ContextManager(warning_threshold=0.75)
        usable = manager.usable_tokens
        manager.update_usage(input_tokens=int(usable * 0.76), output_tokens=0)

        warning = manager.check_and_warn()
        assert warning is not None
        assert warning.level == "warning"
        assert warning.force_action is False

    def test_check_and_warn_only_once(self):
        """Warning should only be issued once."""
        manager = ContextManager(warning_threshold=0.75)
        usable = manager.usable_tokens
        manager.update_usage(input_tokens=int(usable * 0.76), output_tokens=0)

        warning1 = manager.check_and_warn()
        warning2 = manager.check_and_warn()

        assert warning1 is not None
        assert warning2 is None  # Already issued

    def test_check_and_warn_critical(self):
        """Critical warning at critical threshold."""
        manager = ContextManager(critical_threshold=0.90)
        usable = manager.usable_tokens
        manager.update_usage(input_tokens=int(usable * 0.91), output_tokens=0)

        warning = manager.check_and_warn()
        assert warning is not None
        assert warning.level == "critical"
        assert warning.force_action is True

    def test_check_and_warn_hard_stop(self):
        """Hard stop at 100%."""
        manager = ContextManager()
        usable = manager.usable_tokens
        manager.update_usage(input_tokens=usable + 1000, output_tokens=0)

        warning = manager.check_and_warn()
        assert warning is not None
        assert warning.level == "hard_stop"
        assert warning.force_action is True

    def test_can_continue(self):
        """can_continue should return False when exceeded."""
        manager = ContextManager()
        assert manager.can_continue() is True

        usable = manager.usable_tokens
        manager.update_usage(input_tokens=usable + 1000, output_tokens=0)
        assert manager.can_continue() is False

    def test_estimate_turns_remaining(self):
        """Estimate remaining turns."""
        manager = ContextManager()
        initial_turns = manager.estimate_turns_remaining(avg_tokens_per_turn=2000)
        assert initial_turns > 0

        manager.update_usage(input_tokens=10000, output_tokens=0)
        fewer_turns = manager.estimate_turns_remaining(avg_tokens_per_turn=2000)
        assert fewer_turns < initial_turns

    def test_reset(self):
        """Reset should clear all state."""
        manager = ContextManager()
        manager.update_usage(input_tokens=100000, output_tokens=0)
        manager.check_and_warn()  # Issue warning

        manager.reset()

        assert manager.tokens_used == 0
        assert manager.warning_issued is False
        assert manager.critical_issued is False


class TestCreateContextManager:
    """Tests for create_context_manager factory."""

    def test_create_with_defaults(self):
        """Create with default values."""
        manager = create_context_manager()
        assert manager.warning_threshold == 0.75
        assert manager.critical_threshold == 0.90

    def test_create_with_custom_values(self):
        """Create with custom values."""
        manager = create_context_manager(
            model="claude-3-opus-20240229",
            warning_threshold=0.70,
            critical_threshold=0.85,
        )
        assert manager.model == "claude-3-opus-20240229"
        assert manager.warning_threshold == 0.70
        assert manager.critical_threshold == 0.85


class TestGetContextWindowSize:
    """Tests for get_context_window_size."""

    def test_known_model(self):
        """Known model should return correct size."""
        size = get_context_window_size("claude-3-opus-20240229")
        assert size == 200000

    def test_unknown_model(self):
        """Unknown model should return default size."""
        size = get_context_window_size("unknown-model")
        assert size == 200000  # default
