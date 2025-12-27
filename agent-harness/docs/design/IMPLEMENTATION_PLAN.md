# Universal Agent Harness - Implementation Plan

## Version 1.0.0

Based on SYSTEM_DESIGN.md v1.2.1 and SYSTEM_DESIGN_PATCH.md

---

## Overview

This implementation plan breaks down the Universal Agent Harness into small, atomic, composable phases. Each phase:

- Can be implemented independently
- Can be tested in isolation
- Delivers working, usable functionality
- Has clear input/output contracts
- Has explicit dependencies on other phases

The plan follows a **depth-first approach**: build the minimal vertical slice first, then expand horizontally.

---

## Design Deviations

This section documents intentional deviations from the original design made during implementation.

### Phase 3.1: AgentRunner API Changes

The original design specified a simpler API signature. The implementation evolved to:

1. **Constructor changes:** Takes `api_key`, `model`, and `max_tokens` directly instead of a `Config` object, allowing more flexible instantiation.

2. **`run_conversation` signature:** Changed from accepting raw messages and tools to:
   - `initial_message: str` - First user message
   - `session_type: str` - Determines tool selection automatically
   - `tool_executor: Optional[ToolExecutor]` - Callback for tool execution
   - Returns `AgentSession` instead of `AsyncIterator[AgentEvent]`

3. **New dataclasses:** Added `TokenUsage`, `ConversationTurn`, and `AgentSession` for richer state tracking.

**Rationale:** The new API provides better encapsulation of the conversation loop and cleaner integration with the tool system.

### Phase 3.4: Tool Module Restructuring

The original design specified:
```
tools/
├── filesystem.py
├── shell.py
└── schemas.py
```

The implementation uses:
```
tools/
├── definitions.py    # Tool schemas and session mappings
├── executor.py       # ToolExecutor class with handler registration
└── schemas.py        # Core schema types
```

**Rationale:** The harness provides high-level tools (run_tests, mark_feature_complete, etc.) rather than raw file/shell access. File and shell operations are delegated to the underlying agent's native capabilities (e.g., Claude Code's built-in tools). This separation of concerns simplifies the harness while allowing agents to use their full capabilities.

### Tool Execution Model

Original design used standalone functions:
```python
def execute_tool(tool_name: str, params: dict, project_dir: Path) -> ToolResult
```

Implementation uses a class-based approach:
```python
class ToolExecutor:
    def register_handler(self, tool_name: str, handler: ToolHandler) -> None
    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult
```

**Rationale:** The class-based approach allows:
- Handler registration per session
- Execution logging
- Support for both sync and async handlers
- Input validation against schemas

---

## Critical Path

The critical path for a working prototype:

```
Phase 1.1 (Project Structure)
    |
    v
Phase 1.2 (Config Loader) --> Phase 1.3 (CLI Skeleton)
    |
    v
Phase 2.1 (Features Schema) --> Phase 2.2 (Session State)
    |
    v
Phase 3.1 (Agent Runner) --> Phase 3.2 (Prompts)
    |
    v
Phase 4.1 (Git Operations) --> Phase 4.2 (Checkpoints)
    |
    v
Phase 5.1 (Test Runner) --> Phase 5.2 (Verification)
    |
    v
Phase 6.1 (Session Lifecycle) --> First working `harness run`
```

Everything else can be built in parallel or deferred.

---

## Phase 1: Foundation

### Phase 1.1: Project Structure

**Goal:** Establish the Python package structure with Poetry.

**Scope:**
- Create `pyproject.toml` with dependencies
- Create package structure under `src/agent_harness/`
- Set up pytest configuration
- Create `.gitignore`

**Files to Create:**
```
agent-harness/
├── pyproject.toml
├── poetry.lock (generated)
├── README.md
├── .gitignore
├── src/
│   └── agent_harness/
│       ├── __init__.py
│       └── version.py
└── tests/
    ├── __init__.py
    └── conftest.py
```

**Dependencies:** None (first phase)

**Input Contract:** None

**Output Contract:**
- `poetry install` succeeds
- `poetry run python -c "import agent_harness"` succeeds
- `poetry run pytest` runs (even with no tests)

**Acceptance Criteria:**
- [ ] Package installs without errors
- [ ] Version is accessible via `agent_harness.__version__`
- [ ] pytest discovers test directory

**Complexity:** Small

---

### Phase 1.2: Configuration Loader

**Goal:** Load and validate `.harness.yaml` configuration files.

**Scope:**
- Define configuration dataclasses
- Implement YAML loading with defaults
- Implement configuration validation
- Handle missing/invalid config gracefully

**Files to Create/Modify:**
```
src/agent_harness/
├── config.py         # Dataclasses and loading
└── exceptions.py     # Custom exceptions
```

**Dependencies:** Phase 1.1

**Input Contract:**
- Path to project directory (optional, defaults to cwd)
- `.harness.yaml` file (optional, uses defaults if missing)

**Output Contract:**
```python
@dataclass
class Config:
    project: ProjectConfig
    environment: EnvironmentConfig
    testing: TestingConfig
    costs: CostsConfig
    models: ModelsConfig
    context: ContextConfig
    progress: ProgressConfig
    quality: QualityConfig
    verification: VerificationConfig
    features: FeaturesConfig
    github: GithubConfig
    logging: LoggingConfig
    paths: PathsConfig
    tools: ToolsConfig
    preflight: PreflightConfig
    session: SessionConfig
    compatibility: CompatibilityConfig

def load_config(project_dir: Path) -> Config
```

**Acceptance Criteria:**
- [ ] Loads valid YAML config
- [ ] Applies sensible defaults for missing fields
- [ ] Raises `ConfigError` for invalid config
- [ ] Supports all config fields from SYSTEM_DESIGN.md

**Complexity:** Medium

---

### Phase 1.3: CLI Skeleton

**Goal:** Establish the CLI entry point with Click.

**Scope:**
- Create main CLI group
- Add `version` command
- Add placeholder commands (init, run, status, pause, resume)
- Set up Rich for terminal output

**Files to Create/Modify:**
```
src/agent_harness/
├── cli.py            # Click commands
└── console.py        # Rich console utilities
```

**Dependencies:** Phase 1.1, Phase 1.2

**Input Contract:** Command-line arguments

**Output Contract:**
- `harness --version` prints version
- `harness --help` shows available commands
- Commands exit with appropriate codes

**Acceptance Criteria:**
- [ ] `poetry run harness --version` works
- [ ] `poetry run harness --help` lists commands
- [ ] Rich output is colorized in terminals

**Complexity:** Small

---

## Phase 2: State Management

### Phase 2.1: Features Schema

**Goal:** Define and validate the features.json schema.

**Scope:**
- Define Feature dataclass
- Define FeaturesFile dataclass
- Implement loading/saving with validation
- Implement feature queries (next feature, by ID, by status)

**Files to Create/Modify:**
```
src/agent_harness/
└── features.py       # Feature schema and operations
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Path to `features.json`

**Output Contract:**
```python
@dataclass
class Feature:
    id: int
    category: str
    description: str
    test_file: str
    verification_steps: List[str]
    size_estimate: str  # "small", "medium", "large"
    depends_on: List[int]
    passes: bool
    origin: str  # "spec", "existing"
    verification_type: str  # "automated", "hybrid", "manual"
    note: Optional[str]

@dataclass
class FeaturesFile:
    project: str
    generated_by: str
    init_mode: str
    last_updated: str
    features: List[Feature]

def load_features(path: Path) -> FeaturesFile
def save_features(path: Path, features: FeaturesFile) -> None
def get_next_feature(features: FeaturesFile) -> Optional[Feature]
def get_feature_by_id(features: FeaturesFile, id: int) -> Optional[Feature]
def validate_features(features: FeaturesFile) -> ValidationResult
def detect_dependency_cycles(features: List[Feature]) -> List[List[int]]
```

**Acceptance Criteria:**
- [ ] Loads valid features.json
- [ ] Validates required fields (test_file, id, description)
- [ ] Detects dependency cycles
- [ ] Finds next available feature respecting dependencies
- [ ] Flags features with >7 verification steps

**Complexity:** Medium

---

### Phase 2.2: Session State

**Goal:** Track session state between runs.

**Scope:**
- Define SessionState dataclass
- Implement state persistence to `.harness/session_state.json`
- Track current feature, status, stuck count
- Support schema versioning

**Files to Create/Modify:**
```
src/agent_harness/
└── state.py          # Session state management
```

**Dependencies:** Phase 1.2, Phase 2.1

**Input Contract:**
- Path to `.harness/` directory

**Output Contract:**
```python
@dataclass
class SessionState:
    harness_version: str
    schema_version: int
    last_session: int
    status: str  # "complete", "partial", "failed"
    current_feature: Optional[int]
    termination_reason: Optional[str]
    next_prompt: str  # "coding", "continuation", "cleanup"
    stuck_count: int
    timestamp: str
    timeout_count: int

def load_session_state(state_dir: Path) -> SessionState
def save_session_state(state_dir: Path, state: SessionState) -> None
def initialize_session_state(state_dir: Path) -> SessionState
```

**Acceptance Criteria:**
- [ ] Creates state file if missing
- [ ] Preserves state across runs
- [ ] Includes schema version for migrations
- [ ] Updates timestamp on save

**Complexity:** Small

---

### Phase 2.3: Test Baseline

**Goal:** Track which tests were passing before each session.

**Scope:**
- Define TestBaseline dataclass
- Store list of passing test identifiers
- Support adopted projects with pre-existing failures

**Files to Create/Modify:**
```
src/agent_harness/
└── baseline.py       # Test baseline tracking
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Path to `.harness/test_baseline.json`
- Test results from pytest

**Output Contract:**
```python
@dataclass
class TestBaseline:
    session: int
    timestamp: str
    passing_tests: List[str]
    total_passing: int
    total_tests: int
    pre_existing_failures: List[str]  # For adopt mode

def load_baseline(path: Path) -> TestBaseline
def save_baseline(path: Path, baseline: TestBaseline) -> None
def create_baseline_from_test_results(session: int, results: TestResults) -> TestBaseline
```

**Acceptance Criteria:**
- [ ] Stores test identifiers (file::test_name format)
- [ ] Tracks pre-existing failures separately
- [ ] Creates baseline from pytest output

**Complexity:** Small

---

### Phase 2.4: Cost Tracking

**Goal:** Track token usage and costs.

**Scope:**
- Define CostTracker dataclass
- Track per-session and cumulative costs
- Track costs per feature
- Enforce budget limits

**Files to Create/Modify:**
```
src/agent_harness/
└── costs.py          # Cost tracking
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Path to `.harness/costs.yaml`
- Token counts from Claude API

**Output Contract:**
```python
@dataclass
class SessionCost:
    session_id: int
    started: str
    tokens_input: int
    tokens_output: int
    tokens_cached: int
    cost_usd: float

@dataclass
class CostTracker:
    current_session: SessionCost
    total_sessions: int
    total_cost_usd: float
    by_feature: Dict[int, float]

def load_costs(path: Path) -> CostTracker
def save_costs(path: Path, costs: CostTracker) -> None
def add_usage(costs: CostTracker, input_tokens: int, output_tokens: int, cached_tokens: int) -> None
def check_budget(costs: CostTracker, config: CostsConfig) -> BudgetCheck
```

**Acceptance Criteria:**
- [ ] Accumulates costs across sessions
- [ ] Calculates USD from token counts
- [ ] Returns budget exceeded when limits hit
- [ ] Tracks per-feature costs

**Complexity:** Small

---

### Phase 2.5: Progress File Parser

**Goal:** Parse and update claude-progress.txt.

**Scope:**
- Parse structured progress file format
- Extract last session entry
- Extract recent decisions
- Append new session entries

**Files to Create/Modify:**
```
src/agent_harness/
└── progress.py       # Progress file operations
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Path to `claude-progress.txt`

**Output Contract:**
```python
@dataclass
class ProgressEntry:
    session: int
    date: str
    feature_id: Optional[int]
    feature_description: Optional[str]
    what_done: List[str]
    verification: str
    decisions: List[str]
    current_state: str
    next_feature: Optional[str]
    commits: List[str]
    status: str

def parse_progress_file(path: Path) -> List[ProgressEntry]
def get_last_entry(path: Path) -> Optional[ProgressEntry]
def get_recent_decisions(path: Path, n: int = 3) -> List[str]
def append_entry(path: Path, entry: ProgressEntry) -> None
```

**Acceptance Criteria:**
- [ ] Parses session headers correctly
- [ ] Extracts DECISIONS sections
- [ ] Handles empty/new files
- [ ] Appends in correct format

**Complexity:** Medium

---

### Phase 2.6: File Size Tracking

**Goal:** Track source file sizes for quality monitoring.

**Scope:**
- Scan source files and count lines
- Track when files were added
- Detect files over threshold

**Files to Create/Modify:**
```
src/agent_harness/
└── file_sizes.py     # File size tracking
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Project source directory
- Path to `.harness/file_sizes.json`

**Output Contract:**
```python
@dataclass
class FileInfo:
    lines: int
    session_added: int

@dataclass
class FileSizeTracker:
    session: int
    files: Dict[str, FileInfo]

def scan_file_sizes(src_dir: Path) -> Dict[str, int]
def load_file_sizes(path: Path) -> FileSizeTracker
def save_file_sizes(path: Path, tracker: FileSizeTracker) -> None
def get_oversized_files(tracker: FileSizeTracker, max_lines: int) -> List[str]
```

**Acceptance Criteria:**
- [ ] Counts lines in Python files
- [ ] Identifies files over 500 lines (configurable)
- [ ] Tracks growth across sessions

**Complexity:** Small

---

## Phase 3: Agent Integration

### Phase 3.1: Agent Runner

**Goal:** Execute Claude API conversations with tool use.

**Scope:**
- Initialize Anthropic client
- Send messages with system prompt
- Handle streaming responses
- Parse tool use and execute tools
- Track token usage

**Files to Create/Modify:**
```
src/agent_harness/
└── agent.py          # Claude API integration
```

**Dependencies:** Phase 1.2, Phase 2.4

**Input Contract:**
- System prompt
- Initial user message
- Session type (for tool selection)
- Tool executor function
- Config (model, timeouts)

**Output Contract:**
```python
@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_tokens(self) -> int
    def __add__(self, other: "TokenUsage") -> "TokenUsage"

@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]

@dataclass
class AgentResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""

    @property
    def has_tool_calls(self) -> bool

@dataclass
class ConversationTurn:
    role: str  # "user" or "assistant"
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentSession:
    model: str
    system_prompt: str
    session_type: str
    history: list[ConversationTurn] = field(default_factory=list)
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    tool_call_count: int = 0

# Type alias for tool executor function
ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]

class AgentRunner:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    )

    async def send_message(
        self,
        messages: list[MessageParam],
        system_prompt: str,
        tools: Optional[list[dict]] = None,
    ) -> AgentResponse

    async def send_message_streaming(
        self,
        messages: list[MessageParam],
        system_prompt: str,
        tools: Optional[list[dict]] = None,
        on_text: Optional[Callable[[str], None]] = None,
    ) -> AgentResponse

    async def run_conversation(
        self,
        initial_message: str,
        system_prompt: str,
        session_type: str = "coding",
        tool_executor: Optional[ToolExecutor] = None,
        max_turns: int = 50,
        on_response: Optional[Callable[[AgentResponse], None]] = None,
    ) -> AgentSession

    def get_cost(self, usage: TokenUsage) -> float

def create_agent_runner(
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> AgentRunner

def is_anthropic_available() -> bool
```

**Acceptance Criteria:**
- [x] Connects to Claude API
- [x] Sends system and user messages
- [x] Handles streaming responses
- [x] Executes tool calls via ToolExecutor callback
- [x] Reports token usage via TokenUsage dataclass

**Complexity:** Large

---

### Phase 3.2: Prompt Templates

**Goal:** Generate prompts for different session types.

**Scope:**
- Initializer prompt template
- Coding prompt template
- Continuation prompt template
- Cleanup prompt template
- Template variable substitution

**Files to Create/Modify:**
```
src/agent_harness/
├── prompts/
│   ├── __init__.py
│   ├── initializer.py
│   ├── coding.py
│   ├── continuation.py
│   └── cleanup.py
└── prompt_builder.py  # Template rendering
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Prompt type
- Template variables (orientation summary, feature details, etc.)

**Output Contract:**
```python
def build_initializer_prompt(spec_content: str, project_summary: str) -> str
def build_coding_prompt(orientation: str) -> str
def build_continuation_prompt(orientation: str, partial_details: str) -> str
def build_cleanup_prompt(quality_issues: str) -> str

def select_prompt_type(state: SessionState, features: FeaturesFile, config: Config) -> str
```

**Acceptance Criteria:**
- [ ] Generates valid prompts for each type
- [ ] Substitutes template variables
- [ ] Includes structured output prefix instructions
- [ ] Includes verification rules

**Complexity:** Medium

---

### Phase 3.3: Orientation Generator

**Goal:** Generate compact orientation summaries for agents.

**Scope:**
- Generate current state summary
- Generate last session summary
- Identify next feature with dependencies
- Extract recent decisions
- Format for prompt injection

**Files to Create/Modify:**
```
src/agent_harness/
└── orientation.py    # Orientation summary generator
```

**Dependencies:** Phase 2.1, Phase 2.2, Phase 2.5

**Input Contract:**
- Session state
- Features file
- Progress file
- Project directory

**Output Contract:**
```python
def generate_orientation_summary(
    project_dir: Path,
    session_state: SessionState,
    features: FeaturesFile,
    progress_entries: List[ProgressEntry]
) -> str

def generate_continuation_details(
    feature: Feature,
    last_entry: ProgressEntry
) -> str
```

**Acceptance Criteria:**
- [ ] Summary is under 1000 tokens
- [ ] Includes current session number
- [ ] Includes feature progress percentage
- [ ] Includes next feature details
- [ ] Includes last 3 decisions

**Complexity:** Medium

---

### Phase 3.4: Tool Definitions

**Goal:** Define tools available to the agent.

**Scope:**
- Harness-specific tools (test running, progress tracking, feature management)
- Tool schemas for Claude API
- Tool execution with validation
- Session-type-based tool selection

**Files to Create/Modify:**
```
src/agent_harness/
└── tools/
    ├── __init__.py       # Public exports
    ├── definitions.py    # Tool schema definitions and session mappings
    ├── executor.py       # Tool execution with handler registration
    └── schemas.py        # ToolSchema dataclass and validation utilities
```

**Design Note:** The implementation consolidated tool logic into `definitions.py` and `executor.py` rather than separate `filesystem.py` and `shell.py` files. This reflects the harness's focus on high-level operations (running tests, tracking progress) rather than raw file/shell access, which is delegated to the underlying agent's native capabilities.

**Dependencies:** Phase 1.2

**Input Contract:**
- Session type for tool selection
- Project directory (for tool execution context)
- Tool arguments from agent

**Output Contract:**
```python
# schemas.py
@dataclass
class PropertySchema:
    type: str
    description: str
    enum: Optional[list[str]] = None
    default: Optional[Any] = None
    items: Optional[dict[str, Any]] = None  # For array types

@dataclass
class ToolSchema:
    name: str
    description: str
    properties: dict[str, PropertySchema] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]  # Convert to Claude API format

def create_tool_schema(
    name: str,
    description: str,
    properties: Optional[dict[str, dict[str, Any]]] = None,
    required: Optional[list[str]] = None,
) -> ToolSchema

def validate_schema(schema: ToolSchema) -> list[str]
def validate_tool_input(schema: ToolSchema, inputs: dict[str, Any]) -> list[str]

# definitions.py
HARNESS_TOOLS: dict[str, ToolSchema]  # All available tools

# Session-specific tool lists
CODING_TOOLS: list[str]        # mark_feature_complete, run_tests, etc.
CONTINUATION_TOOLS: list[str]  # Same as coding
CLEANUP_TOOLS: list[str]       # run_lint, check_file_sizes, etc.
INIT_TOOLS: list[str]          # create_features_file, create_init_scripts

def get_tool_by_name(name: str) -> Optional[ToolSchema]
def get_tools_for_session(session_type: str) -> list[ToolSchema]
def get_tools_as_api_format(session_type: str) -> list[dict]

# executor.py
@dataclass
class ToolExecutionResult:
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]

# Type aliases for tool handlers
SyncToolHandler = Callable[[dict[str, Any]], ToolExecutionResult]
AsyncToolHandler = Callable[[dict[str, Any]], Awaitable[ToolExecutionResult]]
ToolHandler = Union[SyncToolHandler, AsyncToolHandler]

class ToolExecutor:
    def __init__(self, project_dir: Path)

    def register_handler(self, tool_name: str, handler: ToolHandler) -> None
    def execute(self, tool_name: str, arguments: dict[str, Any], validate: bool = True) -> ToolExecutionResult
    async def execute_async(self, tool_name: str, arguments: dict[str, Any], validate: bool = True) -> ToolExecutionResult
    def get_execution_log(self) -> list[ToolExecutionResult]
    def clear_execution_log(self) -> None

def validate_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> list[str]
def execute_tool(tool_name: str, arguments: dict[str, Any], executor: ToolExecutor) -> ToolExecutionResult
async def execute_tool_async(tool_name: str, arguments: dict[str, Any], executor: ToolExecutor) -> ToolExecutionResult
def create_default_handlers(project_dir: Path) -> dict[str, ToolHandler]
```

**Available Tools:**
- `run_tests` - Execute pytest for feature verification
- `run_lint` - Run linting checks
- `mark_feature_complete` - Mark feature as passing in features.json
- `update_progress` - Add entry to claude-progress.txt
- `create_checkpoint` - Create rollback checkpoint
- `rollback_checkpoint` - Restore from checkpoint
- `get_feature_status` - Query feature status
- `signal_stuck` - Signal agent is stuck
- `check_file_sizes` - Check for oversized files
- `create_features_file` - Create features.json (init only)
- `create_init_scripts` - Create init.sh/reset.sh (init only)

**Acceptance Criteria:**
- [x] Tool schemas match Claude API format
- [x] Tools are filtered by session type
- [x] Tool inputs are validated against schema
- [x] Execution supports both sync and async handlers
- [x] Execution log tracks all tool calls

**Complexity:** Medium

---

## Phase 4: Git Operations

### Phase 4.1: Git Operations

**Goal:** Perform git operations safely.

**Scope:**
- Check git state (branch, clean, HEAD)
- Create commits
- Get HEAD ref
- List commits between refs
- Reset to ref

**Files to Create/Modify:**
```
src/agent_harness/
└── git_ops.py        # Git operations
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Project directory (must be git repo)

**Output Contract:**
```python
def get_current_branch(project_dir: Path) -> str
def is_working_tree_clean(project_dir: Path) -> bool
def is_detached_head(project_dir: Path) -> bool
def get_head_ref(project_dir: Path) -> str
def commits_between(project_dir: Path, from_ref: str, to_ref: str) -> List[str]
def reset_hard(project_dir: Path, ref: str) -> None
def create_commit(project_dir: Path, message: str, files: List[str] = None) -> str
def stash_changes(project_dir: Path) -> bool
def get_changed_files(project_dir: Path) -> List[str]
```

**Acceptance Criteria:**
- [ ] All operations use GitPython
- [ ] Handles non-git directories gracefully
- [ ] Commit messages are formatted correctly
- [ ] Reset restores exact state

**Complexity:** Medium

---

### Phase 4.2: Checkpoint System

**Goal:** Create and restore checkpoints for rollback.

**Scope:**
- Create checkpoint before risky operations
- Store git ref and state file hashes
- Restore from checkpoint
- Checkpoint retention policy

**Files to Create/Modify:**
```
src/agent_harness/
└── checkpoint.py     # Checkpoint operations
```

**Dependencies:** Phase 4.1, Phase 2.2, Phase 2.3

**Input Contract:**
- Project directory
- Reason for checkpoint

**Output Contract:**
```python
@dataclass
class Checkpoint:
    id: str
    timestamp: str
    session: int
    git_ref: str
    features_json_hash: str
    progress_file_hash: str
    reason: str

def create_checkpoint(project_dir: Path, session: int, reason: str) -> Checkpoint
def rollback_to_checkpoint(project_dir: Path, checkpoint_id: str) -> RollbackResult
def list_checkpoints(project_dir: Path) -> List[Checkpoint]
def cleanup_old_checkpoints(project_dir: Path, max_age_days: int, keep_per_feature: int) -> int
```

**Acceptance Criteria:**
- [ ] Captures git ref and file hashes
- [ ] Copies state files to checkpoint dir
- [ ] Rollback restores exact state
- [ ] Verifies restoration with hash checks

**Complexity:** Medium

---

## Phase 5: Verification System

### Phase 5.1: Test Runner

**Goal:** Execute pytest and parse results.

**Scope:**
- Run pytest with specified test file/directory
- Parse output for pass/fail/error
- Extract test identifiers
- Handle timeouts

**Files to Create/Modify:**
```
src/agent_harness/
└── test_runner.py    # Test execution
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Test file or directory path
- Timeout (optional)
- Extra pytest args (optional)

**Output Contract:**
```python
@dataclass
class TestResult:
    test_id: str  # file::test_name
    status: str   # "passed", "failed", "error", "skipped"
    duration: float
    error_message: Optional[str]

@dataclass
class TestRunResult:
    exit_code: int
    passed: List[str]
    failed: List[str]
    errors: List[str]
    skipped: List[str]
    total: int
    duration: float
    raw_output: str

def run_tests(
    project_dir: Path,
    test_path: str,
    timeout: int = 300
) -> TestRunResult
```

**Acceptance Criteria:**
- [ ] Runs pytest subprocess
- [ ] Parses test identifiers from output
- [ ] Handles timeouts gracefully
- [ ] Returns structured results

**Complexity:** Medium

---

### Phase 5.2: Verification Engine

**Goal:** Independently verify agent claims.

**Scope:**
- Validate max 1 feature per session
- Run feature test file
- Check for regressions against baseline
- Run lint check

**Files to Create/Modify:**
```
src/agent_harness/
└── verification.py   # Verification engine
```

**Dependencies:** Phase 5.1, Phase 2.1, Phase 2.3

**Input Contract:**
- Feature that was claimed complete
- Test baseline
- Project directory

**Output Contract:**
```python
@dataclass
class VerificationResult:
    passed: bool
    feature_test_passed: bool
    regression_tests: List[str]  # Tests that regressed
    lint_errors: int
    lint_warnings: int
    details: str

def verify_feature_completion(
    project_dir: Path,
    feature: Feature,
    baseline: TestBaseline,
    config: VerificationConfig
) -> VerificationResult

def check_for_regressions(
    project_dir: Path,
    baseline: TestBaseline
) -> List[str]  # List of regressed test IDs

def validate_features_diff(
    old_features: FeaturesFile,
    new_features: FeaturesFile
) -> ValidationResult  # Check max 1 feature changed
```

**Acceptance Criteria:**
- [ ] Rejects if >1 feature marked passing
- [ ] Runs feature test file independently
- [ ] Detects regressions against baseline
- [ ] Runs lint check and counts errors

**Complexity:** Medium

---

### Phase 5.3: Lint Runner

**Goal:** Execute linting and parse results.

**Scope:**
- Run configured lint command (ruff by default)
- Parse output for error/warning counts
- Return structured results

**Files to Create/Modify:**
```
src/agent_harness/
└── lint.py           # Lint execution
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Project directory
- Lint command from config

**Output Contract:**
```python
@dataclass
class LintResult:
    exit_code: int
    errors: int
    warnings: int
    issues: List[LintIssue]
    raw_output: str

def run_lint(project_dir: Path, command: str) -> LintResult
```

**Acceptance Criteria:**
- [ ] Runs lint subprocess
- [ ] Parses error and warning counts
- [ ] Returns structured results

**Complexity:** Small

---

## Phase 6: Session Lifecycle

### Phase 6.1: Pre-Flight Checks

**Goal:** Verify environment before launching agent.

**Scope:**
- Verify working directory
- Verify harness files exist
- Verify git state
- Run init.sh (with reset.sh fallback)
- Run health check
- Run baseline tests
- Check budget

**Files to Create/Modify:**
```
src/agent_harness/
└── preflight.py      # Pre-flight checks
```

**Dependencies:** Phase 1.2, Phase 4.1, Phase 5.1, Phase 2.4

**Input Contract:**
- Project directory
- Config

**Output Contract:**
```python
@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    duration: float

@dataclass
class PreflightResult:
    passed: bool
    checks: List[CheckResult]
    duration_seconds: float
    error: Optional[str]

def run_preflight_checks(project_dir: Path, config: Config) -> PreflightResult
```

**Acceptance Criteria:**
- [ ] All checks run in order
- [ ] Tries reset.sh if init.sh fails
- [ ] Aborts if baseline tests fail
- [ ] Reports which check failed

**Complexity:** Medium

---

### Phase 6.2: Progress Monitor

**Goal:** Monitor agent progress during session.

**Scope:**
- Check progress at token intervals
- Detect stuck patterns (no file changes, no tests, repeated errors)
- Generate warning messages
- Force stop after prolonged stuck

**Files to Create/Modify:**
```
src/agent_harness/
└── progress_monitor.py  # Progress monitoring
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Current token count
- Agent actions since last check

**Output Contract:**
```python
@dataclass
class ProgressCheckpoint:
    tokens_used: int
    files_changed: Set[str]
    tests_run: int
    commands_executed: int
    errors_seen: Dict[str, int]

class ProgressMonitor:
    def __init__(self, config: ProgressConfig)
    def record_file_change(self, path: str) -> None
    def record_test_run(self) -> None
    def record_command(self) -> None
    def record_error(self, error: str) -> None
    def check_progress(self, current_tokens: int) -> Optional[str]  # Returns injection message
```

**Acceptance Criteria:**
- [ ] Checks at configured token intervals
- [ ] Detects no-progress patterns
- [ ] Returns warning message when stuck
- [ ] Returns force-stop message after 2 stuck checks

**Complexity:** Medium

---

### Phase 6.3: Context Manager

**Goal:** Track context usage and inject warnings.

**Scope:**
- Track token usage against context window
- Inject 75% warning
- Inject 90% force wrap-up
- Handle 100% hard stop

**Files to Create/Modify:**
```
src/agent_harness/
└── context_manager.py  # Context tracking
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Token counts from agent responses
- Context window size

**Output Contract:**
```python
class ContextManager:
    def __init__(self, config: ContextConfig, context_window: int)
    def add_usage(self, input_tokens: int, output_tokens: int) -> None
    def get_usage_percent(self) -> float
    def check_thresholds(self) -> Optional[str]  # Returns injection message
    def is_at_limit(self) -> bool
```

**Acceptance Criteria:**
- [ ] Tracks cumulative token usage
- [ ] Returns warning at 75%
- [ ] Returns force message at 90%
- [ ] Signals hard stop at 100%

**Complexity:** Small

---

### Phase 6.4: Session Orchestrator

**Goal:** Orchestrate a complete session lifecycle.

**Scope:**
- Run pre-flight checks
- Select prompt type
- Generate orientation
- Create checkpoint
- Run agent conversation
- Monitor progress
- Handle context limits
- Verify completion
- Update state files
- Commit if passed

**Files to Create/Modify:**
```
src/agent_harness/
└── session.py        # Session orchestration
```

**Dependencies:** Phase 6.1, Phase 6.2, Phase 6.3, Phase 3.1, Phase 3.2, Phase 3.3, Phase 4.2, Phase 5.2

**Input Contract:**
- Project directory
- Config
- Dry-run flag

**Output Contract:**
```python
@dataclass
class SessionResult:
    session_id: int
    started_at: str
    ended_at: str
    duration_seconds: float
    termination_reason: str
    feature_id: Optional[int]
    feature_completed: bool
    tokens_used: TokenUsage
    cost_usd: float
    verification_result: Optional[VerificationResult]

async def run_session(project_dir: Path, config: Config, dry_run: bool = False) -> SessionResult
```

**Acceptance Criteria:**
- [ ] Runs pre-flight before agent
- [ ] Creates checkpoint before work
- [ ] Monitors progress during agent run
- [ ] Verifies completion claims
- [ ] Rolls back on verification failure
- [ ] Updates all state files on success

**Complexity:** Large

---

## Phase 7: CLI Commands

### Phase 7.1: Init Command

**Goal:** Implement `harness init` to bootstrap a project.

**Scope:**
- Parse spec file
- Detect project mode (new/adopt)
- Run initializer agent
- Validate generated files
- Initialize state

**Files to Create/Modify:**
```
src/agent_harness/
├── cli.py            # Add init command
└── init.py           # Init logic
```

**Dependencies:** Phase 3.1, Phase 3.2, Phase 2.1, Phase 2.2

**Input Contract:**
- --spec: Path to requirements file
- --mode: new/adopt/auto (default: auto)

**Output Contract:**
- Creates .harness.yaml
- Creates features.json
- Creates init.sh, reset.sh
- Creates claude-progress.txt
- Creates .harness/ directory
- Makes initial git commit

**Acceptance Criteria:**
- [ ] Detects existing code for adopt mode
- [ ] Runs initializer agent successfully
- [ ] Validates features.json structure
- [ ] Initializes test baseline

**Complexity:** Large

---

### Phase 7.2: Run Command

**Goal:** Implement `harness run` to execute a session.

**Scope:**
- Load state and config
- Run session orchestrator
- Handle dry-run mode
- Display progress
- Report results

**Files to Create/Modify:**
```
src/agent_harness/
└── cli.py            # Add run command
```

**Dependencies:** Phase 6.4

**Input Contract:**
- --dry-run: Preview without executing
- --feature: Override feature selection

**Output Contract:**
- Session executes
- State files updated
- Results displayed

**Acceptance Criteria:**
- [ ] Runs session to completion
- [ ] Displays progress with Rich
- [ ] Handles Ctrl+C gracefully
- [ ] Reports success/failure

**Complexity:** Medium

---

### Phase 7.3: Status Command

**Goal:** Implement `harness status` to show project state.

**Scope:**
- Load all state files
- Display feature progress
- Display session history
- Display costs

**Files to Create/Modify:**
```
src/agent_harness/
└── cli.py            # Add status command
```

**Dependencies:** Phase 2.1, Phase 2.2, Phase 2.4

**Input Contract:** None (uses project directory)

**Output Contract:**
- Displays formatted status with Rich

**Acceptance Criteria:**
- [ ] Shows feature progress (X/Y passing)
- [ ] Shows current session info
- [ ] Shows cost totals
- [ ] Shows next prompt type

**Complexity:** Small

---

### Phase 7.4: Health Command

**Goal:** Implement `harness health` to show project health.

**Scope:**
- Run all tests
- Run lint
- Check file sizes
- Calculate composite health score

**Files to Create/Modify:**
```
src/agent_harness/
├── cli.py            # Add health command
└── health.py         # Health calculation
```

**Dependencies:** Phase 5.1, Phase 5.3, Phase 2.6

**Input Contract:** None

**Output Contract:**
```python
@dataclass
class ProjectHealth:
    feature_completion: float
    test_pass_rate: float
    lint_score: float
    file_health: float
    overall: float
    status: str  # "GOOD", "FAIR", "POOR"
```

**Acceptance Criteria:**
- [ ] Runs tests and lint
- [ ] Identifies oversized files
- [ ] Calculates weighted health score
- [ ] Displays with colored status

**Complexity:** Small

---

### Phase 7.5: Verify Command

**Goal:** Implement `harness verify` to manually verify a feature.

**Scope:**
- Run specified feature's test file
- Report pass/fail
- Optionally update features.json

**Files to Create/Modify:**
```
src/agent_harness/
└── cli.py            # Add verify command
```

**Dependencies:** Phase 5.1, Phase 2.1

**Input Contract:**
- --feature: Feature ID to verify
- --all: Verify all features

**Output Contract:**
- Test results displayed
- Feature status optionally updated

**Acceptance Criteria:**
- [ ] Runs correct test file
- [ ] Displays pass/fail clearly
- [ ] Asks before updating features.json

**Complexity:** Small

---

### Phase 7.6: Control Commands

**Goal:** Implement pause, resume, skip, handoff commands.

**Scope:**
- pause: Set status to paused
- resume: Clear paused status
- skip: Mark feature as skipped
- handoff: Pause for human work
- takeback: Resume after human work

**Files to Create/Modify:**
```
src/agent_harness/
└── cli.py            # Add control commands
```

**Dependencies:** Phase 2.2, Phase 2.1

**Input Contract:** Various per command

**Output Contract:**
- State updated appropriately
- Status message displayed

**Acceptance Criteria:**
- [ ] pause stops harness run
- [ ] resume continues from paused
- [ ] skip marks feature and continues
- [ ] handoff/takeback work for human intervention

**Complexity:** Small

---

### Phase 7.7: Cleanup Command

**Goal:** Implement `harness cleanup` to trigger cleanup session.

**Scope:**
- Set next_prompt to cleanup
- Optionally run session immediately

**Files to Create/Modify:**
```
src/agent_harness/
└── cli.py            # Add cleanup command
```

**Dependencies:** Phase 2.2, Phase 6.4

**Input Contract:**
- --now: Run cleanup session immediately

**Output Contract:**
- Cleanup session scheduled or executed

**Acceptance Criteria:**
- [ ] Sets next_prompt to cleanup
- [ ] Can run session immediately
- [ ] Cleanup prompt includes quality issues

**Complexity:** Small

---

## Phase 8: Observability

### Phase 8.1: Event Logger

**Goal:** Log events to structured JSONL files.

**Scope:**
- Define event types and levels
- Write events to appropriate log files
- Support log rotation/retention

**Files to Create/Modify:**
```
src/agent_harness/
└── logging.py        # Event logging
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Event type and data
- Log level

**Output Contract:**
```python
def log_event(event_type: str, data: dict, level: str = "important") -> None
def log_decision(decision: str, context: dict) -> None
def log_agent_action(action_type: str, data: dict) -> None
```

**Acceptance Criteria:**
- [ ] Writes to .harness/logs/events.jsonl
- [ ] Writes to .harness/logs/decisions.jsonl
- [ ] Includes timestamps
- [ ] Supports log levels

**Complexity:** Small

---

### Phase 8.2: Agent Output Parser

**Goal:** Parse structured prefixes from agent output.

**Scope:**
- Parse [FILE:READ], [FILE:WRITE], [CMD:RUN], etc.
- Fall back to heuristics when prefixes missing
- Log parsed actions

**Files to Create/Modify:**
```
src/agent_harness/
└── output_parser.py  # Agent output parsing
```

**Dependencies:** Phase 8.1

**Input Contract:**
- Agent output text
- API response (for tool use fallback)

**Output Contract:**
```python
@dataclass
class ParsedAction:
    type: str  # file_read, file_write, cmd_run, verify_pass, etc.
    data: dict
    source: str  # "prefix" or "heuristic"

def parse_agent_output(output: str) -> List[ParsedAction]
def parse_tool_calls(response: dict) -> List[ParsedAction]
```

**Acceptance Criteria:**
- [ ] Parses all defined prefixes
- [ ] Uses heuristics when prefixes missing
- [ ] Reports whether prefix or heuristic was used

**Complexity:** Medium

---

### Phase 8.3: Logs Command

**Goal:** Implement `harness logs` to query logs.

**Scope:**
- Display recent events
- Filter by query string
- Filter by session

**Files to Create/Modify:**
```
src/agent_harness/
└── cli.py            # Add logs command
```

**Dependencies:** Phase 8.1

**Input Contract:**
- --query: Filter string
- --session: Session ID or "last"
- --level: Minimum level

**Output Contract:**
- Formatted log entries

**Acceptance Criteria:**
- [ ] Shows recent events by default
- [ ] Filters by query string
- [ ] Shows specific session logs

**Complexity:** Small

---

## Phase 9: GitHub Integration

### Phase 9.1: GitHub Sync

**Goal:** Sync features to GitHub Issues.

**Scope:**
- Create issues for features
- Close issues when features pass
- Handle API failures gracefully
- Respect rate limits

**Files to Create/Modify:**
```
src/agent_harness/
└── github_sync.py    # GitHub integration
```

**Dependencies:** Phase 1.2, Phase 2.1

**Input Contract:**
- GitHub repo (from config)
- Features file

**Output Contract:**
```python
def sync_to_github(features: FeaturesFile, config: GithubConfig) -> SyncResult
def create_issue_for_feature(feature: Feature, config: GithubConfig) -> str
def close_issue(issue_number: int, config: GithubConfig) -> bool
```

**Acceptance Criteria:**
- [ ] Creates issues for new features
- [ ] Closes issues when features pass
- [ ] Handles API errors without crashing
- [ ] Respects rate limits

**Complexity:** Medium

---

## Phase 10: Adopt Mode

### Phase 10.1: Project Scanner

**Goal:** Scan existing projects for adopt mode.

**Scope:**
- Detect existing source files
- Detect existing tests
- Detect package manager (Poetry, pip)
- Detect Docker configuration

**Files to Create/Modify:**
```
src/agent_harness/
└── scanner.py        # Project scanning
```

**Dependencies:** Phase 1.2

**Input Contract:**
- Project directory

**Output Contract:**
```python
@dataclass
class ProjectSummary:
    has_source: bool
    source_files: int
    has_tests: bool
    test_files: int
    package_manager: str  # "poetry", "pip", "none"
    has_docker: bool
    frameworks: List[str]  # "fastapi", "flask", etc.

def scan_project(project_dir: Path) -> ProjectSummary
```

**Acceptance Criteria:**
- [ ] Detects Python source files
- [ ] Detects test files
- [ ] Detects package manager
- [ ] Identifies frameworks from imports

**Complexity:** Medium

---

### Phase 10.2: Adopt Mode Init

**Goal:** Initialize harness for existing projects.

**Scope:**
- Run existing tests to create baseline
- Map existing code to features
- Create harness files without modifying code

**Files to Create/Modify:**
```
src/agent_harness/
└── init.py           # Add adopt mode logic
```

**Dependencies:** Phase 10.1, Phase 5.1, Phase 7.1

**Input Contract:**
- Project directory
- Spec file for new features

**Output Contract:**
- Harness files created
- Existing features marked as passing
- Pre-existing failures recorded in baseline

**Acceptance Criteria:**
- [ ] Runs existing tests
- [ ] Creates features for existing functionality
- [ ] Records pre-existing failures
- [ ] Does not modify existing code

**Complexity:** Large

---

## Phase 11: Version Compatibility

### Phase 11.1: Schema Migrations

**Goal:** Support state file migrations between versions.

**Scope:**
- Check schema version on startup
- Run migrations if needed
- Backup before migration
- Abort on incompatible newer version

**Files to Create/Modify:**
```
src/agent_harness/
└── migrations.py     # Schema migrations
```

**Dependencies:** Phase 2.2

**Input Contract:**
- State directory
- Current schema version

**Output Contract:**
```python
def check_version_compatibility(state_dir: Path, config: Config) -> VersionCheck
def migrate_state(state_dir: Path, from_version: int, to_version: int) -> None
def backup_state(state_dir: Path) -> Path
```

**Acceptance Criteria:**
- [ ] Detects schema version mismatch
- [ ] Runs migrations in order
- [ ] Creates backup before migrating
- [ ] Aborts on newer schema

**Complexity:** Medium

---

### Phase 11.2: Migrate Command

**Goal:** Implement `harness migrate` for explicit migrations.

**Scope:**
- Show current vs target version
- Run migrations with --no-backup option
- Show migration history

**Files to Create/Modify:**
```
src/agent_harness/
└── cli.py            # Add migrate command
```

**Dependencies:** Phase 11.1

**Input Contract:**
- --no-backup: Skip backup (dangerous)

**Output Contract:**
- Migrations applied
- Status displayed

**Acceptance Criteria:**
- [ ] Shows version comparison
- [ ] Runs migrations
- [ ] Warns about --no-backup

**Complexity:** Small

---

## Phase 12: MCP Integration

### Phase 12.1: MCP Server Manager

**Goal:** Start and manage MCP servers.

**Scope:**
- Start configured MCP servers
- Connect to servers
- Expose tools to agent
- Handle server lifecycle

**Files to Create/Modify:**
```
src/agent_harness/
└── mcp/
    ├── __init__.py
    ├── manager.py
    └── puppeteer.py
```

**Dependencies:** Phase 1.2, Phase 3.4

**Input Contract:**
- MCP server config

**Output Contract:**
```python
class MCPManager:
    async def start_servers(self) -> None
    async def stop_servers(self) -> None
    def get_tools(self) -> List[Tool]
    async def execute_tool(self, tool_name: str, params: dict) -> ToolResult
```

**Acceptance Criteria:**
- [ ] Starts configured MCP servers
- [ ] Exposes MCP tools to agent
- [ ] Handles server crashes
- [ ] Cleans up on session end

**Complexity:** Large

---

## Dependency Graph

```
Phase 1.1 ─────┬──> Phase 1.2 ──┬──> Phase 1.3
              │                 │
              │                 ├──> Phase 2.1 ──┬──> Phase 2.2
              │                 │               │
              │                 ├──> Phase 2.3 <┘
              │                 │
              │                 ├──> Phase 2.4
              │                 │
              │                 ├──> Phase 2.5
              │                 │
              │                 ├──> Phase 2.6
              │                 │
              │                 ├──> Phase 3.4 ───> Phase 3.1
              │                 │                     │
              │                 └──> Phase 3.2 <──────┘
              │                        │
              │                        └──> Phase 3.3 (deps: 2.1, 2.2, 2.5)
              │
              └──> Phase 4.1 ──┬──> Phase 4.2 (deps: 2.2, 2.3)
                              │
                              └──> Phase 5.1 ──┬──> Phase 5.2 (deps: 2.1, 2.3)
                                              │
                                              └──> Phase 5.3
                                                      │
                                                      v
Phase 6.1 (deps: 1.2, 4.1, 5.1, 2.4) ──> Phase 6.2 ──> Phase 6.3 ──> Phase 6.4
                                                                        │
                                                                        v
Phase 7.1 ──> Phase 7.2 ──> Phase 7.3...Phase 7.7
     │
     v
Phase 8.1 ──> Phase 8.2 ──> Phase 8.3
     │
     v
Phase 9.1
     │
     v
Phase 10.1 ──> Phase 10.2
     │
     v
Phase 11.1 ──> Phase 11.2
     │
     v
Phase 12.1
```

---

## Implementation Order

### Sprint 1: Foundation (Week 1)

1. **Phase 1.1** - Project Structure
2. **Phase 1.2** - Configuration Loader
3. **Phase 1.3** - CLI Skeleton
4. **Phase 2.1** - Features Schema
5. **Phase 2.2** - Session State

**Deliverable:** `harness status` shows placeholder data

### Sprint 2: State Management (Week 2)

6. **Phase 2.3** - Test Baseline
7. **Phase 2.4** - Cost Tracking
8. **Phase 2.5** - Progress File Parser
9. **Phase 2.6** - File Size Tracking
10. **Phase 4.1** - Git Operations

**Deliverable:** All state files can be loaded/saved

### Sprint 3: Agent Core (Week 3)

11. **Phase 3.1** - Agent Runner
12. **Phase 3.2** - Prompt Templates
13. **Phase 3.3** - Orientation Generator
14. **Phase 3.4** - Tool Definitions
15. **Phase 4.2** - Checkpoint System

**Deliverable:** Agent can run with tools, checkpoints work

### Sprint 4: Verification (Week 4)

16. **Phase 5.1** - Test Runner
17. **Phase 5.2** - Verification Engine
18. **Phase 5.3** - Lint Runner
19. **Phase 6.1** - Pre-Flight Checks

**Deliverable:** Tests can be run and verified

### Sprint 5: Session Lifecycle (Week 5)

20. **Phase 6.2** - Progress Monitor
21. **Phase 6.3** - Context Manager
22. **Phase 6.4** - Session Orchestrator
23. **Phase 7.2** - Run Command

**Deliverable:** `harness run` executes a complete session

### Sprint 6: Init & Commands (Week 6)

24. **Phase 7.1** - Init Command
25. **Phase 7.3** - Status Command
26. **Phase 7.4** - Health Command
27. **Phase 7.5** - Verify Command
28. **Phase 7.6** - Control Commands
29. **Phase 7.7** - Cleanup Command

**Deliverable:** All core CLI commands working

### Sprint 7: Observability (Week 7)

30. **Phase 8.1** - Event Logger
31. **Phase 8.2** - Agent Output Parser
32. **Phase 8.3** - Logs Command

**Deliverable:** Structured logging and log queries

### Sprint 8: Integrations (Week 8)

33. **Phase 9.1** - GitHub Sync
34. **Phase 10.1** - Project Scanner
35. **Phase 10.2** - Adopt Mode Init
36. **Phase 11.1** - Schema Migrations
37. **Phase 11.2** - Migrate Command

**Deliverable:** GitHub sync and adopt mode working

### Sprint 9: Advanced (Week 9+)

38. **Phase 12.1** - MCP Integration

**Deliverable:** Puppeteer MCP for visual verification

---

## Testing Strategy

### Unit Tests (per phase)

Each phase includes its own unit tests. Example patterns:

```python
# tests/test_features.py
def test_load_valid_features():
    ...

def test_detect_dependency_cycles():
    ...

def test_get_next_feature_respects_dependencies():
    ...
```

### Integration Tests (per sprint)

After each sprint, integration tests verify components work together:

```python
# tests/integration/test_session_flow.py
def test_complete_session_lifecycle():
    ...

def test_rollback_on_verification_failure():
    ...
```

### End-to-End Tests (final)

Full harness tests against a mock project:

```python
# tests/e2e/test_harness_init_and_run.py
def test_init_creates_project():
    ...

def test_run_completes_feature():
    ...
```

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Claude API changes | Abstract API behind AgentRunner interface |
| Test parsing fragility | Use pytest-json-report for reliable parsing |
| Git operations fail | Comprehensive error handling, never lose work |
| MCP servers unstable | MCP is optional, graceful degradation |
| Context window changes | Context limits are configurable |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| `harness init` success rate | > 95% |
| Verification catches false claims | > 99% |
| Regression detection accuracy | 100% |
| Session completion rate | > 90% |
| Context efficiency | < 10% overhead |

---

## Appendix: File Summary

### Core Files (Phase 1-6)

| File | Phase | Purpose |
|------|-------|---------|
| `cli.py` | 1.3+ | CLI entry point |
| `config.py` | 1.2 | Configuration loading |
| `features.py` | 2.1 | Features schema |
| `state.py` | 2.2 | Session state |
| `baseline.py` | 2.3 | Test baseline |
| `costs.py` | 2.4 | Cost tracking |
| `progress.py` | 2.5 | Progress file |
| `file_sizes.py` | 2.6 | File sizes |
| `agent.py` | 3.1 | Agent runner with TokenUsage, AgentSession, ToolExecutor type |
| `prompt_builder.py` | 3.2 | Prompts |
| `orientation.py` | 3.3 | Orientation |
| `tools/__init__.py` | 3.4 | Tool module exports |
| `tools/schemas.py` | 3.4 | ToolSchema, PropertySchema, validation |
| `tools/definitions.py` | 3.4 | Tool definitions, session tool mappings |
| `tools/executor.py` | 3.4 | ToolExecutor class, execution handling |
| `git_ops.py` | 4.1 | Git operations |
| `checkpoint.py` | 4.2 | Checkpoints |
| `test_runner.py` | 5.1 | Test execution |
| `verification.py` | 5.2 | Verification |
| `lint.py` | 5.3 | Lint runner |
| `preflight.py` | 6.1 | Pre-flight |
| `progress_monitor.py` | 6.2 | Progress |
| `context_manager.py` | 6.3 | Context |
| `session.py` | 6.4 | Orchestration |

### Extended Files (Phase 7-12)

| File | Phase | Purpose |
|------|-------|---------|
| `init.py` | 7.1 | Init logic |
| `health.py` | 7.4 | Health calc |
| `logging.py` | 8.1 | Event logging |
| `output_parser.py` | 8.2 | Output parsing |
| `github_sync.py` | 9.1 | GitHub sync |
| `scanner.py` | 10.1 | Project scan |
| `migrations.py` | 11.1 | Migrations |
| `mcp/` | 12.1 | MCP integration |
