# Universal Agent Harness

![Version](https://img.shields.io/badge/version-1.2.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## Overview

The Universal Agent Harness is a CLI tool that orchestrates AI coding agents to build complete software projects autonomously across multiple sessions. It solves the "long-running agent problem" where AI agents lose context between sessions, enabling them to maintain continuity while developing features incrementally.

Built for developers who want to leverage AI agents for substantial coding tasks, the harness manages session state, tracks feature completion, enforces quality gates, and provides cost controls. Instead of manually coordinating agent conversations, you define your requirements once and let the harness manage the entire development lifecycle.

## Features

- **Autonomous Coding Sessions**: Run AI agents that work on your codebase with full tool access, automatically selecting the next feature to implement
- **Feature Tracking with features.json**: Declarative specification of all features with dependencies, test files, and verification steps
- **Test-Driven Verification**: Each feature is verified by running its associated test file before marking as complete
- **Checkpoint and Rollback**: Automatic git-based checkpoints before each session with rollback on failure
- **Cost Tracking**: Per-session and per-project budget controls with detailed token usage tracking
- **GitHub Integration**: Sync features with GitHub Issues for project visibility
- **Progress Monitoring**: Detect stuck agents and automatically intervene with guidance
- **Context Management**: Monitor context window usage and gracefully handle limits
- **Pre-flight Checks**: Validate environment, git state, and baseline tests before sessions
- **Multiple Session Types**: Coding, continuation, cleanup, and initialization sessions

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/agent-harness.git
cd agent-harness

# Install with Poetry
poetry install
```

### Initialize a Project

```bash
# Navigate to your project directory
cd /path/to/your/project

# Initialize the harness with a requirements specification
poetry run harness init --spec docs/requirements.md
```

The initializer agent will:
1. Analyze your specification file
2. Create a `features.json` with all features to implement
3. Set up the `.harness/` directory for state management
4. Create test file stubs for each feature

### Run Your First Session

```bash
# Execute a coding session
poetry run harness run

# Or do a dry run first to see what would happen
poetry run harness run --dry-run
```

### Check Status

```bash
# View project status
poetry run harness status

# View project health metrics
poetry run harness health
```

## Core Concepts

### How the Harness Works

The harness orchestrates a complete session lifecycle:

1. **Pre-flight Checks**: Validates the environment, git state, and baseline tests
2. **Feature Selection**: Identifies the next feature to implement based on dependencies
3. **Checkpoint Creation**: Creates a git-based checkpoint for rollback capability
4. **Prompt Generation**: Builds context-rich prompts including project orientation
5. **Agent Conversation**: Runs the AI agent with tool access (filesystem, shell, etc.)
6. **Progress Monitoring**: Watches for stuck states and intervenes if needed
7. **Verification**: Runs the feature's test file to confirm completion
8. **State Updates**: Updates features.json and session state
9. **Commit on Success**: Creates a git commit with the verified changes

### Session Lifecycle

Each session follows this flow:

```
init -> preflight -> checkpoint -> agent -> verify -> commit -> done
                          |                    |
                          v                    v
                       rollback             retry
```

### Feature-Based Development

Features are the atomic units of work. Each feature in `features.json` includes:

- **ID**: Unique identifier for dependency tracking
- **Description**: What the feature accomplishes
- **Test File**: Path to the test file that verifies completion
- **Verification Steps**: Human-readable steps for verification
- **Dependencies**: List of feature IDs that must pass first
- **Size Estimate**: Small, medium, or large for planning

### Verification System

The harness uses a test-first verification approach:

1. Each feature specifies a `test_file` path
2. After the agent works, the harness runs that test file
3. If all tests pass, the feature is marked complete
4. If tests fail, the feature remains pending for the next session

## CLI Reference

| Command | Description |
|---------|-------------|
| `harness init` | Initialize harness for a project with a specification file |
| `harness run` | Execute a coding session for the next available feature |
| `harness status` | Display current project status and feature progress |
| `harness health` | Show project health metrics (tests, lint, file sizes) |
| `harness verify` | Manually verify a specific feature or all features |
| `harness pause` | Pause harness execution with an optional reason |
| `harness resume` | Resume a paused harness |
| `harness skip` | Skip a feature that cannot or should not be implemented |
| `harness handoff` | Hand off to human developer for manual intervention |
| `harness takeback` | Resume control after human intervention |
| `harness cleanup` | Schedule or run a cleanup session for code quality |
| `harness logs` | Query event logs with filtering |
| `harness scan` | Analyze project structure for adopt mode |
| `harness sync` | Sync features with GitHub Issues |
| `harness migrate` | Migrate state files to current schema version |

### Common Options

```bash
# Global options
harness --project-dir /path/to/project  # Specify project directory
harness --verbose                        # Enable verbose output
harness --version                        # Show version

# Run command options
harness run --dry-run           # Preview without executing
harness run --feature 5         # Work on specific feature
harness run --skip-preflight    # Skip pre-flight checks
harness run --skip-tests        # Skip test verification
harness run --skip-commit       # Skip git commit on success
harness run --max-turns 100     # Set maximum conversation turns
```

## Configuration

Create a `.harness.yaml` file in your project root to customize behavior:

```yaml
project:
  name: my-project
  description: My awesome project
  github_repo: owner/repo

environment:
  python_version: "3.11"
  package_manager: poetry
  init: "./init.sh"
  reset: "./reset.sh"

testing:
  unit: "poetry run pytest tests/unit -x"
  e2e: "poetry run pytest tests/e2e -x"
  full: "poetry run pytest tests/ -v"
  test_command: pytest
  test_timeout: 300

costs:
  per_session_usd: 10.0
  per_feature_usd: 25.0
  total_project_usd: 200.0

models:
  default: claude-sonnet-4
  coding: claude-sonnet-4
  cleanup: claude-haiku-3

context:
  warn_threshold: 0.75
  force_threshold: 0.90

progress:
  check_interval_tokens: 50000
  stuck_warning: "You appear stuck. Consider a different approach."
  force_stop_after_stuck_checks: 2

quality:
  lint_command: "poetry run ruff check src/"
  max_file_lines: 500
  cleanup_interval: 10

verification:
  require_evidence: true
  harness_verify: true
  max_features_per_session: 1
  regression_check: true

github:
  enabled: true
  label: harness
  sync_mode: mirror
  create_missing_issues: true
  close_on_verify: true

logging:
  level: important  # critical, important, routine, debug
  retention_days: 90

preflight:
  on_failure: abort  # abort or warn

session:
  timeout_minutes: 60
  timeout_warning_minutes: 50
```

### Key Configuration Sections

| Section | Purpose |
|---------|---------|
| `project` | Project identity and GitHub repository |
| `environment` | Python version, package manager, setup scripts |
| `testing` | Test commands and timeouts |
| `costs` | Budget limits for sessions, features, and project |
| `models` | AI model selection for different session types |
| `context` | Context window thresholds for warnings |
| `progress` | Stuck detection and intervention settings |
| `quality` | Lint commands and file size limits |
| `verification` | Feature verification requirements |
| `github` | GitHub Issues synchronization |
| `logging` | Log level and retention |

## Project Structure

### Files Created by the Harness

```
your-project/
├── .harness.yaml          # Configuration file
├── features.json          # Feature definitions and status
├── claude-progress.txt    # Session progress log
└── .harness/              # State directory
    ├── state.yaml         # Session state
    ├── costs.yaml         # Cost tracking
    ├── baseline.json      # Test baseline
    ├── file_sizes.json    # File size tracking
    ├── checkpoints/       # Git checkpoint data
    └── logs/              # Event logs
        └── events/
```

### features.json Format

```json
{
  "project": "my-project",
  "generated_by": "harness-init",
  "init_mode": "new",
  "last_updated": "2024-01-15T10:30:00Z",
  "features": [
    {
      "id": 1,
      "category": "core",
      "description": "User authentication with JWT tokens",
      "test_file": "tests/test_auth.py",
      "verification_steps": [
        "Login endpoint returns JWT token",
        "Protected routes require valid token",
        "Token refresh works correctly"
      ],
      "size_estimate": "medium",
      "depends_on": [],
      "passes": false,
      "origin": "spec",
      "verification_type": "automated"
    },
    {
      "id": 2,
      "category": "core",
      "description": "User registration with email verification",
      "test_file": "tests/test_registration.py",
      "verification_steps": [
        "Registration creates user record",
        "Verification email is sent",
        "Email confirmation activates account"
      ],
      "size_estimate": "medium",
      "depends_on": [1],
      "passes": false,
      "origin": "spec",
      "verification_type": "automated"
    }
  ]
}
```

### .harness/ Directory Contents

| File | Purpose |
|------|---------|
| `state.yaml` | Current session state, last session ID, stuck count |
| `costs.yaml` | Accumulated cost and token usage |
| `baseline.json` | Baseline test results for regression detection |
| `file_sizes.json` | File size tracking for quality monitoring |
| `checkpoints/` | Checkpoint data for rollback |
| `logs/events/` | Structured event logs |

## Development

### Setting Up the Development Environment

```bash
# Clone the repository
git clone https://github.com/your-org/agent-harness.git
cd agent-harness

# Install dependencies including dev tools
poetry install

# Activate the virtual environment
poetry shell
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=agent_harness

# Run specific test file
poetry run pytest tests/test_features.py -v
```

### Code Quality

```bash
# Run linter
poetry run ruff check src/

# Run type checking (if configured)
poetry run mypy src/
```

### Project Dependencies

The harness uses these key dependencies:

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude API client for agent conversations |
| `click` | CLI framework |
| `pyyaml` | YAML configuration parsing |
| `gitpython` | Git operations for checkpoints |
| `rich` | Beautiful terminal output |
| `tiktoken` | Token counting for context management |

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with tests
4. Run the test suite: `poetry run pytest`
5. Run the linter: `poetry run ruff check src/`
6. Submit a pull request

## Links

- [Design Documentation](docs/design/) - System architecture and design decisions
- [API Reference](docs/api/) - Detailed module documentation
- [Examples](examples/) - Example projects and configurations

## License

MIT License - see LICENSE file for details.
