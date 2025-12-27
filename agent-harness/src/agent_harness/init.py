"""Project initialization for agent harness.

Handles initializing a new project or adopting an existing codebase:
1. Parse spec file
2. Detect project mode (new/adopt)
3. Run initializer agent
4. Validate generated files
5. Initialize state
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from agent_harness.agent import AgentRunner
from agent_harness.baseline import TestBaseline, create_baseline_from_test_results, save_baseline
from agent_harness.config import Config, save_config
from agent_harness.features import Feature, FeaturesFile, save_features, validate_features
from agent_harness.prompts.builder import build_system_prompt, build_user_prompt
from agent_harness.state import SessionState, initialize_session_state, save_session_state
from agent_harness.test_runner import run_tests
from agent_harness.tools.executor import ToolExecutor, create_default_handlers
from agent_harness.version import __version__


@dataclass
class InitResult:
    """Result of project initialization."""

    success: bool
    project_dir: Path
    mode: str = ""  # "new" or "adopt"
    features_count: int = 0
    message: str = ""
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class InitConfig:
    """Configuration for initialization."""

    project_dir: Path
    spec_file: Path
    mode: str = "auto"  # "new", "adopt", or "auto"
    dry_run: bool = False
    max_turns: int = 30
    on_response: Optional[Callable] = None


def detect_project_mode(project_dir: Path) -> str:
    """Detect whether this is a new project or existing codebase.

    Args:
        project_dir: Path to project directory.

    Returns:
        "new" if empty/minimal project, "adopt" if existing code.
    """
    # Check for common source directories
    source_indicators = [
        "src",
        "lib",
        "app",
        "main.py",
        "index.js",
        "index.ts",
        "Cargo.toml",
        "go.mod",
        "package.json",
        "requirements.txt",
        "setup.py",
        "pyproject.toml",
    ]

    # Count source files
    source_file_count = 0
    for item in project_dir.iterdir():
        if item.name.startswith("."):
            continue
        if item.name in source_indicators:
            source_file_count += 1
        if item.is_dir() and item.name in ["src", "lib", "app"]:
            # Count files in source directories
            source_file_count += sum(1 for _ in item.rglob("*") if _.is_file())

    # If we find significant code, it's adopt mode
    return "adopt" if source_file_count > 5 else "new"


def parse_spec_file(spec_file: Path) -> dict[str, Any]:
    """Parse the specification file.

    Args:
        spec_file: Path to spec file (txt, md, or json).

    Returns:
        Dict with spec content and metadata.
    """
    if not spec_file.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_file}")

    content = spec_file.read_text()

    # Try to parse as JSON first
    if spec_file.suffix == ".json":
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # Otherwise treat as text content
    return {
        "content": content,
        "format": spec_file.suffix.lstrip("."),
        "path": str(spec_file),
    }


def create_harness_directory(project_dir: Path) -> Path:
    """Create the .harness directory structure.

    Args:
        project_dir: Path to project directory.

    Returns:
        Path to .harness directory.
    """
    harness_dir = project_dir / ".harness"
    harness_dir.mkdir(exist_ok=True)

    # Create subdirectories
    (harness_dir / "checkpoints").mkdir(exist_ok=True)
    (harness_dir / "logs").mkdir(exist_ok=True)

    return harness_dir


def create_default_config(
    project_dir: Path,
    project_name: str,
    mode: str,
) -> Config:
    """Create default configuration for the project.

    Args:
        project_dir: Path to project directory.
        project_name: Name of the project.
        mode: Initialization mode.

    Returns:
        Config object.
    """
    from agent_harness.config import Config, ProjectConfig

    # Create config with default values and just set project name
    config = Config()
    config.project = ProjectConfig(name=project_name)

    return config


def validate_initialization(
    project_dir: Path,
    features: FeaturesFile,
) -> list[str]:
    """Validate the initialization results.

    Args:
        project_dir: Path to project directory.
        features: Features file to validate.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    # Check features.json
    if not features.features:
        errors.append("No features generated")
    else:
        for feature in features.features:
            if not feature.description:
                errors.append(f"Feature {feature.id} missing description")
            if not feature.test_file:
                errors.append(f"Feature {feature.id} missing test_file")
            if not feature.category:
                errors.append(f"Feature {feature.id} missing category")

    # Check harness directory
    harness_dir = project_dir / ".harness"
    if not harness_dir.exists():
        errors.append(".harness directory not created")
    if not (harness_dir / "session_state.json").exists():
        errors.append("session_state.json not created")

    return errors


def run_initializer_agent(
    config: InitConfig,
    spec_content: dict[str, Any],
    mode: str,
) -> tuple[Optional[FeaturesFile], list[str]]:
    """Run the initializer agent to generate project structure.

    Args:
        config: Initialization configuration.
        spec_content: Parsed spec file content.
        mode: "new" or "adopt".

    Returns:
        Tuple of (FeaturesFile or None, list of warnings).
    """
    warnings = []

    # Build prompts
    system_prompt = build_system_prompt("initializer", Config())

    # Build context for initializer
    context_parts = [
        f"Project Directory: {config.project_dir}",
        f"Mode: {mode}",
        "",
        "=== SPECIFICATION ===",
        spec_content.get("content", str(spec_content)),
    ]

    # For adopt mode, include file listing
    if mode == "adopt":
        context_parts.append("")
        context_parts.append("=== EXISTING FILES ===")
        for item in sorted(config.project_dir.rglob("*")):
            if item.is_file() and ".git" not in item.parts:
                rel_path = item.relative_to(config.project_dir)
                context_parts.append(str(rel_path))

    user_prompt = "\n".join(context_parts)

    # Initialize agent
    agent = AgentRunner(model="claude-sonnet-4-20250514", max_tokens=4096)

    # Initialize tool executor
    tool_executor = ToolExecutor(config.project_dir)
    handlers = create_default_handlers(config.project_dir)
    for name, handler in handlers.items():
        tool_executor.register_handler(name, handler)

    def execute_tool(name: str, inputs: dict) -> dict:
        result = tool_executor.execute(name, inputs)
        return result.to_dict()

    # Run agent conversation
    try:
        session = agent.run_conversation(
            initial_message=user_prompt,
            system_prompt=system_prompt,
            session_type="initializer",
            tool_executor=execute_tool,
            max_turns=config.max_turns,
            on_response=config.on_response,
        )

        # Extract features from conversation
        # The agent should have created features.json via tool calls
        features_file = config.project_dir / "features.json"
        if features_file.exists():
            from agent_harness.features import load_features
            return load_features(features_file), warnings
        else:
            warnings.append("Agent did not create features.json")
            return None, warnings

    except Exception as e:
        warnings.append(f"Agent error: {str(e)}")
        return None, warnings


def create_default_features(
    project_name: str,
    spec_content: dict[str, Any],
) -> FeaturesFile:
    """Create default features from spec content.

    Used as fallback if agent fails to generate features.

    Args:
        project_name: Name of the project.
        spec_content: Parsed spec content.

    Returns:
        FeaturesFile with default features.
    """
    # Create a minimal feature from the spec
    features = FeaturesFile(
        project=project_name,
        generated_by="harness-init",
        init_mode="new",
        last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        features=[
            Feature(
                id=1,
                category="core",
                description="Initial project setup from specification",
                test_file="tests/test_core.py",
                verification_steps=["Run tests"],
                passes=False,
            )
        ],
    )

    return features


def initialize_project(config: InitConfig) -> InitResult:
    """Initialize a project for harness use.

    Args:
        config: Initialization configuration.

    Returns:
        InitResult with outcome.
    """
    result = InitResult(
        success=False,
        project_dir=config.project_dir,
    )

    try:
        # 1. Parse spec file
        spec_content = parse_spec_file(config.spec_file)

        # 2. Detect mode if auto
        if config.mode == "auto":
            result.mode = detect_project_mode(config.project_dir)
        else:
            result.mode = config.mode

        # 3. Create harness directory
        harness_dir = create_harness_directory(config.project_dir)

        # 4. Derive project name
        project_name = config.project_dir.name

        # 5. Create default config
        project_config = create_default_config(
            config.project_dir,
            project_name,
            result.mode,
        )
        save_config(project_config, config.project_dir)

        # 6. Create initial state
        state = initialize_session_state(harness_dir)

        # 7. Run initializer agent (or skip for dry run)
        features = None
        if not config.dry_run:
            features, warnings = run_initializer_agent(
                config,
                spec_content,
                result.mode,
            )
            result.warnings.extend(warnings)

        # 8. Create default features if agent failed
        if features is None:
            features = create_default_features(project_name, spec_content)
            result.warnings.append("Using default features (agent did not generate)")

        # 9. Save features
        save_features(config.project_dir / "features.json", features)
        result.features_count = len(features.features)

        # 10. Create initial baseline (if tests exist)
        try:
            test_result = run_tests(config.project_dir)
            if test_result.success:
                baseline = create_baseline_from_test_results(test_result)
                save_baseline(harness_dir / "baseline.json", baseline)
        except Exception:
            result.warnings.append("Could not create test baseline")

        # 11. Validate
        validation_errors = validate_initialization(config.project_dir, features)
        if validation_errors:
            result.warnings.extend(validation_errors)

        result.success = True
        result.message = f"Initialized {project_name} in {result.mode} mode with {result.features_count} features"

    except FileNotFoundError as e:
        result.error = str(e)
    except Exception as e:
        result.error = f"Initialization failed: {str(e)}"

    return result


def init_project(
    project_dir: Path,
    spec_file: Path,
    mode: str = "auto",
    dry_run: bool = False,
    on_response: Optional[Callable] = None,
) -> InitResult:
    """Helper function to initialize a project.

    Args:
        project_dir: Path to project directory.
        spec_file: Path to spec file.
        mode: "new", "adopt", or "auto".
        dry_run: If True, skip agent execution.
        on_response: Callback for agent responses.

    Returns:
        InitResult with outcome.
    """
    config = InitConfig(
        project_dir=project_dir,
        spec_file=spec_file,
        mode=mode,
        dry_run=dry_run,
        on_response=on_response,
    )
    return initialize_project(config)
