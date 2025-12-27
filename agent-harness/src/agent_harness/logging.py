"""Event logging for agent-harness.

Logs events to structured JSONL files in .harness/logs/.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Iterator


class LogLevel(Enum):
    """Log levels in order of importance."""
    DEBUG = "debug"
    ROUTINE = "routine"
    IMPORTANT = "important"
    CRITICAL = "critical"


LOG_LEVEL_ORDER = {
    LogLevel.DEBUG: 0,
    LogLevel.ROUTINE: 1,
    LogLevel.IMPORTANT: 2,
    LogLevel.CRITICAL: 3,
}


@dataclass
class LogEvent:
    """A logged event."""

    timestamp: str
    event_type: str
    level: str
    session_id: Optional[int]
    data: dict

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "level": self.level,
            "session_id": self.session_id,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LogEvent":
        """Create from dictionary."""
        return cls(
            timestamp=data.get("timestamp", ""),
            event_type=data.get("event_type", ""),
            level=data.get("level", "routine"),
            session_id=data.get("session_id"),
            data=data.get("data", {}),
        )


class EventLogger:
    """Logger for harness events."""

    def __init__(self, logs_dir: Path, session_id: Optional[int] = None):
        """
        Initialize the event logger.

        Args:
            logs_dir: Path to .harness/logs/ directory.
            session_id: Current session ID (optional).
        """
        self.logs_dir = logs_dir
        self.session_id = session_id
        self._ensure_logs_dir()

    def _ensure_logs_dir(self) -> None:
        """Ensure logs directory exists."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self, log_type: str) -> Path:
        """Get the path to a log file."""
        return self.logs_dir / f"{log_type}.jsonl"

    def _write_event(self, log_type: str, event: LogEvent) -> None:
        """Write an event to a log file."""
        log_file = self._get_log_file(log_type)
        with open(log_file, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def _create_event(
        self,
        event_type: str,
        data: dict,
        level: LogLevel = LogLevel.ROUTINE,
    ) -> LogEvent:
        """Create a log event."""
        return LogEvent(
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            event_type=event_type,
            level=level.value,
            session_id=self.session_id,
            data=data,
        )

    def set_session(self, session_id: int) -> None:
        """Set the current session ID."""
        self.session_id = session_id

    def log_event(
        self,
        event_type: str,
        data: dict,
        level: LogLevel = LogLevel.ROUTINE,
    ) -> None:
        """
        Log a generic event.

        Args:
            event_type: Type of event.
            data: Event data.
            level: Log level.
        """
        event = self._create_event(event_type, data, level)
        self._write_event("events", event)

    def log_decision(
        self,
        decision: str,
        context: Optional[dict] = None,
        level: LogLevel = LogLevel.IMPORTANT,
    ) -> None:
        """
        Log a decision made by the harness or agent.

        Args:
            decision: Description of the decision.
            context: Additional context.
            level: Log level.
        """
        data = {
            "decision": decision,
            "context": context or {},
        }
        event = self._create_event("decision", data, level)
        self._write_event("decisions", event)
        self._write_event("events", event)

    def log_agent_action(
        self,
        action_type: str,
        data: dict,
        level: LogLevel = LogLevel.ROUTINE,
    ) -> None:
        """
        Log an agent action.

        Args:
            action_type: Type of action (file_read, file_write, cmd_run, etc.).
            data: Action data.
            level: Log level.
        """
        action_data = {
            "action_type": action_type,
            **data,
        }
        event = self._create_event("agent_action", action_data, level)
        self._write_event("agent_actions", event)
        self._write_event("events", event)

    def log_error(
        self,
        error: str,
        details: Optional[dict] = None,
        level: LogLevel = LogLevel.CRITICAL,
    ) -> None:
        """
        Log an error.

        Args:
            error: Error message.
            details: Additional details.
            level: Log level.
        """
        data = {
            "error": error,
            "details": details or {},
        }
        event = self._create_event("error", data, level)
        self._write_event("errors", event)
        self._write_event("events", event)

    def log_verification(
        self,
        feature_id: int,
        passed: bool,
        details: Optional[dict] = None,
        level: LogLevel = LogLevel.IMPORTANT,
    ) -> None:
        """
        Log a verification result.

        Args:
            feature_id: ID of the feature verified.
            passed: Whether verification passed.
            details: Additional details.
            level: Log level.
        """
        data = {
            "feature_id": feature_id,
            "passed": passed,
            "details": details or {},
        }
        event = self._create_event("verification", data, level)
        self._write_event("verifications", event)
        self._write_event("events", event)

    def log_session_start(
        self,
        feature_id: Optional[int] = None,
        prompt_type: str = "coding",
    ) -> None:
        """
        Log session start.

        Args:
            feature_id: Feature being worked on.
            prompt_type: Type of prompt being used.
        """
        data = {
            "feature_id": feature_id,
            "prompt_type": prompt_type,
        }
        self.log_event("session_start", data, LogLevel.IMPORTANT)

    def log_session_end(
        self,
        status: str,
        duration_seconds: float,
        tokens_used: int,
        cost_usd: float,
        features_completed: Optional[list[int]] = None,
    ) -> None:
        """
        Log session end.

        Args:
            status: Session end status.
            duration_seconds: Session duration.
            tokens_used: Total tokens used.
            cost_usd: Total cost.
            features_completed: Features completed this session.
        """
        data = {
            "status": status,
            "duration_seconds": duration_seconds,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
            "features_completed": features_completed or [],
        }
        self.log_event("session_end", data, LogLevel.IMPORTANT)


def read_log_file(
    log_file: Path,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list[LogEvent]:
    """
    Read events from a log file.

    Args:
        log_file: Path to the log file.
        limit: Maximum events to return.
        offset: Number of events to skip.

    Returns:
        List of LogEvent objects.
    """
    if not log_file.exists():
        return []

    events = []
    with open(log_file) as f:
        for i, line in enumerate(f):
            if i < offset:
                continue
            if limit and len(events) >= limit:
                break

            line = line.strip()
            if line:
                try:
                    data = json.loads(line)
                    events.append(LogEvent.from_dict(data))
                except json.JSONDecodeError:
                    continue

    return events


def query_logs(
    logs_dir: Path,
    log_type: str = "events",
    query: Optional[str] = None,
    session_id: Optional[int] = None,
    min_level: LogLevel = LogLevel.ROUTINE,
    limit: int = 100,
    reverse: bool = True,
) -> list[LogEvent]:
    """
    Query logs with filters.

    Args:
        logs_dir: Path to logs directory.
        log_type: Type of log to query ("events", "decisions", "errors", etc.).
        query: Text query to filter by.
        session_id: Filter by session ID.
        min_level: Minimum log level.
        limit: Maximum events to return.
        reverse: Return newest first.

    Returns:
        List of matching LogEvent objects.
    """
    log_file = logs_dir / f"{log_type}.jsonl"
    if not log_file.exists():
        return []

    # Read all events
    events = read_log_file(log_file)

    # Filter by level
    min_level_order = LOG_LEVEL_ORDER.get(min_level, 1)
    filtered = []
    for event in events:
        event_level = LogLevel(event.level) if event.level in [l.value for l in LogLevel] else LogLevel.ROUTINE
        if LOG_LEVEL_ORDER.get(event_level, 1) >= min_level_order:
            filtered.append(event)

    events = filtered

    # Filter by session
    if session_id is not None:
        events = [e for e in events if e.session_id == session_id]

    # Filter by query
    if query:
        query_lower = query.lower()
        filtered = []
        for event in events:
            # Search in event type and data
            if query_lower in event.event_type.lower():
                filtered.append(event)
                continue
            if query_lower in json.dumps(event.data).lower():
                filtered.append(event)
                continue
        events = filtered

    # Reverse if needed (newest first)
    if reverse:
        events = list(reversed(events))

    # Apply limit
    return events[:limit]


def get_recent_events(
    logs_dir: Path,
    n: int = 20,
    min_level: LogLevel = LogLevel.ROUTINE,
) -> list[LogEvent]:
    """
    Get the most recent events.

    Args:
        logs_dir: Path to logs directory.
        n: Number of events to return.
        min_level: Minimum log level.

    Returns:
        List of recent LogEvent objects, newest first.
    """
    return query_logs(logs_dir, "events", min_level=min_level, limit=n)


def get_session_events(
    logs_dir: Path,
    session_id: int,
    log_type: str = "events",
) -> list[LogEvent]:
    """
    Get all events for a specific session.

    Args:
        logs_dir: Path to logs directory.
        session_id: Session ID to filter by.
        log_type: Type of log to query.

    Returns:
        List of LogEvent objects for the session.
    """
    return query_logs(logs_dir, log_type, session_id=session_id, limit=10000)


def get_last_session_id(logs_dir: Path) -> Optional[int]:
    """
    Get the session ID of the most recent session.

    Args:
        logs_dir: Path to logs directory.

    Returns:
        Last session ID, or None if no sessions.
    """
    events = query_logs(logs_dir, "events", limit=100)
    for event in events:
        if event.session_id is not None:
            return event.session_id
    return None


def format_log_event(event: LogEvent) -> str:
    """
    Format a log event for display.

    Args:
        event: LogEvent to format.

    Returns:
        Formatted string.
    """
    timestamp = event.timestamp[:19].replace("T", " ")  # Truncate to seconds
    session_str = f"[S{event.session_id}]" if event.session_id else "[---]"
    level_str = event.level.upper()[:4]

    # Format data based on event type
    if event.event_type == "decision":
        data_str = event.data.get("decision", str(event.data))
    elif event.event_type == "error":
        data_str = event.data.get("error", str(event.data))
    elif event.event_type == "agent_action":
        action_type = event.data.get("action_type", "unknown")
        data_str = f"{action_type}: {event.data.get('path', event.data.get('command', ''))}"
    else:
        data_str = str(event.data)[:100]

    return f"{timestamp} {session_str} {level_str} {event.event_type}: {data_str}"


def cleanup_old_logs(
    logs_dir: Path,
    max_age_days: int = 30,
    max_size_mb: float = 100,
) -> int:
    """
    Clean up old log files.

    Args:
        logs_dir: Path to logs directory.
        max_age_days: Maximum age in days.
        max_size_mb: Maximum total size in MB.

    Returns:
        Number of lines removed.
    """
    # For now, just truncate if too large
    lines_removed = 0

    for log_file in logs_dir.glob("*.jsonl"):
        size_mb = log_file.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb / 4:  # Per-file limit is 1/4 of total
            # Read all events
            events = read_log_file(log_file)
            if len(events) > 1000:
                # Keep only the last 1000 events
                lines_removed += len(events) - 1000
                events = events[-1000:]

                # Rewrite file
                with open(log_file, "w") as f:
                    for event in events:
                        f.write(json.dumps(event.to_dict()) + "\n")

    return lines_removed
