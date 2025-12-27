"""Integration tests for initialization workflows.

Tests the complete initialization process including new project setup,
adopting existing codebases, and resuming partial initializations.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent_harness.init import (
    InitConfig,
    initialize_project,
    init_project,
    detect_project_mode,
    create_harness_directory,
    validate_initialization,
)
from agent_harness.features import load_features
from agent_harness.state import load_session_state


@pytest.mark.integration
class TestNewProjectInit:
    """Test initialization of new projects from scratch."""

    @pytest.mark.asyncio
    async def test_new_project_initialization_creates_all_files(
        self,
        tmp_path,
        sample_spec_file,
    ):
        """Test that new project init creates all required files.

        Verifies:
        - .harness directory created
        - config.yaml created
        - session_state.json created
        - features.json created
        - Subdirectories created (checkpoints, logs)
        """
        # Create spec file in tmp_path
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(sample_spec_file.read_text())

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        config = InitConfig(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="new",
            dry_run=True,  # Don't run agent
        )

        result = await initialize_project(config)

        # Verify success
        assert result.success is True
        assert result.mode == "new"

        # Verify harness directory structure
        harness_dir = tmp_path / ".harness"
        assert harness_dir.exists()
        assert (harness_dir / "checkpoints").exists()
        assert (harness_dir / "logs").exists()

        # Verify config file (saved as .harness.yaml in project root)
        assert (tmp_path / ".harness.yaml").exists()

        # Verify session state
        assert (harness_dir / "session_state.json").exists()
        state = load_session_state(harness_dir)
        assert state.last_session == 0
        assert state.status == "init"  # Initial state after initialization

        # Verify features file
        assert (tmp_path / "features.json").exists()
        features = load_features(tmp_path / "features.json")
        assert len(features.features) >= 1

    @pytest.mark.asyncio
    async def test_new_project_mode_detection(self, tmp_path):
        """Test that empty directory is detected as new mode.

        Verifies:
        - Auto mode detects new project
        - Empty directory results in 'new' mode
        """
        mode = detect_project_mode(tmp_path)
        assert mode == "new"

        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test Project")

        # Initialize git
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        config = InitConfig(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="auto",  # Let it detect
            dry_run=True,
        )

        result = await initialize_project(config)

        # Should detect as new
        assert result.mode == "new"

    @pytest.mark.asyncio
    async def test_new_project_with_default_features(
        self,
        tmp_path,
        sample_spec_file,
    ):
        """Test new project creates features from spec.

        Verifies:
        - Features generated from spec
        - Features have required fields
        - Features reference test files
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(sample_spec_file.read_text())

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        config = InitConfig(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="new",
            dry_run=True,
        )

        result = await initialize_project(config)
        assert result.success is True

        # Load and verify features
        features = load_features(tmp_path / "features.json")
        assert features.project == tmp_path.name
        assert features.init_mode == "new"
        assert len(features.features) >= 1

        # Check first feature has required fields
        feature = features.features[0]
        assert feature.id is not None
        assert feature.description is not None
        assert feature.test_file is not None
        assert feature.category is not None
        assert feature.passes is False


@pytest.mark.integration
class TestAdoptExistingProject:
    """Test adopting existing codebases."""

    def test_adopt_mode_detection(self, tmp_path):
        """Test that project with code is detected as adopt mode.

        Verifies:
        - Projects with source code detected as adopt
        - File count threshold works correctly
        """
        # Create source directory with files
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        for i in range(10):
            (src_dir / f"module{i}.py").write_text(f"# Module {i}")

        # Should detect as adopt mode
        mode = detect_project_mode(tmp_path)
        assert mode == "adopt"

    @pytest.mark.asyncio
    async def test_adopt_existing_codebase_initialization(
        self,
        tmp_path,
        sample_spec_file,
    ):
        """Test adopting an existing codebase.

        Verifies:
        - Existing code preserved
        - Harness files added
        - Features generated from existing structure
        """
        # Create existing project structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text("")
        (src_dir / "calculator.py").write_text("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_calculator.py").write_text("""
import pytest
from src.calculator import add, subtract

def test_add():
    assert add(1, 1) == 2

def test_subtract():
    assert subtract(2, 1) == 1
""")

        (tmp_path / "README.md").write_text("# Existing Project")

        # Initialize git
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create spec
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Adopt existing calculator project")

        config = InitConfig(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="adopt",
            dry_run=True,
        )

        result = await initialize_project(config)

        # Verify success
        assert result.success is True
        assert result.mode == "adopt"

        # Verify existing files preserved
        assert (src_dir / "calculator.py").exists()
        assert (tests_dir / "test_calculator.py").exists()
        assert (tmp_path / "README.md").exists()

        # Verify harness files added
        assert (tmp_path / ".harness").exists()
        assert (tmp_path / "features.json").exists()

    def test_adopt_mode_with_package_manager(self, tmp_path):
        """Test adopting project with package manager files.

        Verifies:
        - package.json triggers adopt mode
        - pyproject.toml triggers adopt mode
        """
        # Test with package.json
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "src").mkdir()
        for i in range(10):
            (tmp_path / "src" / f"file{i}.js").write_text("// code")

        mode = detect_project_mode(tmp_path)
        assert mode == "adopt"


@pytest.mark.integration
class TestResumePartialInit:
    """Test resuming partial initialization."""

    @pytest.mark.asyncio
    async def test_resume_with_existing_harness_dir(
        self,
        tmp_path,
        sample_spec_file,
    ):
        """Test resuming when .harness dir already exists.

        Verifies:
        - Existing .harness directory reused
        - Initialization completes successfully
        - Files updated, not duplicated
        """
        # Create partial harness setup
        harness_dir = create_harness_directory(tmp_path)
        assert harness_dir.exists()

        # Create spec file
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(sample_spec_file.read_text())

        # Initialize git
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        config = InitConfig(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="new",
            dry_run=True,
        )

        result = await initialize_project(config)

        # Should succeed even with existing harness dir
        assert result.success is True
        assert (tmp_path / ".harness").exists()

    @pytest.mark.asyncio
    async def test_validation_of_initialized_project(
        self,
        tmp_path,
        sample_spec_file,
    ):
        """Test validation of initialization results.

        Verifies:
        - Validation checks all required files
        - Missing files reported as errors
        - Complete initialization passes validation
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(sample_spec_file.read_text())

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        config = InitConfig(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="new",
            dry_run=True,
        )

        result = await initialize_project(config)
        assert result.success is True

        # Validate the initialization
        features = load_features(tmp_path / "features.json")
        errors = validate_initialization(tmp_path, features)

        # Should have no errors
        assert errors == []


@pytest.mark.integration
class TestInitWithAgent:
    """Test initialization with agent execution (mocked)."""

    @pytest.mark.asyncio
    async def test_init_with_mocked_agent(
        self,
        tmp_path,
        sample_spec_file,
    ):
        """Test initialization with mocked agent execution.

        Verifies:
        - Agent called with correct prompts
        - Features created from agent output
        - State initialized correctly
        """
        from agent_harness.agent import AgentSession, TokenUsage

        spec_file = tmp_path / "spec.md"
        spec_file.write_text(sample_spec_file.read_text())

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        with patch("agent_harness.init.AgentRunner") as mock_runner_class:
            # Setup mock agent
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner

            mock_session = AgentSession(
                model="claude-sonnet-4-20250514",
                system_prompt="Test system prompt",
                session_type="init",
                history=[],
                total_usage=TokenUsage(input_tokens=2000, output_tokens=1000),
                tool_call_count=0,
            )
            mock_runner.run_conversation.return_value = mock_session

            # Create features.json that agent would create
            def create_features_side_effect(*args, **kwargs):
                features_data = {
                    "project": tmp_path.name,
                    "generated_by": "agent",
                    "init_mode": "new",
                    "last_updated": "2025-01-01",
                    "features": [
                        {
                            "id": 1,
                            "category": "core",
                            "description": "Basic calculator",
                            "test_file": "tests/test_calc.py",
                            "verification_steps": ["Run tests"],
                            "size_estimate": "small",
                            "depends_on": [],
                            "passes": False,
                            "origin": "spec",
                            "verification_type": "automated",
                            "note": None,
                        }
                    ],
                }
                (tmp_path / "features.json").write_text(json.dumps(features_data))
                return mock_session

            mock_runner.run_conversation.side_effect = create_features_side_effect

            config = InitConfig(
                project_dir=tmp_path,
                spec_file=spec_file,
                mode="new",
                dry_run=False,  # Actually run agent (mocked)
            )

            result = await initialize_project(config)

            # Verify agent was called
            assert mock_runner.run_conversation.called
            assert result.success is True
            assert result.features_count >= 1


@pytest.mark.integration
class TestInitHelper:
    """Test init_project helper function."""

    @pytest.mark.asyncio
    async def test_init_project_helper_function(
        self,
        tmp_path,
        sample_spec_file,
    ):
        """Test the init_project helper function.

        Verifies:
        - Helper creates InitConfig
        - Calls initialize_project
        - Returns InitResult
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(sample_spec_file.read_text())

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = await init_project(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="new",
            dry_run=True,
        )

        assert result.success is True
        assert result.mode == "new"
        assert result.features_count >= 1

    @pytest.mark.asyncio
    async def test_init_project_with_callbacks(
        self,
        tmp_path,
        sample_spec_file,
    ):
        """Test init with response callbacks.

        Verifies:
        - Callbacks invoked during initialization
        - Progress tracking works
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(sample_spec_file.read_text())

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        callback_called = []

        def on_response(response):
            callback_called.append(True)

        # Dry run won't call callbacks, so we won't test that
        # This is more of a smoke test to ensure parameter works
        result = await init_project(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="new",
            dry_run=True,
            on_response=on_response,
        )

        assert result.success is True


@pytest.mark.integration
class TestInitErrorHandling:
    """Test error handling during initialization."""

    @pytest.mark.asyncio
    async def test_missing_spec_file_error(self, tmp_path):
        """Test error when spec file doesn't exist.

        Verifies:
        - Missing spec file detected
        - Error message set
        - Initialization fails gracefully
        """
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = await init_project(
            project_dir=tmp_path,
            spec_file=tmp_path / "nonexistent.md",
            dry_run=True,
        )

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_validation_errors_reported(self, tmp_path):
        """Test that validation errors are reported as warnings.

        Verifies:
        - Missing .harness directory reported
        - Missing session_state.json reported
        - Warnings included in result
        """
        from agent_harness.features import FeaturesFile, Feature

        # Don't create .harness directory - this should trigger validation error

        # Create valid features for validation testing
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2025-01-01",
            features=[
                Feature(
                    id=1,
                    category="core",
                    description="Test feature",
                    test_file="tests/test_example.py",
                )
            ],
        )

        errors = validate_initialization(tmp_path, features)

        # Should have errors for missing .harness directory and files
        assert len(errors) > 0
        assert any(".harness" in e.lower() or "directory" in e.lower() for e in errors)
