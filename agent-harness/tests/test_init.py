"""Tests for project initialization module."""

import json
from pathlib import Path

import pytest

from agent_harness.init import (
    InitConfig,
    InitResult,
    create_default_config,
    create_default_features,
    create_harness_directory,
    detect_project_mode,
    init_project,
    initialize_project,
    parse_spec_file,
    validate_initialization,
)
from agent_harness.features import FeaturesFile, Feature


class TestInitResult:
    """Tests for InitResult."""

    def test_failed_result(self):
        """Failed result creation."""
        result = InitResult(
            success=False,
            project_dir=Path("/test"),
            error="Spec not found",
        )
        assert result.success is False
        assert result.error == "Spec not found"
        assert result.features_count == 0

    def test_success_result(self):
        """Successful result creation."""
        result = InitResult(
            success=True,
            project_dir=Path("/test"),
            mode="new",
            features_count=5,
            message="Initialized successfully",
        )
        assert result.success is True
        assert result.mode == "new"
        assert result.features_count == 5


class TestInitConfig:
    """Tests for InitConfig."""

    def test_default_config(self, tmp_path):
        """Default configuration values."""
        config = InitConfig(
            project_dir=tmp_path,
            spec_file=tmp_path / "spec.md",
        )
        assert config.mode == "auto"
        assert config.dry_run is False
        assert config.max_turns == 30

    def test_custom_config(self, tmp_path):
        """Custom configuration values."""
        config = InitConfig(
            project_dir=tmp_path,
            spec_file=tmp_path / "spec.md",
            mode="new",
            dry_run=True,
            max_turns=10,
        )
        assert config.mode == "new"
        assert config.dry_run is True
        assert config.max_turns == 10


class TestDetectProjectMode:
    """Tests for detect_project_mode."""

    def test_empty_directory_is_new(self, tmp_path):
        """Empty directory should be new mode."""
        mode = detect_project_mode(tmp_path)
        assert mode == "new"

    def test_directory_with_src_is_adopt(self, tmp_path):
        """Directory with src folder is adopt mode."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        # Create some source files
        for i in range(10):
            (src_dir / f"file{i}.py").write_text("# code")

        mode = detect_project_mode(tmp_path)
        assert mode == "adopt"

    def test_directory_with_package_json_is_adopt(self, tmp_path):
        """Directory with package.json is adopt mode."""
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "src").mkdir()
        for i in range(10):
            (tmp_path / "src" / f"file{i}.js").write_text("// code")

        mode = detect_project_mode(tmp_path)
        assert mode == "adopt"

    def test_minimal_files_is_new(self, tmp_path):
        """Directory with few files is new mode."""
        (tmp_path / "README.md").write_text("# Project")
        (tmp_path / "requirements.txt").write_text("")

        mode = detect_project_mode(tmp_path)
        assert mode == "new"


class TestParseSpecFile:
    """Tests for parse_spec_file."""

    def test_parse_markdown_spec(self, tmp_path):
        """Parse markdown spec file."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# My Project\n\nDescription here.")

        result = parse_spec_file(spec_file)
        assert "content" in result
        assert "# My Project" in result["content"]
        assert result["format"] == "md"

    def test_parse_json_spec(self, tmp_path):
        """Parse JSON spec file."""
        spec_file = tmp_path / "spec.json"
        spec_data = {"name": "test", "features": []}
        spec_file.write_text(json.dumps(spec_data))

        result = parse_spec_file(spec_file)
        assert result["name"] == "test"
        assert result["features"] == []

    def test_parse_text_spec(self, tmp_path):
        """Parse text spec file."""
        spec_file = tmp_path / "spec.txt"
        spec_file.write_text("Build a todo app")

        result = parse_spec_file(spec_file)
        assert result["content"] == "Build a todo app"
        assert result["format"] == "txt"

    def test_spec_not_found(self, tmp_path):
        """Non-existent spec file should raise."""
        with pytest.raises(FileNotFoundError):
            parse_spec_file(tmp_path / "nonexistent.md")


class TestCreateHarnessDirectory:
    """Tests for create_harness_directory."""

    def test_creates_directory(self, tmp_path):
        """Creates .harness directory."""
        harness_dir = create_harness_directory(tmp_path)
        assert harness_dir.exists()
        assert harness_dir == tmp_path / ".harness"

    def test_creates_subdirectories(self, tmp_path):
        """Creates subdirectories."""
        harness_dir = create_harness_directory(tmp_path)
        assert (harness_dir / "checkpoints").exists()
        assert (harness_dir / "logs").exists()

    def test_idempotent(self, tmp_path):
        """Can be called multiple times."""
        create_harness_directory(tmp_path)
        create_harness_directory(tmp_path)  # Should not raise
        assert (tmp_path / ".harness").exists()


class TestCreateDefaultConfig:
    """Tests for create_default_config."""

    def test_creates_config(self, tmp_path):
        """Creates config with project name."""
        config = create_default_config(tmp_path, "my-project", "new")
        assert config.project.name == "my-project"
        assert config.models.default is not None  # Has default model

    def test_config_has_defaults(self, tmp_path):
        """Config has sensible defaults."""
        config = create_default_config(tmp_path, "test", "adopt")
        assert config.costs.per_session_usd > 0
        assert config.costs.total_project_usd > 0


class TestCreateDefaultFeatures:
    """Tests for create_default_features."""

    def test_creates_features(self):
        """Creates features from spec."""
        spec = {"content": "Build a todo app"}
        features = create_default_features("todo-app", spec)

        assert features.project == "todo-app"
        assert len(features.features) >= 1
        assert features.features[0].passes is False

    def test_features_have_required_fields(self):
        """Features have all required fields."""
        spec = {"content": "Test project"}
        features = create_default_features("test", spec)

        feature = features.features[0]
        assert feature.id is not None
        assert feature.category is not None
        assert feature.description is not None
        assert feature.test_file is not None


class TestValidateInitialization:
    """Tests for validate_initialization."""

    def test_valid_initialization(self, tmp_path):
        """Valid initialization has no errors."""
        # Create harness directory
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        (harness_dir / "session_state.json").write_text("{}")

        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[
                Feature(
                    id=1,
                    category="core",
                    description="Test feature",
                    test_file="tests/test.py",
                )
            ],
        )

        errors = validate_initialization(tmp_path, features)
        assert errors == []

    def test_missing_harness_dir(self, tmp_path):
        """Missing .harness directory is an error."""
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[
                Feature(
                    id=1,
                    category="core",
                    description="Test",
                    test_file="tests/test.py",
                )
            ],
        )

        errors = validate_initialization(tmp_path, features)
        assert any(".harness" in e for e in errors)

    def test_empty_features(self, tmp_path):
        """Empty features list is an error."""
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        (harness_dir / "session_state.json").write_text("{}")

        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[],
        )

        errors = validate_initialization(tmp_path, features)
        assert any("No features" in e for e in errors)


class TestInitializeProject:
    """Tests for initialize_project."""

    @pytest.mark.asyncio
    async def test_dry_run_initialization(self, tmp_path):
        """Dry run initialization works."""
        # Create spec file
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test Project\n\nBuild something.")

        config = InitConfig(
            project_dir=tmp_path,
            spec_file=spec_file,
            mode="new",
            dry_run=True,
        )

        result = await initialize_project(config)

        assert result.success is True
        assert result.mode == "new"
        assert (tmp_path / ".harness").exists()
        assert (tmp_path / "features.json").exists()

    @pytest.mark.asyncio
    async def test_spec_not_found_error(self, tmp_path):
        """Missing spec file returns error."""
        config = InitConfig(
            project_dir=tmp_path,
            spec_file=tmp_path / "nonexistent.md",
        )

        result = await initialize_project(config)

        assert result.success is False
        assert "not found" in result.error.lower()


class TestInitProject:
    """Tests for init_project helper."""

    @pytest.mark.asyncio
    async def test_init_project_helper(self, tmp_path):
        """init_project helper works (async)."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test\n\nDescription.")

        result = await init_project(
            project_dir=tmp_path,
            spec_file=spec_file,
            dry_run=True,
        )

        assert isinstance(result, InitResult)
        assert result.success is True
        assert result.features_count >= 1

        assert result.features_count >= 1
