"""Progress monitoring for agent sessions.

Monitors agent progress and detects stuck patterns:
- No file changes over time
- No test activity
- Repeated errors
- Excessive token usage without progress
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class ProgressSnapshot:
    """Snapshot of progress at a point in time."""

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    tokens_used: int = 0
    files_modified: int = 0
    tests_run: int = 0
    tests_passed: int = 0
    tool_calls: int = 0
    features_completed: int = 0
    last_file_change: Optional[str] = None
    last_tool_call: Optional[str] = None
    error_count: int = 0


@dataclass
class ProgressCheck:
    """Result of a progress check."""

    making_progress: bool
    message: str
    force_stop: bool = False
    stuck_count: int = 0
    warning_level: str = "none"  # "none", "low", "medium", "high", "critical"


@dataclass
class StuckPattern:
    """Detected stuck pattern."""

    pattern_type: str  # "no_files", "no_tests", "repeated_errors", "no_progress"
    description: str
    severity: str = "medium"  # "low", "medium", "high"


class ProgressMonitor:
    """Monitors agent progress during a session."""

    def __init__(
        self,
        check_interval_tokens: int = 5000,
        stuck_threshold: int = 2,
        force_stop_threshold: int = 3,
    ):
        """Initialize the progress monitor.

        Args:
            check_interval_tokens: Tokens between progress checks.
            stuck_threshold: Number of stuck checks before warning.
            force_stop_threshold: Number of stuck checks before force stop.
        """
        self.check_interval_tokens = check_interval_tokens
        self.stuck_threshold = stuck_threshold
        self.force_stop_threshold = force_stop_threshold

        self.snapshots: list[ProgressSnapshot] = []
        self.stuck_count = 0
        self.last_check_tokens = 0

    def take_snapshot(
        self,
        tokens_used: int,
        files_modified: int = 0,
        tests_run: int = 0,
        tests_passed: int = 0,
        tool_calls: int = 0,
        features_completed: int = 0,
        last_file_change: Optional[str] = None,
        last_tool_call: Optional[str] = None,
        error_count: int = 0,
    ) -> ProgressSnapshot:
        """Take a progress snapshot.

        Args:
            tokens_used: Total tokens used so far.
            files_modified: Number of files modified.
            tests_run: Number of tests run.
            tests_passed: Number of tests passed.
            tool_calls: Number of tool calls made.
            features_completed: Number of features marked complete.
            last_file_change: Path of last file changed.
            last_tool_call: Name of last tool called.
            error_count: Number of errors encountered.

        Returns:
            The new snapshot.
        """
        snapshot = ProgressSnapshot(
            tokens_used=tokens_used,
            files_modified=files_modified,
            tests_run=tests_run,
            tests_passed=tests_passed,
            tool_calls=tool_calls,
            features_completed=features_completed,
            last_file_change=last_file_change,
            last_tool_call=last_tool_call,
            error_count=error_count,
        )
        self.snapshots.append(snapshot)
        return snapshot

    def should_check(self, current_tokens: int) -> bool:
        """Check if a progress check is due.

        Args:
            current_tokens: Current token count.

        Returns:
            True if check is due.
        """
        return current_tokens - self.last_check_tokens >= self.check_interval_tokens

    def check_progress(self, current_snapshot: ProgressSnapshot) -> ProgressCheck:
        """Check if the agent is making progress.

        Args:
            current_snapshot: Current progress snapshot.

        Returns:
            ProgressCheck with result.
        """
        self.last_check_tokens = current_snapshot.tokens_used

        # Need at least 2 snapshots to compare
        if len(self.snapshots) < 2:
            return ProgressCheck(
                making_progress=True,
                message="Initial check - monitoring started",
            )

        # Get previous snapshot for comparison
        prev_snapshot = self.snapshots[-2]
        current = self.snapshots[-1]

        # Detect stuck patterns
        patterns = self._detect_stuck_patterns(prev_snapshot, current)

        if patterns:
            self.stuck_count += 1

            # Build warning message
            pattern_descs = [p.description for p in patterns]
            message = f"Stuck detected ({self.stuck_count}x): {'; '.join(pattern_descs)}"

            # Determine warning level
            if self.stuck_count >= self.force_stop_threshold:
                return ProgressCheck(
                    making_progress=False,
                    message=message,
                    force_stop=True,
                    stuck_count=self.stuck_count,
                    warning_level="critical",
                )
            elif self.stuck_count >= self.stuck_threshold:
                return ProgressCheck(
                    making_progress=False,
                    message=message,
                    force_stop=False,
                    stuck_count=self.stuck_count,
                    warning_level="high",
                )
            else:
                return ProgressCheck(
                    making_progress=False,
                    message=message,
                    force_stop=False,
                    stuck_count=self.stuck_count,
                    warning_level="medium",
                )

        # Making progress - reset stuck count
        self.stuck_count = 0
        return ProgressCheck(
            making_progress=True,
            message="Making progress",
            stuck_count=0,
            warning_level="none",
        )

    def _detect_stuck_patterns(
        self,
        prev: ProgressSnapshot,
        current: ProgressSnapshot,
    ) -> list[StuckPattern]:
        """Detect stuck patterns between snapshots.

        Args:
            prev: Previous snapshot.
            current: Current snapshot.

        Returns:
            List of detected stuck patterns.
        """
        patterns = []

        # Check for no file changes
        if current.files_modified == prev.files_modified:
            patterns.append(
                StuckPattern(
                    pattern_type="no_files",
                    description="No file changes since last check",
                    severity="medium",
                )
            )

        # Check for no test activity
        if current.tests_run == prev.tests_run:
            patterns.append(
                StuckPattern(
                    pattern_type="no_tests",
                    description="No tests run since last check",
                    severity="low",
                )
            )

        # Check for increasing errors
        if current.error_count > prev.error_count + 2:
            patterns.append(
                StuckPattern(
                    pattern_type="repeated_errors",
                    description=f"Error count increased by {current.error_count - prev.error_count}",
                    severity="high",
                )
            )

        # Check for no tool calls (might be stuck in a loop)
        if current.tool_calls == prev.tool_calls:
            patterns.append(
                StuckPattern(
                    pattern_type="no_progress",
                    description="No tool calls since last check",
                    severity="medium",
                )
            )

        return patterns

    def get_summary(self) -> dict:
        """Get a summary of progress monitoring.

        Returns:
            Dictionary with monitoring summary.
        """
        if not self.snapshots:
            return {
                "snapshots_taken": 0,
                "stuck_count": self.stuck_count,
                "total_tokens": 0,
            }

        latest = self.snapshots[-1]
        first = self.snapshots[0]

        return {
            "snapshots_taken": len(self.snapshots),
            "stuck_count": self.stuck_count,
            "total_tokens": latest.tokens_used,
            "files_modified": latest.files_modified - first.files_modified,
            "tests_run": latest.tests_run - first.tests_run,
            "tool_calls": latest.tool_calls - first.tool_calls,
            "features_completed": latest.features_completed - first.features_completed,
        }

    def reset(self) -> None:
        """Reset the monitor for a new session."""
        self.snapshots = []
        self.stuck_count = 0
        self.last_check_tokens = 0


def create_progress_monitor(
    check_interval: int = 5000,
    stuck_threshold: int = 2,
    force_stop_threshold: int = 3,
) -> ProgressMonitor:
    """Create a progress monitor with configuration.

    Args:
        check_interval: Tokens between checks.
        stuck_threshold: Checks before warning.
        force_stop_threshold: Checks before force stop.

    Returns:
        Configured ProgressMonitor.
    """
    return ProgressMonitor(
        check_interval_tokens=check_interval,
        stuck_threshold=stuck_threshold,
        force_stop_threshold=force_stop_threshold,
    )


def format_progress_warning(check: ProgressCheck) -> str:
    """Format a progress check as a warning message.

    Args:
        check: ProgressCheck to format.

    Returns:
        Formatted warning string.
    """
    if check.making_progress:
        return ""

    lines = ["=" * 40]
    lines.append("PROGRESS WARNING")
    lines.append("=" * 40)
    lines.append("")
    lines.append(check.message)
    lines.append("")

    if check.force_stop:
        lines.append("ACTION REQUIRED: Session will be terminated.")
        lines.append("Please save your progress and wrap up.")
    elif check.warning_level == "high":
        lines.append("SUGGESTION: Consider a different approach.")
        lines.append("If stuck, use signal_stuck tool to report the problem.")
    else:
        lines.append("TIP: Make sure you're making measurable progress.")

    lines.append("=" * 40)

    return "\n".join(lines)
