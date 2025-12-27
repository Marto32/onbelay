"""Context window management for agent sessions.

Tracks token usage against the model's context window and provides
warnings when approaching limits:
- 75% warning: suggest wrapping up
- 90% critical: force wrap-up message
- 100% hard stop: session must end
"""

from dataclasses import dataclass, field
from typing import Optional


# Model context window sizes (in tokens)
MODEL_CONTEXT_WINDOWS = {
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-sonnet-4": 200000,
    "default": 200000,
}


@dataclass
class ContextStatus:
    """Current context window status."""

    tokens_used: int
    context_window: int
    percentage_used: float
    tokens_remaining: int
    warning_level: str = "none"  # "none", "warning", "critical", "exceeded"
    message: Optional[str] = None


@dataclass
class ContextWarning:
    """A context warning to inject into conversation."""

    level: str  # "warning", "critical", "hard_stop"
    message: str
    force_action: bool = False


class ContextManager:
    """Manages context window usage during a session."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        warning_threshold: float = 0.75,
        critical_threshold: float = 0.90,
        reserve_tokens: int = 4000,
    ):
        """Initialize the context manager.

        Args:
            model: Model name for context window lookup.
            warning_threshold: Percentage for initial warning (0.0-1.0).
            critical_threshold: Percentage for critical warning (0.0-1.0).
            reserve_tokens: Tokens to reserve for response.
        """
        self.model = model
        self.context_window = MODEL_CONTEXT_WINDOWS.get(
            model, MODEL_CONTEXT_WINDOWS["default"]
        )
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.reserve_tokens = reserve_tokens

        self.tokens_used = 0
        self.warning_issued = False
        self.critical_issued = False

    @property
    def usable_tokens(self) -> int:
        """Get the usable context window (minus reserve)."""
        return self.context_window - self.reserve_tokens

    @property
    def percentage_used(self) -> float:
        """Get percentage of context used."""
        return self.tokens_used / self.usable_tokens if self.usable_tokens > 0 else 1.0

    @property
    def tokens_remaining(self) -> int:
        """Get tokens remaining in context."""
        return max(0, self.usable_tokens - self.tokens_used)

    def update_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Update token usage after an API call.

        Args:
            input_tokens: Tokens used for input.
            output_tokens: Tokens used for output.
        """
        self.tokens_used += input_tokens + output_tokens

    def get_status(self) -> ContextStatus:
        """Get current context status.

        Returns:
            ContextStatus with current usage info.
        """
        percentage = self.percentage_used

        # Determine warning level
        if percentage >= 1.0:
            warning_level = "exceeded"
            message = "Context window exceeded - session must end"
        elif percentage >= self.critical_threshold:
            warning_level = "critical"
            message = f"Context at {percentage:.0%} - must wrap up immediately"
        elif percentage >= self.warning_threshold:
            warning_level = "warning"
            message = f"Context at {percentage:.0%} - consider wrapping up"
        else:
            warning_level = "none"
            message = None

        return ContextStatus(
            tokens_used=self.tokens_used,
            context_window=self.context_window,
            percentage_used=percentage,
            tokens_remaining=self.tokens_remaining,
            warning_level=warning_level,
            message=message,
        )

    def check_and_warn(self) -> Optional[ContextWarning]:
        """Check if a warning should be issued.

        Returns new warnings only (not repeat warnings).

        Returns:
            ContextWarning if threshold crossed, None otherwise.
        """
        percentage = self.percentage_used

        # Hard stop
        if percentage >= 1.0:
            return ContextWarning(
                level="hard_stop",
                message=self._build_hard_stop_message(),
                force_action=True,
            )

        # Critical (only once)
        if percentage >= self.critical_threshold and not self.critical_issued:
            self.critical_issued = True
            return ContextWarning(
                level="critical",
                message=self._build_critical_message(),
                force_action=True,
            )

        # Warning (only once)
        if percentage >= self.warning_threshold and not self.warning_issued:
            self.warning_issued = True
            return ContextWarning(
                level="warning",
                message=self._build_warning_message(),
                force_action=False,
            )

        return None

    def _build_warning_message(self) -> str:
        """Build the 75% warning message."""
        return f"""
CONTEXT WINDOW WARNING
======================
You have used {self.percentage_used:.0%} of the available context window.
Remaining tokens: ~{self.tokens_remaining:,}

RECOMMENDATIONS:
1. Start wrapping up your current work
2. Focus on completing the current feature
3. Write a clear summary of progress so far
4. Prepare for a potential session handoff

Continue working, but be mindful of the limit.
"""

    def _build_critical_message(self) -> str:
        """Build the 90% critical message."""
        return f"""
CRITICAL: CONTEXT WINDOW NEARLY FULL
====================================
You have used {self.percentage_used:.0%} of the available context window.
Remaining tokens: ~{self.tokens_remaining:,}

IMMEDIATE ACTION REQUIRED:
1. STOP starting new work
2. Complete any in-progress changes
3. Run tests to verify your work
4. Update features.json if feature is complete
5. Write a detailed progress summary
6. Prepare for session end

The session will be terminated soon.
"""

    def _build_hard_stop_message(self) -> str:
        """Build the 100% hard stop message."""
        return """
HARD STOP: CONTEXT WINDOW EXCEEDED
==================================
The context window has been exceeded.
This session must end NOW.

FINAL ACTIONS:
1. Save all work immediately
2. Do not start any new operations
3. The session will terminate after this message
"""

    def can_continue(self) -> bool:
        """Check if the session can continue.

        Returns:
            True if context window not exceeded.
        """
        return self.percentage_used < 1.0

    def estimate_turns_remaining(self, avg_tokens_per_turn: int = 2000) -> int:
        """Estimate how many conversation turns remain.

        Args:
            avg_tokens_per_turn: Average tokens per turn.

        Returns:
            Estimated turns remaining.
        """
        if avg_tokens_per_turn <= 0:
            return 0
        return self.tokens_remaining // avg_tokens_per_turn

    def reset(self) -> None:
        """Reset the context manager for a new session."""
        self.tokens_used = 0
        self.warning_issued = False
        self.critical_issued = False


def create_context_manager(
    model: str = "claude-sonnet-4-20250514",
    warning_threshold: float = 0.75,
    critical_threshold: float = 0.90,
) -> ContextManager:
    """Create a context manager with configuration.

    Args:
        model: Model name.
        warning_threshold: Warning percentage.
        critical_threshold: Critical percentage.

    Returns:
        Configured ContextManager.
    """
    return ContextManager(
        model=model,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
    )


def get_context_window_size(model: str) -> int:
    """Get the context window size for a model.

    Args:
        model: Model name.

    Returns:
        Context window size in tokens.
    """
    return MODEL_CONTEXT_WINDOWS.get(model, MODEL_CONTEXT_WINDOWS["default"])
