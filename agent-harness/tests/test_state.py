"""Tests for session state management."""

import json
import pytest
from pathlib import Path

from agent_harness.state import (
    SessionState,
    SCHEMA_VERSION,
    load_session_state,
    save_session_state,
    initialize_session_state,
    start_new_session,
    end_session,
    increment_stuck_count,
    reset_stuck_count,
    set_paused,
    clear_paused,
    is_paused,
    needs_continuation,
    should_trigger_cleanup,
    get_schema_version,
)
from agent_harness.exceptions import StateError
from agent_harness.version import __version__


class TestSessionStateDataclass:
    """Test SessionState dataclass."""

    def test_default_state(self):
        """Default state should have sensible defaults."""
        state = SessionState()
        assert state.harness_version == __version__
        assert state.schema_version == SCHEMA_VERSION
        assert state.last_session == 0
        assert state.status == "complete"
        assert state.next_prompt == "coding"
        assert state.stuck_count == 0

    def test_invalid_status(self):
        """Invalid status should raise error."""
        with pytest.raises(StateError):
            SessionState(status="invalid")

    def test_invalid_next_prompt(self):
        """Invalid next_prompt should raise error."""
        with pytest.raises(StateError):
            SessionState(next_prompt="invalid")

    def test_valid_statuses(self):
        """All valid statuses should work."""
        for status in ["complete", "partial", "failed", "paused", "init"]:
            state = SessionState(status=status)
            assert state.status == status

    def test_valid_prompts(self):
        """All valid prompts should work."""
        for prompt in ["coding", "continuation", "cleanup", "init"]:
            state = SessionState(next_prompt=prompt)
            assert state.next_prompt == prompt


class TestLoadSaveState:
    """Test loading and saving state."""

    def test_initialize_creates_file(self, temp_project_dir):
        """Initialize should create state file."""
        state_dir = temp_project_dir / ".harness"
        state = initialize_session_state(state_dir)

        assert state.status == "init"
        assert state.next_prompt == "init"
        assert (state_dir / "session_state.json").exists()

    def test_load_existing_state(self, temp_project_dir):
        """Load should read existing state."""
        state_dir = temp_project_dir / ".harness"
        state_dir.mkdir()

        state_data = {
            "harness_version": "1.0.0",
            "schema_version": 1,
            "last_session": 5,
            "status": "complete",
            "current_feature": 10,
            "next_prompt": "coding",
            "stuck_count": 2,
            "timestamp": "2025-01-01T00:00:00Z",
            "timeout_count": 1,
            "total_sessions": 5,
        }
        (state_dir / "session_state.json").write_text(json.dumps(state_data))

        state = load_session_state(state_dir)
        assert state.last_session == 5
        assert state.current_feature == 10
        assert state.stuck_count == 2

    def test_load_missing_creates_new(self, temp_project_dir):
        """Load should create new state if file missing."""
        state_dir = temp_project_dir / ".harness"
        state = load_session_state(state_dir)

        assert state.status == "init"
        assert (state_dir / "session_state.json").exists()

    def test_save_and_reload(self, temp_project_dir):
        """Saved state should be reloadable."""
        state_dir = temp_project_dir / ".harness"
        state_dir.mkdir()

        state = SessionState(
            last_session=10,
            status="partial",
            current_feature=5,
            stuck_count=1,
        )
        save_session_state(state_dir, state)

        loaded = load_session_state(state_dir)
        assert loaded.last_session == 10
        assert loaded.status == "partial"
        assert loaded.current_feature == 5
        assert loaded.stuck_count == 1


class TestSessionLifecycle:
    """Test session lifecycle functions."""

    def test_start_new_session(self):
        """Start new session should increment counters."""
        state = SessionState(last_session=5, total_sessions=10)
        state = start_new_session(state, feature_id=15)

        assert state.last_session == 6
        assert state.total_sessions == 11
        assert state.current_feature == 15
        assert state.status == "partial"
        assert state.features_completed_this_session == []

    def test_end_session_complete(self):
        """End session complete should update state."""
        state = SessionState(
            last_session=5,
            status="partial",
            current_feature=10,
            stuck_count=2,
        )
        state = end_session(
            state,
            status="complete",
            features_completed=[10],
        )

        assert state.status == "complete"
        assert state.next_prompt == "coding"
        assert state.stuck_count == 0
        assert state.features_completed_this_session == [10]
        assert state.current_feature is None

    def test_end_session_partial(self):
        """End session partial should set continuation."""
        state = SessionState(last_session=5, current_feature=10)
        state = end_session(
            state,
            status="partial",
            termination_reason="Context limit",
        )

        assert state.status == "partial"
        assert state.next_prompt == "continuation"
        assert state.termination_reason == "Context limit"

    def test_end_session_failed(self):
        """End session failed should increment stuck count."""
        state = SessionState(stuck_count=0)
        state = end_session(state, status="failed")

        assert state.status == "failed"
        assert state.stuck_count == 1
        assert state.next_prompt == "coding"


class TestStuckTracking:
    """Test stuck count tracking."""

    def test_increment_stuck_count(self):
        """Increment should increase stuck count."""
        state = SessionState(stuck_count=1)
        state = increment_stuck_count(state)
        assert state.stuck_count == 2

    def test_reset_stuck_count(self):
        """Reset should clear stuck count."""
        state = SessionState(stuck_count=5)
        state = reset_stuck_count(state)
        assert state.stuck_count == 0


class TestPauseResume:
    """Test pause and resume functionality."""

    def test_set_paused(self):
        """Set paused should update status."""
        state = SessionState(status="complete")
        state = set_paused(state, reason="Manual pause")

        assert state.status == "paused"
        assert state.termination_reason == "Manual pause"
        assert is_paused(state) is True

    def test_clear_paused(self):
        """Clear paused should reset to complete."""
        state = SessionState(status="paused")
        state = clear_paused(state)

        assert state.status == "complete"
        assert state.termination_reason is None
        assert is_paused(state) is False

    def test_clear_paused_noop_if_not_paused(self):
        """Clear paused should be noop if not paused."""
        state = SessionState(status="partial")
        state = clear_paused(state)
        assert state.status == "partial"


class TestStateQueries:
    """Test state query functions."""

    def test_needs_continuation(self):
        """Needs continuation should check partial status."""
        state = SessionState(status="partial", next_prompt="continuation")
        assert needs_continuation(state) is True

        state = SessionState(status="complete", next_prompt="coding")
        assert needs_continuation(state) is False

    def test_should_trigger_cleanup(self):
        """Should trigger cleanup at intervals."""
        state = SessionState(total_sessions=10)
        assert should_trigger_cleanup(state, cleanup_interval=5) is True

        state = SessionState(total_sessions=7)
        assert should_trigger_cleanup(state, cleanup_interval=5) is False

        state = SessionState(total_sessions=0)
        assert should_trigger_cleanup(state, cleanup_interval=5) is False


class TestSchemaVersion:
    """Test schema version handling."""

    def test_get_schema_version_exists(self, temp_project_dir):
        """Get schema version from existing file."""
        state_dir = temp_project_dir / ".harness"
        state_dir.mkdir()

        state_data = {"schema_version": 2}
        (state_dir / "session_state.json").write_text(json.dumps(state_data))

        version = get_schema_version(state_dir)
        assert version == 2

    def test_get_schema_version_missing(self, temp_project_dir):
        """Get schema version returns None for missing file."""
        state_dir = temp_project_dir / ".harness"
        version = get_schema_version(state_dir)
        assert version is None
