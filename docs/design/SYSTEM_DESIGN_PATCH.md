# Universal Agent Harness v1.2.1 Patch

> **Note:** Most content from this patch has been merged into SYSTEM_DESIGN.md v1.2.1.
> This file is retained for reference on adopt mode workflows.

This patch restores content inadvertently dropped from v1.1 and adds support for existing projects.

---

## Patch 1: Restored Distribution & Installation Details

*Insert after "Running Harness Commands" section in v1.2*

### Local Development (Developing Harness Alongside Projects)

If you're actively developing the harness while using it on a project:

```
~/code/
├── agent-harness/            # Harness repo (clone this)
│   ├── .git/
│   ├── pyproject.toml
│   └── src/agent_harness/
│
└── my-project/               # Your target project (separate repo)
    ├── .git/
    ├── pyproject.toml
    └── src/
```

Use a **path dependency** for live development:

```bash
cd my-project
poetry add --group dev --editable ../agent-harness
```

```toml
# my-project/pyproject.toml (during development)

[tool.poetry.group.dev.dependencies]
agent-harness = { path = "../agent-harness", develop = true }
```

Now edits to `~/code/agent-harness/` are immediately available — no reinstall needed.

When done developing, switch back to Git dependency:

```bash
poetry add --group dev git+https://github.com/you/agent-harness.git#v1.2.0
```

### Version Pinning Strategy

| Strategy | pyproject.toml | When to Use |
|----------|----------------|-------------|
| **Tag** | `tag = "v1.2.0"` | Production projects, stability |
| **Branch** | `branch = "main"` | Active development, want latest |
| **Commit** | `rev = "abc1234"` | Exact reproducibility |
| **Path** | `path = "../agent-harness"` | Local harness development |

### Upgrading the Harness

```bash
# Update to a new tag
# 1. Edit pyproject.toml to change tag = "v1.2.0" to tag = "v1.3.0"
# 2. Run:
poetry update agent-harness

# Or if tracking a branch:
poetry update agent-harness   # Fetches latest from branch
```

---

## Patch 2: Restored Implementation Details

*Insert in appropriate sections or as an Appendix*

### Checkpoint Implementation

```python
@dataclass
class Checkpoint:
    id: str
    timestamp: datetime
    session: int
    git_commit: str
    features_json_hash: str
    progress_file_hash: str
    test_baseline_hash: str
    reason: str  # "pre_feature", "pre_verification", "manual"
    
def create_checkpoint(reason: str = "pre_feature") -> Checkpoint:
    """Create recovery point before risky operations."""
    return Checkpoint(
        id=generate_id(),
        timestamp=now(),
        session=get_current_session(),
        git_commit=git.get_head(),
        features_json_hash=hash_file("features.json"),
        progress_file_hash=hash_file("claude-progress.txt"),
        test_baseline_hash=hash_file(".harness/test_baseline.json"),
        reason=reason
    )

def rollback_to_checkpoint(checkpoint: Checkpoint):
    """Restore state to checkpoint."""
    # 1. Git rollback
    git.reset_hard(checkpoint.git_commit)
    
    # 2. Verify critical files restored
    assert hash_file("features.json") == checkpoint.features_json_hash
    assert hash_file("claude-progress.txt") == checkpoint.progress_file_hash
    
    # 3. Restore test baseline
    restore_test_baseline(checkpoint.test_baseline_hash)
    
    # 4. Log the rollback
    log_event("rollback", {
        "checkpoint_id": checkpoint.id,
        "reason": "verification_failed",
        "rolled_back_commits": git.commits_since(checkpoint.git_commit)
    })
```

### Prompt Selection Logic

```python
def select_prompt_for_session() -> str:
    """Determine which prompt to use based on previous session state."""
    
    state_file = Path(".harness/session_state.json")
    
    if not state_file.exists():
        # First run ever - but is this a new or existing project?
        # This is handled by init, not run
        raise HarnessNotInitialized("Run 'harness init' first")
    
    state = json.loads(state_file.read_text())
    
    # Check for scheduled cleanup
    features = load_features()
    passing_count = sum(1 for f in features.features if f.passes)
    cleanup_interval = get_config().quality.cleanup_interval
    
    if passing_count > 0 and passing_count % cleanup_interval == 0:
        if state.get("last_prompt") != "cleanup":
            return "cleanup"
    
    # Normal selection logic
    if state["status"] == "partial":
        # Previous session didn't complete the feature
        return "continuation"
    elif state["status"] == "complete":
        # Previous session completed cleanly
        return "coding"
    elif state["status"] == "failed":
        # Previous session hit an error
        return "continuation"
    else:
        return "coding"
```

### Full init.sh Example

```bash
#!/bin/bash
# init.sh - Start development environment
# Created by initializer agent, do not modify manually

set -e

echo "Starting development environment..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker required but not installed. Aborting." >&2; exit 1; }
command -v poetry >/dev/null 2>&1 || { echo "Poetry required but not installed. Aborting." >&2; exit 1; }

# Start database and services
echo "Starting services..."
docker-compose up -d postgres redis

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
for i in {1..30}; do
  if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "PostgreSQL ready."
    break
  fi
  if [ $i -eq 30 ]; then
    echo "ERROR: PostgreSQL failed to start"
    exit 1
  fi
  sleep 1
done

# Wait for Redis
echo "Waiting for Redis..."
for i in {1..30}; do
  if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "Redis ready."
    break
  fi
  if [ $i -eq 30 ]; then
    echo "ERROR: Redis failed to start"
    exit 1
  fi
  sleep 1
done

# Install dependencies (if needed)
if [ ! -d ".venv" ]; then
  echo "Installing dependencies..."
  poetry install
fi

# Run migrations
echo "Running database migrations..."
poetry run alembic upgrade head

# Start dev server in background
echo "Starting dev server..."
poetry run uvicorn src.main:app --reload --port 8000 &
DEV_SERVER_PID=$!
echo $DEV_SERVER_PID > .harness/dev_server.pid

# Wait for server to be ready
echo "Waiting for dev server..."
for i in {1..30}; do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    echo "========================================"
    echo "Development environment ready!"
    echo "========================================"
    echo "Dev server: http://localhost:8000"
    echo "API docs:   http://localhost:8000/docs"
    echo "PID:        $DEV_SERVER_PID"
    echo ""
    echo "To stop:    kill $DEV_SERVER_PID && docker-compose down"
    echo "Or run:     ./reset.sh"
    exit 0
  fi
  sleep 1
done

echo "ERROR: Dev server failed to start"
kill $DEV_SERVER_PID 2>/dev/null || true
exit 1
```

---

## Patch 3: Init Modes for Existing Projects

*Insert as new section after "Distribution & Installation"*

## Initialization Modes

The harness supports three initialization modes to handle different project states:

### Mode Detection

```bash
# Auto-detect mode (default)
harness init --spec requirements.md

# Force specific mode
harness init --spec requirements.md --mode new     # Greenfield project
harness init --spec requirements.md --mode adopt   # Existing codebase
harness init --resume                              # Continue partial init
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INIT MODE AUTO-DETECTION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ harness init --spec requirements.md                                     │
│                                                                             │
│  STEP 1: Check for existing harness files                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  if exists(.harness.yaml) or exists(features.json):                │   │
│  │                                                                     │   │
│  │      Found existing harness configuration.                         │   │
│  │                                                                     │   │
│  │      Options:                                                       │   │
│  │      [R]esume  - Continue from existing state                      │   │
│  │      [O]verwrite - Start fresh (backs up existing to .harness.bak)│   │
│  │      [A]bort - Exit without changes                                │   │
│  │                                                                     │   │
│  │      Choice: _                                                      │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  STEP 2: Analyze project state (if no harness files)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  Scanning project...                                                │   │
│  │                                                                     │   │
│  │  Source code:     ✓ Found (src/, 47 Python files)                  │   │
│  │  Tests:           ✓ Found (tests/, 23 test files)                  │   │
│  │  Package manager: ✓ Found (pyproject.toml, Poetry)                 │   │
│  │  Docker:          ✓ Found (docker-compose.yaml)                    │   │
│  │  Database:        ✓ Found (alembic/, PostgreSQL)                   │   │
│  │                                                                     │   │
│  │  Detected: Existing project with test suite                        │   │
│  │  Recommended mode: ADOPT                                            │   │
│  │                                                                     │   │
│  │  Proceed with adopt mode? [Y/n]: _                                 │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  STEP 3: Mode selection matrix                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  Has Harness │ Has Code │ Has Tests │ Auto Mode                    │   │
│  │  ──────────────────────────────────────────────────────────────── │   │
│  │     Yes      │    *     │     *     │ Prompt (resume/overwrite)   │   │
│  │     No       │   Yes    │    Yes    │ ADOPT                        │   │
│  │     No       │   Yes    │    No     │ ADOPT (with warning)         │   │
│  │     No       │   No     │     *     │ NEW (greenfield)             │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Mode: NEW (Greenfield Project)

For projects starting from scratch. This is the default behavior documented in v1.2.

```bash
harness init --spec requirements.md --mode new
```

**Initializer creates:**
- Complete project structure (src/, tests/, etc.)
- All configuration files
- init.sh and reset.sh
- features.json with all features passes: false
- Empty test stubs for each feature

### Mode: ADOPT (Existing Project)

For adding harness management to an existing codebase.

```bash
harness init --spec requirements.md --mode adopt
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ADOPT MODE WORKFLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ harness init --spec new-features.md --mode adopt                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 1: PROJECT ANALYSIS                                          │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  Analyzing existing project...                                      │   │
│  │                                                                     │   │
│  │  Structure:                                                         │   │
│  │    src/                                                             │   │
│  │    ├── main.py (FastAPI app)                                       │   │
│  │    ├── api/ (12 route files)                                       │   │
│  │    ├── models/ (8 SQLAlchemy models)                               │   │
│  │    └── services/ (6 service modules)                               │   │
│  │                                                                     │   │
│  │  Detected patterns:                                                 │   │
│  │    • Framework: FastAPI                                            │   │
│  │    • ORM: SQLAlchemy                                               │   │
│  │    • Auth: JWT (python-jose)                                       │   │
│  │    • Testing: pytest + httpx                                       │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 2: TEST DISCOVERY                                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  Running existing tests...                                          │   │
│  │                                                                     │   │
│  │  $ poetry run pytest tests/ -v --tb=no                             │   │
│  │                                                                     │   │
│  │  Results:                                                           │   │
│  │    ✓ 45 passed                                                     │   │
│  │    ✗ 3 failed (pre-existing failures)                              │   │
│  │    ○ 2 skipped                                                     │   │
│  │                                                                     │   │
│  │  Test files found:                                                  │   │
│  │    tests/test_auth.py (8 tests, all passing)                       │   │
│  │    tests/test_users.py (12 tests, all passing)                     │   │
│  │    tests/test_posts.py (15 tests, 2 failing)                       │   │
│  │    tests/test_comments.py (10 tests, all passing)                  │   │
│  │    tests/test_admin.py (5 tests, 1 failing)                        │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 3: FEATURE MAPPING                                           │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  Mapping existing functionality to features...                      │   │
│  │                                                                     │   │
│  │  EXISTING (inferred from code + tests):                            │   │
│  │    #1  User registration        → tests/test_auth.py    ✓ PASSING │   │
│  │    #2  User login               → tests/test_auth.py    ✓ PASSING │   │
│  │    #3  User logout              → tests/test_auth.py    ✓ PASSING │   │
│  │    #4  View user profile        → tests/test_users.py   ✓ PASSING │   │
│  │    #5  Update user profile      → tests/test_users.py   ✓ PASSING │   │
│  │    #6  Create post              → tests/test_posts.py   ✗ FAILING │   │
│  │    #7  Edit post                → tests/test_posts.py   ✓ PASSING │   │
│  │    ...                                                              │   │
│  │                                                                     │   │
│  │  NEW (from spec):                                                   │   │
│  │    #20 User can upload avatar   → tests/e2e/test_avatar.py (new)  │   │
│  │    #21 User can follow others   → tests/e2e/test_follow.py (new)  │   │
│  │    #22 Activity feed            → tests/e2e/test_feed.py (new)    │   │
│  │    ...                                                              │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 4: CREATE HARNESS FILES                                      │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  Creating harness configuration...                                  │   │
│  │                                                                     │   │
│  │  Created: .harness.yaml                                             │   │
│  │  Created: features.json                                             │   │
│  │    • 19 existing features (17 passing, 2 failing)                  │   │
│  │    • 12 new features (all pending)                                 │   │
│  │  Created: claude-progress.txt                                       │   │
│  │                                                                     │   │
│  │  Checking for init.sh...                                            │   │
│  │    Found existing docker-compose.yaml                              │   │
│  │    No init.sh found                                                 │   │
│  │  Created: init.sh (wraps existing docker-compose)                  │   │
│  │  Created: reset.sh                                                  │   │
│  │                                                                     │   │
│  │  Created: .harness/                                                 │   │
│  │    • test_baseline.json (45 passing tests recorded)                │   │
│  │    • file_sizes.json (tracked 47 source files)                     │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 5: SUMMARY                                                   │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  ✓ Harness initialized in ADOPT mode                               │   │
│  │                                                                     │   │
│  │  Project status:                                                    │   │
│  │    Features:  17/31 passing (55%)                                  │   │
│  │    Tests:     45/50 passing (90%)                                  │   │
│  │                                                                     │   │
│  │  Pre-existing issues:                                               │   │
│  │    ⚠ 2 features have failing tests (marked passes: false)         │   │
│  │    ⚠ 3 test failures in baseline (will not trigger regression)    │   │
│  │                                                                     │   │
│  │  Next steps:                                                        │   │
│  │    1. Review features.json for accuracy                            │   │
│  │    2. Fix pre-existing test failures (optional)                    │   │
│  │    3. Run: harness run                                              │   │
│  │                                                                     │   │
│  │  Committed: "Initialize harness (adopt mode)"                       │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Adopt Mode Initializer Prompt

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ADOPT MODE INITIALIZER PROMPT                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  You are ADOPTING an existing project for harness management.              │
│                                                                             │
│  This project already has code and possibly tests. Your job is to         │
│  catalog and configure — NOT to modify existing code.                      │
│                                                                             │
│  PHASE 1: ANALYZE EXISTING CODE                                            │
│  ─────────────────────────────────────────────────────────────────────────  │
│  1. Explore the codebase structure                                         │
│     - ls -la, find . -name "*.py", etc.                                   │
│     - Identify main entry point                                           │
│     - Map out the module structure                                        │
│                                                                             │
│  2. Identify frameworks and patterns                                       │
│     - Check pyproject.toml / requirements.txt for dependencies            │
│     - Note: web framework, ORM, auth method, etc.                         │
│     - Document these in claude-progress.txt                               │
│                                                                             │
│  3. Find existing test files                                               │
│     - List all test files                                                 │
│     - Note the testing framework (pytest, unittest, etc.)                 │
│                                                                             │
│  PHASE 2: RUN EXISTING TESTS                                               │
│  ─────────────────────────────────────────────────────────────────────────  │
│  4. Execute the test suite                                                 │
│     $ poetry run pytest tests/ -v --tb=short                              │
│                                                                             │
│  5. Record results                                                         │
│     - Which tests pass → these features are DONE                          │
│     - Which tests fail → these need fixing OR are pre-existing failures  │
│     - Note: pre-existing failures go in baseline, not treated as regressions│
│                                                                             │
│  PHASE 3: CREATE features.json                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│  6. Identify existing features from code and tests                        │
│     - Each test file often maps to a feature area                         │
│     - Each passing test file = feature with passes: true                  │
│                                                                             │
│  7. Add new features from the provided spec                               │
│     - These all start as passes: false                                    │
│     - Create test_file paths for each (can be new files)                  │
│                                                                             │
│  8. Apply granularity rules to new features                               │
│     - ≤7 verification steps per feature                                   │
│     - ≤5 files touched per feature                                        │
│                                                                             │
│  PHASE 4: CREATE HARNESS FILES ONLY                                        │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Create these files:                                                       │
│  ✓ .harness.yaml      - Configuration                                     │
│  ✓ features.json      - Feature tracking                                  │
│  ✓ claude-progress.txt - Progress log with Session 0 entry               │
│                                                                             │
│  For init.sh / reset.sh:                                                   │
│  - If they exist: DO NOT overwrite, note in progress file                 │
│  - If docker-compose.yaml exists: create init.sh that wraps it            │
│  - If neither exists: create both from scratch                            │
│                                                                             │
│  PHASE 5: DO NOT MODIFY EXISTING CODE                                      │
│  ─────────────────────────────────────────────────────────────────────────  │
│  ✗ Do NOT refactor existing code                                          │
│  ✗ Do NOT "fix" existing issues you find                                  │
│  ✗ Do NOT update dependencies                                             │
│  ✗ Do NOT modify existing tests                                           │
│                                                                             │
│  Your job is OBSERVATION and CATALOGING only.                              │
│  Future coding sessions will make changes.                                 │
│                                                                             │
│  PHASE 6: DOCUMENT ARCHITECTURE                                            │
│  ─────────────────────────────────────────────────────────────────────────  │
│  In claude-progress.txt Session 0, document:                              │
│  - Existing architecture patterns                                          │
│  - Technology choices (ORM, auth, etc.)                                   │
│  - Code conventions observed                                               │
│  - Pre-existing issues/tech debt noted                                    │
│  - Recommendations for future agents                                       │
│                                                                             │
│  This helps future agents follow existing patterns instead of              │
│  introducing inconsistencies.                                              │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  EXISTING PROJECT SUMMARY (from harness scan):                             │
│  {{existing_project_summary}}                                              │
│                                                                             │
│  NEW FEATURES TO ADD (from spec):                                          │
│  {{spec_content}}                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Mode: RESUME (Continue Partial Init)

For continuing when initialization was interrupted.

```bash
harness init --resume
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RESUME MODE                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ harness init --resume                                                   │
│                                                                             │
│  Checking initialization state...                                          │
│                                                                             │
│  Found partial initialization:                                             │
│    ✓ .harness.yaml exists                                                  │
│    ✓ features.json exists (32 features)                                    │
│    ✗ init.sh missing                                                       │
│    ✗ reset.sh missing                                                      │
│    ✗ claude-progress.txt missing                                           │
│    ✗ test stubs not created                                                │
│                                                                             │
│  Resuming initialization...                                                │
│                                                                             │
│  [Runs initializer with context about what's already done]                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Add Features to Existing Harnessed Project

For adding features after initial setup is complete:

```bash
harness add-features --spec new-requirements.md
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ADD FEATURES                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ harness add-features --spec new-requirements.md                         │
│                                                                             │
│  Current state:                                                            │
│    Features: 47/47 passing (100%)                                          │
│    Status: All features complete                                           │
│                                                                             │
│  Analyzing new requirements...                                             │
│                                                                             │
│  New features to add:                                                      │
│    #48 User can enable 2FA                                                 │
│    #49 User can connect social accounts                                    │
│    #50 Admin can view audit log                                            │
│    #51 Admin can export user data                                          │
│    #52 Rate limiting on API endpoints                                      │
│                                                                             │
│  Add 5 new features? [Y/n]: y                                             │
│                                                                             │
│  Updated: features.json (47 → 52 features)                                │
│  Created: test stubs for new features                                      │
│  Updated: claude-progress.txt                                              │
│  Committed: "Add 5 new features from new-requirements.md"                  │
│                                                                             │
│  Ready for: harness run                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Patch 4: Test Baseline for Adopt Mode

*Insert in Verification System section*

### Initializing Baseline from Existing Tests

In adopt mode, the test baseline captures the current state, including any pre-existing failures:

```python
@dataclass
class AdoptedTestBaseline(TestBaseline):
    """Extended baseline for adopted projects."""
    pre_existing_failures: List[str]  # Tests that were already failing
    adoption_note: str
    
def initialize_baseline_from_existing(project_dir: Path) -> AdoptedTestBaseline:
    """For adopt mode: discover what's already passing and failing."""
    
    # Try to run existing tests
    result = run_command(
        "poetry run pytest tests/ -v --tb=no",
        cwd=project_dir,
        timeout=300
    )
    
    # Parse output
    passing, failing = parse_pytest_output(result.stdout)
    
    return AdoptedTestBaseline(
        session=0,
        timestamp=now(),
        passing_tests=passing,
        total_passing=len(passing),
        total_tests=len(passing) + len(failing),
        pre_existing_failures=failing,
        adoption_note=f"Adopted existing project. {len(failing)} pre-existing test failures."
    )

def check_for_regressions_with_adoption(
    project_dir: Path, 
    baseline: AdoptedTestBaseline
) -> List[str]:
    """
    Check for regressions, but don't flag pre-existing failures.
    
    A regression is when a previously-PASSING test now fails.
    Pre-existing failures are expected and not regressions.
    """
    current = run_tests(project_dir)
    
    # Only tests that WERE passing but NOW fail are regressions
    regressions = [
        t for t in baseline.passing_tests 
        if t not in current.passing_tests
    ]
    
    # Log if pre-existing failures got fixed (nice to know!)
    fixed = [
        t for t in baseline.pre_existing_failures
        if t in current.passing_tests
    ]
    if fixed:
        log_event("pre_existing_failures_fixed", {"tests": fixed})
    
    return regressions
```

### features.json for Adopted Projects

```json
{
  "project": "existing-api",
  "generated_by": "initializer",
  "init_mode": "adopt",
  "adopted_at": "2025-01-16T10:00:00Z",
  "last_updated": "2025-01-16T10:00:00Z",
  
  "adoption_notes": {
    "pre_existing_test_failures": 3,
    "features_from_existing_code": 19,
    "features_from_spec": 12
  },
  
  "features": [
    {
      "id": 1,
      "category": "auth",
      "description": "User can register with email and password",
      "test_file": "tests/test_auth.py::TestRegistration",
      "origin": "existing",
      "passes": true
    },
    {
      "id": 6,
      "category": "posts",
      "description": "User can create a post",
      "test_file": "tests/test_posts.py::TestCreatePost",
      "origin": "existing",
      "passes": false,
      "note": "Pre-existing test failure"
    },
    {
      "id": 20,
      "category": "social",
      "description": "User can upload avatar",
      "test_file": "tests/e2e/test_avatar.py",
      "origin": "spec",
      "verification_steps": [
        "Navigate to profile settings",
        "Click upload avatar",
        "Select valid image file",
        "Verify avatar appears on profile"
      ],
      "size_estimate": "small",
      "passes": false
    }
  ]
}
```

---

## Patch 5: Updated CLI Reference

*Replace CLI section in Human Escape Hatches*

```bash
# ============================================================================
# INITIALIZATION COMMANDS
# ============================================================================

# Initialize new project (auto-detects mode)
harness init --spec requirements.md

# Force specific init mode
harness init --spec requirements.md --mode new      # Greenfield
harness init --spec requirements.md --mode adopt    # Existing codebase

# Resume partial initialization
harness init --resume

# Add features to already-initialized project
harness add-features --spec new-requirements.md

# ============================================================================
# SESSION COMMANDS  
# ============================================================================

# Run a coding session
harness run

# Run in dry-run mode (preview without executing)
harness run --dry-run

# Run with specific feature (override auto-selection)
harness run --feature 15

# ============================================================================
# STATUS & HEALTH COMMANDS
# ============================================================================

# Check overall status
harness status

# Check project health
harness health

# Verify a specific feature
harness verify --feature 12

# Verify all features (full re-verification)
harness verify --all

# ============================================================================
# QUALITY COMMANDS
# ============================================================================

# Trigger cleanup session
harness cleanup

# Run lint check
harness lint

# Show file size report
harness files

# ============================================================================
# CONTROL COMMANDS
# ============================================================================

# Pause harness
harness pause

# Resume paused harness
harness resume

# Skip a feature
harness skip --feature 12 --reason "Blocked on external API"

# Override feature status
harness override --feature 11 --passes true

# Manual verification
harness manual-verify --feature 11

# ============================================================================
# HANDOFF COMMANDS
# ============================================================================

# Hand off to human
harness handoff

# Take back from human
harness takeback

# Abort everything
harness abort

# ============================================================================
# DEBUG COMMANDS
# ============================================================================

# Show detailed logs
harness logs

# Query logs
harness logs --query "feature 12"

# Show last session details
harness logs --session last

# Export session for debugging
harness export-session --session 7 --output session-7-debug.json
```

---

## Patch 6: Updated Configuration for Adopt Mode

*Add to Configuration section*

```yaml
# .harness.yaml - Additional settings for adopt mode

# Initialization mode (set automatically, can be referenced)
init:
  mode: adopt                      # "new" or "adopt"
  adopted_at: "2025-01-16T10:00:00Z"
  spec_file: requirements.md

# Adopt-mode specific settings
adoption:
  # How to handle pre-existing test failures
  pre_existing_failures: baseline  # "baseline" (ignore) or "fix_first" (prioritize fixing)
  
  # Whether to create wrappers for existing scripts
  wrap_existing_scripts: true      # Create init.sh wrapper for docker-compose, etc.
  
  # Preserve these files (never overwrite)
  preserve:
    - docker-compose.yaml
    - Dockerfile
    - .env.example
    - Makefile
```

---

## Summary of Patches

| Patch | Description |
|-------|-------------|
| **Patch 1** | Restored distribution details: local dev, version pinning, upgrading |
| **Patch 2** | Restored implementation details: Checkpoint class, prompt selection, full init.sh |
| **Patch 3** | New init modes: auto-detection, new/adopt/resume modes, adopt workflow |
| **Patch 4** | Adopt mode test baseline: handling pre-existing failures |
| **Patch 5** | Updated CLI reference: all commands including new init options |
| **Patch 6** | Configuration updates: adopt-mode specific settings |

---

## Applying This Patch

To create v1.2.1, merge these patches into the appropriate sections of the v1.2 document:

1. **Patch 1** → Insert after "Running Harness Commands"
2. **Patch 2** → Insert as "Appendix: Implementation Details" or inline in relevant sections
3. **Patch 3** → Insert as new major section "Initialization Modes" after Distribution
4. **Patch 4** → Insert in "Verification System" section
5. **Patch 5** → Replace CLI section in "Human Escape Hatches"
6. **Patch 6** → Add to "Configuration" section

Update version references from v1.2.0 to v1.2.1 throughout.