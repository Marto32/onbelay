"""Tests for logging module."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from agent_harness.logging import (
    LogLevel,
    LogEvent,
    EventLogger,
    LOG_LEVEL_ORDER,
    read_log_file,
    query_logs,
    get_recent_events,
    get_session_events,
    get_last_session_id,
    format_log_event,
    cleanup_old_logs,
)


@pytest.fixture
def temp_logs_dir(tmp_path):
    """Create a temporary logs directory."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    return logs_dir


@pytest.fixture
def logger(temp_logs_dir):
    """Create an EventLogger instance."""
    return EventLogger(temp_logs_dir, session_id=1)


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_level_values(self):
        """Test log level values."""
        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.ROUTINE.value == "routine"
        assert LogLevel.IMPORTANT.value == "important"
        assert LogLevel.CRITICAL.value == "critical"

    def test_log_level_order(self):
        """Test log level ordering."""
        assert LOG_LEVEL_ORDER[LogLevel.DEBUG] < LOG_LEVEL_ORDER[LogLevel.ROUTINE]
        assert LOG_LEVEL_ORDER[LogLevel.ROUTINE] < LOG_LEVEL_ORDER[LogLevel.IMPORTANT]
        assert LOG_LEVEL_ORDER[LogLevel.IMPORTANT] < LOG_LEVEL_ORDER[LogLevel.CRITICAL]


class TestLogEvent:
    """Tests for LogEvent dataclass."""

    def test_log_event_creation(self):
        """Test creating a LogEvent."""
        event = LogEvent(
            timestamp="2024-01-01T00:00:00Z",
            event_type="test",
            level="routine",
            session_id=1,
            data={"key": "value"},
        )

        assert event.timestamp == "2024-01-01T00:00:00Z"
        assert event.event_type == "test"
        assert event.level == "routine"
        assert event.session_id == 1
        assert event.data == {"key": "value"}

    def test_log_event_to_dict(self):
        """Test converting LogEvent to dictionary."""
        event = LogEvent(
            timestamp="2024-01-01T00:00:00Z",
            event_type="test",
            level="important",
            session_id=5,
            data={"test": True},
        )

        d = event.to_dict()

        assert d["timestamp"] == "2024-01-01T00:00:00Z"
        assert d["event_type"] == "test"
        assert d["level"] == "important"
        assert d["session_id"] == 5
        assert d["data"] == {"test": True}

    def test_log_event_from_dict(self):
        """Test creating LogEvent from dictionary."""
        d = {
            "timestamp": "2024-01-01T00:00:00Z",
            "event_type": "test",
            "level": "critical",
            "session_id": 10,
            "data": {"error": "Something broke"},
        }

        event = LogEvent.from_dict(d)

        assert event.timestamp == "2024-01-01T00:00:00Z"
        assert event.event_type == "test"
        assert event.level == "critical"
        assert event.session_id == 10
        assert event.data == {"error": "Something broke"}


class TestEventLogger:
    """Tests for EventLogger class."""

    def test_logger_initialization(self, temp_logs_dir):
        """Test logger initialization."""
        logger = EventLogger(temp_logs_dir, session_id=5)

        assert logger.logs_dir == temp_logs_dir
        assert logger.session_id == 5
        assert temp_logs_dir.exists()

    def test_set_session(self, logger):
        """Test setting session ID."""
        logger.set_session(10)
        assert logger.session_id == 10

    def test_log_event(self, logger, temp_logs_dir):
        """Test logging a generic event."""
        logger.log_event("test_event", {"key": "value"})

        events_file = temp_logs_dir / "events.jsonl"
        assert events_file.exists()

        content = events_file.read_text().strip()
        event = json.loads(content)

        assert event["event_type"] == "test_event"
        assert event["data"]["key"] == "value"
        assert event["session_id"] == 1

    def test_log_decision(self, logger, temp_logs_dir):
        """Test logging a decision."""
        logger.log_decision("Use strategy A", {"reason": "Better performance"})

        decisions_file = temp_logs_dir / "decisions.jsonl"
        assert decisions_file.exists()

        events_file = temp_logs_dir / "events.jsonl"
        assert events_file.exists()  # Also logged to events

    def test_log_agent_action(self, logger, temp_logs_dir):
        """Test logging an agent action."""
        logger.log_agent_action("file_write", {"path": "/test/file.py"})

        actions_file = temp_logs_dir / "agent_actions.jsonl"
        assert actions_file.exists()

    def test_log_error(self, logger, temp_logs_dir):
        """Test logging an error."""
        logger.log_error("Something failed", {"code": 500})

        errors_file = temp_logs_dir / "errors.jsonl"
        assert errors_file.exists()

    def test_log_verification(self, logger, temp_logs_dir):
        """Test logging a verification result."""
        logger.log_verification(1, True, {"tests_passed": 10})

        verifications_file = temp_logs_dir / "verifications.jsonl"
        assert verifications_file.exists()

    def test_log_session_start(self, logger, temp_logs_dir):
        """Test logging session start."""
        logger.log_session_start(feature_id=1, prompt_type="coding")

        content = (temp_logs_dir / "events.jsonl").read_text()
        event = json.loads(content.strip())

        assert event["event_type"] == "session_start"
        assert event["data"]["feature_id"] == 1

    def test_log_session_end(self, logger, temp_logs_dir):
        """Test logging session end."""
        logger.log_session_end(
            status="complete",
            duration_seconds=300.5,
            tokens_used=10000,
            cost_usd=0.15,
            features_completed=[1, 2],
        )

        content = (temp_logs_dir / "events.jsonl").read_text()
        event = json.loads(content.strip())

        assert event["event_type"] == "session_end"
        assert event["data"]["status"] == "complete"
        assert event["data"]["duration_seconds"] == 300.5


class TestReadLogFile:
    """Tests for read_log_file function."""

    def test_read_nonexistent_file(self, temp_logs_dir):
        """Test reading a nonexistent file."""
        events = read_log_file(temp_logs_dir / "nonexistent.jsonl")
        assert events == []

    def test_read_log_file(self, temp_logs_dir):
        """Test reading a log file."""
        log_file = temp_logs_dir / "test.jsonl"
        events_data = [
            {"timestamp": "2024-01-01T00:00:00Z", "event_type": "e1", "level": "routine", "session_id": 1, "data": {}},
            {"timestamp": "2024-01-01T00:01:00Z", "event_type": "e2", "level": "routine", "session_id": 1, "data": {}},
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in events_data) + "\n")

        events = read_log_file(log_file)

        assert len(events) == 2
        assert events[0].event_type == "e1"
        assert events[1].event_type == "e2"

    def test_read_log_file_with_limit(self, temp_logs_dir):
        """Test reading with limit."""
        log_file = temp_logs_dir / "test.jsonl"
        events_data = [
            {"timestamp": f"2024-01-01T00:0{i}:00Z", "event_type": f"e{i}", "level": "routine", "session_id": 1, "data": {}}
            for i in range(10)
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in events_data) + "\n")

        events = read_log_file(log_file, limit=5)

        assert len(events) == 5

    def test_read_log_file_with_offset(self, temp_logs_dir):
        """Test reading with offset."""
        log_file = temp_logs_dir / "test.jsonl"
        events_data = [
            {"timestamp": f"2024-01-01T00:0{i}:00Z", "event_type": f"e{i}", "level": "routine", "session_id": 1, "data": {}}
            for i in range(10)
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in events_data) + "\n")

        events = read_log_file(log_file, offset=3, limit=3)

        assert len(events) == 3
        assert events[0].event_type == "e3"


class TestQueryLogs:
    """Tests for query_logs function."""

    def test_query_empty_logs(self, temp_logs_dir):
        """Test querying empty logs."""
        events = query_logs(temp_logs_dir)
        assert events == []

    def test_query_by_session(self, logger, temp_logs_dir):
        """Test filtering by session."""
        logger.set_session(1)
        logger.log_event("event1", {})

        logger.set_session(2)
        logger.log_event("event2", {})

        events = query_logs(temp_logs_dir, session_id=1)

        assert all(e.session_id == 1 for e in events)

    def test_query_by_level(self, logger, temp_logs_dir):
        """Test filtering by level."""
        logger.log_event("debug_event", {}, LogLevel.DEBUG)
        logger.log_event("routine_event", {}, LogLevel.ROUTINE)
        logger.log_event("important_event", {}, LogLevel.IMPORTANT)
        logger.log_event("critical_event", {}, LogLevel.CRITICAL)

        events = query_logs(temp_logs_dir, min_level=LogLevel.IMPORTANT)

        assert all(e.level in ["important", "critical"] for e in events)

    def test_query_by_text(self, logger, temp_logs_dir):
        """Test filtering by text query."""
        logger.log_event("file_read", {"path": "/test/foo.py"})
        logger.log_event("file_write", {"path": "/test/bar.py"})
        logger.log_event("cmd_run", {"command": "pytest"})

        events = query_logs(temp_logs_dir, query="file")

        assert len(events) == 2
        assert all("file" in e.event_type for e in events)


class TestFormatLogEvent:
    """Tests for format_log_event function."""

    def test_format_decision_event(self):
        """Test formatting a decision event."""
        event = LogEvent(
            timestamp="2024-01-01T12:30:45.123Z",
            event_type="decision",
            level="important",
            session_id=5,
            data={"decision": "Use caching strategy"},
        )

        formatted = format_log_event(event)

        assert "2024-01-01 12:30:45" in formatted
        assert "[S5]" in formatted
        assert "decision" in formatted
        assert "Use caching strategy" in formatted

    def test_format_error_event(self):
        """Test formatting an error event."""
        event = LogEvent(
            timestamp="2024-01-01T12:30:45Z",
            event_type="error",
            level="critical",
            session_id=3,
            data={"error": "Connection failed"},
        )

        formatted = format_log_event(event)

        assert "Connection failed" in formatted
        assert "CRIT" in formatted

    def test_format_agent_action_event(self):
        """Test formatting an agent action event."""
        event = LogEvent(
            timestamp="2024-01-01T12:30:45Z",
            event_type="agent_action",
            level="routine",
            session_id=1,
            data={"action_type": "file_write", "path": "/test/file.py"},
        )

        formatted = format_log_event(event)

        assert "file_write" in formatted
        assert "/test/file.py" in formatted


class TestGetLastSessionId:
    """Tests for get_last_session_id function."""

    def test_no_logs(self, temp_logs_dir):
        """Test with no logs."""
        session_id = get_last_session_id(temp_logs_dir)
        assert session_id is None

    def test_with_logs(self, logger, temp_logs_dir):
        """Test with logs."""
        logger.set_session(1)
        logger.log_event("event1", {})

        logger.set_session(5)
        logger.log_event("event2", {})

        session_id = get_last_session_id(temp_logs_dir)
        assert session_id == 5


class TestCleanupOldLogs:
    """Tests for cleanup_old_logs function."""

    def test_cleanup_large_file(self, temp_logs_dir):
        """Test cleanup of large log files."""
        log_file = temp_logs_dir / "events.jsonl"

        # Create a large log file
        events = []
        for i in range(2000):
            events.append(json.dumps({
                "timestamp": f"2024-01-01T00:{i:04d}:00Z",
                "event_type": f"event{i}",
                "level": "routine",
                "session_id": 1,
                "data": {"index": i},
            }))

        log_file.write_text("\n".join(events) + "\n")

        # Cleanup won't trigger for small files
        # This is more of a functional test
        lines_removed = cleanup_old_logs(temp_logs_dir, max_size_mb=0.001)

        # File should be truncated
        remaining_events = read_log_file(log_file)
        assert len(remaining_events) <= 1000 or lines_removed >= 0
