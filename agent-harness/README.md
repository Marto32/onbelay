# Agent Harness

Autonomous coding agent orchestration for long-running projects.

## Overview

The Universal Agent Harness enables AI agents to build complete applications across multiple sessions. It solves the "long-running agent problem" where agents lose context between sessions.

## Installation

```bash
# Install with Poetry
cd agent-harness
poetry install

# Or add as a dev dependency to your project
poetry add --group dev git+https://github.com/you/agent-harness.git
```

## Quick Start

```bash
# Initialize harness in your project
poetry run harness init --spec docs/requirements.md

# Run a coding session
poetry run harness run

# Check status
poetry run harness status

# Check project health
poetry run harness health
```

## Commands

- `harness init` - Initialize harness for a new or existing project
- `harness run` - Execute a coding session
- `harness status` - Show project state
- `harness health` - Show project health metrics
- `harness verify` - Verify a specific feature
- `harness pause` / `harness resume` - Control session execution
- `harness cleanup` - Trigger a cleanup session
- `harness logs` - Query event logs

## Configuration

Create a `.harness.yaml` file in your project root:

```yaml
project:
  name: my-project
  description: My awesome project

environment:
  python_version: "3.11"
  package_manager: poetry

testing:
  test_command: pytest
  test_timeout: 300

costs:
  budget_per_session: 5.0
  budget_total: 100.0
```

## License

MIT
