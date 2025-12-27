"""Pytest configuration and fixtures for integration tests."""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch, AsyncMock

import pytest

from agent_harness.agent import AgentSession, TokenUsage
from agent_harness.config import Config
from agent_harness.features import FeaturesFile, Feature


@pytest.fixture
def integration_project(tmp_path):
    """Create a complete project setup for integration testing.

    This fixture creates all necessary files and directories for a
    fully functional harness project, including git initialization.

    Yields:
        Path: Path to the temporary project directory.
    """
    # Create git repository
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Create .harness directory structure
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()
    (harness_dir / "checkpoints").mkdir()
    (harness_dir / "logs").mkdir()

    # Create session_state.json
    state = {
        "harness_version": "1.0.0",
        "schema_version": 1,
        "last_session": 0,
        "status": "complete",
        "next_prompt": "coding",
        "stuck_count": 0,
        "total_sessions": 0,
        "sessions": [],
    }
    (harness_dir / "session_state.json").write_text(json.dumps(state, indent=2))

    # Create config.yaml
    config_content = """project:
  name: test-project
  description: Integration test project

models:
  default: claude-sonnet-4-20250514

costs:
  per_session_usd: 5.0
  total_project_usd: 100.0

testing:
  test_command: pytest
  test_timeout: 300

verification:
  regression_check: true

progress:
  check_interval_tokens: 10000
"""
    (harness_dir / "config.yaml").write_text(config_content)

    # Create features.json
    features = {
        "project": "test-project",
        "generated_by": "test-fixture",
        "init_mode": "new",
        "last_updated": "2025-01-01",
        "features": [
            {
                "id": 1,
                "category": "core",
                "description": "Implement basic calculator functions",
                "test_file": "tests/test_calculator.py",
                "verification_steps": ["Run tests"],
                "size_estimate": "small",
                "depends_on": [],
                "passes": False,
                "origin": "spec",
                "verification_type": "automated",
                "note": None,
            },
            {
                "id": 2,
                "category": "feature",
                "description": "Add advanced math operations",
                "test_file": "tests/test_advanced.py",
                "verification_steps": ["Run tests"],
                "size_estimate": "medium",
                "depends_on": [1],
                "passes": False,
                "origin": "spec",
                "verification_type": "automated",
                "note": None,
            },
        ],
    }
    (tmp_path / "features.json").write_text(json.dumps(features, indent=2))

    # Create baseline.json
    baseline = {
        "created_at": "2025-01-01T00:00:00Z",
        "test_command": "pytest",
        "total_tests": 0,
        "results": {
            "passed": [],
            "failed": [],
            "errors": [],
            "skipped": [],
        },
    }
    (harness_dir / "baseline.json").write_text(json.dumps(baseline, indent=2))

    # Create costs.yaml
    costs_content = """sessions: []
total_cost_usd: 0.0
total_input_tokens: 0
total_output_tokens: 0
"""
    (harness_dir / "costs.yaml").write_text(costs_content)

    # Create claude-progress.txt
    progress_content = """# Agent Harness Progress Log

Project: test-project
Started: 2025-01-01
Last Updated: 2025-01-01

## Session History
"""
    (tmp_path / "claude-progress.txt").write_text(progress_content)

    # Create test directory with basic test file
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("")

    test_calculator = '''"""Tests for calculator functions."""

import pytest

def test_add():
    """Test addition."""
    assert 1 + 1 == 2

def test_subtract():
    """Test subtraction."""
    assert 2 - 1 == 1
'''
    (tests_dir / "test_calculator.py").write_text(test_calculator)

    # Create src directory
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "__init__.py").write_text("")

    # Initial git commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    yield tmp_path


@pytest.fixture
def mock_agent_runner():
    """Create a mock AgentRunner for testing without API calls.

    Returns:
        Mock: Configured mock agent runner.
    """
    with patch("agent_harness.session.AgentRunner") as mock_runner_class:
        # Create mock instance
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        # Mock successful conversation with correct AgentSession signature
        from agent_harness.agent import AgentSession, TokenUsage
        mock_session = AgentSession(
            model="claude-sonnet-4-20250514",
            system_prompt="Test system prompt",
            session_type="coding",
            history=[],
            total_usage=TokenUsage(input_tokens=1000, output_tokens=500),
            tool_call_count=0,
        )
        # Use AsyncMock for async run_conversation method
        mock_runner.run_conversation = AsyncMock(return_value=mock_session)
        mock_runner.get_cost.return_value = 0.05

        yield mock_runner


@pytest.fixture
def mock_claude_api():
    """Mock Claude API responses for agent interactions.

    Returns:
        Mock: Configured mock for anthropic client.
    """
    with patch("agent_harness.agent.Anthropic") as mock_anthropic:
        # Create mock client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock message creation
        mock_response = MagicMock()
        mock_response.id = "msg_test123"
        mock_response.content = [
            MagicMock(
                type="text",
                text="I've completed the feature implementation.",
            )
        ]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(
            input_tokens=1000,
            output_tokens=500,
        )

        mock_client.messages.create.return_value = mock_response

        yield mock_client


@pytest.fixture
def mock_test_runner():
    """Mock test runner for verification tests.

    Returns:
        Mock: Configured mock for run_tests_async function.
    """
    from agent_harness.test_runner import TestRunResult
    from unittest.mock import AsyncMock

    with patch("agent_harness.verification.run_tests_async") as mock_run:
        # Default: all tests pass with correct TestRunResult signature
        mock_result = TestRunResult(
            exit_code=0,
            passed=["tests/test_calculator.py::test_add", "tests/test_calculator.py::test_subtract"],
            failed=[],
            errors=[],
            skipped=[],
            total=2,
            duration=0.5,
            raw_output="test output",
            results=[],
        )
        # Use AsyncMock for async function
        mock_run.return_value = mock_result
        mock_run.side_effect = None  # Reset side_effect to ensure return_value works

        yield mock_run


@pytest.fixture
def sample_spec_file(tmp_path):
    """Create a sample specification file for init testing.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        Path: Path to the spec file.
    """
    spec_file = tmp_path / "spec.md"
    spec_content = """# Test Project Specification

## Overview
Build a simple calculator application with basic and advanced operations.

## Features

### 1. Basic Operations
- Addition
- Subtraction
- Multiplication
- Division

### 2. Advanced Operations
- Power
- Square root
- Trigonometric functions

## Testing Requirements
- Unit tests for all operations
- 95% code coverage
- Integration tests for calculator workflows
"""
    spec_file.write_text(spec_content)
    return spec_file


@pytest.fixture
def mock_preflight_checks():
    """Mock preflight checks to avoid real git/test operations.

    Returns:
        Mock: Configured mock for run_preflight_checks_async.
    """
    from agent_harness.preflight import PreflightResult

    with patch("agent_harness.session.run_preflight_checks_async", new_callable=AsyncMock) as mock_preflight:
        # Default: all checks pass
        mock_result = PreflightResult(
            passed=True,
            checks={
                "git_clean": True,
                "tests_passing": True,
                "features_valid": True,
                "budget_available": True,
            },
            warnings=[],
            abort_reason=None,
        )
        mock_preflight.return_value = mock_result

        yield mock_preflight


@pytest.fixture
def mock_checkpoint():
    """Mock checkpoint creation and rollback.

    Returns:
        Dict: Dictionary with mock checkpoint functions.
    """
    from agent_harness.checkpoint import Checkpoint, RollbackResult

    with patch("agent_harness.session.create_checkpoint") as mock_create, \
         patch("agent_harness.session.rollback_to_checkpoint") as mock_rollback:

        # Mock checkpoint creation
        mock_checkpoint_info = Checkpoint(
            id="cp_test_001",
            timestamp="2025-01-01T00:00:00Z",
            session=1,
            git_ref="abc123",
            features_json_hash="hash1",
            progress_file_hash="hash2",
            session_state_hash="hash3",
            reason="Test checkpoint",
            files_backed_up=["features.json", "session_state.json"],
        )
        mock_create.return_value = mock_checkpoint_info

        # Mock successful rollback
        mock_rollback_result = RollbackResult(
            success=True,
            checkpoint_id="cp_test_001",
            git_restored=True,
            files_restored=["features.json", "session_state.json"],
            errors=[],
            message="Rollback successful",
        )
        mock_rollback.return_value = mock_rollback_result

        yield {
            "create": mock_create,
            "rollback": mock_rollback,
        }


def create_feature_dict(
    feature_id: int,
    description: str,
    test_file: str,
    passes: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Helper to create a feature dictionary.

    Args:
        feature_id: Feature ID.
        description: Feature description.
        test_file: Test file path.
        passes: Whether feature passes tests.
        **kwargs: Additional feature fields.

    Returns:
        Dict with feature data.
    """
    feature = {
        "id": feature_id,
        "category": kwargs.get("category", "core"),
        "description": description,
        "test_file": test_file,
        "verification_steps": kwargs.get("verification_steps", ["Run tests"]),
        "size_estimate": kwargs.get("size_estimate", "small"),
        "depends_on": kwargs.get("depends_on", []),
        "passes": passes,
        "origin": kwargs.get("origin", "spec"),
        "verification_type": kwargs.get("verification_type", "automated"),
        "note": kwargs.get("note", None),
    }
    return feature


@pytest.fixture
def cleanup_integration_files():
    """Cleanup fixture that runs after each test.

    Ensures no temporary files or state leak between tests.
    """
    yield
    # Cleanup happens automatically with tmp_path, but this fixture
    # can be extended for additional cleanup if needed
