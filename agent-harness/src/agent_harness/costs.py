"""Cost tracking for agent-harness.

Tracks token usage and costs per session and per feature.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from agent_harness.config import CostsConfig
from agent_harness.exceptions import BudgetExceededError, StateError


# Token pricing per model (per 1M tokens as of late 2024)
# These are approximate and should be updated as pricing changes
MODEL_PRICING = {
    # Claude 3.5 Sonnet
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00, "cached": 0.30},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00, "cached": 0.30},
    # Claude 3 Haiku
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25, "cached": 0.03},
    "claude-haiku-3": {"input": 0.25, "output": 1.25, "cached": 0.03},
    # Claude 3 Opus
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00, "cached": 1.50},
    # Default fallback
    "default": {"input": 3.00, "output": 15.00, "cached": 0.30},
}


@dataclass
class SessionCost:
    """Cost tracking for a single session."""

    session_id: int
    started: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    ended: Optional[str] = None
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cached: int = 0
    cost_usd: float = 0.0
    model: str = "claude-sonnet-4"
    feature_id: Optional[int] = None


@dataclass
class BudgetCheck:
    """Result of a budget check."""

    within_budget: bool
    budget_type: Optional[str] = None  # "session", "feature", "project"
    limit: float = 0.0
    current: float = 0.0
    remaining: float = 0.0
    message: str = ""


@dataclass
class CostTracker:
    """Tracks costs across sessions and features."""

    current_session: Optional[SessionCost] = None
    total_sessions: int = 0
    total_cost_usd: float = 0.0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_tokens_cached: int = 0
    by_feature: dict[int, float] = field(default_factory=dict)
    session_history: list[SessionCost] = field(default_factory=list)


def _session_cost_to_dict(cost: SessionCost) -> dict:
    """Convert SessionCost to dictionary."""
    return {
        "session_id": cost.session_id,
        "started": cost.started,
        "ended": cost.ended,
        "tokens_input": cost.tokens_input,
        "tokens_output": cost.tokens_output,
        "tokens_cached": cost.tokens_cached,
        "cost_usd": cost.cost_usd,
        "model": cost.model,
        "feature_id": cost.feature_id,
    }


def _dict_to_session_cost(data: dict) -> SessionCost:
    """Convert dictionary to SessionCost."""
    return SessionCost(
        session_id=data.get("session_id", 0),
        started=data.get("started", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
        ended=data.get("ended"),
        tokens_input=data.get("tokens_input", 0),
        tokens_output=data.get("tokens_output", 0),
        tokens_cached=data.get("tokens_cached", 0),
        cost_usd=data.get("cost_usd", 0.0),
        model=data.get("model", "claude-sonnet-4"),
        feature_id=data.get("feature_id"),
    )


def _tracker_to_dict(tracker: CostTracker) -> dict:
    """Convert CostTracker to dictionary."""
    return {
        "current_session": _session_cost_to_dict(tracker.current_session) if tracker.current_session else None,
        "total_sessions": tracker.total_sessions,
        "total_cost_usd": tracker.total_cost_usd,
        "total_tokens_input": tracker.total_tokens_input,
        "total_tokens_output": tracker.total_tokens_output,
        "total_tokens_cached": tracker.total_tokens_cached,
        "by_feature": tracker.by_feature,
        "session_history": [_session_cost_to_dict(s) for s in tracker.session_history],
    }


def _dict_to_tracker(data: dict) -> CostTracker:
    """Convert dictionary to CostTracker."""
    current = data.get("current_session")
    history = data.get("session_history", [])

    return CostTracker(
        current_session=_dict_to_session_cost(current) if current else None,
        total_sessions=data.get("total_sessions", 0),
        total_cost_usd=data.get("total_cost_usd", 0.0),
        total_tokens_input=data.get("total_tokens_input", 0),
        total_tokens_output=data.get("total_tokens_output", 0),
        total_tokens_cached=data.get("total_tokens_cached", 0),
        by_feature={int(k): v for k, v in data.get("by_feature", {}).items()},
        session_history=[_dict_to_session_cost(s) for s in history],
    )


def load_costs(path: Path) -> CostTracker:
    """
    Load cost tracker from file.

    Args:
        path: Path to costs.yaml file.

    Returns:
        CostTracker object.

    Raises:
        StateError: If file is invalid.
    """
    if not path.exists():
        return CostTracker()

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise StateError(f"Invalid YAML in costs file: {e}")

    return _dict_to_tracker(data)


def save_costs(path: Path, costs: CostTracker) -> None:
    """
    Save cost tracker to file.

    Args:
        path: Path to costs.yaml file.
        costs: CostTracker object to save.
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        yaml.dump(_tracker_to_dict(costs), f, default_flow_style=False, sort_keys=False)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    model: str = "claude-sonnet-4",
) -> float:
    """
    Calculate cost in USD from token counts.

    Args:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cached_tokens: Number of cached input tokens.
        model: Model name for pricing lookup.

    Returns:
        Cost in USD.
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])

    # Calculate cost (pricing is per 1M tokens)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    cached_cost = (cached_tokens / 1_000_000) * pricing["cached"]

    return input_cost + output_cost + cached_cost


def add_usage(
    costs: CostTracker,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    model: str = "claude-sonnet-4",
) -> None:
    """
    Add token usage to the current session.

    Args:
        costs: CostTracker object.
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens used.
        cached_tokens: Number of cached input tokens.
        model: Model name for cost calculation.
    """
    if costs.current_session is None:
        raise StateError("No active session. Call start_session first.")

    # Update session tokens
    costs.current_session.tokens_input += input_tokens
    costs.current_session.tokens_output += output_tokens
    costs.current_session.tokens_cached += cached_tokens
    costs.current_session.model = model

    # Calculate incremental cost
    incremental_cost = calculate_cost(input_tokens, output_tokens, cached_tokens, model)
    costs.current_session.cost_usd += incremental_cost

    # Update totals
    costs.total_tokens_input += input_tokens
    costs.total_tokens_output += output_tokens
    costs.total_tokens_cached += cached_tokens
    costs.total_cost_usd += incremental_cost

    # Update feature cost if applicable
    if costs.current_session.feature_id is not None:
        feature_id = costs.current_session.feature_id
        costs.by_feature[feature_id] = costs.by_feature.get(feature_id, 0.0) + incremental_cost


def start_session(
    costs: CostTracker,
    session_id: int,
    feature_id: Optional[int] = None,
    model: str = "claude-sonnet-4",
) -> SessionCost:
    """
    Start tracking a new session.

    Args:
        costs: CostTracker object.
        session_id: ID of the new session.
        feature_id: Feature being worked on (optional).
        model: Model to use for this session.

    Returns:
        New SessionCost object.
    """
    # End current session if one exists
    if costs.current_session is not None:
        end_session(costs)

    costs.current_session = SessionCost(
        session_id=session_id,
        model=model,
        feature_id=feature_id,
    )

    return costs.current_session


def end_session(costs: CostTracker) -> Optional[SessionCost]:
    """
    End the current session.

    Args:
        costs: CostTracker object.

    Returns:
        Ended SessionCost object, or None if no session was active.
    """
    if costs.current_session is None:
        return None

    # Mark session as ended
    costs.current_session.ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Add to history
    costs.session_history.append(costs.current_session)
    costs.total_sessions += 1

    ended_session = costs.current_session
    costs.current_session = None

    return ended_session


def check_budget(costs: CostTracker, config: CostsConfig) -> BudgetCheck:
    """
    Check if any budget limits have been exceeded.

    Args:
        costs: CostTracker object.
        config: CostsConfig with budget limits.

    Returns:
        BudgetCheck result.
    """
    # Check session budget
    if costs.current_session:
        session_cost = costs.current_session.cost_usd
        if session_cost >= config.per_session_usd:
            return BudgetCheck(
                within_budget=False,
                budget_type="session",
                limit=config.per_session_usd,
                current=session_cost,
                remaining=0.0,
                message=f"Session budget exceeded: ${session_cost:.2f} >= ${config.per_session_usd:.2f}",
            )

        # Check feature budget if applicable
        if costs.current_session.feature_id is not None:
            feature_id = costs.current_session.feature_id
            feature_cost = costs.by_feature.get(feature_id, 0.0)
            if feature_cost >= config.per_feature_usd:
                return BudgetCheck(
                    within_budget=False,
                    budget_type="feature",
                    limit=config.per_feature_usd,
                    current=feature_cost,
                    remaining=0.0,
                    message=f"Feature {feature_id} budget exceeded: ${feature_cost:.2f} >= ${config.per_feature_usd:.2f}",
                )

    # Check project budget
    if costs.total_cost_usd >= config.total_project_usd:
        return BudgetCheck(
            within_budget=False,
            budget_type="project",
            limit=config.total_project_usd,
            current=costs.total_cost_usd,
            remaining=0.0,
            message=f"Project budget exceeded: ${costs.total_cost_usd:.2f} >= ${config.total_project_usd:.2f}",
        )

    # All within budget
    remaining = config.total_project_usd - costs.total_cost_usd
    return BudgetCheck(
        within_budget=True,
        remaining=remaining,
        message=f"Within budget. Remaining: ${remaining:.2f}",
    )


def check_budget_or_raise(costs: CostTracker, config: CostsConfig) -> None:
    """
    Check budget and raise exception if exceeded.

    Args:
        costs: CostTracker object.
        config: CostsConfig with budget limits.

    Raises:
        BudgetExceededError: If any budget is exceeded.
    """
    result = check_budget(costs, config)
    if not result.within_budget:
        raise BudgetExceededError(
            budget_type=result.budget_type or "unknown",
            limit=result.limit,
            current=result.current,
        )


def get_session_summary(costs: CostTracker) -> dict:
    """
    Get a summary of the current session costs.

    Args:
        costs: CostTracker object.

    Returns:
        Dictionary with session cost summary.
    """
    if costs.current_session is None:
        return {
            "active": False,
            "tokens_input": 0,
            "tokens_output": 0,
            "tokens_cached": 0,
            "cost_usd": 0.0,
        }

    return {
        "active": True,
        "session_id": costs.current_session.session_id,
        "feature_id": costs.current_session.feature_id,
        "tokens_input": costs.current_session.tokens_input,
        "tokens_output": costs.current_session.tokens_output,
        "tokens_cached": costs.current_session.tokens_cached,
        "cost_usd": costs.current_session.cost_usd,
        "model": costs.current_session.model,
    }


def get_project_summary(costs: CostTracker) -> dict:
    """
    Get a summary of total project costs.

    Args:
        costs: CostTracker object.

    Returns:
        Dictionary with project cost summary.
    """
    return {
        "total_sessions": costs.total_sessions,
        "total_cost_usd": costs.total_cost_usd,
        "total_tokens_input": costs.total_tokens_input,
        "total_tokens_output": costs.total_tokens_output,
        "total_tokens_cached": costs.total_tokens_cached,
        "features_with_costs": len(costs.by_feature),
        "average_session_cost": costs.total_cost_usd / costs.total_sessions if costs.total_sessions > 0 else 0.0,
    }


def get_feature_cost(costs: CostTracker, feature_id: int) -> float:
    """
    Get the total cost for a specific feature.

    Args:
        costs: CostTracker object.
        feature_id: Feature ID to look up.

    Returns:
        Total cost in USD for the feature.
    """
    return costs.by_feature.get(feature_id, 0.0)
