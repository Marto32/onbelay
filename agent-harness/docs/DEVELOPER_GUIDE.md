# Universal Agent Harness - Developer Guide

This guide provides comprehensive documentation for developers contributing to the Universal Agent Harness project.

## Table of Contents

1. [Getting Started as a Developer](#getting-started-as-a-developer)
2. [Architecture Overview](#architecture-overview)
3. [Module Deep Dives](#module-deep-dives)
4. [Key Data Structures](#key-data-structures)
5. [Adding New Features](#adding-new-features)
6. [Testing](#testing)
7. [CLI Development](#cli-development)
8. [Tool System](#tool-system)
9. [Prompt Engineering](#prompt-engineering)
10. [Release Process](#release-process)

---

## Getting Started as a Developer

### Prerequisites

- Python 3.11 or higher
- Poetry (package manager)
- Git

### Cloning the Repository

```bash
git clone https://github.com/onbelay/agent-harness.git
cd agent-harness
```

### Setting Up the Development Environment

1. **Install dependencies with Poetry:**

```bash
poetry install
```

2. **Activate the virtual environment:**

```bash
poetry shell
```

3. **Verify installation:**

```bash
harness --version
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_config.py

# Run with coverage
poetry run pytest --cov=agent_harness
```

### Code Style and Linting

The project uses Ruff for linting and formatting:

```bash
# Check for lint errors
poetry run ruff check src/

# Auto-fix issues
poetry run ruff check src/ --fix

# Format code
poetry run ruff format src/
```

Configuration is in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
```

---

## Architecture Overview

### High-Level System Design

The Universal Agent Harness orchestrates AI coding sessions across multiple runs, maintaining context and state between sessions. It solves the "long-running agent problem" where agents lose context.

```
+-------------------+     +------------------+     +------------------+
|     CLI Layer     |---->|  Session Layer   |---->|   Agent Layer    |
|    (cli.py)       |     | (session.py)     |     |   (agent.py)     |
+-------------------+     +------------------+     +------------------+
         |                        |                        |
         v                        v                        v
+-------------------+     +------------------+     +------------------+
|  Configuration    |     |  State Manager   |     |  Tool Executor   |
|   (config.py)     |     |   (state.py)     |     | (tools/*.py)     |
+-------------------+     +------------------+     +------------------+
         |                        |                        |
         +------------------------+------------------------+
                                  |
                                  v
                    +---------------------------+
                    |     Verification Engine   |
                    | (verification.py,         |
                    |  test_runner.py)          |
                    +---------------------------+
```

### Module Structure

```
src/agent_harness/
|-- __init__.py           # Package initialization
|-- version.py            # Version information
|-- cli.py                # CLI entry point (Click commands)
|-- config.py             # Configuration loading and validation
|-- state.py              # Session state management
|-- features.py           # Feature tracking and validation
|-- session.py            # Session orchestration
|-- agent.py              # Anthropic API integration
|-- preflight.py          # Pre-flight checks
|-- verification.py       # Feature verification engine
|-- test_runner.py        # Pytest execution and parsing
|-- checkpoint.py         # Rollback checkpoints
|-- baseline.py           # Test baseline tracking
|-- costs.py              # Cost tracking
|-- git_ops.py            # Git operations
|-- console.py            # Rich console output
|-- exceptions.py         # Custom exceptions
|-- prompts/              # Prompt templates and builders
|   |-- __init__.py
|   |-- builder.py        # Prompt construction
|   |-- coding.py         # Coding session prompts
|   |-- continuation.py   # Continuation prompts
|   |-- cleanup.py        # Cleanup prompts
|   +-- initializer.py    # Init session prompts
|-- tools/                # Tool system
|   |-- __init__.py
|   |-- schemas.py        # Tool schema definitions
|   |-- definitions.py    # Tool definitions
|   +-- executor.py       # Tool execution
+-- mcp/                  # MCP server integrations
    |-- __init__.py
    |-- manager.py        # MCP management
    +-- puppeteer.py      # Puppeteer integration
```

### Key Components and Their Roles

| Component | Role |
|-----------|------|
| `cli.py` | Entry point, command parsing, user interaction |
| `session.py` | Orchestrates complete session lifecycle |
| `agent.py` | Manages Anthropic API communication |
| `config.py` | Loads and validates YAML configuration |
| `state.py` | Persists session state between runs |
| `features.py` | Tracks feature completion and dependencies |
| `verification.py` | Independently verifies agent claims |
| `preflight.py` | Pre-session environment checks |
| `checkpoint.py` | Creates and restores rollback points |

### Data Flow

1. **Session Start:**
   ```
   CLI -> Preflight -> State Load -> Feature Selection -> Prompt Build
   ```

2. **Agent Loop:**
   ```
   Prompt -> Agent -> Tool Calls -> Executor -> Results -> Agent
   ```

3. **Session End:**
   ```
   Verification -> State Update -> Cost Tracking -> Git Commit
   ```

---

## Module Deep Dives

### Configuration System (config.py)

The configuration system uses nested dataclasses for type-safe configuration:

```python
@dataclass
class Config:
    """Complete harness configuration."""
    project: ProjectConfig
    environment: EnvironmentConfig
    testing: TestingConfig
    costs: CostsConfig
    models: ModelsConfig
    context: ContextConfig
    # ... more sections
```

**Key Functions:**

- `load_config(project_dir)` - Load and validate `.harness.yaml`
- `save_config(config, project_dir)` - Save configuration to file
- `get_default_config()` - Return defaults for all settings

**Adding a New Configuration Section:**

1. Create a new dataclass:
```python
@dataclass
class MyNewConfig:
    setting_a: str = "default"
    setting_b: int = 10
```

2. Add to the main `Config` class:
```python
@dataclass
class Config:
    # ... existing fields
    my_new: MyNewConfig = field(default_factory=MyNewConfig)
```

3. Add validation in `_validate_config()` if needed

### State Management (state.py, features.py)

**SessionState (state.py):**

Tracks session-to-session state:

```python
@dataclass
class SessionState:
    harness_version: str
    schema_version: int
    last_session: int
    status: str  # "complete", "partial", "failed", "paused"
    current_feature: Optional[int]
    next_prompt: str  # "coding", "continuation", "cleanup", "init"
    stuck_count: int
    # ...
```

**Key Functions:**
- `load_session_state(state_dir)` - Load from `.harness/session_state.json`
- `save_session_state(state_dir, state)` - Persist state
- `start_new_session(state, feature_id)` - Initialize new session
- `end_session(state, status, ...)` - Finalize session

**Features (features.py):**

Tracks feature implementation status:

```python
@dataclass
class Feature:
    id: int
    category: str
    description: str
    test_file: str
    verification_steps: list[str]
    size_estimate: str  # "small", "medium", "large"
    depends_on: list[int]
    passes: bool
    origin: str  # "spec", "existing"
    verification_type: str  # "automated", "hybrid", "manual"
```

**Key Functions:**
- `load_features(path)` - Load `features.json`
- `get_next_feature(features_file)` - Get next ready feature
- `validate_features(features_file)` - Check for cycles, missing deps
- `mark_feature_complete(features_file, id)` - Update status

### Agent Integration (agent.py, prompts/)

**AgentRunner Class:**

Handles Anthropic API communication:

```python
class AgentRunner:
    def __init__(self, api_key, model, max_tokens):
        self.client = Anthropic(api_key=self.api_key)

    def send_message(self, messages, system_prompt, tools):
        # Single API call

    def run_conversation(self, initial_message, system_prompt,
                         tool_executor, max_turns):
        # Full conversation loop with tool use
```

**Prompt Building (prompts/builder.py):**

```python
def build_system_prompt(session_type, config) -> str:
    """Build system prompt for session type."""

def build_user_prompt(orientation, additional_context) -> str:
    """Build initial user message."""

def select_prompt_type(state, features, config) -> str:
    """Select prompt type based on state."""
```

### Verification System (verification.py, test_runner.py)

**Verification Flow:**

1. Run feature-specific tests
2. Check for regressions against baseline
3. Run lint checks
4. Return verification result

```python
def verify_feature_completion(
    project_dir: Path,
    feature: Feature,
    baseline: TestBaseline,
    config: VerificationConfig,
) -> VerificationResult:
```

**Test Runner (test_runner.py):**

```python
def run_tests(
    project_dir: Path,
    test_path: Optional[str] = None,
    timeout: int = 300,
) -> TestRunResult:
    """Run pytest and return structured results."""
```

### Session Lifecycle (session.py, preflight.py)

**SessionOrchestrator:**

Orchestrates the complete session lifecycle:

1. Pre-flight checks
2. Prompt selection
3. State initialization
4. Checkpoint creation
5. Agent conversation
6. Progress monitoring
7. Verification
8. State updates
9. Git commit

```python
class SessionOrchestrator:
    def run_session(self, session_config: SessionConfig) -> SessionResult:
        # 1. Pre-flight checks
        preflight = run_preflight_checks(...)

        # 2. Select prompt type
        prompt_type = select_prompt_type(state, features, config)

        # 3-4. Start session and create checkpoint
        state = start_new_session(state, feature_id)
        checkpoint = create_checkpoint(...)

        # 5. Generate prompts and run agent
        agent_session = self._run_agent_loop(...)

        # 6-9. Verify, update state, commit
        verification = verify_feature_completion(...)
        # ...
```

**Pre-flight Checks (preflight.py):**

```python
def run_preflight_checks(project_dir, config, skip_tests):
    # 1. Working directory exists
    # 2. Harness files present
    # 3. Git state clean
    # 4. Features file valid
    # 5. Init script runs
    # 6. Baseline tests pass
    # 7. Budget available
```

### CLI Layer (cli.py)

Uses Click for command-line interface:

```python
@click.group()
@click.option("--project-dir", "-p", ...)
@click.option("--verbose", "-v", ...)
@click.version_option(version=__version__)
@pass_context
def main(ctx: HarnessContext, project_dir, verbose):
    """Universal Agent Harness - Autonomous coding agent orchestration."""

@main.command()
@click.option("--spec", "-s", required=True, ...)
@pass_context
def init(ctx: HarnessContext, spec: Path, mode: str, dry_run: bool):
    """Initialize harness for a project."""
```

---

## Key Data Structures

### Config Dataclass

```python
@dataclass
class Config:
    project: ProjectConfig          # name, github_repo, description
    environment: EnvironmentConfig  # init, reset, python_version
    testing: TestingConfig          # unit, e2e, full commands
    costs: CostsConfig             # per_session_usd, total_project_usd
    models: ModelsConfig           # default, initializer, coding models
    context: ContextConfig         # warn_threshold, force_threshold
    progress: ProgressConfig       # check_interval, stuck_warning
    quality: QualityConfig         # lint_command, max_file_lines
    verification: VerificationConfig  # require_evidence, regression_check
    features: FeaturesConfig       # max_verification_steps
    github: GithubConfig          # enabled, repo, sync settings
    logging: LoggingConfig        # level, retention_days
    paths: PathsConfig            # features, progress, state_dir
    tools: ToolsConfig            # filesystem, shell, mcp_servers
    preflight: PreflightConfig    # checks, on_failure
    session: SessionConfig        # timeout_minutes
    compatibility: CompatibilityConfig  # migration settings
    init: InitConfig              # mode (new/adopt)
```

### Feature and FeaturesFile

```python
@dataclass
class Feature:
    id: int                       # Unique identifier
    category: str                 # Feature category
    description: str              # What the feature does
    test_file: str               # Path to test file
    verification_steps: list[str] # Steps to verify
    size_estimate: str           # "small", "medium", "large"
    depends_on: list[int]        # Feature dependencies
    passes: bool                 # Current status
    origin: str                  # "spec" or "existing"
    verification_type: str       # "automated", "hybrid", "manual"
    note: Optional[str]          # Additional notes

@dataclass
class FeaturesFile:
    project: str                 # Project name
    generated_by: str           # Generator version
    init_mode: str              # "new" or "adopt"
    last_updated: str           # ISO timestamp
    features: list[Feature]     # All features
```

### SessionState

```python
@dataclass
class SessionState:
    harness_version: str         # Harness version
    schema_version: int          # State schema version
    last_session: int            # Last session number
    status: str                  # "complete", "partial", "failed", "paused"
    current_feature: Optional[int]  # Feature being worked on
    termination_reason: Optional[str]  # Why session ended
    next_prompt: str             # "coding", "continuation", "cleanup", "init"
    stuck_count: int             # Times agent got stuck
    timestamp: str               # Last update time
    timeout_count: int           # Times session timed out
    total_sessions: int          # Total sessions run
    features_completed_this_session: list[int]  # Features done this session
    last_checkpoint_id: Optional[str]  # Most recent checkpoint
```

### TestBaseline

```python
@dataclass
class TestBaseline:
    session: int                  # Session when baseline was created
    timestamp: str               # Creation time
    passing_tests: list[str]     # Test IDs that were passing
    total_passing: int           # Count of passing tests
    total_tests: int             # Total test count
    pre_existing_failures: list[str]  # Failures from adopt mode
```

### Checkpoint

```python
@dataclass
class Checkpoint:
    id: str                      # Unique checkpoint ID
    timestamp: str               # Creation time
    session: int                 # Session number
    git_ref: str                # Git commit hash
    features_json_hash: str      # Hash of features.json
    progress_file_hash: str      # Hash of progress file
    session_state_hash: str      # Hash of session state
    reason: str                  # Why checkpoint was created
    files_backed_up: list[str]   # Files included in backup
```

---

## Adding New Features

### Where to Add New Functionality

| Type of Change | Location |
|----------------|----------|
| New CLI command | `cli.py` |
| New configuration option | `config.py` |
| New tool for agent | `tools/definitions.py` |
| State tracking change | `state.py` |
| Verification logic | `verification.py` |
| Prompt modifications | `prompts/*.py` |

### Following Existing Patterns

**Example: Adding a New CLI Command**

```python
# In cli.py

@main.command()
@click.option("--option", "-o", type=str, help="Description")
@pass_context
def mycommand(ctx: HarnessContext, option: str):
    """Command description."""
    from agent_harness.my_module import do_something

    try:
        config = ctx.load_config()
        result = do_something(ctx.project_dir, config, option)

        if result.success:
            print_success(result.message)
        else:
            print_error(result.message)
            sys.exit(1)

    except Exception as e:
        print_error(str(e))
        if ctx.verbose:
            traceback.print_exc()
        sys.exit(1)
```

**Example: Adding a New Configuration Section**

```python
# In config.py

@dataclass
class MyFeatureConfig:
    """My feature configuration."""
    enabled: bool = True
    setting: str = "default"

# Add to Config dataclass:
@dataclass
class Config:
    # ... existing fields
    my_feature: MyFeatureConfig = field(default_factory=MyFeatureConfig)
```

### Adding Tests

For every new feature:

1. Create a test file in `tests/`
2. Follow the naming convention: `test_<module>.py`
3. Use pytest fixtures for common setup
4. Test both success and error cases

```python
# tests/test_my_feature.py
import pytest
from agent_harness.my_feature import my_function

class TestMyFeature:
    def test_success_case(self):
        result = my_function(valid_input)
        assert result.success

    def test_error_handling(self):
        with pytest.raises(MyError):
            my_function(invalid_input)
```

### Documentation Requirements

When adding new functionality:

1. Add docstrings to all public functions and classes
2. Update this developer guide if architecture changes
3. Update README.md for user-facing features
4. Add inline comments for complex logic

---

## Testing

### Test Structure

```
tests/
|-- conftest.py           # Shared fixtures
|-- test_config.py        # Configuration tests
|-- test_state.py         # State management tests
|-- test_features.py      # Feature tracking tests
|-- test_verification.py  # Verification tests
|-- test_cli.py           # CLI integration tests
+-- fixtures/             # Test fixtures
    |-- sample_config.yaml
    |-- sample_features.json
    +-- ...
```

### Running Unit Tests

```bash
# All unit tests
poetry run pytest tests/unit -x

# With coverage
poetry run pytest tests/unit --cov=agent_harness --cov-report=html

# Specific test
poetry run pytest tests/unit/test_config.py::TestConfig::test_load_config
```

### Running Integration Tests

```bash
# All integration tests
poetry run pytest tests/e2e -x

# Full test suite
poetry run pytest tests/ -v
```

### Writing New Tests

**Using Fixtures:**

```python
# conftest.py
import pytest
from pathlib import Path
import tempfile

@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_config(temp_project_dir):
    """Create a sample configuration."""
    config_path = temp_project_dir / ".harness.yaml"
    config_path.write_text("""
project:
  name: test-project
""")
    return temp_project_dir
```

**Test Example:**

```python
def test_load_config(sample_config):
    from agent_harness.config import load_config

    config = load_config(sample_config)

    assert config.project.name == "test-project"
    assert config.testing.test_command == "pytest"  # default
```

### Mocking Guidelines

**Mocking External Services:**

```python
from unittest.mock import Mock, patch

def test_agent_runner_with_mock():
    with patch('agent_harness.agent.Anthropic') as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text="response")],
            usage=Mock(input_tokens=100, output_tokens=50)
        )

        runner = AgentRunner(api_key="test-key")
        # ... test code
```

**Mocking File System:**

```python
def test_with_temp_files(temp_project_dir):
    # Create necessary files
    (temp_project_dir / "features.json").write_text('{"features": []}')
    (temp_project_dir / ".harness").mkdir()

    # Test code that reads files
```

---

## CLI Development

### Adding New Commands

1. Define the command in `cli.py`:

```python
@main.command()
@click.option("--required", "-r", required=True, help="Required option")
@click.option("--flag", "-f", is_flag=True, help="Boolean flag")
@click.option(
    "--choice", "-c",
    type=click.Choice(["option1", "option2"]),
    default="option1",
    help="Choice option"
)
@pass_context
def newcommand(ctx: HarnessContext, required: str, flag: bool, choice: str):
    """Description for help text.

    Detailed description of what the command does.
    """
    # Implementation
```

2. Use the context object for shared state:

```python
config = ctx.load_config()  # Lazy-loaded
project_dir = ctx.project_dir
verbose = ctx.verbose
```

### Click Patterns Used

**Common Option Types:**

```python
# Path that must exist
@click.option("--path", type=click.Path(exists=True, path_type=Path))

# Integer with bounds
@click.option("--count", type=click.IntRange(1, 100))

# Multiple values
@click.option("--tag", "-t", multiple=True)
```

**Progress Display:**

```python
from rich.progress import Progress, SpinnerColumn, TextColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console,
) as progress:
    task = progress.add_task("Working...", total=None)
    # Long operation
    progress.update(task, description="Almost done...")
```

### Console Output with Rich

The project uses Rich for terminal output. Use the helpers in `console.py`:

```python
from agent_harness.console import (
    console,           # Raw Rich console
    print_info,        # Informational (cyan)
    print_success,     # Success (green)
    print_warning,     # Warning (yellow)
    print_error,       # Error (red bold)
    print_heading,     # Section heading
    print_panel,       # Content in a box
    create_status_table,  # Status table
)

# Usage
print_heading("Section Title")
print_info("Some information")
print_success("Operation completed")
print_warning("Something to note")
print_error("Something went wrong")

# Tables
from rich.table import Table
table = Table(show_header=True)
table.add_column("Name")
table.add_column("Value")
table.add_row("key", "value")
console.print(table)
```

---

## Tool System

### How Tools Work

Tools are functions the agent can call during a session. The system:

1. **Defines schemas** in `tools/schemas.py`
2. **Creates tool definitions** in `tools/definitions.py`
3. **Executes tools** via `tools/executor.py`

### Adding New Tools

**Step 1: Define the Schema (tools/definitions.py)**

```python
MY_NEW_TOOL = create_tool_schema(
    name="my_new_tool",
    description=(
        "Description of what the tool does. "
        "Include when and why to use it."
    ),
    properties={
        "required_param": {
            "type": "string",
            "description": "Description of this parameter",
        },
        "optional_param": {
            "type": "integer",
            "description": "Optional parameter",
            "default": 10,
        },
    },
    required=["required_param"],
)
```

**Step 2: Add to Tool Collection**

```python
# Add to HARNESS_TOOLS dict
HARNESS_TOOLS: dict[str, ToolSchema] = {
    # ... existing tools
    "my_new_tool": MY_NEW_TOOL,
}

# Add to appropriate session types
CODING_TOOLS = [
    # ... existing tools
    "my_new_tool",
]
```

**Step 3: Create Handler (tools/executor.py)**

```python
def my_new_tool_handler(args: dict[str, Any]) -> ToolExecutionResult:
    """Handler for my_new_tool."""
    required_param = args["required_param"]
    optional_param = args.get("optional_param", 10)

    try:
        # Do the work
        result = do_something(required_param, optional_param)

        return ToolExecutionResult(
            tool_name="my_new_tool",
            success=True,
            result={"output": result},
            metadata={"param": required_param},
        )
    except Exception as e:
        return ToolExecutionResult(
            tool_name="my_new_tool",
            success=False,
            error=str(e),
        )

# Register in create_default_handlers()
handlers["my_new_tool"] = my_new_tool_handler
```

### Tool Schemas

Schemas use Claude's tool format:

```python
@dataclass
class ToolSchema:
    name: str                    # Tool identifier
    description: str             # Help text for agent
    properties: dict[str, PropertySchema]  # Input parameters
    required: list[str]          # Required parameters

@dataclass
class PropertySchema:
    type: str                    # "string", "integer", "boolean", "array", "object"
    description: str             # Parameter description
    enum: Optional[list[str]]    # Allowed values
    default: Optional[Any]       # Default value
    items: Optional[dict]        # For array types
```

### Tool Handlers

Handlers receive arguments and return `ToolExecutionResult`:

```python
@dataclass
class ToolExecutionResult:
    tool_name: str
    success: bool
    result: Any = None           # Return value for agent
    error: Optional[str] = None  # Error message if failed
    execution_time_ms: float = 0.0
    metadata: dict[str, Any]     # Additional info for logging
```

---

## Prompt Engineering

### Prompt System Architecture

```
prompts/
|-- builder.py        # Main prompt construction
|-- coding.py         # Coding session specifics
|-- continuation.py   # Continuation session specifics
|-- cleanup.py        # Cleanup session specifics
+-- initializer.py    # Init session specifics
```

### Prompt Types

| Type | Purpose | Model (default) |
|------|---------|-----------------|
| `init` | Project initialization | claude-sonnet-4 |
| `coding` | Feature implementation | claude-sonnet-4 |
| `continuation` | Continue previous work | claude-sonnet-4 |
| `cleanup` | Code quality improvements | claude-haiku-3 |

### Modifying Prompts

**System Prompt (builder.py):**

```python
BASE_SYSTEM_PROMPT = """You are an expert software engineer...

CORE RULES:
1. Focus on ONE feature per session...
"""

def build_system_prompt(session_type: str, config: Config) -> str:
    lines = [BASE_SYSTEM_PROMPT]

    if session_type == "cleanup":
        lines.append("\nCLEANUP SESSION:")
        lines.append("- Focus on code quality...")
    # Add session-specific instructions

    return "\n".join(lines)
```

**Adding Session-Specific Content:**

```python
# In the appropriate module (e.g., coding.py)

CODING_INSTRUCTIONS = """
CODING SESSION RULES:
- Write tests before implementation
- Follow existing code patterns
- Document your decisions
"""

# Use in build_system_prompt()
if session_type == "coding":
    from agent_harness.prompts.coding import CODING_INSTRUCTIONS
    lines.append(CODING_INSTRUCTIONS)
```

### Testing Prompt Changes

1. **Dry Run Testing:**
```bash
harness run --dry-run
```

2. **Manual Review:**
- Check prompt content in logs
- Verify tool availability
- Test with sample scenarios

3. **Automated Testing:**
```python
def test_coding_prompt_includes_rules():
    prompt = build_system_prompt("coding", get_default_config())
    assert "CORE RULES" in prompt
    assert "ONE feature per session" in prompt
```

---

## Release Process

### Version Bumping

The version is defined in `src/agent_harness/version.py`:

```python
__version__ = "1.2.0"
```

Also update `pyproject.toml`:

```toml
[tool.poetry]
version = "1.2.0"
```

### Versioning Scheme

Follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes to CLI or configuration
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, documentation

### Pre-Release Checklist

1. **Update version numbers:**
   - `src/agent_harness/version.py`
   - `pyproject.toml`

2. **Run full test suite:**
   ```bash
   poetry run pytest tests/ -v
   ```

3. **Check linting:**
   ```bash
   poetry run ruff check src/
   ```

4. **Update CHANGELOG.md:**
   ```markdown
   ## [1.2.0] - 2025-01-15
   ### Added
   - New feature X
   ### Changed
   - Improved Y
   ### Fixed
   - Bug in Z
   ```

5. **Create release commit:**
   ```bash
   git add .
   git commit -m "Release v1.2.0"
   git tag v1.2.0
   ```

### Publishing

```bash
# Build package
poetry build

# Publish to PyPI (if configured)
poetry publish

# Push tags
git push origin main --tags
```

### State Migration

When making breaking changes to state files:

1. Increment `SCHEMA_VERSION` in `state.py`
2. Add migration logic in `migrations.py`
3. Test with old state files

```python
# In migrations.py
def migrate_v1_to_v2(old_state: dict) -> dict:
    """Migrate from schema v1 to v2."""
    new_state = old_state.copy()
    # Apply transformations
    new_state["schema_version"] = 2
    return new_state
```

---

## Appendix: File Reference

| File | Purpose |
|------|---------|
| `cli.py` | CLI commands and entry point |
| `config.py` | Configuration dataclasses and loading |
| `state.py` | Session state management |
| `features.py` | Feature tracking and validation |
| `session.py` | Session orchestration |
| `agent.py` | Anthropic API integration |
| `preflight.py` | Pre-session checks |
| `verification.py` | Feature verification |
| `test_runner.py` | Pytest execution |
| `checkpoint.py` | Rollback checkpoints |
| `baseline.py` | Test baseline tracking |
| `costs.py` | Cost tracking |
| `console.py` | Rich console helpers |
| `git_ops.py` | Git operations |
| `exceptions.py` | Custom exceptions |
| `tools/schemas.py` | Tool schema definitions |
| `tools/definitions.py` | Tool definitions |
| `tools/executor.py` | Tool execution |
| `prompts/builder.py` | Prompt construction |
