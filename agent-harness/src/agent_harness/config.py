"""Configuration loading and validation for agent-harness."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from agent_harness.exceptions import ConfigError, ConfigNotFoundError, ConfigValidationError


# --- Sub-configuration dataclasses ---


@dataclass
class ProjectConfig:
    """Project identity configuration."""

    name: str = "unnamed-project"
    github_repo: Optional[str] = None
    description: Optional[str] = None


@dataclass
class EnvironmentConfig:
    """Environment setup configuration."""

    init: str = "./init.sh"
    reset: str = "./reset.sh"
    health_check: Optional[str] = None
    stop: Optional[str] = None
    python_version: str = "3.11"
    package_manager: str = "poetry"


@dataclass
class SanityConfig:
    """Sanity test configuration."""

    health: Optional[str] = None
    lint: Optional[str] = None


@dataclass
class TestingConfig:
    """Testing configuration."""

    sanity: SanityConfig = field(default_factory=SanityConfig)
    unit: str = "poetry run pytest tests/unit -x"
    e2e: str = "poetry run pytest tests/e2e -x"
    full: str = "poetry run pytest tests/ -v"
    test_command: str = "pytest"
    test_timeout: int = 300


@dataclass
class CostsConfig:
    """Cost control configuration."""

    per_session_usd: float = 10.0
    per_feature_usd: float = 25.0
    total_project_usd: float = 200.0


@dataclass
class ModelsConfig:
    """Model configuration for different prompt types."""

    default: str = "claude-sonnet-4"
    initializer: str = "claude-sonnet-4"
    coding: str = "claude-sonnet-4"
    continuation: str = "claude-sonnet-4"
    cleanup: str = "claude-haiku-3"


@dataclass
class ContextLimitConfig:
    """What to do when context limit is reached."""

    auto_commit: bool = True
    commit_message_prefix: str = "WIP: Context limit - "
    append_to_progress: bool = True


@dataclass
class ContextConfig:
    """Context management configuration."""

    warn_threshold: float = 0.75
    force_threshold: float = 0.90
    on_limit: ContextLimitConfig = field(default_factory=ContextLimitConfig)


@dataclass
class ProgressConfig:
    """Progress monitoring configuration."""

    check_interval_tokens: int = 50000
    stuck_warning: str = "You appear stuck. Consider a different approach."
    force_stop_after_stuck_checks: int = 2
    max_repeated_errors: int = 5


@dataclass
class QualityConfig:
    """Code quality configuration."""

    lint_command: str = "poetry run ruff check src/"
    max_file_lines: int = 500
    cleanup_interval: int = 10
    warn_on_lint_errors: bool = True


@dataclass
class VerificationConfig:
    """Verification configuration."""

    require_evidence: bool = True
    harness_verify: bool = True
    max_features_per_session: int = 1
    regression_check: bool = True


@dataclass
class FeaturesConfig:
    """Feature rules configuration."""

    max_verification_steps: int = 7
    max_stuck_sessions: int = 3
    require_test_file: bool = True


@dataclass
class GithubConfig:
    """GitHub integration configuration."""

    enabled: bool = False
    repo: Optional[str] = None
    label: str = "harness"
    sync_mode: str = "mirror"  # "mirror" or "none"
    sync_on_session_end: bool = True
    create_missing_issues: bool = True
    close_on_verify: bool = True
    on_sync_failure: str = "warn"  # "warn" or "fail"


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "important"  # critical, important, routine, debug
    retention_days: int = 90
    structured_agent_output: bool = True
    require_prefixes: bool = False
    fallback_tracking: bool = True


@dataclass
class PathsConfig:
    """Custom paths configuration."""

    features: str = "features.json"
    progress: str = "claude-progress.txt"
    state_dir: str = ".harness"


@dataclass
class FilesystemToolConfig:
    """Filesystem tool configuration."""

    enabled: bool = True
    allowed_paths: list[str] = field(default_factory=lambda: ["."])
    denied_paths: list[str] = field(default_factory=lambda: [".harness/", ".git/", "../"])


@dataclass
class ShellToolConfig:
    """Shell tool configuration."""

    enabled: bool = True
    timeout_seconds: int = 300
    denied_commands: list[str] = field(
        default_factory=lambda: ["rm -rf /", "sudo", "> /dev/"]
    )


@dataclass
class MCPServerConfig:
    """MCP server configuration."""

    enabled: bool = False
    command: str = "npx"
    args: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServersConfig:
    """MCP servers configuration."""

    puppeteer: MCPServerConfig = field(default_factory=MCPServerConfig)
    postgres: MCPServerConfig = field(default_factory=MCPServerConfig)


@dataclass
class ToolsConfig:
    """Tools configuration."""

    filesystem: FilesystemToolConfig = field(default_factory=FilesystemToolConfig)
    shell: ShellToolConfig = field(default_factory=ShellToolConfig)
    mcp_servers: MCPServersConfig = field(default_factory=MCPServersConfig)


@dataclass
class PreflightChecksConfig:
    """Pre-flight checks configuration."""

    working_directory: bool = True
    harness_files: bool = True
    git_state: bool = True
    environment: bool = True
    baseline_tests: bool = True
    budget: bool = True


@dataclass
class PreflightConfig:
    """Pre-flight configuration."""

    checks: PreflightChecksConfig = field(default_factory=PreflightChecksConfig)
    on_failure: str = "abort"  # "abort" or "warn"


@dataclass
class SessionTimeoutConfig:
    """Session timeout configuration."""

    auto_commit: bool = True
    message_prefix: str = "WIP: Session timeout - "


@dataclass
class SessionConfig:
    """Session configuration."""

    timeout_minutes: int = 60
    timeout_warning_minutes: int = 50
    on_timeout: SessionTimeoutConfig = field(default_factory=SessionTimeoutConfig)


@dataclass
class CompatibilityConfig:
    """Version compatibility configuration."""

    on_older_state: str = "migrate"  # "migrate" or "abort"
    on_newer_state: str = "abort"  # "abort" or "warn"
    backup_before_migrate: bool = True


@dataclass
class InitConfig:
    """Initialization mode configuration."""

    mode: str = "new"  # "new" or "adopt"
    adopted_at: Optional[str] = None


# --- Main configuration dataclass ---


@dataclass
class Config:
    """Complete harness configuration."""

    project: ProjectConfig = field(default_factory=ProjectConfig)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    testing: TestingConfig = field(default_factory=TestingConfig)
    costs: CostsConfig = field(default_factory=CostsConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    progress: ProgressConfig = field(default_factory=ProgressConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    github: GithubConfig = field(default_factory=GithubConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    preflight: PreflightConfig = field(default_factory=PreflightConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    compatibility: CompatibilityConfig = field(default_factory=CompatibilityConfig)
    init: InitConfig = field(default_factory=InitConfig)


# --- Configuration loading functions ---


def _merge_dict(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _dict_to_dataclass(cls: type, data: dict) -> Any:
    """Convert a dictionary to a dataclass, handling nested dataclasses."""
    if data is None:
        return cls()

    # Get field types from the dataclass
    field_types = {}
    for f in cls.__dataclass_fields__.values():
        field_types[f.name] = f.type

    # Process each field
    kwargs = {}
    for field_name, field_type in field_types.items():
        if field_name not in data:
            continue

        value = data[field_name]

        # Check if field_type is a dataclass
        if hasattr(field_type, "__dataclass_fields__"):
            if isinstance(value, dict):
                kwargs[field_name] = _dict_to_dataclass(field_type, value)
            else:
                kwargs[field_name] = value
        else:
            kwargs[field_name] = value

    return cls(**kwargs)


def _load_yaml_file(path: Path) -> dict:
    """Load a YAML file and return its contents as a dictionary."""
    if not path.exists():
        raise ConfigNotFoundError(str(path))

    try:
        with open(path) as f:
            content = yaml.safe_load(f)
            return content if content else {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}")


def _validate_config(config: Config) -> None:
    """Validate configuration values."""
    # Validate thresholds
    if not 0 < config.context.warn_threshold < 1:
        raise ConfigValidationError(
            "context.warn_threshold", "Must be between 0 and 1"
        )

    if not 0 < config.context.force_threshold <= 1:
        raise ConfigValidationError(
            "context.force_threshold", "Must be between 0 and 1"
        )

    if config.context.warn_threshold >= config.context.force_threshold:
        raise ConfigValidationError(
            "context.warn_threshold",
            "Must be less than context.force_threshold"
        )

    # Validate costs
    if config.costs.per_session_usd <= 0:
        raise ConfigValidationError(
            "costs.per_session_usd", "Must be positive"
        )

    if config.costs.total_project_usd <= 0:
        raise ConfigValidationError(
            "costs.total_project_usd", "Must be positive"
        )

    # Validate session timeout
    if config.session.timeout_minutes <= 0:
        raise ConfigValidationError(
            "session.timeout_minutes", "Must be positive"
        )

    if config.session.timeout_warning_minutes >= config.session.timeout_minutes:
        raise ConfigValidationError(
            "session.timeout_warning_minutes",
            "Must be less than session.timeout_minutes"
        )

    # Validate verification
    if config.verification.max_features_per_session < 1:
        raise ConfigValidationError(
            "verification.max_features_per_session", "Must be at least 1"
        )

    # Validate logging level
    valid_levels = {"critical", "important", "routine", "debug"}
    if config.logging.level not in valid_levels:
        raise ConfigValidationError(
            "logging.level", f"Must be one of: {', '.join(valid_levels)}"
        )

    # Validate github sync_mode
    valid_sync_modes = {"mirror", "none"}
    if config.github.sync_mode not in valid_sync_modes:
        raise ConfigValidationError(
            "github.sync_mode", f"Must be one of: {', '.join(valid_sync_modes)}"
        )

    # Validate compatibility modes
    valid_state_modes = {"migrate", "abort", "warn"}
    if config.compatibility.on_older_state not in {"migrate", "abort"}:
        raise ConfigValidationError(
            "compatibility.on_older_state", "Must be 'migrate' or 'abort'"
        )
    if config.compatibility.on_newer_state not in {"abort", "warn"}:
        raise ConfigValidationError(
            "compatibility.on_newer_state", "Must be 'abort' or 'warn'"
        )


def load_config(project_dir: Optional[Path] = None) -> Config:
    """
    Load configuration from .harness.yaml in the project directory.

    Args:
        project_dir: Path to the project directory. Defaults to current working directory.

    Returns:
        Loaded and validated Config object.

    Raises:
        ConfigError: If configuration is invalid.
        ConfigNotFoundError: If configuration file is not found (only if strict mode).
    """
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    config_path = project_dir / ".harness.yaml"

    # Load config file if it exists, otherwise use defaults
    if config_path.exists():
        config_data = _load_yaml_file(config_path)
    else:
        config_data = {}

    # Convert to Config dataclass with defaults
    config = _dict_to_dataclass(Config, config_data)

    # Handle legacy aliased fields (budget_per_session -> per_session_usd)
    costs_data = config_data.get("costs", {})
    if "budget_per_session" in costs_data:
        config.costs.per_session_usd = costs_data["budget_per_session"]
    if "budget_total" in costs_data:
        config.costs.total_project_usd = costs_data["budget_total"]

    # Validate
    _validate_config(config)

    return config


def get_default_config() -> Config:
    """Return a Config object with all default values."""
    return Config()


def save_config(config: Config, project_dir: Path) -> None:
    """
    Save configuration to .harness.yaml in the project directory.

    Args:
        config: Config object to save.
        project_dir: Path to the project directory.
    """
    config_path = project_dir / ".harness.yaml"

    # Convert dataclass to dict
    def dataclass_to_dict(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for f in obj.__dataclass_fields__:
                value = getattr(obj, f)
                result[f] = dataclass_to_dict(value)
            return result
        elif isinstance(obj, list):
            return [dataclass_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: dataclass_to_dict(v) for k, v in obj.items()}
        else:
            return obj

    config_dict = dataclass_to_dict(config)

    with open(config_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
