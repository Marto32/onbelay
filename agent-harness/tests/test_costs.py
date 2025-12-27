"""Tests for costs.py - Cost tracking."""

import pytest
from pathlib import Path

from agent_harness.costs import (
    SessionCost,
    BudgetCheck,
    CostTracker,
    load_costs,
    save_costs,
    calculate_cost,
    add_usage,
    start_session,
    end_session,
    check_budget,
    check_budget_or_raise,
    get_session_summary,
    get_project_summary,
    get_feature_cost,
)
from agent_harness.config import CostsConfig
from agent_harness.exceptions import BudgetExceededError, StateError


class TestSessionCost:
    """Tests for SessionCost dataclass."""

    def test_create_session_cost(self):
        """Test creating a session cost entry."""
        cost = SessionCost(session_id=1)
        assert cost.session_id == 1
        assert cost.tokens_input == 0
        assert cost.tokens_output == 0
        assert cost.cost_usd == 0.0

    def test_session_cost_with_tokens(self):
        """Test session cost with token counts."""
        cost = SessionCost(
            session_id=5,
            tokens_input=1000,
            tokens_output=500,
            tokens_cached=200,
            cost_usd=0.15,
            model="claude-sonnet-4",
            feature_id=42,
        )
        assert cost.session_id == 5
        assert cost.tokens_input == 1000
        assert cost.tokens_output == 500
        assert cost.tokens_cached == 200
        assert cost.feature_id == 42


class TestCostTracker:
    """Tests for CostTracker dataclass."""

    def test_create_empty_tracker(self):
        """Test creating an empty cost tracker."""
        tracker = CostTracker()
        assert tracker.current_session is None
        assert tracker.total_sessions == 0
        assert tracker.total_cost_usd == 0.0
        assert tracker.by_feature == {}


class TestLoadSaveCosts:
    """Tests for load/save costs functions."""

    def test_save_and_load_costs(self, tmp_path):
        """Test saving and loading costs."""
        costs_path = tmp_path / "costs.yaml"
        tracker = CostTracker(
            total_sessions=5,
            total_cost_usd=25.50,
            total_tokens_input=100000,
            by_feature={1: 10.0, 2: 15.5},
        )

        save_costs(costs_path, tracker)
        loaded = load_costs(costs_path)

        assert loaded.total_sessions == 5
        assert loaded.total_cost_usd == 25.50
        assert loaded.total_tokens_input == 100000
        assert loaded.by_feature[1] == 10.0
        assert loaded.by_feature[2] == 15.5

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Test loading from missing file returns empty tracker."""
        loaded = load_costs(tmp_path / "missing.yaml")
        assert loaded.total_sessions == 0
        assert loaded.total_cost_usd == 0.0

    def test_save_creates_parent_directory(self, tmp_path):
        """Test that save creates parent directories."""
        costs_path = tmp_path / "nested" / "dir" / "costs.yaml"
        tracker = CostTracker()

        save_costs(costs_path, tracker)
        assert costs_path.exists()


class TestCalculateCost:
    """Tests for cost calculation functions."""

    def test_calculate_cost_sonnet(self):
        """Test cost calculation for Claude Sonnet."""
        # 1M input tokens at $3, 1M output at $15
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cached_tokens=0,
            model="claude-sonnet-4",
        )
        assert cost == pytest.approx(18.0, rel=0.01)

    def test_calculate_cost_with_cache(self):
        """Test cost calculation with cached tokens."""
        # Cached tokens are cheaper
        cost = calculate_cost(
            input_tokens=500_000,
            output_tokens=100_000,
            cached_tokens=500_000,  # Half cached at $0.30/M
            model="claude-sonnet-4",
        )
        # 500k input at $3/M = $1.50
        # 100k output at $15/M = $1.50
        # 500k cached at $0.30/M = $0.15
        expected = 1.50 + 1.50 + 0.15
        assert cost == pytest.approx(expected, rel=0.01)

    def test_calculate_cost_haiku(self):
        """Test cost calculation for Claude Haiku."""
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            model="claude-haiku-3",
        )
        # Haiku: $0.25/M input, $1.25/M output
        assert cost == pytest.approx(1.50, rel=0.01)

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model uses default."""
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            model="unknown-model",
        )
        # Should use default pricing (same as Sonnet)
        assert cost == pytest.approx(18.0, rel=0.01)


class TestSessionManagement:
    """Tests for session management functions."""

    def test_start_session(self):
        """Test starting a session."""
        tracker = CostTracker()

        session = start_session(tracker, session_id=1, feature_id=42)

        assert tracker.current_session is not None
        assert session.session_id == 1
        assert session.feature_id == 42

    def test_end_session(self):
        """Test ending a session."""
        tracker = CostTracker()
        start_session(tracker, session_id=1)
        tracker.current_session.cost_usd = 5.0

        ended = end_session(tracker)

        assert tracker.current_session is None
        assert tracker.total_sessions == 1
        assert len(tracker.session_history) == 1
        assert ended.ended is not None

    def test_start_new_session_ends_previous(self):
        """Test that starting new session ends previous one."""
        tracker = CostTracker()
        start_session(tracker, session_id=1)
        start_session(tracker, session_id=2)

        assert tracker.current_session.session_id == 2
        assert tracker.total_sessions == 1
        assert len(tracker.session_history) == 1


class TestAddUsage:
    """Tests for adding usage to sessions."""

    def test_add_usage(self):
        """Test adding token usage."""
        tracker = CostTracker()
        start_session(tracker, session_id=1)

        add_usage(tracker, input_tokens=1000, output_tokens=500)

        assert tracker.current_session.tokens_input == 1000
        assert tracker.current_session.tokens_output == 500
        assert tracker.current_session.cost_usd > 0
        assert tracker.total_tokens_input == 1000
        assert tracker.total_tokens_output == 500

    def test_add_usage_without_session_raises(self):
        """Test that adding usage without session raises error."""
        tracker = CostTracker()

        with pytest.raises(StateError, match="No active session"):
            add_usage(tracker, input_tokens=1000, output_tokens=500)

    def test_add_usage_updates_feature_cost(self):
        """Test that add_usage updates feature cost."""
        tracker = CostTracker()
        start_session(tracker, session_id=1, feature_id=42)

        add_usage(tracker, input_tokens=1000, output_tokens=500)

        assert 42 in tracker.by_feature
        assert tracker.by_feature[42] > 0

    def test_add_multiple_usages(self):
        """Test adding multiple usages accumulates correctly."""
        tracker = CostTracker()
        start_session(tracker, session_id=1)

        add_usage(tracker, input_tokens=1000, output_tokens=500)
        add_usage(tracker, input_tokens=2000, output_tokens=1000)

        assert tracker.current_session.tokens_input == 3000
        assert tracker.current_session.tokens_output == 1500


class TestBudgetChecking:
    """Tests for budget checking functions."""

    def test_check_budget_within_limits(self):
        """Test budget check when within limits."""
        tracker = CostTracker()
        start_session(tracker, session_id=1)
        tracker.current_session.cost_usd = 5.0
        tracker.total_cost_usd = 50.0

        config = CostsConfig(
            per_session_usd=10.0,
            per_feature_usd=25.0,
            total_project_usd=200.0,
        )

        result = check_budget(tracker, config)

        assert result.within_budget is True
        assert result.remaining == pytest.approx(150.0)

    def test_check_budget_session_exceeded(self):
        """Test budget check when session limit exceeded."""
        tracker = CostTracker()
        start_session(tracker, session_id=1)
        tracker.current_session.cost_usd = 15.0

        config = CostsConfig(per_session_usd=10.0)

        result = check_budget(tracker, config)

        assert result.within_budget is False
        assert result.budget_type == "session"

    def test_check_budget_feature_exceeded(self):
        """Test budget check when feature limit exceeded."""
        tracker = CostTracker()
        start_session(tracker, session_id=1, feature_id=42)
        tracker.by_feature[42] = 30.0

        config = CostsConfig(per_feature_usd=25.0, per_session_usd=100.0)

        result = check_budget(tracker, config)

        assert result.within_budget is False
        assert result.budget_type == "feature"

    def test_check_budget_project_exceeded(self):
        """Test budget check when project limit exceeded."""
        tracker = CostTracker(total_cost_usd=250.0)

        config = CostsConfig(total_project_usd=200.0)

        result = check_budget(tracker, config)

        assert result.within_budget is False
        assert result.budget_type == "project"

    def test_check_budget_or_raise(self):
        """Test check_budget_or_raise raises on exceeded."""
        tracker = CostTracker(total_cost_usd=250.0)
        config = CostsConfig(total_project_usd=200.0)

        with pytest.raises(BudgetExceededError) as exc_info:
            check_budget_or_raise(tracker, config)

        assert exc_info.value.budget_type == "project"
        assert exc_info.value.limit == 200.0
        assert exc_info.value.current == 250.0


class TestSummaries:
    """Tests for summary functions."""

    def test_get_session_summary_no_session(self):
        """Test session summary when no active session."""
        tracker = CostTracker()

        summary = get_session_summary(tracker)

        assert summary["active"] is False
        assert summary["tokens_input"] == 0

    def test_get_session_summary_with_session(self):
        """Test session summary with active session."""
        tracker = CostTracker()
        start_session(tracker, session_id=5, feature_id=42)
        add_usage(tracker, input_tokens=1000, output_tokens=500)

        summary = get_session_summary(tracker)

        assert summary["active"] is True
        assert summary["session_id"] == 5
        assert summary["feature_id"] == 42
        assert summary["tokens_input"] == 1000

    def test_get_project_summary(self):
        """Test project summary."""
        tracker = CostTracker(
            total_sessions=10,
            total_cost_usd=100.0,
            total_tokens_input=1000000,
            total_tokens_output=500000,
            by_feature={1: 50.0, 2: 50.0},
        )

        summary = get_project_summary(tracker)

        assert summary["total_sessions"] == 10
        assert summary["total_cost_usd"] == 100.0
        assert summary["features_with_costs"] == 2
        assert summary["average_session_cost"] == 10.0


class TestFeatureCost:
    """Tests for feature cost tracking."""

    def test_get_feature_cost(self):
        """Test getting cost for a feature."""
        tracker = CostTracker(by_feature={42: 15.50})

        cost = get_feature_cost(tracker, 42)

        assert cost == 15.50

    def test_get_feature_cost_missing(self):
        """Test getting cost for missing feature returns 0."""
        tracker = CostTracker()

        cost = get_feature_cost(tracker, 999)

        assert cost == 0.0
