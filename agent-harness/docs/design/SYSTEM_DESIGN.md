# Universal Agent Harness

## Design Document v1.2.1

---

## Overview

The Universal Agent Harness is an autonomous coding system that enables AI agents to build complete applications across multiple sessions. It solves the "long-running agent problem" where agents lose context between sessions.

### Core Principles

1. **GitHub is the Single Source of Truth** — All other state is derived/cached
2. **Harness Controls All Writes** — Agents propose, harness disposes (Phase 2+)
3. **Fail Safe, Recover Fast** — Every operation is idempotent and reversible
4. **Human Escape Hatches** — Easy to pause, override, or take over manually
5. **Start Simple, Add Complexity Later** — Serial execution first, parallel later
6. **Observable but Not Bloated** — Log decisions that matter, sample the rest
7. **Cost Aware** — Track spending, enforce budgets
8. **Agent-First Artifacts** — State files designed for agent consumption, not just humans
9. **Graceful Degradation** — When context fills, hand off cleanly to next session
10. **Trust but Verify** — Harness independently validates agent claims *(NEW in v1.2)*
11. **Regression-Proof** — No commit leaves the codebase worse than before *(NEW in v1.2)*

### What's Different in v1.2

| v1.1 (Previous) | v1.2 (This Document) |
|-----------------|----------------------|
| Agent reads orientation files | Harness-generated orientation summary injected |
| Prose verification steps | Executable verification with required test files |
| Agent self-reports completion | Harness independently verifies before accepting |
| Regression detection in Phase 3 | Regression detection in Phase 1 |
| init.sh only | init.sh + reset.sh for recovery |
| No code quality checks | Linting in sanity test, periodic cleanup |
| No stuck detection | Intra-session progress monitoring |
| No feature size guidance | Feature granularity rules for initializer |
| Trust agent's pass claims | Validate max 1 feature per session |
| GitHub sync unspecified | GitHub as best-effort mirror with config |
| Orientation consumes context | Cached/injected orientation reduces token cost |

### What's New in v1.2.1

| v1.2 | v1.2.1 (This Document) |
|------|------------------------|
| Agent runs sanity tests first | Harness pre-flight checks before agent launch |
| Implicit session boundaries | Explicit session definition + wall-clock timeout |
| Implicit tool access | Configurable tools & MCP servers (Puppeteer, etc.) |
| All verification via pytest | Verification types: automated, hybrid, manual |
| `depends_on` unspecified | Full dependency enforcement with cycle detection |
| Checkpoint scope unclear | Explicit rollback granularity with verification |
| Prefixes required | Structured output fallback with heuristics |
| Single model config | Per-prompt-type model selection |
| No migration strategy | Schema versioning with auto-migration |

---

## Distribution & Installation

The harness is a **standalone Python package** distributed via Git. It operates on target projects but doesn't live inside them.

### Harness Repository Structure

```
agent-harness/                    # The harness repo (github.com/you/agent-harness)
├── pyproject.toml                # Package definition
├── poetry.lock
├── README.md
├── src/
│   └── agent_harness/
│       ├── __init__.py
│       ├── cli.py                # Entry point (harness command)
│       ├── harness.py            # Core orchestration logic
│       ├── agents.py             # Agent runner (Claude API)
│       ├── state.py              # State management
│       ├── git_ops.py            # Git operations
│       ├── github_sync.py        # GitHub Issues sync
│       ├── context.py            # Context management / token tracking
│       ├── verification.py       # Harness-side verification (NEW)
│       ├── progress.py           # Stuck detection (NEW)
│       ├── quality.py            # Code quality checks (NEW)
│       ├── orientation.py        # Orientation summary generator (NEW)
│       └── prompts/
│           ├── initializer.md    # Session 0 prompt
│           ├── coding.md         # Sessions 1-N prompt
│           └── continuation.md   # After partial completion
└── tests/
    ├── test_harness.py
    ├── test_state.py
    ├── test_context.py
    ├── test_verification.py      # NEW
    └── test_progress.py          # NEW
```

### Harness pyproject.toml

```toml
# agent-harness/pyproject.toml

[tool.poetry]
name = "agent-harness"
version = "1.2.0"
description = "Autonomous coding agent orchestration for long-running projects"
authors = ["Your Name <you@example.com>"]
readme = "README.md"
packages = [{include = "agent_harness", from = "src"}]

[tool.poetry.dependencies]
python = "^3.11"
anthropic = "^0.40.0"      # Claude SDK
click = "^8.0"             # CLI framework
pyyaml = "^6.0"            # Config parsing
gitpython = "^3.1"         # Git operations
rich = "^13.0"             # Terminal output
tiktoken = "^0.5"          # Token counting (NEW)

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"

[tool.poetry.scripts]
harness = "agent_harness.cli:main"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### Installing in Target Projects

Add the harness as a dev dependency in your project's `pyproject.toml`:

```bash
# Option 1: Add via Poetry CLI (recommended)
cd my-project
poetry add --group dev git+https://github.com/you/agent-harness.git#v1.2.0

# Option 2: Manual edit to pyproject.toml, then install
poetry install
```

```toml
# my-project/pyproject.toml

[tool.poetry.group.dev.dependencies]
# Pin to a specific tag (recommended for stability)
agent-harness = { git = "https://github.com/you/agent-harness.git", tag = "v1.2.0" }

# Or pin to a branch (for tracking latest)
# agent-harness = { git = "https://github.com/you/agent-harness.git", branch = "main" }

# Or pin to exact commit (maximum reproducibility)
# agent-harness = { git = "https://github.com/you/agent-harness.git", rev = "abc1234" }
```

### Running Harness Commands

```bash
# Initialize harness in your project (runs initializer agent)
poetry run harness init --spec docs/requirements.md

# Run a coding session
poetry run harness run

# Run in dry-run mode (preview without executing) [NEW]
poetry run harness run --dry-run

# Check status
poetry run harness status

# Verify a specific feature [NEW]
poetry run harness verify --feature 12

# Check project health [NEW]
poetry run harness health

# Other commands
poetry run harness pause
poetry run harness resume
poetry run harness skip --feature 12
poetry run harness cleanup  # Trigger cleanup phase [NEW]
```

### Harness Version Compatibility (NEW in v1.2.1)

When upgrading the harness mid-project, the harness must handle state file migrations.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VERSION COMPATIBILITY                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STATE FILE VERSIONING:                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  # .harness/session_state.json                                      │   │
│  │  {                                                                  │   │
│  │    "harness_version": "1.2.1",    # Version that created this state│   │
│  │    "schema_version": 3,           # State file schema version       │   │
│  │    "last_session": 7,                                               │   │
│  │    ...                                                              │   │
│  │  }                                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ON HARNESS STARTUP:                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. Read state file schema_version                                  │   │
│  │  2. Compare to current harness schema_version                       │   │
│  │  3. If older: run migrations                                        │   │
│  │  4. If newer: abort with warning                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  MIGRATION EXAMPLE (schema v2 → v3):                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  def migrate_v2_to_v3(state_dir: Path):                            │   │
│  │      """Add timeout tracking introduced in v1.2.1"""               │   │
│  │                                                                     │   │
│  │      session_state = load_json(state_dir / "session_state.json")   │   │
│  │                                                                     │   │
│  │      # Add new fields with defaults                                │   │
│  │      if "timeout_count" not in session_state:                      │   │
│  │          session_state["timeout_count"] = 0                        │   │
│  │                                                                     │   │
│  │      session_state["schema_version"] = 3                           │   │
│  │      save_json(state_dir / "session_state.json", session_state)    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```yaml
# .harness.yaml - Version compatibility config

compatibility:
  # Behavior when state is from older harness version
  on_older_state: migrate      # "migrate" (auto-upgrade) or "abort"

  # Behavior when state is from newer harness version
  on_newer_state: abort        # "abort" (recommended) or "warn"

  # Backup before migration
  backup_before_migrate: true
```

```python
# version.py

HARNESS_VERSION = "1.2.1"
SCHEMA_VERSION = 3

MIGRATIONS = {
    (1, 2): migrate_v1_to_v2,  # Added test_baseline.json
    (2, 3): migrate_v2_to_v3,  # Added timeout tracking, preflight config
}

def check_version_compatibility(state_dir: Path, config: Config) -> VersionCheck:
    """Check and migrate state files if needed."""

    state = load_session_state(state_dir)
    state_schema = state.get("schema_version", 1)

    if state_schema == SCHEMA_VERSION:
        return VersionCheck(compatible=True, migrated=False)

    if state_schema > SCHEMA_VERSION:
        if config.compatibility.on_newer_state == "abort":
            raise IncompatibleVersion(
                f"State was created with harness v{state.get('harness_version', 'unknown')} "
                f"(schema {state_schema}), but current harness is v{HARNESS_VERSION} "
                f"(schema {SCHEMA_VERSION}). Please upgrade the harness."
            )
        else:
            log_warning("State is from newer harness version, proceeding with caution")
            return VersionCheck(compatible=True, migrated=False, warning=True)

    # state_schema < SCHEMA_VERSION: need migration
    if config.compatibility.on_older_state == "abort":
        raise IncompatibleVersion(
            f"State needs migration from schema {state_schema} to {SCHEMA_VERSION}. "
            f"Run 'harness migrate' or set on_older_state: migrate"
        )

    # Perform migration
    if config.compatibility.backup_before_migrate:
        backup_state_dir(state_dir)

    for from_v in range(state_schema, SCHEMA_VERSION):
        to_v = from_v + 1
        migration_fn = MIGRATIONS.get((from_v, to_v))
        if migration_fn:
            log_event("migration_start", {"from": from_v, "to": to_v})
            migration_fn(state_dir)
            log_event("migration_complete", {"from": from_v, "to": to_v})

    return VersionCheck(compatible=True, migrated=True, from_schema=state_schema)
```

```bash
# CLI commands for version management

# Check compatibility without running
$ harness version
  Harness version: 1.2.1
  Schema version: 3
  Project state schema: 2
  Status: Migration needed (v2 → v3)

  Run 'harness migrate' to upgrade, or 'harness run' will auto-migrate.

# Explicit migration
$ harness migrate
  Backing up .harness/ to .harness.backup.20250116/
  Migrating schema v2 → v3...
  Migration complete.

# Force migration with backup skip (dangerous)
$ harness migrate --no-backup
  WARNING: Proceeding without backup.
  Migrating schema v2 → v3...
  Migration complete.
```

### What Lives Where

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEPARATION OF CONCERNS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  HARNESS REPO (github.com/you/agent-harness)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  The TOOL. Installed as a dependency, not cloned into projects.     │   │
│  │                                                                     │   │
│  │  Contains:                                                          │   │
│  │  • CLI entry point                                                  │   │
│  │  • Orchestration logic                                              │   │
│  │  • Agent prompts (initializer, coding, continuation)                │   │
│  │  • State management code                                            │   │
│  │  • Git/GitHub integration                                           │   │
│  │  • Verification engine (NEW)                                        │   │
│  │  • Progress/stuck detection (NEW)                                   │   │
│  │  • Code quality checks (NEW)                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│                              │                                              │
│                              │ poetry add (fetches into .venv)              │
│                              ▼                                              │
│                                                                             │
│  TARGET PROJECT (your existing repo)                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  YOUR CODE. Harness operates on it via `poetry run harness`.        │   │
│  │                                                                     │   │
│  │  my-project/                                                        │   │
│  │  ├── pyproject.toml        # Has agent-harness as dev dependency   │   │
│  │  ├── poetry.lock           # Locks harness version                 │   │
│  │  ├── .venv/                # Harness installed here (not visible)  │   │
│  │  │                                                                  │   │
│  │  ├── .harness.yaml         # Config (COMMITTED)                    │   │
│  │  ├── features.json         # Feature list (COMMITTED)              │   │
│  │  ├── claude-progress.txt   # Progress log (COMMITTED)              │   │
│  │  ├── init.sh               # Env startup (COMMITTED)               │   │
│  │  ├── reset.sh              # Force clean state (COMMITTED) [NEW]   │   │
│  │  ├── .harness/             # Runtime state (GITIGNORED)            │   │
│  │  │   ├── session_state.json                                        │   │
│  │  │   ├── costs.yaml                                                │   │
│  │  │   ├── test_baseline.json  # Known-passing tests (NEW)          │   │
│  │  │   ├── file_sizes.json     # Track file growth (NEW)            │   │
│  │  │   ├── checkpoints/                                              │   │
│  │  │   └── logs/                                                     │   │
│  │  │       ├── events.jsonl                                          │   │
│  │  │       ├── decisions.jsonl                                       │   │
│  │  │       └── agent_actions.jsonl  # Structured agent log (NEW)    │   │
│  │  │                                                                  │   │
│  │  ├── src/                  # Your application code                 │   │
│  │  └── tests/                # Your tests                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### System Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TRUSTED BOUNDARY                                │
│                         (Harness controls everything here)                   │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   State     │  │  Execution  │  │   Agent     │  │   Event     │       │
│  │   Manager   │  │   Engine    │  │   Runner    │  │   Log       │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                │               │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐                        │
│  │ Orientation │  │ Verification│  │  Progress   │  [NEW IN v1.2]         │
│  │  Generator  │  │   Engine    │  │  Monitor    │                        │
│  └─────────────┘  └─────────────┘  └─────────────┘                        │
│                                                                             │
└─────────┼────────────────┼────────────────┼────────────────┼───────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐
│  GitHub Issues  │ │   Git Repo      │ │  Claude API     │ │  Local Files  │
│  (Best-effort   │ │   (Code)        │ │  (Single Agent) │ │  (Session     │
│   mirror)       │ │                 │ │                 │ │   Authority)  │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └───────────────┘
```

### Two-Prompt Architecture

**Key Insight from Anthropic:** The first session needs a fundamentally different prompt than subsequent sessions. The initializer agent scaffolds the project; coding agents make incremental progress.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TWO-PROMPT ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SESSION 0 (First Run):                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  INITIALIZER PROMPT                                                 │   │
│  │                                                                     │   │
│  │  "You are setting up a new project. Your job is to:                │   │
│  │   1. Analyze the user's requirements                               │   │
│  │   2. Create a comprehensive features.json with ALL features        │   │
│  │   3. Write init.sh and reset.sh scripts                            │   │
│  │   4. Create the initial project structure                          │   │
│  │   5. Write the first claude-progress.txt entry                     │   │
│  │   6. Make an initial git commit                                    │   │
│  │                                                                     │   │
│  │  FEATURE GRANULARITY RULES:                                        │   │
│  │   - Each feature MUST be completable in a single session           │   │
│  │   - If a feature has >7 verification steps, split it               │   │
│  │   - If a feature touches >5 files, split it                        │   │
│  │   - When in doubt, make features smaller                           │   │
│  │                                                                     │   │
│  │  Do NOT implement features yet. Your job is scaffolding only."     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  SESSIONS 1-N (All Subsequent Runs):                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CODING PROMPT                                                      │   │
│  │                                                                     │   │
│  │  [Harness injects orientation summary - agent doesn't read files]  │   │
│  │                                                                     │   │
│  │  "You are continuing work on an existing project.                  │   │
│  │                                                                     │   │
│  │  ORIENTATION SUMMARY (from harness):                               │   │
│  │  {{orientation_summary}}                                           │   │
│  │                                                                     │   │
│  │  Your job is to:                                                   │   │
│  │   1. Run init.sh (or reset.sh if it fails)                         │   │
│  │   2. Run sanity tests (includes linting)                           │   │
│  │   3. Implement the ONE feature indicated above                     │   │
│  │   4. Show verification output as evidence                          │   │
│  │   5. Update claude-progress.txt                                    │   │
│  │   6. Commit with descriptive message                               │   │
│  │                                                                     │   │
│  │  VERIFICATION RULES:                                               │   │
│  │   - You MUST run the test file specified in the feature            │   │
│  │   - You MUST show the test output in your response                 │   │
│  │   - Only mark done if the test file passes                         │   │
│  │   - The harness will independently verify your claim               │   │
│  │                                                                     │   │
│  │  Work on only ONE feature. Leave the codebase clean and passing."  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  CONTINUATION PROMPT (After partial completion):                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  "You are CONTINUING a partially-completed feature.                │   │
│  │                                                                     │   │
│  │  ORIENTATION SUMMARY (from harness):                               │   │
│  │  {{orientation_summary}}                                           │   │
│  │  {{partial_completion_details}}                                    │   │
│  │                                                                     │   │
│  │   Your priority:                                                   │   │
│  │   1. Run init.sh (or reset.sh if it fails)                         │   │
│  │   2. Run sanity tests                                              │   │
│  │   3. COMPLETE the partial feature before starting anything new     │   │
│  │   4. Do NOT restart — continue from where it stopped               │   │
│  │   5. Run the feature's test file and show output                   │   │
│  │                                                                     │   │
│  │  Only after the partial feature is done, consider the next one."   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Harness-Generated Orientation Summary (NEW in v1.2)

Instead of the agent reading files (which consumes context), the harness generates a compact orientation summary:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ORIENTATION SUMMARY (Injected by Harness)                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  The harness generates this and injects it into the system prompt:         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ## Current State                                                   │   │
│  │                                                                     │   │
│  │  **Session:** 8                                                     │   │
│  │  **Project:** my-api                                                │   │
│  │  **Progress:** 12/47 features passing (25%)                         │   │
│  │  **Health:** All tests passing, no lint errors                      │   │
│  │                                                                     │   │
│  │  ## Last Session (Session 7)                                        │   │
│  │  - Completed: Feature #12 (User can update profile)                 │   │
│  │  - Commits: 3 (abc123, def456, ghi789)                              │   │
│  │  - Status: Complete                                                 │   │
│  │                                                                     │   │
│  │  ## Your Task This Session                                          │   │
│  │  **Feature #13:** User can upload profile picture                   │   │
│  │  **Test file:** tests/e2e/test_avatar_upload.py                     │   │
│  │  **Dependencies:** Features #1, #12 (all passing ✓)                 │   │
│  │                                                                     │   │
│  │  ## Key Files                                                       │   │
│  │  - src/api/profile.py (last modified Session 7)                     │   │
│  │  - src/models/user.py (last modified Session 5)                     │   │
│  │                                                                     │   │
│  │  ## Recent Decisions                                                │   │
│  │  - Session 7: Used S3 for file storage (consistent with init)      │   │
│  │  - Session 5: JWT tokens expire after 24 hours                      │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  BENEFITS:                                                                  │
│  • ~500 tokens vs ~5000+ tokens for agent reading files                    │
│  • Harness knows exactly what changed — more accurate than agent parsing   │
│  • Agent can start working immediately                                     │
│  • Consistent format every session                                         │
│                                                                             │
│  WHAT AGENT STILL READS (only if needed):                                  │
│  • Specific source files when implementing                                 │
│  • Test files to understand requirements                                   │
│  • NOT: progress file, features.json, git log (harness summarizes these)  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```python
# orientation.py

def generate_orientation_summary(
    project_dir: Path,
    session_state: SessionState,
    features: FeaturesJson,
    progress: ProgressFile
) -> str:
    """Generate compact orientation for agent injection."""
    
    # Calculate stats
    passing = sum(1 for f in features.features if f.passes)
    total = len(features.features)
    
    # Get last session summary from progress file (just the most recent entry)
    last_entry = progress.get_last_entry()
    
    # Find next feature
    next_feature = find_next_feature(features)
    
    # Get key files for next feature (files likely to be touched)
    key_files = identify_key_files(project_dir, next_feature)
    
    # Extract recent decisions (last 3 sessions)
    recent_decisions = progress.get_recent_decisions(n=3)
    
    return f"""## Current State

**Session:** {session_state.last_session + 1}
**Project:** {features.project}
**Progress:** {passing}/{total} features passing ({100*passing//total}%)
**Health:** {get_health_status(project_dir)}

## Last Session (Session {session_state.last_session})
- Completed: Feature #{last_entry.feature_id} ({last_entry.feature_description})
- Commits: {len(last_entry.commits)} ({', '.join(last_entry.commits[:3])})
- Status: {last_entry.status}

## Your Task This Session
**Feature #{next_feature.id}:** {next_feature.description}
**Test file:** {next_feature.test_file}
**Dependencies:** {format_dependencies(next_feature, features)}

## Key Files
{format_key_files(key_files)}

## Recent Decisions
{format_decisions(recent_decisions)}
"""
```

### Single Agent, Multiple Prompts

We use a **single agent** with different prompts—not multiple specialized agents:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT MODEL                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASE 1 (This Design):                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │                    ┌──────────────────┐                             │   │
│  │                    │   Claude Agent   │                             │   │
│  │                    │   (Sonnet 4)     │                             │   │
│  │                    └────────┬─────────┘                             │   │
│  │                             │                                       │   │
│  │              ┌──────────────┼──────────────┐                        │   │
│  │              ▼              ▼              ▼                        │   │
│  │     ┌────────────┐  ┌────────────┐  ┌────────────┐                 │   │
│  │     │ Initializer│  │  Coding    │  │Continuation│                 │   │
│  │     │   Prompt   │  │  Prompt    │  │  Prompt    │                 │   │
│  │     └────────────┘  └────────────┘  └────────────┘                 │   │
│  │                                                                     │   │
│  │  Same model, same tools, different instructions.                    │   │
│  │  Harness injects orientation summary into prompts.                  │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Direct Writes with Verification

In Phase 1, agents write directly to files. The harness provides safety through checkpoints, rollback, and **independent verification**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 1: DIRECT WRITES + VERIFICATION                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐         ┌───────────┐         ┌─────────────────┐             │
│  │  Agent  │ ──────▶ │   Files   │ ──────▶ │  Agent Claims   │             │
│  └─────────┘ writes  └───────────┘         │  "Feature Done" │             │
│              directly                       └────────┬────────┘             │
│                                                      │                      │
│                                                      ▼                      │
│                                          ┌─────────────────────┐           │
│                                          │  HARNESS VERIFIES   │  [NEW]    │
│                                          │  (runs test file    │           │
│                                          │   independently)    │           │
│                                          └──────────┬──────────┘           │
│                                                     │                       │
│                          ┌──────────────────────────┴──────────────────┐   │
│                          │                                             │   │
│                          ▼                                             ▼   │
│                    ┌──────────┐                                 ┌──────────┐│
│                    │  PASS    │                                 │  FAIL    ││
│                    │  + No    │                                 │ Rollback ││
│                    │  regress │                                 │ or retry ││
│                    │  ───────▶│                                 └──────────┘│
│                    │  Commit  │                                             │
│                    └──────────┘                                             │
│                                                                             │
│  Safety comes from:                                                         │
│  • Checkpoint before each feature                                          │
│  • Harness runs feature test independently (doesn't trust agent)           │
│  • Full regression test before commit                                      │
│  • Automatic rollback on any test failure                                  │
│  • Git history for manual recovery                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Verification System (NEW in v1.2)

### The Problem

Agents sometimes "declare victory" without proper verification. They may:
- Claim a feature works without running tests
- Run tests but misinterpret failures
- Mark multiple features done in one session
- Break previously-working features (regressions)

### Solution: Harness-Side Verification

The harness **never trusts agent claims**. It independently verifies:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VERIFICATION FLOW                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  AGENT CLAIMS: "Feature #13 is complete"                                   │
│                                                                             │
│                         │                                                   │
│                         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: VALIDATE CLAIM COUNT                                       │   │
│  │                                                                     │   │
│  │  newly_passing = features where passes changed false → true         │   │
│  │                                                                     │   │
│  │  if len(newly_passing) > 1:                                        │   │
│  │      REJECT: "Agent claimed multiple features. Max is 1."          │   │
│  │      ACTION: Revert all, retry session                             │   │
│  │                                                                     │   │
│  │  if len(newly_passing) == 0:                                       │   │
│  │      OK: Agent didn't complete a feature this session              │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                         │                                                   │
│                         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: RUN FEATURE TEST (harness runs, not agent)                 │   │
│  │                                                                     │   │
│  │  feature = get_feature(13)                                         │   │
│  │  result = run_command(f"poetry run pytest {feature.test_file} -v") │   │
│  │                                                                     │   │
│  │  if result.exit_code != 0:                                         │   │
│  │      REJECT: "Feature test failed when harness ran it."            │   │
│  │      ACTION: Revert passes change, agent must fix                  │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                         │                                                   │
│                         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: RUN REGRESSION TEST (all previously-passing features)      │   │
│  │                                                                     │   │
│  │  baseline = load_test_baseline()  # Tests that passed before       │   │
│  │  result = run_command("poetry run pytest tests/ -v")               │   │
│  │                                                                     │   │
│  │  newly_failing = baseline.passing - result.passing                 │   │
│  │                                                                     │   │
│  │  if len(newly_failing) > 0:                                        │   │
│  │      REJECT: f"Regression: {newly_failing} tests now failing"      │   │
│  │      ACTION: Rollback to checkpoint, agent must fix                │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                         │                                                   │
│                         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: RUN CODE QUALITY CHECKS                                    │   │
│  │                                                                     │   │
│  │  result = run_command("poetry run ruff check src/")                │   │
│  │                                                                     │   │
│  │  if result.exit_code != 0:                                         │   │
│  │      WARN: "Lint errors introduced. Agent should fix."             │   │
│  │      ACTION: Continue but flag for cleanup                         │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                         │                                                   │
│                         ▼                                                   │
│                   ┌──────────┐                                             │
│                   │  ACCEPT  │                                             │
│                   │  Commit  │                                             │
│                   │  & Push  │                                             │
│                   └──────────┘                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Test Baseline Tracking

The harness tracks which tests were passing before each session:

```python
# .harness/test_baseline.json

{
  "session": 7,
  "timestamp": "2025-01-16T10:00:00Z",
  "passing_tests": [
    "tests/unit/test_auth.py::test_register",
    "tests/unit/test_auth.py::test_login",
    "tests/unit/test_auth.py::test_logout",
    "tests/e2e/test_registration.py::test_full_flow",
    "tests/e2e/test_login.py::test_full_flow"
  ],
  "total_passing": 5,
  "total_tests": 5
}
```

```python
# verification.py

def update_test_baseline(project_dir: Path) -> TestBaseline:
    """Capture current passing tests as baseline for next session."""
    result = run_tests(project_dir)
    baseline = TestBaseline(
        session=get_current_session(),
        timestamp=now(),
        passing_tests=result.passing_tests,
        total_passing=len(result.passing_tests),
        total_tests=result.total_tests
    )
    save_baseline(baseline)
    return baseline

def check_for_regressions(
    project_dir: Path, 
    baseline: TestBaseline
) -> List[str]:
    """Return list of tests that were passing but now fail."""
    current = run_tests(project_dir)
    return [t for t in baseline.passing_tests if t not in current.passing_tests]
```

### Verification Evidence Requirements

The agent must show evidence of verification in its output:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VERIFICATION EVIDENCE (Required in Agent Output)         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BEFORE marking a feature as passes: true, agent MUST show:                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ## Verification for Feature #13                                    │   │
│  │                                                                     │   │
│  │  **Test file:** tests/e2e/test_avatar_upload.py                     │   │
│  │                                                                     │   │
│  │  **Command run:**                                                   │   │
│  │  ```                                                                │   │
│  │  $ poetry run pytest tests/e2e/test_avatar_upload.py -v            │   │
│  │  ```                                                                │   │
│  │                                                                     │   │
│  │  **Output:**                                                        │   │
│  │  ```                                                                │   │
│  │  ==================== test session starts ====================      │   │
│  │  tests/e2e/test_avatar_upload.py::test_upload_valid_image PASSED   │   │
│  │  tests/e2e/test_avatar_upload.py::test_upload_invalid_type PASSED  │   │
│  │  tests/e2e/test_avatar_upload.py::test_upload_too_large PASSED     │   │
│  │  tests/e2e/test_avatar_upload.py::test_avatar_displays PASSED      │   │
│  │  ==================== 4 passed in 2.34s ====================        │   │
│  │  ```                                                                │   │
│  │                                                                     │   │
│  │  **Result:** All tests passing. Marking Feature #13 as complete.   │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  If agent marks feature done WITHOUT showing this evidence:                │
│  → Harness rejects the session and requires re-verification               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Progress Monitoring (NEW in v1.2)

### Stuck Detection

The harness monitors for agents that are burning context without making progress:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STUCK DETECTION                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PROBLEM: Agent tries to fix an error, hits another error, tries again...  │
│  burns through 50% of context without making progress.                     │
│                                                                             │
│  SOLUTION: Monitor progress at intervals, intervene if stuck.              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Every 50k tokens (configurable), harness checks:                   │   │
│  │                                                                     │   │
│  │  PROGRESS INDICATORS:                                               │   │
│  │  • Files changed since last check: ≥1 expected                     │   │
│  │  • Tests run since last check: ≥1 expected                         │   │
│  │  • Commands executed: ≥3 expected                                  │   │
│  │  • Errors repeated: <3 of same error expected                      │   │
│  │                                                                     │   │
│  │  If NO progress indicators:                                         │   │
│  │  → Inject: "You appear to be stuck. Consider a different approach  │   │
│  │     or ask for help by documenting the blocker."                   │   │
│  │                                                                     │   │
│  │  If stuck 2 checks in a row:                                        │   │
│  │  → Inject: "Still stuck. Documenting current state and stopping.   │   │
│  │     Please describe what's blocking you in claude-progress.txt."   │   │
│  │  → Force wrap-up                                                   │   │
│  │                                                                     │   │
│  │  If same error appears 5+ times:                                    │   │
│  │  → Inject: "You've hit the same error 5 times. This approach       │   │
│  │     isn't working. Try something fundamentally different."         │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Progress Monitor Implementation

```python
# progress.py

@dataclass
class ProgressCheckpoint:
    tokens_used: int
    files_changed: Set[str]
    tests_run: int
    commands_executed: int
    errors_seen: Dict[str, int]  # error message -> count

class ProgressMonitor:
    def __init__(self, config: ProgressConfig):
        self.config = config
        self.checkpoints: List[ProgressCheckpoint] = []
        self.current = ProgressCheckpoint(0, set(), 0, 0, {})
    
    def check_progress(self, current_tokens: int) -> Optional[str]:
        """Called periodically. Returns injection message if stuck."""
        
        if current_tokens - self.last_check_tokens < self.config.check_interval:
            return None
        
        # Take checkpoint
        checkpoint = self.current
        self.checkpoints.append(checkpoint)
        self.current = ProgressCheckpoint(current_tokens, set(), 0, 0, {})
        
        # Check for stuck patterns
        if self._is_stuck(checkpoint):
            if self._was_stuck_last_check():
                return self.config.force_stop_message
            return self.config.stuck_warning_message
        
        # Check for repeated errors
        max_error_count = max(checkpoint.errors_seen.values(), default=0)
        if max_error_count >= self.config.max_repeated_errors:
            return self.config.repeated_error_message
        
        return None
    
    def _is_stuck(self, checkpoint: ProgressCheckpoint) -> bool:
        return (
            len(checkpoint.files_changed) < 1 and
            checkpoint.tests_run < 1 and
            checkpoint.commands_executed < 3
        )
    
    def _was_stuck_last_check(self) -> bool:
        if len(self.checkpoints) < 2:
            return False
        return self._is_stuck(self.checkpoints[-2])
```

---

## Code Quality (NEW in v1.2)

### Linting in Sanity Test

Code quality checks are part of the sanity test, not optional:

```yaml
# .harness.yaml

testing:
  sanity:
    health: curl -sf http://localhost:8000/health
    lint: poetry run ruff check src/ --select=E,F,W  # Errors, fatal, warnings
    type_check: poetry run mypy src/ --ignore-missing-imports  # Optional
  unit: poetry run pytest tests/unit -x
  e2e: poetry run pytest tests/e2e -x
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SANITY TEST (includes quality)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BEFORE any implementation work, agent runs:                               │
│                                                                             │
│  1. Health check (app responds)                                            │
│  2. Lint check (no errors introduced)                                      │
│  3. Quick test (existing tests still pass)                                 │
│                                                                             │
│  If ANY fail → agent must fix BEFORE new work                              │
│                                                                             │
│  This catches:                                                              │
│  • Previous session left lint errors                                       │
│  • Previous session broke tests                                            │
│  • App in bad state                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### File Size Tracking

Monitor for code quality degradation:

```python
# .harness/file_sizes.json

{
  "session": 7,
  "files": {
    "src/main.py": {"lines": 245, "session_added": 0},
    "src/api/auth.py": {"lines": 312, "session_added": 3},
    "src/api/profile.py": {"lines": 189, "session_added": 5},
    "src/models/user.py": {"lines": 87, "session_added": 2}
  }
}
```

```python
# quality.py

def check_file_growth(project_dir: Path) -> List[QualityWarning]:
    """Flag files that have grown too large."""
    warnings = []
    sizes = load_file_sizes()
    
    for file, info in sizes.files.items():
        if info.lines > 500:
            warnings.append(QualityWarning(
                file=file,
                message=f"{file} has {info.lines} lines. Consider splitting.",
                severity="warning"
            ))
        
        # Check growth rate
        growth = info.lines - get_size_at_session(file, info.session_added)
        sessions_elapsed = get_current_session() - info.session_added
        if sessions_elapsed > 0 and growth / sessions_elapsed > 50:
            warnings.append(QualityWarning(
                file=file,
                message=f"{file} growing rapidly ({growth} lines in {sessions_elapsed} sessions).",
                severity="info"
            ))
    
    return warnings
```

### Periodic Cleanup Phase

Every N features (configurable), trigger a cleanup session:

```yaml
# .harness.yaml

quality:
  lint_command: poetry run ruff check src/
  max_file_lines: 500
  cleanup_interval: 10  # Every 10 features, do a cleanup session
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLEANUP SESSION (Every N Features)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRIGGERED: After Feature #10, #20, #30, etc.                              │
│                                                                             │
│  CLEANUP PROMPT:                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  "Before starting Feature #21, perform code cleanup:                │   │
│  │                                                                     │   │
│  │   1. Review files flagged for growth:                              │   │
│  │      - src/api/routes.py (523 lines) → split by resource           │   │
│  │      - src/services/user.py (412 lines) → extract helpers          │   │
│  │                                                                     │   │
│  │   2. Fix any lint warnings (currently 12)                          │   │
│  │                                                                     │   │
│  │   3. Remove dead code (unused imports, unreachable code)           │   │
│  │                                                                     │   │
│  │   4. Add missing docstrings to public functions                    │   │
│  │                                                                     │   │
│  │   5. Run full test suite to verify no regressions                  │   │
│  │                                                                     │   │
│  │   This is a CLEANUP session — no new features."                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Context Management

### The Problem

From Anthropic's research:

> "Often, this led to the model running out of context in the middle of its implementation, leaving the next session to start with a feature half-implemented and undocumented."

### Solution: Graceful Handoff + Forced Checkpoint

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTEXT MANAGEMENT                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TOKEN THRESHOLDS:                                                          │
│                                                                             │
│  0%────────────50%────────────75%────────────90%────────────100%           │
│  │              │              │              │               │             │
│  │   Normal     │   Normal     │   Warn       │   Force       │  Hard      │
│  │   operation  │   operation  │   agent      │   wrap-up     │  stop      │
│  │              │              │              │               │             │
│  │              │   [Progress  │              │               │             │
│  │              │    checks]   │              │               │             │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  AT 50% - PROGRESS CHECK (NEW in v1.2):                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Harness silently checks progress indicators.                       │   │
│  │  If stuck, inject warning. Otherwise, continue silently.           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  AT 75% - SOFT WARNING:                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  System injection to agent:                                         │   │
│  │                                                                     │   │
│  │  "Note: You've used 75% of available context. Start planning to    │   │
│  │   wrap up. If you cannot complete this feature soon, document      │   │
│  │   your progress clearly so the next session can continue."         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  AT 90% - FORCED WRAP-UP:                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  System injection to agent:                                         │   │
│  │                                                                     │   │
│  │  "IMPORTANT: Context is nearly full. You must now:                 │   │
│  │   1. Stop implementation work immediately                          │   │
│  │   2. Document exactly where you stopped in claude-progress.txt     │   │
│  │   3. Note what's done, what's partially done, what's left          │   │
│  │   4. Commit current state (even if incomplete)                     │   │
│  │   5. The next session will continue from here                      │   │
│  │                                                                     │   │
│  │   Do NOT try to rush to completion. Clean handoff is better        │   │
│  │   than broken code."                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  AT 100% - HARD STOP:                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Harness actions (agent has no choice):                            │   │
│  │                                                                     │   │
│  │  1. Session terminates immediately                                 │   │
│  │  2. Harness auto-appends to claude-progress.txt:                   │   │
│  │     "SESSION TERMINATED: Context limit reached mid-implementation" │   │
│  │  3. Harness commits with message: "WIP: Context limit reached"     │   │
│  │  4. Next session uses CONTINUATION PROMPT                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Session State Tracking

```python
# .harness/session_state.json

{
  "last_session": 7,
  "status": "partial",           # "complete" | "partial" | "failed"
  "current_feature": 15,
  "termination_reason": "context_limit",  # null | "context_limit" | "user_pause" | "error" | "stuck"
  "next_prompt": "continuation", # "coding" | "continuation" | "cleanup"
  "stuck_count": 0,              # NEW: consecutive sessions stuck on same feature
  "timestamp": "2025-01-16T14:30:00Z"
}
```

### Feature Stuck Escalation (NEW in v1.2)

If a feature fails to complete across multiple sessions:

```python
def check_feature_stuck(state: SessionState, feature_id: int) -> Optional[Escalation]:
    """Escalate if same feature stuck for 3+ sessions."""
    
    if state.current_feature != feature_id:
        # Working on different feature, reset counter
        return None
    
    if state.stuck_count >= 3:
        return Escalation(
            type="feature_stuck",
            feature_id=feature_id,
            sessions=state.stuck_count,
            message=f"Feature #{feature_id} has failed to complete in {state.stuck_count} sessions.",
            options=[
                "Split feature into smaller sub-features",
                "Mark feature as blocked and skip",
                "Manual implementation",
                "Abort"
            ]
        )
    
    return None
```

---

## State Management

### File Layout

```
my-project/
├── .harness.yaml          # Config (COMMITTED) - how to run/test/budget
├── features.json          # Feature list (COMMITTED) - what to build
├── claude-progress.txt    # Progress notes (COMMITTED) - what was done
├── init.sh                # Environment startup (COMMITTED) - how to start
├── reset.sh               # Force clean state (COMMITTED) - recovery [NEW]
├── .harness/              # Runtime state (GITIGNORED)
│   ├── session_state.json # Tracks partial completion
│   ├── costs.yaml         # Cost tracking
│   ├── test_baseline.json # Known-passing tests [NEW]
│   ├── file_sizes.json    # Track file growth [NEW]
│   ├── checkpoints/       # Recovery points
│   └── logs/
│       ├── events.jsonl   # What happened (observability)
│       ├── decisions.jsonl # Why (critical decisions only)
│       └── agent_actions.jsonl  # Structured agent output [NEW]
├── src/                   # Your application code
└── tests/                 # Your tests
```

### features.json (With Required Test Files)

Each feature **must** have a test file for verification:

```json
{
  "project": "my-api",
  "generated_by": "initializer",
  "last_updated": "2025-01-15T10:00:00Z",
  
  "features": [
    {
      "id": 1,
      "category": "auth",
      "description": "User can register with email and password",
      "test_file": "tests/e2e/test_registration.py",
      "verification_steps": [
        "Navigate to /register",
        "Enter email and password",
        "Submit form",
        "Verify user is created in database",
        "Verify user can log in with credentials"
      ],
      "size_estimate": "small",
      "passes": false
    },
    {
      "id": 2,
      "category": "auth", 
      "description": "User can log in with email and password",
      "test_file": "tests/e2e/test_login.py",
      "verification_steps": [
        "Navigate to /login",
        "Enter valid credentials",
        "Submit form",
        "Verify user is redirected to dashboard",
        "Verify session is created"
      ],
      "size_estimate": "small",
      "passes": false
    },
    {
      "id": 3,
      "category": "auth",
      "description": "User can reset password via email",
      "test_file": "tests/e2e/test_password_reset.py",
      "verification_steps": [
        "Navigate to /forgot-password",
        "Enter registered email",
        "Check email for reset link",
        "Click link, enter new password",
        "Verify login with new password works"
      ],
      "size_estimate": "medium",
      "depends_on": [1, 2],
      "passes": false
    }
  ],
  
  "instructions": "IMPORTANT: Only change 'passes' from false to true after the test_file passes. Never remove or edit feature descriptions. Max 1 feature per session."
}
```

### Feature Granularity Rules

The initializer must follow these rules when creating features:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FEATURE GRANULARITY RULES                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Each feature MUST be completable in a single session. Guidelines:         │
│                                                                             │
│  SIZE HEURISTICS:                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ✓ GOOD (fits in one session):                                      │   │
│  │    • ≤7 verification steps                                          │   │
│  │    • ≤5 files touched                                               │   │
│  │    • ≤300 lines of new code                                         │   │
│  │    • One clear user-facing capability                               │   │
│  │                                                                     │   │
│  │  ✗ TOO BIG (split required):                                        │   │
│  │    • >7 verification steps → split by capability                   │   │
│  │    • >5 files touched → split by layer (API, UI, DB)               │   │
│  │    • Multiple user-facing capabilities → separate features         │   │
│  │    • "User can manage X" → split into CRUD operations              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  SPLITTING EXAMPLES:                                                        │
│                                                                             │
│  ✗ BAD: "User can manage their profile"                                    │
│  ✓ GOOD:                                                                    │
│    • "User can view their profile"                                         │
│    • "User can update their display name"                                  │
│    • "User can update their email (with verification)"                     │
│    • "User can upload a profile picture"                                   │
│    • "User can delete their account"                                       │
│                                                                             │
│  ✗ BAD: "Admin dashboard"                                                  │
│  ✓ GOOD:                                                                    │
│    • "Admin can view list of users"                                        │
│    • "Admin can search users by email"                                     │
│    • "Admin can disable a user account"                                    │
│    • "Admin can view system metrics"                                       │
│                                                                             │
│  SIZE ESTIMATE FIELD:                                                       │
│  • "small": 1-3 verification steps, ~100 lines                            │
│  • "medium": 4-5 verification steps, ~200 lines                           │
│  • "large": 6-7 verification steps, ~300 lines                            │
│  • If you think it's "xlarge", SPLIT IT                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### reset.sh (NEW in v1.2)

Created by initializer alongside init.sh:

```bash
#!/bin/bash
# reset.sh - Force clean state (use when init.sh fails)
# Created by initializer agent

set -e

echo "Forcing clean state..."

# Kill any existing processes
echo "Stopping existing processes..."
pkill -f "uvicorn src.main:app" || true
pkill -f "node" || true

# Reset Docker state
echo "Resetting Docker..."
docker-compose down -v --remove-orphans 2>/dev/null || true
docker-compose up -d postgres redis

# Wait for services
echo "Waiting for PostgreSQL..."
until docker-compose exec -T postgres pg_isready 2>/dev/null; do
  sleep 1
done

# Fresh database
echo "Resetting database..."
poetry run alembic downgrade base 2>/dev/null || true
poetry run alembic upgrade head

# Clear caches
echo "Clearing caches..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
rm -rf .coverage htmlcov/ 2>/dev/null || true

# Start fresh
echo "Starting dev server..."
poetry run uvicorn src.main:app --reload --port 8000 &
DEV_SERVER_PID=$!

# Wait for server
echo "Waiting for dev server..."
for i in {1..30}; do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "Development environment ready (clean state)!"
    echo "Dev server PID: $DEV_SERVER_PID"
    exit 0
  fi
  sleep 1
done

echo "ERROR: Dev server failed to start"
exit 1
```

### claude-progress.txt

Same format as v1.1, but agent is now instructed to read only when specifically needed (harness provides summary):

```
================================================================================
CLAUDE PROGRESS LOG - my-api
================================================================================

This file documents what has been done. The harness will summarize recent 
entries for you — you don't need to read the whole file.

--------------------------------------------------------------------------------
SESSION 7 - 2025-01-16 14:30
--------------------------------------------------------------------------------

FEATURE: #12 (User can update profile)

WHAT I DID:
- Added PATCH /api/profile endpoint
- Added validation for display name (2-50 chars)
- Added e2e test for profile update flow
- Updated User model with updated_at timestamp

VERIFICATION:
$ poetry run pytest tests/e2e/test_profile_update.py -v
tests/e2e/test_profile_update.py::test_update_display_name PASSED
tests/e2e/test_profile_update.py::test_update_invalid_name PASSED
tests/e2e/test_profile_update.py::test_update_requires_auth PASSED
==================== 3 passed in 1.23s ====================

DECISIONS:
- Used PATCH instead of PUT for partial updates (REST convention)
- Display name min 2 chars to prevent empty-looking names

CURRENT STATE:
- All tests passing (47 total)
- No lint errors
- Feature #12 complete

NEXT: Feature #13 (User can upload profile picture)

...
```

---

## Session Lifecycle

### Session 0: Initialization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SESSION 0: INITIALIZATION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRIGGER: harness init --spec design-doc.md                                │
│                                                                             │
│  INITIALIZER AGENT ACTIONS:                                                │
│                                                                             │
│  1. ANALYZE REQUIREMENTS                                                    │
│     - Read user's project spec / design doc                                │
│     - Identify all features needed                                         │
│     - Break down into testable units                                       │
│                                                                             │
│  2. CREATE features.json                                                    │
│     - Comprehensive list of ALL features                                   │
│     - Each with test_file path (REQUIRED)                                  │
│     - Each with verification steps                                         │
│     - Each with size_estimate                                              │
│     - APPLY GRANULARITY RULES (≤7 steps, ≤5 files)                        │
│     - All marked passes: false                                             │
│     - Order by logical dependency                                          │
│                                                                             │
│  3. CREATE init.sh AND reset.sh                                            │
│     - init.sh: Start dev environment                                       │
│     - reset.sh: Force clean state (for recovery)                          │
│                                                                             │
│  4. CREATE PROJECT STRUCTURE                                                │
│     - Directory layout                                                     │
│     - Configuration files                                                  │
│     - Base dependencies                                                    │
│     - Linting config (ruff.toml or pyproject.toml section)                │
│                                                                             │
│  5. CREATE TEST STUBS                                                       │
│     - Create empty test files for each feature                            │
│     - Each file has a placeholder test that fails                         │
│     - e.g., def test_placeholder(): pytest.fail("Not implemented")        │
│                                                                             │
│  6. WRITE claude-progress.txt                                              │
│     - Document what was set up                                             │
│     - Record architecture decisions                                        │
│     - Note next priority                                                   │
│                                                                             │
│  7. MAKE INITIAL COMMIT                                                     │
│     - git add -A                                                           │
│     - git commit -m "Initial project setup by initializer agent"          │
│                                                                             │
│  HARNESS ACTIONS (After Initializer Completes):                            │
│  - Validate features.json structure (test_file required for each)         │
│  - Validate feature sizes (flag any with >7 verification steps)           │
│  - Initialize test baseline (all tests should fail initially)             │
│  - Initialize file size tracking                                           │
│  - Set session_state.json: status="complete", next_prompt="coding"        │
│                                                                             │
│  END STATE:                                                                 │
│  - Project scaffolded, no features implemented                             │
│  - features.json has all features with test_file paths                     │
│  - init.sh and reset.sh can manage the environment                        │
│  - Lint config in place                                                    │
│  - Test stubs created for each feature                                     │
│  - claude-progress.txt has Session 0 entry                                 │
│  - Clean git commit                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sessions 1-N: Coding (Normal)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SESSIONS 1-N: CODING (Normal Flow)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRIGGER: harness run (when session_state.next_prompt == "coding")         │
│                                                                             │
│  HARNESS PREPARATION (before agent starts):                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. Generate orientation summary                                    │   │
│  │  2. Identify next feature                                           │   │
│  │  3. Cache features.json in prompt                                   │   │
│  │  4. Load test baseline                                              │   │
│  │  5. Create checkpoint                                               │   │
│  │  6. Initialize progress monitor                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 1: STARTUP (Agent Actions - Minimal)                         │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  1. Run init.sh (or reset.sh if it fails)                          │   │
│  │     "Starting the development environment."                        │   │
│  │     If init.sh fails: "Running reset.sh to force clean state."     │   │
│  │                                                                     │   │
│  │  2. SANITY TEST (includes lint)                                    │   │
│  │     $ poetry run ruff check src/                                   │   │
│  │     $ curl -sf http://localhost:8000/health                        │   │
│  │     $ poetry run pytest tests/ -x --tb=short -q                    │   │
│  │                                                                     │   │
│  │     If broken: FIX FIRST before any new work                       │   │
│  │                                                                     │   │
│  │  NOTE: Agent does NOT need to read progress file, features.json,   │   │
│  │  or git log — harness has provided orientation summary.            │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 2: IMPLEMENTATION (Agent Actions)                            │   │
│  │           [Context warnings + stuck detection active]               │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  3. IMPLEMENT THE ASSIGNED FEATURE                                  │   │
│  │     - Feature ID and test_file from orientation summary            │   │
│  │     - Work on ONLY THIS FEATURE                                    │   │
│  │     - Write code                                                   │   │
│  │     - Write/update tests in the specified test_file                │   │
│  │     - Make incremental commits                                     │   │
│  │                                                                     │   │
│  │  4. VERIFY END-TO-END (with evidence)                              │   │
│  │     - Run the test file:                                           │   │
│  │       $ poetry run pytest {test_file} -v                           │   │
│  │     - SHOW THE OUTPUT in response                                  │   │
│  │     - Only proceed if all tests pass                               │   │
│  │                                                                     │   │
│  │  5. UPDATE features.json                                            │   │
│  │     - Change passes: false → passes: true                          │   │
│  │     - ONLY if test file passed                                     │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 3: CLEANUP (Agent Actions)                                   │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  6. RUN FULL TEST SUITE (regression check)                         │   │
│  │     $ poetry run pytest tests/ -v                                  │   │
│  │     - If any test that was passing before now fails: FIX IT        │   │
│  │                                                                     │   │
│  │  7. RUN LINT CHECK                                                  │   │
│  │     $ poetry run ruff check src/                                   │   │
│  │     - Fix any errors introduced                                    │   │
│  │                                                                     │   │
│  │  8. UPDATE claude-progress.txt                                      │   │
│  │     - What I worked on                                             │   │
│  │     - Verification output (copy/paste test results)                │   │
│  │     - Decisions made                                               │   │
│  │     - Current state                                                │   │
│  │                                                                     │   │
│  │  9. FINAL COMMIT                                                    │   │
│  │     - git add -A                                                   │   │
│  │     - git commit -m "Implement [feature]: [description]"          │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  HARNESS VERIFICATION (After Agent Completes):                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. Validate features.json changes (max 1 feature, only passes)    │   │
│  │  2. Run feature test independently (don't trust agent)             │   │
│  │  3. Run full test suite (check for regressions)                    │   │
│  │  4. Run lint check                                                  │   │
│  │  5. If all pass: accept commit, push, update baseline              │   │
│  │  6. If any fail: reject, rollback, require fix                     │   │
│  │  7. Sync to GitHub Issues                                           │   │
│  │  8. Update cost tracking                                            │   │
│  │  9. Update session state                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sessions 1-N: Continuation (After Partial)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SESSIONS 1-N: CONTINUATION (After Partial)               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRIGGER: harness run (when session_state.next_prompt == "continuation")   │
│                                                                             │
│  HARNESS PREPARATION:                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. Generate orientation summary WITH partial completion details   │   │
│  │  2. Include: what was done, what's left, which files are WIP       │   │
│  │  3. Check stuck_count — escalate if ≥3                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ORIENTATION SUMMARY INCLUDES:                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ## Continuing Partial Feature                                      │   │
│  │                                                                     │   │
│  │  **Feature #15:** User can upload profile picture                   │   │
│  │  **Status:** PARTIAL (context limit in Session 7)                   │   │
│  │  **Test file:** tests/e2e/test_avatar_upload.py                     │   │
│  │                                                                     │   │
│  │  **What's Done:**                                                   │   │
│  │  - Backend endpoint for image upload (/api/profile/avatar) ✓       │   │
│  │  - Image validation (type, size) ✓                                 │   │
│  │  - S3 storage integration ✓                                        │   │
│  │                                                                     │   │
│  │  **What's Left:**                                                   │   │
│  │  - Complete frontend component (src/components/AvatarUpload.tsx)   │   │
│  │  - Wire up to profile page                                         │   │
│  │  - E2E test verification                                           │   │
│  │                                                                     │   │
│  │  **WIP Files:**                                                     │   │
│  │  - src/components/AvatarUpload.tsx (started, ~60% done)            │   │
│  │                                                                     │   │
│  │  **DO NOT restart from scratch. Continue from where it stopped.**  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  REST OF FLOW: Same as normal coding session                               │
│                                                                             │
│  HARNESS POST-SESSION:                                                      │
│  - If feature completed: reset stuck_count to 0                            │
│  - If still partial: increment stuck_count                                 │
│  - If stuck_count >= 3: escalate to human                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sessions: Cleanup (Periodic)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SESSIONS: CLEANUP (Every N Features)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRIGGER: harness run (when session_state.next_prompt == "cleanup")        │
│           Automatically set after every cleanup_interval features          │
│                                                                             │
│  CLEANUP PROMPT:                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  "This is a CLEANUP session. Do not implement new features.        │   │
│  │                                                                     │   │
│  │  ## Quality Issues to Address                                       │   │
│  │                                                                     │   │
│  │  **Large Files (need splitting):**                                  │   │
│  │  - src/api/routes.py (523 lines) → split by resource               │   │
│  │  - src/services/user.py (412 lines) → extract helpers              │   │
│  │                                                                     │   │
│  │  **Lint Warnings:** 12 total                                        │   │
│  │  - 5 unused imports                                                │   │
│  │  - 4 line too long                                                 │   │
│  │  - 3 missing docstrings                                            │   │
│  │                                                                     │   │
│  │  ## Your Tasks                                                      │   │
│  │                                                                     │   │
│  │  1. Split large files into logical modules                         │   │
│  │  2. Fix all lint warnings                                          │   │
│  │  3. Remove dead code (unused functions, commented code)            │   │
│  │  4. Add docstrings to public functions                             │   │
│  │  5. Run full test suite — no regressions allowed                   │   │
│  │                                                                     │   │
│  │  Do NOT change functionality. Focus on code quality only."         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  HARNESS POST-SESSION:                                                      │
│  - Run full test suite (verify no regressions)                             │
│  - Run lint check (should be clean)                                        │
│  - Update file size tracking                                               │
│  - Set next_prompt back to "coding"                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Failure Handling

### Failure Taxonomy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FAILURE TAXONOMY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CATEGORY: VERIFICATION FAILURES (NEW)                                      │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Failure              │ Detection         │ Response                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Agent claims >1 done │ Diff features.json│ Reject all, revert, retry      │
│  Test fails (harness) │ Exit code != 0    │ Reject passes change, fix      │
│  Regression detected  │ Baseline compare  │ Rollback to checkpoint         │
│  No evidence shown    │ Parse agent output│ Reject, require evidence       │
│  Lint errors intro'd  │ Ruff exit code    │ Warn, flag for cleanup         │
│                                                                             │
│  CATEGORY: PROGRESS FAILURES (NEW)                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Failure              │ Detection         │ Response                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Stuck (no progress)  │ Progress monitor  │ Inject warning, then force stop│
│  Repeated errors (5x) │ Error tracking    │ Suggest different approach     │
│  Feature stuck (3 ses)│ Session state     │ Escalate to human              │
│                                                                             │
│  CATEGORY: CONTEXT MANAGEMENT                                               │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Failure              │ Detection         │ Response                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  75% context used     │ Token counter     │ Inject soft warning            │
│  90% context used     │ Token counter     │ Inject force wrap-up message   │
│  100% context used    │ Token counter     │ Hard stop, auto-commit, log    │
│  Agent ignores wrap-up│ No progress write │ Harness auto-appends to log    │
│                                                                             │
│  CATEGORY: ENVIRONMENT FAILURES (ENHANCED)                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Failure              │ Detection         │ Response                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  init.sh fails        │ Exit code != 0    │ Run reset.sh, retry init.sh   │
│  reset.sh fails       │ Exit code != 0    │ Escalate to human              │
│  Port in use          │ Bind error        │ reset.sh kills processes       │
│  Docker bad state     │ Connection error  │ reset.sh resets containers     │
│  DB migration fails   │ Alembic error     │ reset.sh drops and recreates   │
│                                                                             │
│  CATEGORY: API FAILURES                                                     │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Failure              │ Detection         │ Response                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Claude rate limit    │ 429 response      │ Exponential backoff, max 5 min │
│  Claude overloaded    │ 529 response      │ Wait 30s, retry 3x, then pause │
│  Claude timeout       │ No response 120s  │ Retry once, then checkpoint    │
│  Invalid API key      │ 401 response      │ Abort, notify user             │
│  Malformed response   │ JSON parse error  │ Retry once, then log & skip    │
│                                                                             │
│  CATEGORY: GIT FAILURES                                                     │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Failure              │ Detection         │ Response                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Merge conflict       │ git exit code     │ Stash changes, notify user     │
│  Push rejected        │ git exit code     │ Pull, retry once, then pause   │
│  Dirty working tree   │ git status check  │ Stash or abort based on config │
│  Detached HEAD        │ git status check  │ Checkout main, warn user       │
│                                                                             │
│  CATEGORY: GITHUB FAILURES                                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Failure              │ Detection         │ Response                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Rate limit           │ 403 + header      │ Wait for reset, continue       │
│  Issue not found      │ 404 response      │ Create issue or skip           │
│  Network error        │ Connection error  │ Retry 3x, continue without sync│
│  Auth expired         │ 401 response      │ Warn, continue without sync    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Recovery Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RECOVERY FLOWCHART                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                         ┌─────────────┐                                     │
│                         │   FAILURE   │                                     │
│                         └──────┬──────┘                                     │
│                                │                                            │
│                                ▼                                            │
│                    ┌───────────────────────┐                                │
│                    │  Is it a verification │                                │
│                    │  failure?             │                                │
│                    └───────────┬───────────┘                                │
│                          │           │                                      │
│                         YES          NO                                     │
│                          │           │                                      │
│                          ▼           ▼                                      │
│              ┌─────────────────┐  ┌─────────────────┐                      │
│              │ Revert passes   │  │ Is it retryable?│                      │
│              │ change, require │  └────────┬────────┘                      │
│              │ agent fix       │       │        │                          │
│              └─────────────────┘      YES       NO                          │
│                                        │        │                           │
│                                        ▼        ▼                          │
│                            ┌─────────────────┐ ┌─────────────────┐         │
│                            │ Retry with      │ │ Is there a      │         │
│                            │ backoff         │ │ checkpoint?     │         │
│                            │ (max 3 attempts)│ └────────┬────────┘         │
│                            └────────┬────────┘      │        │             │
│                                     │              YES       NO             │
│                             ┌───────┴───────┐       │        │             │
│                             │               │       ▼        ▼             │
│                          SUCCESS         FAIL  ┌──────────┐ ┌──────────┐   │
│                             │               │  │ Rollback │ │ Escalate │   │
│                             ▼               │  │ to       │ │ to human │   │
│                       ┌──────────┐          │  │checkpoint│ └──────────┘   │
│                       │ Continue │          │  └────┬─────┘                │
│                       └──────────┘          │       │                      │
│                                             │       ▼                      │
│                                             │  ┌──────────────┐            │
│                                             └─▶│ Log failure  │            │
│                                                │ Ask user:    │            │
│                                                │ retry/skip/  │            │
│                                                │ abort?       │            │
│                                                └──────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Human Escape Hatches

### Commands for Human Intervention

```bash
# Initialize a new project (runs initializer agent)
$ harness init --spec design-doc.md
  Running initializer agent...
  Created: .harness.yaml (configuration)
  Created: features.json (47 features, all with test_file)
  Created: init.sh, reset.sh
  Created: claude-progress.txt
  Created: test stubs for each feature
  Added .harness/ to .gitignore
  Initial commit: abc123
  Ready for: harness run

# Run a coding session
$ harness run
  Session 5 starting...
  Generating orientation summary...
  Prompt type: coding (previous session completed)
  Agent working on Feature #12: User can update profile
  ...
  Agent claims Feature #12 complete.
  Verifying: running tests/e2e/test_profile_update.py... PASSED
  Verifying: checking for regressions... PASSED (47/47 tests)
  Verifying: lint check... PASSED
  Session complete. Feature #12 verified.

# Run in dry-run mode (preview without executing) [NEW]
$ harness run --dry-run
  Would run Session 5 with:
    Prompt type: coding
    Feature: #12 (User can update profile)
    Test file: tests/e2e/test_profile_update.py
  
  Orientation summary that would be injected:
  [shows summary]
  
  No changes made.

# Verify a specific feature manually [NEW]
$ harness verify --feature 12
  Running verification for Feature #12...
  Test file: tests/e2e/test_profile_update.py
  
  $ poetry run pytest tests/e2e/test_profile_update.py -v
  tests/e2e/test_profile_update.py::test_update_display_name PASSED
  tests/e2e/test_profile_update.py::test_update_invalid_name PASSED
  tests/e2e/test_profile_update.py::test_update_requires_auth PASSED
  
  Feature #12 verification: PASSED

# Check project health [NEW]
$ harness health
  Project: my-api
  
  FEATURES:     12/47 passing (25%)
  TESTS:        52/52 passing (100%)
  LINT:         0 errors, 3 warnings
  
  FILE HEALTH:
    ⚠ src/api/routes.py (456 lines) — consider splitting
    ✓ All other files under 500 lines
  
  OVERALL HEALTH: GOOD
  
  Next cleanup due: After Feature #20

# Check status
$ harness status
  Project: my-api
  Session: 5 (complete)
  Features: 12/47 passing (25%)
  Current: Ready for Feature #13
  Last session: complete
  Next prompt: coding
  Stuck count: 0
  Costs: $5.47 total, $0.92 last session
  Health: GOOD

# Trigger cleanup session manually [NEW]
$ harness cleanup
  Triggering cleanup session...
  [runs cleanup session]

# Pause harness, keep state
$ harness pause
  Pausing after current operation...
  State saved. Resume with: harness resume
  
# Resume paused harness  
$ harness resume
  Resuming from session 5...
  Next prompt: coding
  Feature #13 queued.

# Skip a problematic feature
$ harness skip --feature 12 --reason "Blocked on external API"
  Skipped Feature #12. Added to blocked list.
  Continuing with next feature...

# Override feature status manually
$ harness override --feature 11 --passes true
  WARNING: This bypasses verification. Are you sure? [y/N]: y
  Marked Feature #11 as passes: true.
  Will sync to GitHub at next session end.

# Human does verification
$ harness manual-verify --feature 11
  Please verify Feature #11 manually.
  Test file: tests/e2e/test_profile.py
  
  Run: poetry run pytest tests/e2e/test_profile.py -v
  
  Did all tests pass? [y/n]: y
  Recorded manual verification for Feature #11.

# Take over completely (harness stops, human works)
$ harness handoff
  Harness paused.
  Current state:
    - Feature #12 in progress (not complete)
    - 11/47 features passing
  
  When done, run: harness takeback

# Give control back to harness
$ harness takeback
  Scanning for changes...
  Found: 3 new commits
  Feature #12 test file: tests/e2e/test_profile_update.py
  Running verification... PASSED
  Mark Feature #12 as passes: true? [y/n]: y
  Updated features.json.
  Updating test baseline...
  Resuming autonomous operation...

# Abort everything
$ harness abort
  Are you sure? This will:
    - Stop all operations
    - Keep git commits as-is
    - Clear harness state
  Confirm [y/N]: y
  Harness stopped.
```

### Escalation Triggers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ESCALATION TO HUMAN                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. FEATURE STUCK (3+ sessions) [NEW]                                      │
│     "Feature #15 has failed to complete in 3 sessions."                    │
│     Options: [S]plit feature, [M]anual implement, [K]ip, [A]bort           │
│                                                                             │
│  2. VERIFICATION FAILED AFTER AGENT CLAIMED DONE [NEW]                     │
│     "Agent claimed Feature #12 complete, but harness verification failed." │
│     Options: [R]etry session, [M]anual verify, [S]kip, [A]bort             │
│                                                                             │
│  3. REGRESSION DETECTED [NEW]                                              │
│     "3 previously-passing tests now fail after Session 7."                 │
│     Failing: test_login, test_register, test_profile                       │
│     Options: [R]ollback, [M]anual fix, [A]bort                             │
│                                                                             │
│  4. REPEATED FAILURES                                                       │
│     "Feature #12 has failed verification 3 times."                         │
│     Options: [R]etry, [S]kip, [M]anual fix, [A]bort                        │
│                                                                             │
│  5. SANITY TEST FAILS AFTER FIX ATTEMPT                                    │
│     "App still broken after agent attempted fix."                          │
│     Options: [R]etry, [R]ollback, [M]anual fix, [A]bort                    │
│                                                                             │
│  6. reset.sh FAILED [NEW]                                                  │
│     "Could not recover clean state. Manual intervention needed."           │
│     Options: [M]anual fix environment, [A]bort                             │
│                                                                             │
│  7. BUDGET EXCEEDED                                                         │
│     "Session cost $15.00 exceeds budget $10.00."                           │
│     Options: [I]ncrease budget, [P]ause, [A]bort                           │
│                                                                             │
│  8. DEPENDENCY CYCLE DETECTED                                               │
│     "Feature #20 depends on #21 which depends on #20."                     │
│     Options: [E]dit features.json, [S]kip both, [A]bort                    │
│                                                                             │
│  9. ALL FEATURES CLAIM DONE BUT TESTS FAIL                                 │
│     "47/47 features marked passing but E2E suite has 12 failures."        │
│     Options: [R]eset false positives, [I]nvestigate, [A]bort               │
│                                                                             │
│  10. LARGE FEATURE DETECTED [NEW]                                          │
│      "Feature #25 has 12 verification steps (max recommended: 7)."        │
│      Options: [S]plit feature, [P]roceed anyway, [S]kip                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## GitHub Sync (Clarified in v1.2)

### GitHub as Best-Effort Mirror

GitHub Issues are a **mirror** of local state, not the source of truth:

```yaml
# .harness.yaml

github:
  repo: user/my-api              # Required for sync
  sync_mode: mirror              # "mirror" (default) or "none"
  sync_on_session_end: true      # Sync after each successful session
  create_missing_issues: true    # Create issues for features without them
  close_on_verify: true          # Close issue when feature passes
  on_sync_failure: warn          # "warn" (continue) or "fail" (stop)
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GITHUB SYNC BEHAVIOR                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LOCAL (features.json)          GITHUB (Issues)                            │
│  ─────────────────────          ───────────────                            │
│  Source of truth                Mirror / human visibility                  │
│  Updated during session         Updated at session boundaries              │
│  Binary: passes true/false      Open = incomplete, Closed = verified       │
│                                                                             │
│  SYNC OPERATIONS:                                                           │
│                                                                             │
│  After session completes:                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  for feature in features where passes changed:                      │   │
│  │      if feature.passes == true:                                     │   │
│  │          close_github_issue(feature.id)                             │   │
│  │      else:                                                          │   │
│  │          reopen_github_issue(feature.id)  # (shouldn't happen)     │   │
│  │                                                                     │   │
│  │  if create_missing_issues:                                          │   │
│  │      for feature where no issue exists:                             │   │
│  │          create_github_issue(feature)                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  FAILURE HANDLING:                                                          │
│                                                                             │
│  If GitHub API fails:                                                       │
│  • on_sync_failure: warn → Log warning, continue (session still valid)    │
│  • on_sync_failure: fail → Abort session (rare, for strict workflows)     │
│                                                                             │
│  If issue was manually closed by human:                                     │
│  • Harness doesn't reopen it                                               │
│  • features.json remains authoritative                                     │
│  • Human intervention is respected                                         │
│                                                                             │
│  If issue was manually opened by human:                                     │
│  • Harness will close it if feature.passes == true                        │
│  • Or add comment explaining status                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Cost Management

### Cost Tracking

```yaml
# .harness/costs.yaml (auto-updated by harness)

current_session:
  session_id: 5
  started: "2025-01-15T10:00:00Z"
  tokens:
    input: 145000
    output: 32000
    cached: 45000      # NEW: track cache hits
  cost_usd: 0.92
  
cumulative:
  total_sessions: 5
  total_tokens:
    input: 892000
    output: 187000
    cached: 234000
  total_cost_usd: 5.47
  
  by_feature:
    - feature_id: 1
      cost_usd: 0.45
      sessions: 1
    - feature_id: 2
      cost_usd: 0.67
      sessions: 1
    - feature_id: 15
      cost_usd: 2.85
      sessions: 3        # Took 3 sessions (was stuck)

budgets:
  per_session_usd: 10.00
  per_feature_usd: 25.00
  total_project_usd: 200.00
```

### Cost Optimization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COST OPTIMIZATION                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STRATEGY                  │ IMPLEMENTATION                                 │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Harness-generated         │ Agent doesn't read files for orientation      │
│  orientation (NEW)         │ Saves ~5-15% context per session              │
│                                                                             │
│  Prompt caching            │ System prompt + orientation cacheable         │
│                            │ Track cached tokens in costs.yaml             │
│                                                                             │
│  Single model (Phase 1)    │ Use Sonnet 4 for everything                   │
│                            │ Simpler, good enough for most tasks            │
│                                                                             │
│  Incremental context       │ Don't send full codebase                       │
│                            │ Agent reads files as needed                    │
│                                                                             │
│  Early termination         │ Stuck detection catches spinning early        │
│                            │ Escalate to human instead of burning tokens   │
│                                                                             │
│  Feature size limits       │ Small features = fewer sessions per feature   │
│                            │ Less context waste on continuations           │
│                                                                             │
│  Graceful context handoff  │ Clean handoff preserves work                  │
│                            │ Avoids re-doing partially complete work       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Observability

### Structured Agent Actions (NEW in v1.2)

Agent output is parsed for structured logging:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STRUCTURED AGENT OUTPUT                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Agent is instructed to prefix certain outputs:                            │
│                                                                             │
│  [FILE:READ] src/api/routes.py                                             │
│  [FILE:WRITE] src/api/profile.py                                           │
│  [CMD:RUN] poetry run pytest tests/e2e/test_profile.py -v                 │
│  [CMD:OUTPUT]                                                              │
│  ==================== test session starts ====================              │
│  ...                                                                        │
│  [CMD:EXIT] 0                                                              │
│  [VERIFY:START] Feature #12                                                │
│  [VERIFY:PASS] Feature #12                                                 │
│  [DECISION] Using PATCH instead of PUT for partial updates                │
│                                                                             │
│  Harness parses these into:                                                │
│                                                                             │
│  .harness/logs/agent_actions.jsonl                                         │
│  {"ts": "...", "type": "file_read", "path": "src/api/routes.py"}          │
│  {"ts": "...", "type": "file_write", "path": "src/api/profile.py"}        │
│  {"ts": "...", "type": "cmd_run", "cmd": "poetry run pytest..."}          │
│  {"ts": "...", "type": "cmd_exit", "code": 0}                             │
│  {"ts": "...", "type": "verify_pass", "feature": 12}                      │
│  {"ts": "...", "type": "decision", "text": "Using PATCH..."}              │
│                                                                             │
│  BENEFITS:                                                                  │
│  • Progress monitor can track file changes, commands, etc.                 │
│  • Debugging: exactly what agent did and when                              │
│  • Verification: can confirm agent actually ran tests                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Structured Output Fallback (NEW in v1.2.1)

The prefix system is **best-effort** — the harness degrades gracefully if the agent doesn't use them.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STRUCTURED OUTPUT FALLBACK                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ENFORCEMENT LEVEL: SOFT (configurable)                                     │
│                                                                             │
│  The harness ALWAYS works, even if agent doesn't use prefixes.             │
│  Prefixes enhance observability but aren't required for correctness.       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  FALLBACK BEHAVIOR:                                                 │   │
│  │                                                                     │   │
│  │  If agent uses prefixes:                                            │   │
│  │  ✓ Parsed into structured logs                                     │   │
│  │  ✓ Progress monitor gets rich data                                 │   │
│  │  ✓ Debugging is easy                                               │   │
│  │                                                                     │   │
│  │  If agent omits prefixes:                                           │   │
│  │  ✓ Session still works (not blocked)                               │   │
│  │  • Progress monitor uses heuristics:                                │   │
│  │    - Track tool calls via API response                             │   │
│  │    - Infer file changes from git diff                              │   │
│  │    - Detect test runs from output patterns                         │   │
│  │  • Log: "Agent output not fully structured, using fallback"        │   │
│  │  • Debugging is harder but possible                                │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  CONFIGURATION:                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  # .harness.yaml                                                    │   │
│  │                                                                     │   │
│  │  logging:                                                           │   │
│  │    structured_agent_output: true    # Parse prefixes if present    │   │
│  │    require_prefixes: false          # Don't fail without them      │   │
│  │    fallback_tracking: true          # Use heuristics when missing  │   │
│  │    warn_on_missing_prefixes: true   # Log warning if not used      │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  HEURISTIC TRACKING (when prefixes missing):                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  File changes:                                                      │   │
│  │    $ git diff --name-only HEAD                                     │   │
│  │    → Infer which files agent modified                              │   │
│  │                                                                     │   │
│  │  Commands executed:                                                 │   │
│  │    Parse Claude API response for tool_use with bash/shell          │   │
│  │    → Track commands agent ran                                      │   │
│  │                                                                     │   │
│  │  Tests run:                                                         │   │
│  │    Regex: /pytest.*passed|failed|error/                            │   │
│  │    → Detect test execution and results                             │   │
│  │                                                                     │   │
│  │  Verification claims:                                               │   │
│  │    Check features.json diff for passes: true changes               │   │
│  │    → Detect when agent claims completion                           │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  PROMPT INSTRUCTION (for prefixes):                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  "When performing actions, prefix your output for tracking:        │   │
│  │                                                                     │   │
│  │   [FILE:READ] path     - When reading a file                       │   │
│  │   [FILE:WRITE] path    - When writing a file                       │   │
│  │   [CMD:RUN] command    - Before running a command                  │   │
│  │   [CMD:EXIT] code      - After command completes                   │   │
│  │   [VERIFY:START] #N    - Starting feature verification             │   │
│  │   [VERIFY:PASS] #N     - Feature verification passed               │   │
│  │   [VERIFY:FAIL] #N     - Feature verification failed               │   │
│  │   [DECISION] text      - Recording an architectural decision       │   │
│  │                                                                     │   │
│  │   These prefixes help the harness track your progress.             │   │
│  │   The session will work without them, but tracking improves."      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Project Health Metric (NEW in v1.2)

```python
# harness health

def calculate_health() -> ProjectHealth:
    """Calculate overall project health score."""
    
    features = load_features()
    tests = run_tests()
    lint = run_lint()
    files = analyze_file_sizes()
    
    return ProjectHealth(
        feature_completion=len([f for f in features if f.passes]) / len(features),
        test_pass_rate=tests.passed / tests.total,
        lint_score=1.0 - (lint.errors / max(lint.total_lines, 1)),
        file_health=1.0 - (len(files.oversized) / max(len(files.all), 1)),
        
        # Composite score
        overall=weighted_average([
            (feature_completion, 0.4),
            (test_pass_rate, 0.3),
            (lint_score, 0.2),
            (file_health, 0.1)
        ]),
        
        status="GOOD" if overall > 0.8 else "FAIR" if overall > 0.6 else "POOR"
    )
```

### Event Levels

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT LEVELS                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LEVEL      │ WHAT                        │ RETENTION  │ EXAMPLES          │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  CRITICAL   │ Decisions that matter       │ Forever    │ Library choice,   │
│             │ Full context captured       │            │ API design,       │
│             │ Always logged               │            │ Verification fail │
│                                                                             │
│  IMPORTANT  │ Significant actions         │ 90 days    │ Feature complete, │
│             │ Summary context             │            │ Context limit hit,│
│             │ Always logged               │            │ Rollback, Stuck   │
│                                                                             │
│  ROUTINE    │ Normal operations           │ 30 days    │ File read,        │
│             │ Minimal context             │            │ Command run       │
│             │ Sampled (10%)               │            │                   │
│                                                                             │
│  DEBUG      │ Detailed traces             │ 7 days     │ Token counts,     │
│             │ Full detail                 │            │ API latencies,    │
│             │ Only if debug enabled       │            │ Progress checks   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Complete Configuration Reference

```yaml
# .harness.yaml - Full configuration reference

# Required: Project identity
project:
  name: my-api
  github_repo: user/my-api   # For GitHub Issues sync (optional)

# Required: How to run the project
environment:
  init: ./init.sh            # Start dev environment
  reset: ./reset.sh          # Force clean state (NEW)
  health_check: curl -sf http://localhost:8000/health
  stop: docker-compose down  # Optional

# Required: How to run tests
testing:
  sanity:
    health: curl -sf http://localhost:8000/health
    lint: poetry run ruff check src/ --select=E,F,W    # NEW: lint in sanity
  unit: poetry run pytest tests/unit -x
  e2e: poetry run pytest tests/e2e -x
  full: poetry run pytest tests/ -v                    # NEW: regression check

# Required: Cost controls
costs:
  per_session_usd: 10.00
  per_feature_usd: 25.00
  total_project_usd: 200.00

# Model configuration (NEW in v1.2.1: per-prompt-type models)
models:
  default: claude-sonnet-4       # Fallback for unspecified prompt types
  initializer: claude-sonnet-4   # Session 0: project scaffolding
  coding: claude-sonnet-4        # Sessions 1-N: feature implementation
  continuation: claude-sonnet-4  # After partial completion
  cleanup: claude-haiku-3        # Code quality (simpler task, save cost)

  # GUIDANCE:
  # - Initializer: Consider claude-opus for better planning on complex projects
  # - Coding: claude-sonnet-4 is the sweet spot for most implementation
  # - Continuation: Same as coding (needs full capability)
  # - Cleanup: claude-haiku works well (simpler refactoring task)

# Context management
context:
  warn_threshold: 0.75
  force_threshold: 0.90
  on_limit:
    auto_commit: true
    commit_message_prefix: "WIP: Context limit - "
    append_to_progress: true

# Progress monitoring (NEW)
progress:
  check_interval_tokens: 50000
  stuck_warning: "You appear stuck. Consider a different approach."
  force_stop_after_stuck_checks: 2
  max_repeated_errors: 5

# Code quality (NEW)
quality:
  lint_command: poetry run ruff check src/
  max_file_lines: 500
  cleanup_interval: 10           # Cleanup session every N features
  warn_on_lint_errors: true      # Warn but don't fail

# Verification (NEW)
verification:
  require_evidence: true         # Agent must show test output
  harness_verify: true           # Harness re-runs tests independently
  max_features_per_session: 1    # Reject if agent claims more
  regression_check: true         # Run full suite before commit

# Feature rules (NEW)
features:
  max_verification_steps: 7      # Flag features with more
  max_stuck_sessions: 3          # Escalate after this many
  require_test_file: true        # Every feature needs test_file

# GitHub integration
github:
  sync_mode: mirror              # "mirror" or "none"
  sync_on_session_end: true
  create_missing_issues: true
  close_on_verify: true
  on_sync_failure: warn          # "warn" or "fail"

# Logging
logging:
  level: important               # critical, important, routine, debug
  retention_days: 90
  structured_agent_output: true  # NEW: parse agent prefixes

# Custom paths (if you don't want defaults)
paths:
  features: features.json
  progress: claude-progress.txt
  state_dir: .harness
```

---

## Tool & MCP Configuration (NEW in v1.2.1)

### The Problem

The agent needs appropriate tools to verify features effectively. For UI features, automated tests alone may not catch visual regressions or UX issues. The Anthropic research specifically recommends "browser automation tools (Puppeteer MCP) for human-like verification."

### Tool Configuration

```yaml
# .harness.yaml

# Tools available to the agent
tools:
  # Core tools (always available)
  filesystem:
    enabled: true
    allowed_paths:
      - "."                    # Project root
    denied_paths:
      - ".harness/"            # Protect harness state
      - ".git/"                # Protect git internals
      - "../"                  # No escaping project

  shell:
    enabled: true
    timeout_seconds: 300       # 5 min max per command
    denied_commands:           # Block dangerous commands
      - "rm -rf /"
      - "sudo"
      - "> /dev/"

  # MCP servers for extended capabilities
  mcp_servers:
    # Browser automation for UI verification
    puppeteer:
      enabled: true            # Enable for projects with UI
      command: "npx"
      args: ["-y", "@anthropic/puppeteer-mcp"]
      config:
        headless: true
        viewport: { width: 1280, height: 720 }
        screenshots_dir: ".harness/screenshots"

    # Database access for data verification
    postgres:
      enabled: false           # Enable if needed
      command: "npx"
      args: ["-y", "@anthropic/postgres-mcp"]
      config:
        connection_string: "${DATABASE_URL}"
        read_only: true        # Safety: no writes via MCP
```

### Browser Automation for UI Features

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BROWSER AUTOMATION VERIFICATION                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  For features with UI components, use Puppeteer MCP for verification:      │
│                                                                             │
│  FEATURE EXAMPLE:                                                           │
│  {                                                                          │
│    "id": 15,                                                                │
│    "description": "User can upload profile picture",                        │
│    "test_file": "tests/e2e/test_avatar_upload.py",                         │
│    "visual_verification": {                                                 │
│      "enabled": true,                                                       │
│      "steps": [                                                             │
│        "Navigate to /profile/settings",                                     │
│        "Screenshot before upload",                                          │
│        "Upload test image via file picker",                                 │
│        "Screenshot after upload",                                           │
│        "Verify avatar visible in header"                                    │
│      ]                                                                      │
│    }                                                                        │
│  }                                                                          │
│                                                                             │
│  AGENT VERIFICATION FLOW:                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. Run automated tests (pytest)                                    │   │
│  │     $ poetry run pytest tests/e2e/test_avatar_upload.py -v         │   │
│  │                                                                     │   │
│  │  2. If visual_verification enabled, use Puppeteer MCP:             │   │
│  │     - Navigate to page                                              │   │
│  │     - Take screenshot (before state)                                │   │
│  │     - Perform action                                                │   │
│  │     - Take screenshot (after state)                                 │   │
│  │     - Describe what's visible                                       │   │
│  │                                                                     │   │
│  │  3. Show evidence in output:                                        │   │
│  │     [VISUAL:SCREENSHOT] .harness/screenshots/avatar_before.png     │   │
│  │     [VISUAL:SCREENSHOT] .harness/screenshots/avatar_after.png      │   │
│  │     [VISUAL:VERIFY] Avatar image visible in header, 64x64px        │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  HARNESS ACTIONS:                                                           │
│  • Store screenshots with session metadata                                 │
│  • Log visual verification steps                                           │
│  • Human can review screenshots if verification disputed                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Non-Automated Verification

For features that cannot be fully automated (UX quality, design fidelity):

```yaml
# In features.json
{
  "id": 30,
  "description": "Dashboard layout matches design mockup",
  "test_file": "tests/e2e/test_dashboard.py",
  "verification_type": "hybrid",
  "automated_checks": [
    "All dashboard components render",
    "No console errors",
    "Responsive breakpoints work"
  ],
  "manual_checks": [
    "Visual design matches Figma mockup",
    "Animations feel smooth"
  ],
  "passes": false
}
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID VERIFICATION                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  verification_type: "automated" (default)                                   │
│    → Agent runs tests, harness verifies independently                       │
│    → Fully autonomous                                                       │
│                                                                             │
│  verification_type: "hybrid"                                                │
│    → Agent runs automated_checks                                            │
│    → Agent takes screenshots for manual_checks                              │
│    → Harness prompts human to verify manual items                          │
│    → Feature not marked passing until human confirms                        │
│                                                                             │
│  verification_type: "manual"                                                │
│    → Agent completes implementation                                         │
│    → Harness immediately escalates to human                                 │
│    → Human uses `harness manual-verify --feature N`                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Session Definition (NEW in v1.2.1)

### What Is a Session?

A **session** is one execution of `harness run`, which corresponds to:
- One harness run command invocation
- One Claude API conversation (one context window)
- One feature attempt (complete, partial, or failed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SESSION BOUNDARIES                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SESSION STARTS when:                                                        │
│  • User runs `harness run`                                                  │
│  • Harness completes pre-flight checks                                      │
│  • Agent is launched with orientation prompt                                │
│                                                                             │
│  SESSION ENDS when any of:                                                   │
│  • Agent completes feature and harness verifies (SUCCESS)                   │
│  • Agent signals completion, harness commits (COMPLETE)                     │
│  • Context reaches 100% (CONTEXT_LIMIT)                                     │
│  • Wall-clock timeout reached (TIMEOUT)                                     │
│  • Agent stuck for 2 check intervals (STUCK)                                │
│  • User pauses harness (USER_PAUSE)                                         │
│  • Unrecoverable error (ERROR)                                              │
│                                                                             │
│  SESSION STATE RECORDED:                                                     │
│  {                                                                          │
│    "session_id": 7,                                                         │
│    "started_at": "2025-01-16T10:00:00Z",                                   │
│    "ended_at": "2025-01-16T10:45:00Z",                                     │
│    "duration_seconds": 2700,                                                │
│    "termination_reason": "complete",                                        │
│    "feature_id": 15,                                                        │
│    "feature_completed": true,                                               │
│    "tokens_used": { "input": 145000, "output": 32000 },                    │
│    "cost_usd": 0.92                                                         │
│  }                                                                          │
│                                                                             │
│  ONE SESSION = ONE CONTEXT WINDOW                                           │
│  • No conversation continuation across sessions                             │
│  • Each session starts fresh with orientation summary                       │
│  • State preserved via files, not conversation history                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Session Timeout

```yaml
# .harness.yaml

session:
  # Wall-clock timeout (prevents runaway sessions)
  timeout_minutes: 60          # Hard stop after 1 hour

  # Warning before timeout
  timeout_warning_minutes: 50  # Warn at 50 min

  # What to do on timeout
  on_timeout:
    auto_commit: true          # Commit WIP state
    message_prefix: "WIP: Session timeout - "
```

```python
# Session timeout handling
class SessionManager:
    def __init__(self, config: SessionConfig):
        self.start_time = time.time()
        self.timeout = config.timeout_minutes * 60
        self.warned = False

    def check_timeout(self) -> Optional[str]:
        elapsed = time.time() - self.start_time

        if elapsed >= self.timeout:
            return "TIMEOUT: Session exceeded time limit. Stopping now."

        if not self.warned and elapsed >= self.config.timeout_warning_minutes * 60:
            self.warned = True
            return f"WARNING: {self.config.timeout_minutes - int(elapsed/60)} minutes remaining."

        return None
```

---

## Pre-Flight Checks (NEW in v1.2.1)

### Harness Verifies Before Agent Starts

The harness validates the environment is healthy **before** launching the agent. This prevents wasting context on a broken environment.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRE-FLIGHT CHECK FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ harness run                                                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: PRE-FLIGHT CHECKS (Harness, before agent)                  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  1. Verify working directory                                        │   │
│  │     $ pwd                                                           │   │
│  │     ✓ /Users/you/projects/my-api                                   │   │
│  │                                                                     │   │
│  │  2. Verify harness files exist                                      │   │
│  │     ✓ .harness.yaml                                                │   │
│  │     ✓ features.json                                                 │   │
│  │     ✓ claude-progress.txt                                          │   │
│  │     ✓ init.sh (executable)                                         │   │
│  │     ✓ reset.sh (executable)                                        │   │
│  │                                                                     │   │
│  │  3. Verify git state                                                │   │
│  │     ✓ On branch: main                                              │   │
│  │     ✓ Working tree clean (or stashable)                            │   │
│  │     ✓ Not in detached HEAD                                         │   │
│  │                                                                     │   │
│  │  4. Start environment                                               │   │
│  │     $ ./init.sh                                                     │   │
│  │     ✓ Exit code 0                                                  │   │
│  │                                                                     │   │
│  │     If init.sh fails:                                               │   │
│  │     $ ./reset.sh                                                    │   │
│  │     $ ./init.sh                                                     │   │
│  │     If still fails → ABORT, escalate to human                      │   │
│  │                                                                     │   │
│  │  5. Health check                                                    │   │
│  │     $ curl -sf http://localhost:8000/health                        │   │
│  │     ✓ HTTP 200                                                     │   │
│  │                                                                     │   │
│  │  6. Run baseline tests                                              │   │
│  │     $ poetry run pytest tests/ -x --tb=short -q                    │   │
│  │     ✓ All baseline tests pass                                      │   │
│  │                                                                     │   │
│  │     If tests fail that were passing:                                │   │
│  │     → ABORT: "Environment is broken. Baseline tests failing."      │   │
│  │     → Do NOT launch agent                                          │   │
│  │                                                                     │   │
│  │  7. Check budget                                                    │   │
│  │     ✓ Session budget available: $10.00                             │   │
│  │     ✓ Project budget remaining: $147.50                            │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                │                                            │
│                         ALL CHECKS PASS                                     │
│                                │                                            │
│                                ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: LAUNCH AGENT                                               │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  • Generate orientation summary                                     │   │
│  │  • Select prompt type (coding/continuation/cleanup)                 │   │
│  │  • Create checkpoint                                                │   │
│  │  • Start Claude API conversation                                    │   │
│  │  • Agent begins work...                                             │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pre-Flight Configuration

```yaml
# .harness.yaml

preflight:
  # Checks to run before launching agent
  checks:
    working_directory: true    # Verify pwd matches project
    harness_files: true        # Verify config files exist
    git_state: true            # Verify clean git state
    environment: true          # Run init.sh, verify health
    baseline_tests: true       # Run tests, verify passing
    budget: true               # Check cost budget available

  # Behavior on failure
  on_failure:
    auto_reset: true           # Try reset.sh if init.sh fails
    max_reset_attempts: 2      # Give up after 2 reset attempts
```

```python
# preflight.py

@dataclass
class PreflightResult:
    passed: bool
    checks: List[CheckResult]
    duration_seconds: float
    error: Optional[str]

def run_preflight_checks(project_dir: Path, config: Config) -> PreflightResult:
    """Run all pre-flight checks before launching agent."""
    checks = []

    # 1. Working directory
    if config.preflight.checks.working_directory:
        checks.append(verify_working_directory(project_dir))

    # 2. Harness files
    if config.preflight.checks.harness_files:
        checks.append(verify_harness_files(project_dir))

    # 3. Git state
    if config.preflight.checks.git_state:
        checks.append(verify_git_state(project_dir))

    # 4. Environment
    if config.preflight.checks.environment:
        env_result = start_environment(project_dir, config)
        if not env_result.passed and config.preflight.on_failure.auto_reset:
            # Try reset
            for attempt in range(config.preflight.on_failure.max_reset_attempts):
                reset_result = run_reset(project_dir)
                if reset_result.passed:
                    env_result = start_environment(project_dir, config)
                    if env_result.passed:
                        break
        checks.append(env_result)

    # 5. Baseline tests
    if config.preflight.checks.baseline_tests:
        checks.append(verify_baseline_tests(project_dir))

    # 6. Budget
    if config.preflight.checks.budget:
        checks.append(verify_budget(project_dir, config))

    passed = all(c.passed for c in checks)
    return PreflightResult(
        passed=passed,
        checks=checks,
        duration_seconds=sum(c.duration for c in checks),
        error=next((c.error for c in checks if not c.passed), None)
    )
```

---

## Dependency Enforcement (NEW in v1.2.1)

### How Dependencies Work

Features can declare dependencies on other features. The harness enforces these dependencies.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY ENFORCEMENT                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FEATURES.JSON:                                                             │
│  [                                                                          │
│    { "id": 1, "description": "User registration", "passes": true },        │
│    { "id": 2, "description": "User login", "depends_on": [1], "passes": true },│
│    { "id": 3, "description": "Password reset", "depends_on": [1,2], "passes": false },│
│    { "id": 4, "description": "Profile edit", "depends_on": [2], "passes": false },│
│    { "id": 5, "description": "Admin dashboard", "depends_on": [], "passes": false }│
│  ]                                                                          │
│                                                                             │
│  DEPENDENCY GRAPH:                                                          │
│                                                                             │
│       ┌───┐                                                                 │
│       │ 1 │ ✓ User registration                                            │
│       └─┬─┘                                                                 │
│         │                                                                   │
│       ┌─▼─┐                                                                 │
│       │ 2 │ ✓ User login                                                   │
│       └─┬─┘                                                                 │
│      ┌──┴──┐                                                                │
│      ▼     ▼                                                                │
│   ┌───┐ ┌───┐     ┌───┐                                                    │
│   │ 3 │ │ 4 │     │ 5 │ (no dependencies)                                  │
│   └───┘ └───┘     └───┘                                                    │
│                                                                             │
│  FEATURE SELECTION ORDER:                                                   │
│  1. Filter: Only features where passes == false                            │
│  2. Filter: Only features where ALL depends_on are passing                 │
│  3. Sort: By id (or priority if specified)                                 │
│  4. Select: First available feature                                        │
│                                                                             │
│  In example above:                                                          │
│  • Feature 3: depends_on [1,2] both ✓ → AVAILABLE                          │
│  • Feature 4: depends_on [2] ✓ → AVAILABLE                                 │
│  • Feature 5: no dependencies → AVAILABLE                                  │
│  • Next feature: 3 (lowest id among available)                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Dependency Regression Handling

What happens if a dependency regresses (was passing, now failing)?

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY REGRESSION                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SCENARIO:                                                                  │
│  • Feature 2 (login) was passing                                           │
│  • Session 8 worked on Feature 5 (unrelated)                               │
│  • Feature 2's test now fails (regression)                                 │
│                                                                             │
│  DETECTION:                                                                 │
│  • Regression check catches Feature 2 failure                              │
│  • Harness identifies: Feature 2 is a dependency of Features 3, 4          │
│                                                                             │
│  RESPONSE:                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  REGRESSION DETECTED                                                │   │
│  │                                                                     │   │
│  │  Feature 2 (User login) now failing.                               │   │
│  │  This blocks: Feature 3, Feature 4                                 │   │
│  │                                                                     │   │
│  │  Actions taken:                                                     │   │
│  │  1. Rolling back Session 8 changes                                 │   │
│  │  2. Marking Feature 2 as passes: false                             │   │
│  │  3. Next session will fix Feature 2 before continuing              │   │
│  │                                                                     │   │
│  │  Options:                                                           │   │
│  │  [R]etry - Run new session to fix regression                       │   │
│  │  [I]nvestigate - Human reviews what broke                          │   │
│  │  [S]kip - Mark Feature 2 as skipped, unblock dependents            │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cycle Detection

```python
# features.py

def detect_dependency_cycles(features: List[Feature]) -> List[List[int]]:
    """Detect circular dependencies in feature graph."""

    # Build adjacency list
    graph = {f.id: f.depends_on or [] for f in features}

    # DFS for cycle detection
    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found cycle
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])

        path.pop()
        rec_stack.remove(node)

    for feature_id in graph:
        if feature_id not in visited:
            dfs(feature_id, [])

    return cycles

def validate_dependencies(features: List[Feature]) -> ValidationResult:
    """Validate feature dependencies during init or add-features."""

    errors = []

    # Check for cycles
    cycles = detect_dependency_cycles(features)
    if cycles:
        for cycle in cycles:
            errors.append(f"Dependency cycle detected: {' → '.join(map(str, cycle))}")

    # Check for missing dependencies
    feature_ids = {f.id for f in features}
    for f in features:
        for dep_id in (f.depends_on or []):
            if dep_id not in feature_ids:
                errors.append(f"Feature {f.id} depends on non-existent Feature {dep_id}")

    return ValidationResult(valid=len(errors) == 0, errors=errors)
```

---

## Rollback Granularity (NEW in v1.2.1)

### What Gets Rolled Back

When a rollback is triggered, the harness must restore the project to a known-good state.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROLLBACK SCOPE                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CHECKPOINT CAPTURES:                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  checkpoint_abc123/                                                 │   │
│  │  ├── git_ref: "def456"              # Git commit SHA               │   │
│  │  ├── features_json_hash: "..."      # Hash of features.json        │   │
│  │  ├── progress_file_hash: "..."      # Hash of claude-progress.txt  │   │
│  │  ├── session_state.json             # Copy of session state        │   │
│  │  └── test_baseline.json             # Copy of test baseline        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ROLLBACK RESTORES:                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  1. GIT STATE                                                       │   │
│  │     $ git reset --hard {checkpoint.git_ref}                        │   │
│  │     This restores: src/, tests/, features.json, claude-progress.txt│   │
│  │                                                                     │   │
│  │  2. SESSION STATE                                                   │   │
│  │     Copy checkpoint/session_state.json → .harness/session_state.json│   │
│  │     This restores: stuck_count, current_feature, status            │   │
│  │                                                                     │   │
│  │  3. TEST BASELINE                                                   │   │
│  │     Copy checkpoint/test_baseline.json → .harness/test_baseline.json│   │
│  │     This restores: known-passing test list                         │   │
│  │                                                                     │   │
│  │  4. VERIFY RESTORATION                                              │   │
│  │     Assert: hash(features.json) == checkpoint.features_json_hash   │   │
│  │     Assert: hash(claude-progress.txt) == checkpoint.progress_hash  │   │
│  │     Assert: git rev-parse HEAD == checkpoint.git_ref               │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  NOT ROLLED BACK (preserved):                                               │
│  • .harness/logs/ — Keep for debugging                                     │
│  • .harness/costs.yaml — Keep cost history                                 │
│  • .harness/checkpoints/ — Keep other checkpoints                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Checkpoint and Rollback Implementation

```python
# checkpoint.py

@dataclass
class Checkpoint:
    id: str
    timestamp: datetime
    session: int
    git_ref: str
    features_json_hash: str
    progress_file_hash: str
    reason: str  # "pre_feature", "pre_verification", "manual"

def create_checkpoint(
    project_dir: Path,
    session: int,
    reason: str = "pre_feature"
) -> Checkpoint:
    """Create recovery point before risky operations."""

    checkpoint_id = generate_id()
    checkpoint_dir = project_dir / ".harness" / "checkpoints" / checkpoint_id
    checkpoint_dir.mkdir(parents=True)

    # Capture git state
    git_ref = git.get_head(project_dir)

    # Capture file hashes
    features_hash = hash_file(project_dir / "features.json")
    progress_hash = hash_file(project_dir / "claude-progress.txt")

    # Copy state files
    shutil.copy(
        project_dir / ".harness" / "session_state.json",
        checkpoint_dir / "session_state.json"
    )
    shutil.copy(
        project_dir / ".harness" / "test_baseline.json",
        checkpoint_dir / "test_baseline.json"
    )

    checkpoint = Checkpoint(
        id=checkpoint_id,
        timestamp=datetime.now(),
        session=session,
        git_ref=git_ref,
        features_json_hash=features_hash,
        progress_file_hash=progress_hash,
        reason=reason
    )

    # Save checkpoint metadata
    save_json(checkpoint_dir / "checkpoint.json", asdict(checkpoint))

    log_event("checkpoint_created", {
        "checkpoint_id": checkpoint_id,
        "git_ref": git_ref,
        "reason": reason
    })

    return checkpoint

def rollback_to_checkpoint(project_dir: Path, checkpoint_id: str) -> RollbackResult:
    """Restore state to checkpoint."""

    checkpoint_dir = project_dir / ".harness" / "checkpoints" / checkpoint_id
    checkpoint = load_checkpoint(checkpoint_dir)

    # 1. Record what we're rolling back
    current_git_ref = git.get_head(project_dir)
    rolled_back_commits = git.commits_between(checkpoint.git_ref, current_git_ref)

    # 2. Git rollback
    git.reset_hard(project_dir, checkpoint.git_ref)

    # 3. Restore state files
    shutil.copy(
        checkpoint_dir / "session_state.json",
        project_dir / ".harness" / "session_state.json"
    )
    shutil.copy(
        checkpoint_dir / "test_baseline.json",
        project_dir / ".harness" / "test_baseline.json"
    )

    # 4. Verify restoration
    assert hash_file(project_dir / "features.json") == checkpoint.features_json_hash
    assert hash_file(project_dir / "claude-progress.txt") == checkpoint.progress_file_hash
    assert git.get_head(project_dir) == checkpoint.git_ref

    # 5. Log the rollback
    log_event("rollback_completed", {
        "checkpoint_id": checkpoint_id,
        "rolled_back_commits": rolled_back_commits,
        "restored_to_session": checkpoint.session
    })

    return RollbackResult(
        success=True,
        checkpoint=checkpoint,
        rolled_back_commits=rolled_back_commits
    )
```

### Partial Completion and Checkpoints

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PARTIAL COMPLETION SCENARIOS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SCENARIO 1: Context limit mid-feature                                      │
│  ────────────────────────────────────────────────────────────────────────   │
│  • Checkpoint created at session start                                      │
│  • Agent works, hits 90% context                                           │
│  • Agent commits WIP (checkpoint NOT taken here)                           │
│  • Session ends with status: "partial"                                     │
│                                                                             │
│  Next session: Continuation prompt, works from WIP commit                  │
│  If continuation fails: Can rollback to pre-session checkpoint             │
│                                                                             │
│  SCENARIO 2: Verification fails after agent claims done                     │
│  ────────────────────────────────────────────────────────────────────────   │
│  • Checkpoint created at session start                                      │
│  • Agent works, claims feature complete                                    │
│  • Harness verification fails (test doesn't pass)                          │
│  • DO NOT rollback yet — give agent chance to fix                          │
│  • If agent can't fix in remaining context: rollback to checkpoint         │
│                                                                             │
│  SCENARIO 3: Regression detected                                            │
│  ────────────────────────────────────────────────────────────────────────   │
│  • Checkpoint created at session start                                      │
│  • Agent works, feature passes                                             │
│  • Regression check finds other tests failing                              │
│  • IMMEDIATE rollback to checkpoint                                        │
│  • Session marked as failed, next session retries                          │
│                                                                             │
│  CHECKPOINT RETENTION:                                                       │
│  • Keep last 5 checkpoints per feature                                     │
│  • Keep last checkpoint for each completed feature                         │
│  • Auto-cleanup checkpoints older than 7 days (configurable)               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phased Implementation

### Phase 1: Core Loop with Verification (Ship This)

**Goal:** End-to-end flow with all v1.2 safety features.

```
- [ ] CLI: harness init, run, status, pause, resume, verify, health
- [ ] Initializer agent prompt with granularity rules
- [ ] Coding agent prompt with harness-generated orientation
- [ ] Continuation agent prompt with partial completion details
- [ ] features.json with required test_file field
- [ ] init.sh AND reset.sh generation
- [ ] Harness-generated orientation summary (not agent file reading)
- [ ] Verification system:
  - [ ] Validate max 1 feature per session
  - [ ] Harness runs feature test independently
  - [ ] Require verification evidence in agent output
- [ ] Regression detection:
  - [ ] Test baseline tracking
  - [ ] Full test suite before commit
  - [ ] Rollback on regression
- [ ] Progress monitoring:
  - [ ] Stuck detection at intervals
  - [ ] Repeated error detection
  - [ ] Feature stuck escalation (3 sessions)
- [ ] Code quality:
  - [ ] Lint in sanity test
  - [ ] File size tracking
- [ ] Context management (75% warn, 90% force, 100% hard stop)
- [ ] Session state with stuck_count
- [ ] Git commit after verification passes
- [ ] Basic cost tracking
- [ ] Human escape hatches (pause, resume, skip, verify, handoff)
```

**Success Criteria:** 
- Initializer creates features with appropriate granularity
- Agent claims are independently verified by harness
- Regressions are caught before commit
- Stuck agents are detected and escalated
- Context limit results in clean handoff

### Phase 2: Quality & Cleanup

**Goal:** Maintain code quality over long projects.

```
- [ ] Cleanup session prompt and triggering
- [ ] File growth alerts
- [ ] Lint warning aggregation
- [ ] Project health metric
- [ ] harness cleanup command
- [ ] --dry-run mode
```

### Phase 3: Observability

**Goal:** Understand what happened and why.

```
- [ ] Structured agent action logging
- [ ] Decision logging (critical only)
- [ ] Query interface (harness log query "...")
- [ ] Session summaries
```

### Phase 4: GitHub & Collaboration

**Goal:** Team visibility and integration.

```
- [ ] GitHub Issues sync with configurable behavior
- [ ] Issue creation for new features
- [ ] Issue closing on verification
- [ ] Conflict handling for manual changes
```

### Phase 5: Proposal Validation (If Needed)

**Goal:** Additional guardrails if agents misbehave.

```
- [ ] Agent output schema for proposals
- [ ] Proposal validation (no writes outside project)
- [ ] Dangerous command blocking
```

**Trigger:** Only implement if you observe agents:
- Writing outside project directory
- Running dangerous commands
- Modifying harness state files

### Phase 6: Advanced Features

**Goal:** Handle complex scenarios.

```
- [ ] Multi-feature dependencies with ordering
- [ ] Automatic feature splitting suggestions
- [ ] Parallelization for independent features
```

---

## All Done State (NEW in v1.2)

What happens when all features are complete:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ALL FEATURES COMPLETE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ harness run                                                             │
│                                                                             │
│  🎉 All 47 features are passing!                                           │
│                                                                             │
│  Running final verification...                                             │
│  • Full test suite: 156/156 passing ✓                                     │
│  • Lint check: 0 errors ✓                                                  │
│  • Code quality: GOOD ✓                                                    │
│                                                                             │
│  Project complete. Options:                                                │
│  [M]aintenance mode - Watch for regressions, keep tests passing           │
│  [A]dd features - Edit features.json to add more                          │
│  [E]xit - Stop harness                                                     │
│                                                                             │
│  > m                                                                       │
│                                                                             │
│  Entering maintenance mode...                                              │
│  Harness will run periodic health checks.                                  │
│  Add features with: harness add-feature "Description"                      │
│  Exit with: harness stop                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Testing the Harness

### Unit Tests

```python
# tests/harness/test_verification.py (NEW)

def test_rejects_multiple_features_completed():
    """Agent cannot complete more than 1 feature per session."""
    
def test_harness_runs_test_independently():
    """Harness runs feature test, not just trusts agent."""
    
def test_detects_regression():
    """Catches when previously-passing test now fails."""
    
def test_requires_verification_evidence():
    """Agent must show test output in response."""

# tests/harness/test_progress_monitor.py (NEW)

def test_detects_stuck_agent():
    """Flags when agent makes no progress over interval."""
    
def test_detects_repeated_errors():
    """Flags when same error appears 5+ times."""
    
def test_escalates_after_3_stuck_sessions():
    """Escalates to human if feature stuck 3 sessions."""

# tests/harness/test_orientation.py (NEW)

def test_generates_orientation_summary():
    """Harness generates compact orientation for agent."""
    
def test_orientation_includes_partial_details():
    """Continuation orientation includes what's done/left."""
    
def test_orientation_token_count():
    """Orientation is under 1000 tokens."""

# tests/harness/test_quality.py (NEW)

def test_lint_in_sanity_check():
    """Sanity test includes lint check."""
    
def test_tracks_file_sizes():
    """File sizes are tracked across sessions."""
    
def test_triggers_cleanup_session():
    """Cleanup triggered after N features."""

# tests/harness/test_features_validation.py

def test_rejects_removed_features():
    """Agent cannot remove features from features.json."""
    
def test_rejects_edited_descriptions():
    """Agent cannot edit feature descriptions."""
    
def test_accepts_passes_change():
    """Agent can change passes: false → true."""
    
def test_requires_test_file():
    """Features must have test_file field."""
    
def test_flags_large_features():
    """Features with >7 verification steps are flagged."""
```

### Integration Tests

```python
# tests/integration/test_verification_flow.py (NEW)

def test_agent_claim_verified_by_harness():
    """Agent claims done, harness verifies independently."""
    
def test_false_claim_rejected():
    """Agent claims done but test fails → rejected."""
    
def test_regression_blocks_commit():
    """Regression detected → rollback, no commit."""

# tests/integration/test_stuck_detection.py (NEW)

def test_stuck_warning_injected():
    """Warning injected when no progress detected."""
    
def test_force_stop_after_prolonged_stuck():
    """Session force-stopped after 2 stuck intervals."""

# tests/integration/test_reset_recovery.py (NEW)

def test_reset_recovers_from_bad_state():
    """reset.sh recovers from crashed environment."""
    
def test_agent_uses_reset_on_init_failure():
    """Agent runs reset.sh when init.sh fails."""
```

### Chaos Tests

```python
# tests/chaos/test_agent_lying.py (NEW)

def test_catches_agent_not_running_tests():
    """Agent says passed but didn't run tests → caught."""
    
def test_catches_agent_multiple_claims():
    """Agent marks 3 features done → all rejected."""

# tests/chaos/test_regressions.py (NEW)

def test_subtle_regression_caught():
    """Change that breaks unrelated test is caught."""
    
def test_rollback_restores_passing_state():
    """After rollback, all baseline tests pass again."""
```

---

## Glossary

| Term | Definition |
|------|------------|
| **Harness** | The control system that orchestrates agents |
| **Initializer Agent** | Agent that runs in Session 0 to scaffold project |
| **Coding Agent** | Agent that runs in Sessions 1-N to implement features |
| **Continuation Agent** | Agent that runs after partial completion to finish features |
| **Cleanup Agent** | Agent that runs periodically to improve code quality |
| **Checkpoint** | Recovery point before risky operations |
| **Progress File** | claude-progress.txt — prose summary for agent orientation |
| **Features File** | features.json — structured feature list with pass/fail status |
| **Orientation Summary** | Harness-generated context injected into agent prompt (NEW) |
| **Sanity Test** | Quick test including health + lint to verify app state |
| **Test Baseline** | Record of which tests were passing before session (NEW) |
| **Regression** | Previously-passing test that now fails (NEW) |
| **Verification Evidence** | Test output agent must show to claim completion (NEW) |
| **Stuck Detection** | Monitoring for agents making no progress (NEW) |
| **Feature Granularity** | Size rules ensuring features fit in one session (NEW) |
| **Escalation** | When harness asks human for help |
| **Context Limit** | When token usage approaches context window size |
| **Graceful Handoff** | Agent documents progress before context exhausted |
| **Hard Stop** | Harness terminates session when context is 100% full |
| **Project Health** | Composite metric of features, tests, lint, files (NEW) |
| **Pre-Flight Check** | Harness verification before launching agent (NEW v1.2.1) |
| **Session** | One harness run = one context window = one feature attempt (NEW v1.2.1) |
| **Session Timeout** | Wall-clock limit on session duration (NEW v1.2.1) |
| **MCP Server** | Model Context Protocol server providing tools to agent (NEW v1.2.1) |
| **Visual Verification** | Browser automation to verify UI features (NEW v1.2.1) |
| **Hybrid Verification** | Mix of automated tests and human checks (NEW v1.2.1) |
| **Dependency Enforcement** | Harness ensures features are worked in dependency order (NEW v1.2.1) |
| **Schema Version** | Version number for state file format, enables migrations (NEW v1.2.1) |

---

## Appendix: Key Changes from v1.1

### 1. Harness-Generated Orientation

**Before (v1.1):** Agent reads progress file, features.json, git log at session start.

**After (v1.2):** Harness generates compact orientation summary and injects it. Agent doesn't read files for orientation. Saves ~5-15% context per session.

### 2. Required Test Files

**Before (v1.1):** Features had prose verification_steps.

**After (v1.2):** Features require `test_file` field. Verification is running that file.

### 3. Harness-Side Verification

**Before (v1.1):** Harness validated features.json changes only.

**After (v1.2):** Harness independently runs the feature's test file. Doesn't trust agent's claim.

### 4. Regression Detection in Phase 1

**Before (v1.1):** Regression detection was Phase 3.

**After (v1.2):** Test baseline tracking and regression check before every commit. Phase 1 feature.

### 5. Feature Granularity Rules

**Before (v1.1):** No guidance on feature size.

**After (v1.2):** Explicit rules: ≤7 verification steps, ≤5 files. Initializer must follow. Large features flagged.

### 6. reset.sh for Recovery

**Before (v1.1):** Only init.sh.

**After (v1.2):** Both init.sh and reset.sh. Agent uses reset.sh when init.sh fails.

### 7. Stuck Detection

**Before (v1.1):** No intra-session progress monitoring.

**After (v1.2):** Progress checked at intervals. Stuck agents warned, then force-stopped.

### 8. Verification Evidence

**Before (v1.1):** Agent could claim done without showing proof.

**After (v1.2):** Agent must show test output. Harness parses for evidence.

### 9. Code Quality in Phase 1

**Before (v1.1):** No quality checks until later phases.

**After (v1.2):** Lint in sanity test. File size tracking. Periodic cleanup sessions.

### 10. Feature Stuck Escalation

**Before (v1.1):** No tracking of repeated failures on same feature.

**After (v1.2):** stuck_count in session state. Escalate after 3 sessions on same feature.

### 11. Max One Feature Per Session

**Before (v1.1):** Mentioned but not enforced.

**After (v1.2):** Harness rejects if agent marks >1 feature as passing.

### 12. GitHub as Mirror

**Before (v1.1):** GitHub sync behavior unspecified.

**After (v1.2):** GitHub is best-effort mirror with explicit config. Failures warn but don't block.

### 13. Structured Agent Output

**Before (v1.1):** Agent output unstructured.

**After (v1.2):** Agent uses prefixes like [FILE:READ], [CMD:RUN]. Harness parses for logging and monitoring.

### 14. Project Health Metric

**Before (v1.1):** No composite health score.

**After (v1.2):** `harness health` shows features, tests, lint, file health.

### 15. All Done State

**Before (v1.1):** Unspecified behavior when all features complete.

**After (v1.2):** Final verification, then maintenance mode or exit.

---

## Appendix: Key Changes from v1.2 to v1.2.1

### 1. Tool & MCP Configuration

**Before (v1.2):** Implicit tool access, no MCP configuration.

**After (v1.2.1):** Explicit `tools:` and `mcp_servers:` configuration in `.harness.yaml`. Puppeteer MCP for browser automation on UI features. Visual verification support.

### 2. Pre-Flight Checks

**Before (v1.2):** Agent ran sanity tests as first step.

**After (v1.2.1):** Harness runs pre-flight checks *before* launching agent. Verifies working directory, harness files, git state, environment health, baseline tests, and budget. Prevents wasting context on broken environments.

### 3. Session Definition & Timeout

**Before (v1.2):** Session boundaries implicit.

**After (v1.2.1):** Explicit session definition: one `harness run` = one context window = one feature attempt. Wall-clock timeout (configurable, default 60 min) in addition to context limit.

### 4. Dependency Enforcement

**Before (v1.2):** `depends_on` field mentioned but behavior unspecified.

**After (v1.2.1):** Full dependency enforcement: feature selection respects dependencies, cycle detection, dependency regression handling (rollback and re-prioritize blocked feature).

### 5. Rollback Granularity

**Before (v1.2):** Checkpoints mentioned, scope unclear.

**After (v1.2.1):** Explicit rollback scope: git state, session_state.json, test_baseline.json. Logs and costs preserved. Verification after rollback. Checkpoint retention policy.

### 6. Structured Output Fallback

**Before (v1.2):** Prefixes required for progress tracking.

**After (v1.2.1):** Prefixes are best-effort. Harness uses heuristics (git diff, API response parsing) when prefixes missing. Session works regardless, observability degrades gracefully.

### 7. Model Per Prompt Type

**Before (v1.2):** Single `model:` config.

**After (v1.2.1):** `models:` config with per-prompt-type selection (initializer, coding, continuation, cleanup). Allows cost optimization (e.g., Haiku for cleanup).

### 8. Harness Version Compatibility

**Before (v1.2):** No migration strategy.

**After (v1.2.1):** Schema versioning in state files. Automatic migration with backup. CLI commands `harness version` and `harness migrate`.

### 9. Verification Types

**Before (v1.2):** All verification via pytest.

**After (v1.2.1):** Three verification types: `automated` (default), `hybrid` (automated + human checks), `manual` (human only). Supports UI/UX features that can't be fully automated.

---

## Appendix: What We're NOT Building (Yet)

- **Multi-agent architecture** — Single agent with prompts first
- **Proposal validation** — Direct writes with verification first
- **Parallelization** — Serial execution works fine
- **Multi-repo support** — One repo at a time
- **Web dashboard** — CLI only
- **Team features** — Single user
- **Cloud hosting** — Runs locally
- **SDK compaction reliance** — Graceful handoff instead
- **PyPI distribution** — Git dependency via Poetry is simpler
- **Automatic feature splitting** — Human decides how to split (for now)