"""Tests for configuration loading and validation."""

import pytest
from pathlib import Path

from agent_harness.config import (
    Config,
    load_config,
    get_default_config,
    save_config,
    ProjectConfig,
    CostsConfig,
)
from agent_harness.exceptions import ConfigError, ConfigValidationError


class TestConfigDefaults:
    """Test default configuration values."""

    def test_get_default_config(self):
        """Default config should have sensible defaults."""
        config = get_default_config()
        assert config.project.name == "unnamed-project"
        assert config.costs.per_session_usd == 10.0
        assert config.context.warn_threshold == 0.75
        assert config.context.force_threshold == 0.90
        assert config.verification.max_features_per_session == 1

    def test_default_models(self):
        """Default model configuration."""
        config = get_default_config()
        assert config.models.default == "claude-sonnet-4"
        assert config.models.coding == "claude-sonnet-4"
        assert config.models.cleanup == "claude-haiku-3"

    def test_default_paths(self):
        """Default paths configuration."""
        config = get_default_config()
        assert config.paths.features == "features.json"
        assert config.paths.progress == "claude-progress.txt"
        assert config.paths.state_dir == ".harness"

    def test_default_tools(self):
        """Default tools configuration."""
        config = get_default_config()
        assert config.tools.filesystem.enabled is True
        assert config.tools.shell.enabled is True
        assert config.tools.shell.timeout_seconds == 300


class TestConfigLoading:
    """Test configuration file loading."""

    def test_load_missing_config_uses_defaults(self, temp_project_dir):
        """Loading from directory without .harness.yaml should use defaults."""
        config = load_config(temp_project_dir)
        assert config.project.name == "unnamed-project"

    def test_load_valid_config(self, temp_project_dir):
        """Loading valid YAML config should work."""
        config_content = """
project:
  name: test-project
  github_repo: user/test-project

costs:
  per_session_usd: 5.0
  total_project_usd: 50.0
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        config = load_config(temp_project_dir)
        assert config.project.name == "test-project"
        assert config.project.github_repo == "user/test-project"
        assert config.costs.per_session_usd == 5.0
        assert config.costs.total_project_usd == 50.0

    def test_load_partial_config_merges_defaults(self, temp_project_dir):
        """Partial config should merge with defaults."""
        config_content = """
project:
  name: partial-project
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        config = load_config(temp_project_dir)
        assert config.project.name == "partial-project"
        # Should have default values for unspecified fields
        assert config.costs.per_session_usd == 10.0
        assert config.context.warn_threshold == 0.75

    def test_load_invalid_yaml_raises_error(self, temp_project_dir):
        """Invalid YAML should raise ConfigError."""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text("invalid: yaml: content: [")

        with pytest.raises(ConfigError):
            load_config(temp_project_dir)


class TestConfigValidation:
    """Test configuration validation."""

    def test_invalid_warn_threshold(self, temp_project_dir):
        """warn_threshold must be between 0 and 1."""
        config_content = """
context:
  warn_threshold: 1.5
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(temp_project_dir)
        assert "warn_threshold" in str(exc_info.value)

    def test_warn_threshold_must_be_less_than_force(self, temp_project_dir):
        """warn_threshold must be less than force_threshold."""
        config_content = """
context:
  warn_threshold: 0.95
  force_threshold: 0.90
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            load_config(temp_project_dir)

    def test_invalid_logging_level(self, temp_project_dir):
        """Logging level must be valid."""
        config_content = """
logging:
  level: invalid
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(temp_project_dir)
        assert "logging.level" in str(exc_info.value)

    def test_invalid_github_sync_mode(self, temp_project_dir):
        """GitHub sync_mode must be valid."""
        config_content = """
github:
  sync_mode: invalid
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            load_config(temp_project_dir)

    def test_negative_costs_invalid(self, temp_project_dir):
        """Costs must be positive."""
        config_content = """
costs:
  per_session_usd: -5.0
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            load_config(temp_project_dir)


class TestConfigSaving:
    """Test configuration saving."""

    def test_save_and_reload_config(self, temp_project_dir):
        """Saved config should be reloadable."""
        config = get_default_config()
        config.project.name = "saved-project"
        config.costs.per_session_usd = 15.0

        save_config(config, temp_project_dir)

        loaded = load_config(temp_project_dir)
        assert loaded.project.name == "saved-project"
        assert loaded.costs.per_session_usd == 15.0


class TestNestedConfig:
    """Test nested configuration structures."""

    def test_nested_context_config(self, temp_project_dir):
        """Nested context.on_limit config should load correctly."""
        config_content = """
context:
  warn_threshold: 0.70
  force_threshold: 0.85
  on_limit:
    auto_commit: false
    commit_message_prefix: "Custom: "
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        config = load_config(temp_project_dir)
        assert config.context.warn_threshold == 0.70
        assert config.context.force_threshold == 0.85
        assert config.context.on_limit.auto_commit is False
        assert config.context.on_limit.commit_message_prefix == "Custom: "

    def test_nested_tools_config(self, temp_project_dir):
        """Nested tools config should load correctly."""
        config_content = """
tools:
  filesystem:
    enabled: true
    allowed_paths:
      - "."
      - "./src"
    denied_paths:
      - ".git/"
  shell:
    timeout_seconds: 600
    denied_commands:
      - "rm -rf /"
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        config = load_config(temp_project_dir)
        assert config.tools.filesystem.enabled is True
        assert "./src" in config.tools.filesystem.allowed_paths
        assert config.tools.shell.timeout_seconds == 600

    def test_preflight_checks_config(self, temp_project_dir):
        """Preflight checks config should load correctly."""
        config_content = """
preflight:
  checks:
    working_directory: true
    harness_files: true
    git_state: false
    environment: true
    baseline_tests: false
    budget: true
  on_failure: warn
"""
        config_path = temp_project_dir / ".harness.yaml"
        config_path.write_text(config_content)

        config = load_config(temp_project_dir)
        assert config.preflight.checks.git_state is False
        assert config.preflight.checks.baseline_tests is False
        assert config.preflight.on_failure == "warn"
