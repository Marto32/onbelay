"""Pytest configuration and fixtures for agent-harness tests."""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for testing project operations."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_harness_yaml():
    """Return a sample .harness.yaml configuration."""
    return """
project:
  name: test-project
  description: A test project for harness

environment:
  python_version: "3.11"
  package_manager: poetry

testing:
  test_command: pytest
  test_timeout: 300

costs:
  budget_per_session: 5.0
  budget_total: 100.0
"""


@pytest.fixture
def sample_features_json():
    """Return a sample features.json structure."""
    return {
        "project": "test-project",
        "generated_by": "harness-init",
        "init_mode": "new",
        "last_updated": "2025-01-01T00:00:00Z",
        "features": [
            {
                "id": 1,
                "category": "core",
                "description": "Basic feature one",
                "test_file": "tests/test_feature_1.py",
                "verification_steps": ["Run tests", "Check output"],
                "size_estimate": "small",
                "depends_on": [],
                "passes": False,
                "origin": "spec",
                "verification_type": "automated",
                "note": None
            }
        ]
    }
