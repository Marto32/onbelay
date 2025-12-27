# Universal Agent Harness User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Your First Project](#your-first-project)
4. [Understanding Sessions](#understanding-sessions)
5. [Feature Management](#feature-management)
6. [Verification System](#verification-system)
7. [Cost Management](#cost-management)
8. [Working with Git](#working-with-git)
9. [Controlling the Harness](#controlling-the-harness)
10. [Advanced Usage](#advanced-usage)
11. [Troubleshooting](#troubleshooting)

---

## Introduction

### Who Is This Guide For

This guide is for developers who want to leverage AI agents to build and maintain software projects across multiple sessions. The Universal Agent Harness is particularly useful for:

- Building complete applications from specifications
- Automating incremental feature development
- Maintaining code quality with test-driven development
- Managing long-running AI coding sessions with context preservation

### Prerequisites

Before using the Universal Agent Harness, you should have:

- Python 3.11 or later installed
- Poetry package manager installed
- Git installed and configured
- An Anthropic API key (set as `ANTHROPIC_API_KEY` environment variable)
- Basic familiarity with command-line tools
- Understanding of test-driven development concepts

### What You Will Learn

By the end of this guide, you will understand how to:

- Initialize projects for autonomous development
- Run and monitor coding sessions
- Manage feature progress and dependencies
- Control costs and budgets
- Handle failures and rollbacks
- Integrate with GitHub Issues
- Troubleshoot common problems

---

## Installation

### System Requirements

| Requirement | Minimum Version |
|-------------|-----------------|
| Python | 3.11+ |
| Poetry | 1.0+ |
| Git | 2.0+ |
| Operating System | macOS, Linux, Windows (WSL) |

### Installing with Poetry

1. Clone or navigate to the agent-harness directory:

```bash
cd agent-harness
```

2. Install dependencies with Poetry:

```bash
poetry install
```

3. Alternatively, add as a development dependency to your project:

```bash
poetry add --group dev git+https://github.com/yourorg/agent-harness.git
```

### Verifying Installation

Run the version command to verify the installation:

```bash
poetry run harness version
```

You should see output similar to:

```
Agent Harness v1.2.0
```

Verify all commands are available:

```bash
poetry run harness --help
```

### Troubleshooting Common Installation Issues

**Poetry not found:**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Python version too old:**
```bash
# Using pyenv
pyenv install 3.11
pyenv local 3.11
```

**Missing API key:**
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Add to your shell profile (`.bashrc`, `.zshrc`) for persistence.

---

## Your First Project

This tutorial walks you through creating and running your first harness-managed project.

### Step 1: Create a Requirements Specification

Create a file describing what you want to build. This can be a markdown file, text file, or JSON.

Create `requirements.md`:

```markdown
# Task Manager CLI

Build a command-line task manager application with the following features:

## Core Features
1. Add new tasks with a description and optional due date
2. List all tasks with status (pending/completed)
3. Mark tasks as complete
4. Delete tasks

## Technical Requirements
- Use Python 3.11+
- Store tasks in a JSON file
- Include comprehensive tests
- Follow PEP 8 style guidelines
```

### Step 2: Initialize the Project

Run the initialization command with your specification:

```bash
poetry run harness init --spec requirements.md
```

The harness will:

1. Detect whether this is a new project or existing codebase
2. Run an AI agent to parse your specification
3. Generate a `features.json` file with discrete features
4. Create the `.harness/` directory structure
5. Create a `.harness.yaml` configuration file
6. Establish a test baseline (if tests exist)

**Expected output:**

```
Harness Initialization
Project: /path/to/your/project
Spec file: requirements.md
Mode: auto

Initializing project...

Initialization successful!
Mode: new
Features: 6

Next steps:
  1. Review features.json
  2. Run 'harness status' to check project state
  3. Run 'harness run' to start coding session
```

### Step 3: Review Generated Files

After initialization, examine the generated files:

**features.json** - Contains all features to be implemented:

```json
{
  "project": "task-manager",
  "generated_by": "harness-init",
  "init_mode": "new",
  "last_updated": "2024-01-15T10:30:00Z",
  "features": [
    {
      "id": 1,
      "category": "core",
      "description": "Add new tasks with description and optional due date",
      "test_file": "tests/test_add_task.py",
      "verification_steps": ["Run pytest tests/test_add_task.py"],
      "size_estimate": "medium",
      "depends_on": [],
      "passes": false,
      "origin": "spec",
      "verification_type": "automated"
    }
  ]
}
```

**.harness.yaml** - Configuration settings:

```yaml
project:
  name: task-manager
  description: Task Manager CLI

environment:
  python_version: "3.11"
  package_manager: poetry

testing:
  test_command: pytest
  test_timeout: 300

costs:
  per_session_usd: 10.0
  per_feature_usd: 25.0
  total_project_usd: 200.0
```

**.harness/** directory structure:

```
.harness/
  session_state.json    # Current session state
  costs.yaml            # Cost tracking
  baseline.json         # Test baseline
  checkpoints/          # Rollback checkpoints
  logs/                 # Event logs
```

### Step 4: Run Your First Session

Start a coding session:

```bash
poetry run harness run
```

The harness will:

1. Run pre-flight checks
2. Select the next feature to implement
3. Create a checkpoint for rollback
4. Launch the AI agent
5. Monitor progress
6. Verify completion via tests
7. Commit changes if verification passes

**During the session, you will see:**

```
Harness Run
Project: task-manager
Target: Next available feature

Status          Running pre-flight checks...
Tokens          0
Turns           0
```

The display updates as the agent works:

```
Status          Agent working...
Tokens          15,432
Turns           8
```

### Step 5: Check Results

After the session completes:

```bash
poetry run harness status
```

**Output:**

```
Project Status: task-manager

Features        1/6 passing (16%)
Next Feature    #2: List all tasks with status

Last Session    1
Status          complete
Next Prompt     coding

Total Sessions  1
Total Cost      $0.23
Total Tokens    15,432
```

Verify specific features:

```bash
poetry run harness verify --feature 1
```

---

## Understanding Sessions

### What Happens During a Session

A session follows this lifecycle:

```
1. Pre-flight Checks
   |
   v
2. Feature Selection
   |
   v
3. Checkpoint Creation
   |
   v
4. Agent Conversation
   |
   v
5. Progress Monitoring
   |
   v
6. Verification
   |
   v
7. State Update
   |
   v
8. Commit (on success)
```

Each phase serves a specific purpose:

1. **Pre-flight Checks**: Validates the environment is ready
2. **Feature Selection**: Picks the next feature based on dependencies
3. **Checkpoint Creation**: Saves state for potential rollback
4. **Agent Conversation**: AI implements the feature
5. **Progress Monitoring**: Detects if agent is stuck
6. **Verification**: Runs tests to confirm completion
7. **State Update**: Updates features.json and session state
8. **Commit**: Creates a git commit on successful verification

### Session Types

The harness uses different session types based on context:

| Type | When Used | Purpose |
|------|-----------|---------|
| `init` | First run | Parse specification and generate features |
| `coding` | Normal operation | Implement a new feature |
| `continuation` | After partial completion | Resume incomplete work |
| `cleanup` | After N sessions | Address code quality issues |

The harness automatically selects the appropriate type.

### How the Agent Works

The agent operates within a structured conversation:

1. Receives orientation context (project state, feature details)
2. Uses tools to read/write files, run commands
3. Follows test-driven development principles
4. Reports progress via structured output
5. Claims completion when tests pass

The agent is constrained by:

- Maximum conversation turns (default: 50)
- Session timeout (default: 60 minutes)
- Context window limits
- Budget constraints

### Monitoring Progress

During a session, the harness monitors:

- **Token usage**: Tracks API costs
- **Turn count**: Number of agent responses
- **File modifications**: Changes made to codebase
- **Test executions**: Test runs by the agent
- **Tool calls**: Commands and file operations

The progress monitor detects when the agent appears stuck:

- No file modifications over extended periods
- Repeated similar actions without progress
- Test failures without changes

When stuck behavior is detected, the harness may:

1. Inject a warning message
2. Force a session end
3. Trigger a continuation with different context

---

## Feature Management

### Understanding features.json

The `features.json` file is the source of truth for project progress:

```json
{
  "project": "my-project",
  "generated_by": "harness-init",
  "init_mode": "new",
  "last_updated": "2024-01-15T10:30:00Z",
  "features": [...]
}
```

Each feature contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique identifier |
| `category` | string | Grouping category |
| `description` | string | What the feature does |
| `test_file` | string | Path to test file for verification |
| `verification_steps` | array | Human-readable verification steps |
| `size_estimate` | string | "small", "medium", or "large" |
| `depends_on` | array | IDs of prerequisite features |
| `passes` | boolean | Whether feature is complete |
| `origin` | string | "spec" or "existing" |
| `verification_type` | string | "automated", "hybrid", or "manual" |
| `note` | string | Optional notes (e.g., skip reason) |

### Feature Lifecycle

Features progress through these states:

```
pending (passes: false)
    |
    v
in_progress (during session)
    |
    +---> complete (passes: true)
    |
    +---> stuck (after max attempts)
    |
    +---> skipped (manual skip)
```

### Dependencies Between Features

Features can declare dependencies using the `depends_on` field:

```json
{
  "id": 3,
  "description": "Delete tasks",
  "depends_on": [1, 2],
  ...
}
```

The harness respects dependencies:

- Feature 3 will not be attempted until features 1 and 2 pass
- Circular dependencies are detected and rejected
- Invalid dependency IDs cause validation errors

View blocked features:

```bash
poetry run harness status
```

### Manual Verification

For features with `verification_type: "manual"` or `"hybrid"`:

1. The harness runs automated tests if available
2. Manual steps are logged for human review
3. Use `harness verify --update` to mark manually verified:

```bash
# After manually testing the feature
poetry run harness verify --feature 5 --update
```

---

## Verification System

### How Verification Works

When a session completes, the harness verifies claims:

1. **Feature Tests**: Runs the test file specified in `test_file`
2. **Regression Check**: Ensures existing tests still pass
3. **Lint Check**: Validates code quality (optional)
4. **Evidence Required**: Agent must demonstrate completion

Verification result determines next steps:

| Result | Action |
|--------|--------|
| All tests pass | Mark feature complete, commit changes |
| Feature tests fail | Keep feature pending, log failure |
| Regression detected | Rollback to checkpoint |

### Test-Driven Development

The harness enforces test-driven development:

1. Each feature must have an associated test file
2. Tests are written first (or specified in features.json)
3. Feature is only complete when tests pass
4. No manual marking of completion without test evidence

Configure testing in `.harness.yaml`:

```yaml
testing:
  test_command: pytest
  test_timeout: 300  # seconds

verification:
  require_evidence: true
  harness_verify: true
  max_features_per_session: 1
  regression_check: true
```

### Handling Failures

When verification fails:

1. **Feature tests fail:**
   - Feature remains in pending state
   - `stuck_count` is incremented
   - Next session uses continuation prompt with failure context

2. **Regressions detected:**
   - Changes are rolled back to checkpoint
   - Session marked as failed
   - Error logged for investigation

3. **Maximum stuck count reached:**
   - Feature is flagged for human intervention
   - Consider using `harness skip` or manual fixes

### Rollback Mechanism

Checkpoints enable safe rollback:

```bash
# Checkpoints are created automatically at session start
# Located in .harness/checkpoints/

# View checkpoints
ls .harness/checkpoints/

# Manual rollback (if needed)
git reset --hard <checkpoint-commit>
```

Each checkpoint saves:

- Git state (commit reference)
- `features.json` hash
- `claude-progress.txt` hash
- `session_state.json` hash

Rollback restores all state files and git working tree.

---

## Cost Management

### Token Tracking

The harness tracks all API token usage:

```yaml
# .harness/costs.yaml
current_session: null
total_sessions: 5
total_cost_usd: 12.45
total_tokens_input: 125000
total_tokens_output: 45000
by_feature:
  1: 2.50
  2: 3.20
  3: 6.75
session_history:
  - session_id: 1
    cost_usd: 2.50
    ...
```

View current costs:

```bash
poetry run harness status
```

### Budget Limits

Configure budgets in `.harness.yaml`:

```yaml
costs:
  per_session_usd: 10.0    # Max per session
  per_feature_usd: 25.0    # Max per feature (across sessions)
  total_project_usd: 200.0 # Max for entire project
```

When limits are reached:

| Limit Type | Behavior |
|------------|----------|
| Session | Session ends gracefully |
| Feature | Feature marked as blocked, human review needed |
| Project | All sessions blocked until budget increased |

### Cost Optimization Tips

1. **Use appropriate models:**
   ```yaml
   models:
     coding: claude-sonnet-4
     cleanup: claude-haiku-3  # Cheaper for refactoring
   ```

2. **Set reasonable turn limits:**
   ```bash
   poetry run harness run --max-turns 30
   ```

3. **Skip expensive features:**
   ```bash
   poetry run harness skip --feature 10 --reason "Manual implementation preferred"
   ```

4. **Review stuck features:**
   - Features with high `stuck_count` consume budget without progress
   - Consider manual fixes or splitting into smaller features

5. **Monitor per-feature costs:**
   ```bash
   poetry run harness status
   ```

---

## Working with Git

### Checkpoint System

The harness creates git checkpoints for safety:

```
Session Start
    |
    v
Create Checkpoint -----> .harness/checkpoints/checkpoint-1-abc12345/
    |                       - checkpoint.json
    |                       - features.json
    |                       - claude-progress.txt
    |                       - session_state.json
    v
Agent Works...
    |
    +---> Success: Commit changes
    |
    +---> Failure: Rollback to checkpoint
```

Checkpoints are automatically cleaned up based on age and session count.

### Rollback to Checkpoints

If automatic rollback fails or you need manual recovery:

```bash
# View available checkpoints
ls .harness/checkpoints/

# Each checkpoint contains:
# - checkpoint.json: Metadata including git ref
# - Copies of state files

# Manual git rollback:
git log --oneline  # Find checkpoint commit
git reset --hard <commit-hash>

# Restore state files from checkpoint:
cp .harness/checkpoints/<checkpoint-id>/features.json ./features.json
cp .harness/checkpoints/<checkpoint-id>/session_state.json .harness/
```

### Commit Behavior

The harness commits on successful verification:

```
Session 5: Complete feature(s) [3]

Generated with Universal Agent Harness
Session: 5
Feature: 3 - Delete tasks from list
```

Control commit behavior:

```bash
# Skip automatic commit
poetry run harness run --skip-commit

# Commits are only made when:
# - Verification passes
# - No regressions detected
# - --skip-commit not specified
```

---

## Controlling the Harness

### Pause and Resume

Pause to prevent further sessions:

```bash
poetry run harness pause --reason "Waiting for API quota reset"
```

Resume when ready:

```bash
poetry run harness resume
```

While paused:

- `harness run` will refuse to start
- Status shows paused state
- Manual work can be done

### Skip Features

Skip features that should not be automated:

```bash
poetry run harness skip --feature 7 --reason "Requires manual setup"
```

Skipped features:

- Are marked as passing with a "SKIPPED" note
- Will not be selected for future sessions
- Can be un-skipped by editing features.json

### Manual Intervention

For complex situations requiring human work:

```bash
# Hand off to human
poetry run harness handoff --reason "Complex integration work needed"
```

After completing manual work:

```bash
# Take back control and update baseline
poetry run harness takeback
```

The `takeback` command:

1. Updates the test baseline
2. Clears the paused state
3. Allows sessions to resume

### Abort and Recovery

If a session is running and needs to be stopped:

1. Press `Ctrl+C` once for graceful shutdown
2. Press `Ctrl+C` twice for immediate abort

After abort:

```bash
# Check state
poetry run harness status

# If state is corrupted, reset from last checkpoint
# (Manual recovery may be needed)
```

---

## Advanced Usage

### Custom Configuration

Full `.harness.yaml` configuration options:

```yaml
project:
  name: my-project
  github_repo: owner/repo
  description: Project description

environment:
  init: ./init.sh
  reset: ./reset.sh
  python_version: "3.11"
  package_manager: poetry

testing:
  test_command: pytest
  test_timeout: 300

costs:
  per_session_usd: 10.0
  per_feature_usd: 25.0
  total_project_usd: 200.0

models:
  default: claude-sonnet-4
  initializer: claude-sonnet-4
  coding: claude-sonnet-4
  cleanup: claude-haiku-3

context:
  warn_threshold: 0.75
  force_threshold: 0.90

progress:
  check_interval_tokens: 50000
  force_stop_after_stuck_checks: 2

quality:
  lint_command: "poetry run ruff check src/"
  max_file_lines: 500
  cleanup_interval: 10

verification:
  require_evidence: true
  max_features_per_session: 1
  regression_check: true

features:
  max_verification_steps: 7
  max_stuck_sessions: 3

github:
  enabled: false
  repo: owner/repo
  label: harness
  sync_mode: mirror

logging:
  level: important
  retention_days: 90

preflight:
  on_failure: abort

session:
  timeout_minutes: 60
  timeout_warning_minutes: 50
```

### GitHub Integration

Enable GitHub Issues integration:

```yaml
github:
  enabled: true
  repo: owner/repo
  label: harness
  sync_mode: mirror
  create_missing_issues: true
  close_on_verify: true
```

Sync features with GitHub:

```bash
# Authenticate with GitHub CLI first
gh auth login

# Sync features to issues
poetry run harness sync
```

This creates GitHub Issues for pending features and closes them when verified.

### Adopt Mode for Existing Projects

For existing codebases:

```bash
# Scan project structure
poetry run harness scan

# Initialize in adopt mode
poetry run harness init --spec requirements.md --mode adopt
```

Adopt mode:

- Scans existing source files
- Identifies existing test files
- Creates features for remaining work
- Preserves existing structure

### Cleanup Sessions

Trigger code quality cleanup:

```bash
# Schedule cleanup for next session
poetry run harness cleanup

# Run cleanup immediately
poetry run harness cleanup --now
```

Cleanup sessions:

- Address lint errors
- Refactor oversized files
- Improve code organization
- Do not implement new features

Configure automatic cleanup:

```yaml
quality:
  cleanup_interval: 10  # Every 10 sessions
```

---

## Troubleshooting

### Common Issues and Solutions

#### "Missing required files" Error

**Symptom:**
```
Pre-flight failed: harness_files: Missing required files: .harness/, features.json
```

**Solution:**
```bash
poetry run harness init --spec your-spec.md
```

#### "Budget exceeded" Error

**Symptom:**
```
Pre-flight failed: budget: Project budget exceeded
```

**Solution:**
Edit `.harness.yaml` to increase budget:
```yaml
costs:
  total_project_usd: 500.0  # Increase limit
```

#### Tests Failing Unexpectedly

**Symptom:**
Features fail verification despite agent claiming completion.

**Solution:**
1. Run tests manually: `poetry run pytest tests/`
2. Check for environment issues
3. Review test file path in features.json
4. Verify dependencies are installed

#### Agent Appears Stuck

**Symptom:**
High token usage with no visible progress.

**Solution:**
1. Press `Ctrl+C` to stop gracefully
2. Check `harness status` for stuck count
3. Consider:
   - Simplifying the feature description
   - Breaking feature into smaller parts
   - Adding more specific test cases

#### Git State Issues

**Symptom:**
```
Pre-flight warning: git_state: Uncommitted changes: N files
```

**Solution:**
```bash
# Commit or stash changes before running
git add . && git commit -m "WIP"
# or
git stash
```

### Reading Logs

Query event logs for debugging:

```bash
# View recent events
poetry run harness logs

# Filter by session
poetry run harness logs --session last

# Filter by level
poetry run harness logs --level critical

# Search for specific content
poetry run harness logs --query "error"
```

Log levels:

| Level | Description |
|-------|-------------|
| `debug` | Detailed debugging information |
| `routine` | Normal operations |
| `important` | Key decisions and milestones |
| `critical` | Errors and failures |

Log files are stored in `.harness/logs/`:

```
.harness/logs/
  events.jsonl       # All events
  decisions.jsonl    # Decision events
  errors.jsonl       # Error events
  agent_actions.jsonl # Agent tool calls
```

### Debug Commands

```bash
# Verbose output
poetry run harness run --verbose

# Dry run (no agent execution)
poetry run harness run --dry-run

# Skip pre-flight checks
poetry run harness run --skip-preflight

# Skip test verification
poetry run harness run --skip-tests

# Check project health
poetry run harness health

# Quick health check (no tests)
poetry run harness health --quick
```

### Getting Help

1. **Check command help:**
   ```bash
   poetry run harness --help
   poetry run harness <command> --help
   ```

2. **Review this guide:**
   Common patterns and solutions are documented above.

3. **Check logs:**
   ```bash
   poetry run harness logs --level important --limit 50
   ```

4. **Inspect state files:**
   ```bash
   cat .harness/session_state.json
   cat features.json
   ```

5. **Verify environment:**
   ```bash
   poetry run harness health
   python --version
   poetry --version
   git --version
   echo $ANTHROPIC_API_KEY
   ```

---

## Quick Reference

### Essential Commands

| Command | Purpose |
|---------|---------|
| `harness init --spec FILE` | Initialize project |
| `harness run` | Execute coding session |
| `harness status` | Show project status |
| `harness health` | Show project health |
| `harness verify --feature N` | Verify specific feature |
| `harness pause` | Pause harness |
| `harness resume` | Resume harness |
| `harness logs` | Query event logs |

### File Reference

| File | Purpose |
|------|---------|
| `features.json` | Feature definitions and status |
| `.harness.yaml` | Configuration |
| `.harness/session_state.json` | Current session state |
| `.harness/costs.yaml` | Cost tracking |
| `.harness/baseline.json` | Test baseline |
| `.harness/checkpoints/` | Rollback checkpoints |
| `.harness/logs/` | Event logs |
| `claude-progress.txt` | Session progress log |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error occurred |
| 130 | Interrupted by user (Ctrl+C) |

---

*This guide covers the Universal Agent Harness v1.2.0. For updates and additional documentation, refer to the project repository.*
