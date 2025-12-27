"""Custom exceptions for agent-harness."""


class HarnessError(Exception):
    """Base exception for all harness errors."""

    pass


class ConfigError(HarnessError):
    """Error loading or validating configuration."""

    pass


class ConfigNotFoundError(ConfigError):
    """Configuration file not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Configuration file not found: {path}")


class ConfigValidationError(ConfigError):
    """Configuration validation failed."""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Invalid configuration for '{field}': {message}")


class StateError(HarnessError):
    """Error with harness state files."""

    pass


class GitError(HarnessError):
    """Error with git operations."""

    pass


class VerificationError(HarnessError):
    """Error during verification."""

    pass


class AgentError(HarnessError):
    """Error with agent operations."""

    pass


class BudgetExceededError(HarnessError):
    """Budget limit has been exceeded."""

    def __init__(self, budget_type: str, limit: float, current: float):
        self.budget_type = budget_type
        self.limit = limit
        self.current = current
        super().__init__(
            f"{budget_type} budget exceeded: ${current:.2f} >= ${limit:.2f}"
        )


class PreflightError(HarnessError):
    """Pre-flight check failed."""

    def __init__(self, check_name: str, message: str):
        self.check_name = check_name
        super().__init__(f"Pre-flight check '{check_name}' failed: {message}")


class MigrationError(HarnessError):
    """Error during state migration."""

    pass


class ToolExecutionError(HarnessError):
    """Error executing a tool."""

    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}")
