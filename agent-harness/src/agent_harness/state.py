"""Session state management for agent-harness."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_harness.exceptions import StateError
from agent_harness.version import __version__


# Current schema version - increment when making breaking changes
SCHEMA_VERSION = 1


@dataclass
class SessionState:
    """Session state tracking between runs."""

    harness_version: str = __version__
    schema_version: int = SCHEMA_VERSION
    last_session: int = 0
    status: str = "complete"  # "complete", "partial", "failed", "paused"
    current_feature: Optional[int] = None
    termination_reason: Optional[str] = None
    next_prompt: str = "coding"  # "coding", "continuation", "cleanup", "init"
    stuck_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    timeout_count: int = 0

    # Additional tracking
    total_sessions: int = 0
    features_completed_this_session: list[int] = field(default_factory=list)
    last_checkpoint_id: Optional[str] = None

    def __post_init__(self):
        """Validate state fields."""
        valid_statuses = {"complete", "partial", "failed", "paused", "init"}
        if self.status not in valid_statuses:
            raise StateError(f"Invalid status: {self.status}. Must be one of: {valid_statuses}")

        valid_prompts = {"coding", "continuation", "cleanup", "init"}
        if self.next_prompt not in valid_prompts:
            raise StateError(f"Invalid next_prompt: {self.next_prompt}. Must be one of: {valid_prompts}")


def _state_to_dict(state: SessionState) -> dict:
    """Convert SessionState to dictionary for serialization."""
    return {
        "harness_version": state.harness_version,
        "schema_version": state.schema_version,
        "last_session": state.last_session,
        "status": state.status,
        "current_feature": state.current_feature,
        "termination_reason": state.termination_reason,
        "next_prompt": state.next_prompt,
        "stuck_count": state.stuck_count,
        "timestamp": state.timestamp,
        "timeout_count": state.timeout_count,
        "total_sessions": state.total_sessions,
        "features_completed_this_session": state.features_completed_this_session,
        "last_checkpoint_id": state.last_checkpoint_id,
    }


def _dict_to_state(data: dict) -> SessionState:
    """Convert dictionary to SessionState."""
    return SessionState(
        harness_version=data.get("harness_version", __version__),
        schema_version=data.get("schema_version", SCHEMA_VERSION),
        last_session=data.get("last_session", 0),
        status=data.get("status", "complete"),
        current_feature=data.get("current_feature"),
        termination_reason=data.get("termination_reason"),
        next_prompt=data.get("next_prompt", "coding"),
        stuck_count=data.get("stuck_count", 0),
        timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
        timeout_count=data.get("timeout_count", 0),
        total_sessions=data.get("total_sessions", 0),
        features_completed_this_session=data.get("features_completed_this_session", []),
        last_checkpoint_id=data.get("last_checkpoint_id"),
    )


def load_session_state(state_dir: Path) -> SessionState:
    """
    Load session state from state directory.

    Args:
        state_dir: Path to .harness/ directory.

    Returns:
        SessionState object.

    Raises:
        StateError: If state file is invalid.
    """
    state_file = state_dir / "session_state.json"

    if not state_file.exists():
        # Return fresh state if file doesn't exist
        return initialize_session_state(state_dir)

    try:
        with open(state_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise StateError(f"Invalid JSON in session state: {e}")

    return _dict_to_state(data)


def save_session_state(state_dir: Path, state: SessionState) -> None:
    """
    Save session state to state directory.

    Args:
        state_dir: Path to .harness/ directory.
        state: SessionState object to save.
    """
    # Update timestamp
    state.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Ensure directory exists
    state_dir.mkdir(parents=True, exist_ok=True)

    state_file = state_dir / "session_state.json"
    with open(state_file, "w") as f:
        json.dump(_state_to_dict(state), f, indent=2)


def initialize_session_state(state_dir: Path) -> SessionState:
    """
    Initialize a fresh session state.

    Args:
        state_dir: Path to .harness/ directory.

    Returns:
        Fresh SessionState object.
    """
    state = SessionState(
        harness_version=__version__,
        schema_version=SCHEMA_VERSION,
        last_session=0,
        status="init",
        next_prompt="init",
    )

    # Save to disk
    save_session_state(state_dir, state)

    return state


def start_new_session(state: SessionState, feature_id: Optional[int] = None) -> SessionState:
    """
    Start a new session, updating state accordingly.

    Args:
        state: Current SessionState.
        feature_id: Feature to work on (optional).

    Returns:
        Updated SessionState.
    """
    state.last_session += 1
    state.total_sessions += 1
    state.current_feature = feature_id
    state.status = "partial"
    state.features_completed_this_session = []
    state.termination_reason = None
    state.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return state


def end_session(
    state: SessionState,
    status: str,
    termination_reason: Optional[str] = None,
    features_completed: Optional[list[int]] = None,
) -> SessionState:
    """
    End the current session, updating state accordingly.

    Args:
        state: Current SessionState.
        status: Final status ("complete", "partial", "failed").
        termination_reason: Why session ended (optional).
        features_completed: Features completed this session (optional).

    Returns:
        Updated SessionState.
    """
    state.status = status
    state.termination_reason = termination_reason
    state.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if features_completed:
        state.features_completed_this_session = features_completed

    # Update next_prompt based on status
    if status == "complete":
        state.next_prompt = "coding"
        state.stuck_count = 0
    elif status == "partial":
        state.next_prompt = "continuation"
    elif status == "failed":
        state.stuck_count += 1
        state.next_prompt = "coding"

    # Clear current feature if completed
    if status == "complete" and state.current_feature in (state.features_completed_this_session or []):
        state.current_feature = None

    return state


def increment_stuck_count(state: SessionState) -> SessionState:
    """
    Increment the stuck count when agent makes no progress.

    Args:
        state: Current SessionState.

    Returns:
        Updated SessionState.
    """
    state.stuck_count += 1
    return state


def reset_stuck_count(state: SessionState) -> SessionState:
    """
    Reset the stuck count when progress is made.

    Args:
        state: Current SessionState.

    Returns:
        Updated SessionState.
    """
    state.stuck_count = 0
    return state


def set_paused(state: SessionState, reason: Optional[str] = None) -> SessionState:
    """
    Set the harness to paused state.

    Args:
        state: Current SessionState.
        reason: Reason for pausing (optional).

    Returns:
        Updated SessionState.
    """
    state.status = "paused"
    state.termination_reason = reason or "Manual pause"
    state.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return state


def clear_paused(state: SessionState) -> SessionState:
    """
    Clear the paused state, allowing sessions to resume.

    Args:
        state: Current SessionState.

    Returns:
        Updated SessionState.
    """
    if state.status == "paused":
        state.status = "complete"
        state.termination_reason = None
        state.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return state


def is_paused(state: SessionState) -> bool:
    """Check if harness is paused."""
    return state.status == "paused"


def needs_continuation(state: SessionState) -> bool:
    """Check if session needs continuation from previous partial work."""
    return state.status == "partial" and state.next_prompt == "continuation"


def should_trigger_cleanup(state: SessionState, cleanup_interval: int) -> bool:
    """
    Check if a cleanup session should be triggered.

    Args:
        state: Current SessionState.
        cleanup_interval: Number of sessions between cleanups.

    Returns:
        True if cleanup should be triggered.
    """
    return state.total_sessions > 0 and state.total_sessions % cleanup_interval == 0


def get_schema_version(state_dir: Path) -> Optional[int]:
    """
    Get the schema version from existing state file.

    Args:
        state_dir: Path to .harness/ directory.

    Returns:
        Schema version, or None if no state file exists.
    """
    state_file = state_dir / "session_state.json"

    if not state_file.exists():
        return None

    try:
        with open(state_file) as f:
            data = json.load(f)
            return data.get("schema_version")
    except (json.JSONDecodeError, KeyError):
        return None
