# Enhanced Agent Harness Architecture v2.0

## Design Document

**Version**: 2.0.0
**Status**: Draft
**Date**: 2025-01-27
**Authors**: Architecture Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Principles](#design-principles)
3. [High-Level Architecture](#high-level-architecture)
4. [Component Specifications](#component-specifications)
5. [Data Flow Diagrams](#data-flow-diagrams)
6. [Integration Points](#integration-points)
7. [Migration Strategy](#migration-strategy)
8. [Configuration Schema](#configuration-schema)
9. [Risk Assessment](#risk-assessment)

---

## Executive Summary

This document describes the enhanced architecture for the Universal Agent Harness, incorporating five major capability areas:

1. **Contractor Model**: Formalized contracts as single source of truth with context staging
2. **Self-Improving Architecture (SICA)**: Agent self-modification with smart code navigation
3. **Producer-Critic Model**: Separation of code generation and review for quality
4. **Specialized Agent Roles**: Project Manager, Scaffolder, Test Engineer, Reviewer, Overseer
5. **Advanced Patterns**: Prompt chaining, routing, sandboxed execution, RAG integration

The design preserves existing strengths (single-feature focus, checkpoint/rollback, independent verification) while adding layered capabilities that can be adopted incrementally.

### Design Philosophy

**Complexity Resistance**: This design favors simplicity. Each enhancement is optional and independently deployable. The base system remains a single-agent, single-feature orchestrator. Multi-agent capabilities layer on top only when needed.

**Loose Coupling**: All new components communicate through well-defined interfaces. The Contract Registry is independent of the Agent Pool. The Overseer observes without directly controlling agent execution.

---

## Design Principles

### Preserved from v1.2

1. **GitHub is Single Source of Truth** - All state derived from git
2. **Harness Controls All Writes** - Agents propose, harness disposes
3. **Fail Safe, Recover Fast** - Idempotent and reversible operations
4. **Human Escape Hatches** - Easy to pause, override, or take over
5. **Observable but Not Bloated** - Log decisions that matter
6. **Trust but Verify** - Independent validation of agent claims

### New Principles for v2.0

7. **Contracts as Truth** - Formalized specifications replace loose prompts
8. **Separation of Concerns** - Distinct agents for generation vs. evaluation
9. **Hierarchical Decomposition** - Complex tasks split into manageable sub-tasks
10. **Observable Agents** - Overseer monitors behavior, not just output
11. **Incremental Enhancement** - New features layer on existing architecture
12. **Model-Appropriate Routing** - Right-size model for task complexity

---

## High-Level Architecture

### System Overview

```
+==============================================================================+
|                           ENHANCED AGENT HARNESS v2.0                         |
+==============================================================================+
|                                                                              |
|  +-------------------------------------------------------------------------+ |
|  |                         CONTRACT LAYER                                  | |
|  |  +-------------------+  +-------------------+  +--------------------+   | |
|  |  | Contract Registry |  | Context Staging   |  | Decomposition      |   | |
|  |  | - Specifications  |  | Area (task-ctx/)  |  | Engine             |   | |
|  |  | - Validation      |  | - Curated files   |  | - Task breakdown   |   | |
|  |  | - Dependencies    |  | - API definitions |  | - Subcontracts     |   | |
|  |  +-------------------+  +-------------------+  +--------------------+   | |
|  +-------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +-------------------------------------------------------------------------+ |
|  |                       ORCHESTRATION LAYER                               | |
|  |                                                                         | |
|  |  +--------------------+     +-----------------+     +----------------+  | |
|  |  | SessionOrchestrator|<--->| Multi-Agent     |<--->| Overseer       |  | |
|  |  | (Enhanced)         |     | Coordinator     |     | - Monitoring   |  | |
|  |  | - Contract exec    |     | - Role dispatch |     | - Intervention |  | |
|  |  | - Quality scoring  |     | - State sync    |     | - Patterns     |  | |
|  |  +--------------------+     +-----------------+     +----------------+  | |
|  |           |                        |                       ^            | |
|  +-----------|------------------------|------------------------|------------+ |
|              |                        |                        |             |
|              v                        v                        |             |
|  +-------------------------------------------------------------------------+ |
|  |                          AGENT POOL                                     | |
|  |                                                                         | |
|  |  +---------------+  +---------------+  +---------------+  +----------+  | |
|  |  | Producer      |  | Critic        |  | Test Engineer |  | Cleanup  |  | |
|  |  | (Scaffolder)  |  | (Reviewer)    |  |               |  | Agent    |  | |
|  |  | - Code gen    |  | - Review      |  | - Test gen    |  | - Refactor |
|  |  | - Impl        |  | - Feedback    |  | - Coverage    |  | - Lint fix |
|  |  +---------------+  +---------------+  +---------------+  +----------+  | |
|  |         |                  ^                   |                        | |
|  |         +------------------+-------------------+                        | |
|  |                   Producer-Critic Loop                                  | |
|  +-------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +-------------------------------------------------------------------------+ |
|  |                        EXECUTION LAYER                                  | |
|  |                                                                         | |
|  |  +-----------------+  +----------------+  +------------------+          | |
|  |  | AgentRunner     |  | ToolExecutor   |  | Sandbox          |          | |
|  |  | - API calls     |  | - Handlers     |  | - Safe execution |          | |
|  |  | - Streaming     |  | - Validation   |  | - Isolation      |          | |
|  |  +-----------------+  +----------------+  +------------------+          | |
|  |                                                                         | |
|  |  +-----------------+  +----------------+  +------------------+          | |
|  |  | Smart Editor    |  | Symbol Locator |  | RAG/Vector       |          | |
|  |  | - AST-aware     |  | - Code nav     |  | - Pattern search |          | |
|  |  | - Refactoring   |  | - References   |  | - Context        |          | |
|  |  +-----------------+  +----------------+  +------------------+          | |
|  +-------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +-------------------------------------------------------------------------+ |
|  |                       VERIFICATION LAYER                                | |
|  |                                                                         | |
|  |  +-----------------+  +----------------+  +------------------+          | |
|  |  | Quality Scorer  |  | Verification   |  | Baseline Manager |          | |
|  |  | - Security      |  | Engine         |  | - Regression     |          | |
|  |  | - Readability   |  | - Tests        |  | - Comparison     |          | |
|  |  | - Performance   |  | - Lint         |  | - History        |          | |
|  |  +-----------------+  +----------------+  +------------------+          | |
|  +-------------------------------------------------------------------------+ |
|                                    |                                         |
|                                    v                                         |
|  +-------------------------------------------------------------------------+ |
|  |                        PERSISTENCE LAYER                                | |
|  |                                                                         | |
|  |  Git Repo | Contracts | State Files | Checkpoints | Event Log          | |
|  +-------------------------------------------------------------------------+ |
|                                                                              |
+==============================================================================+
                                     |
                                     v
                    +--------------------------------+
                    |        EXTERNAL SERVICES       |
                    |                                |
                    | Claude API | GitHub | Vector DB|
                    +--------------------------------+
```

### Layered Architecture Benefits

| Layer | Responsibility | Coupling |
|-------|---------------|----------|
| Contract | Task specification and decomposition | Loosely coupled to orchestration |
| Orchestration | Coordination and monitoring | Depends on agents, not their implementation |
| Agent Pool | Specialized task execution | Isolated, communicate via contracts |
| Execution | Tool use and code manipulation | Stateless, reusable across agents |
| Verification | Quality assurance | Independent of generation |
| Persistence | State management | All layers read, orchestration writes |

---

## Component Specifications

### 1. Contract Layer

#### 1.1 Contract Registry

**Purpose**: Central repository for task specifications that serve as single source of truth.

**Location**: `src/agent_harness/contracts/registry.py`

```python
@dataclass
class Contract:
    """Formal specification for a task."""

    id: str                          # Unique identifier (e.g., "feature-12-impl")
    type: ContractType               # "feature", "refactor", "test", "review"
    parent_id: Optional[str]         # For subcontracts

    # Specification
    description: str                 # What must be accomplished
    acceptance_criteria: list[str]   # Verifiable conditions for completion
    constraints: list[str]           # Limitations and requirements

    # Context
    relevant_files: list[str]        # Files agent should focus on
    api_definitions: list[str]       # APIs agent can use
    style_guide: Optional[str]       # Coding standards reference

    # Verification
    test_requirements: list[str]     # Tests that must pass
    quality_thresholds: QualityThresholds

    # Metadata
    priority: int = 0
    estimated_complexity: str = "medium"  # small, medium, large
    dependencies: list[str] = field(default_factory=list)

    # State
    status: ContractStatus = ContractStatus.PENDING
    assigned_agent: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3


class ContractRegistry:
    """Manages contracts and their lifecycle."""

    def __init__(self, contracts_dir: Path):
        self.contracts_dir = contracts_dir
        self._contracts: dict[str, Contract] = {}
        self._load_contracts()

    def create_contract(self, spec: dict) -> Contract:
        """Create a new contract from specification."""
        ...

    def decompose_contract(self, contract_id: str) -> list[Contract]:
        """Break a contract into subcontracts using PM agent."""
        ...

    def get_ready_contracts(self) -> list[Contract]:
        """Get contracts ready for assignment (deps satisfied)."""
        ...

    def validate_contract(self, contract_id: str) -> ValidationResult:
        """Validate a contract before assignment."""
        ...

    def complete_contract(
        self,
        contract_id: str,
        result: ContractResult
    ) -> bool:
        """Mark contract complete with result."""
        ...
```

**Interface with Existing System**:
- Wraps `Feature` objects from `features.py` as contracts
- Adds formal specification layer without replacing features.json
- `get_next_feature()` becomes `get_next_contract()` internally

#### 1.2 Context Staging Area

**Purpose**: Curated workspace with relevant code, APIs, and standards for agent context.

**Location**: `src/agent_harness/context/staging.py`

```python
@dataclass
class StagedContext:
    """Curated context for a contract."""

    contract_id: str

    # Code context
    source_files: dict[str, str]     # path -> content (curated)
    test_files: dict[str, str]       # path -> content

    # Reference materials
    api_definitions: list[APIDefinition]
    type_definitions: list[TypeDefinition]
    style_guide: Optional[str]

    # Examples
    similar_implementations: list[str]  # Paths to reference code
    test_patterns: list[str]            # Example test structures

    # Statistics
    total_tokens: int
    file_count: int


class ContextStager:
    """Builds curated context for contracts."""

    def __init__(
        self,
        project_dir: Path,
        symbol_locator: SymbolLocator,
        vector_store: Optional[VectorStore] = None,
    ):
        self.project_dir = project_dir
        self.symbol_locator = symbol_locator
        self.vector_store = vector_store
        self.staging_dir = project_dir / "task-context"

    def stage_context(self, contract: Contract) -> StagedContext:
        """Build optimized context for a contract.

        Process:
        1. Identify relevant files from contract.relevant_files
        2. Use symbol_locator to find related definitions
        3. Query vector_store for similar patterns (if available)
        4. Curate to fit within token budget
        5. Stage in task-context/ directory
        """
        ...

    def _curate_for_tokens(
        self,
        files: dict[str, str],
        max_tokens: int
    ) -> dict[str, str]:
        """Intelligently trim context to fit token budget."""
        ...

    def clear_staging(self, contract_id: str) -> None:
        """Clean up staging area after contract completion."""
        ...
```

**Directory Structure**:
```
task-context/
├── current/                    # Active contract context
│   ├── contract.json          # Contract specification
│   ├── source/                # Curated source files
│   ├── tests/                 # Relevant test files
│   ├── apis/                  # API definitions
│   └── examples/              # Reference implementations
└── history/                   # Previous contexts (for learning)
    └── {contract_id}/
```

### 2. Orchestration Layer

#### 2.1 Enhanced SessionOrchestrator

**Purpose**: Extended session lifecycle with contract execution, multi-agent coordination, and quality scoring.

**Location**: `src/agent_harness/session.py` (enhanced)

```python
class EnhancedSessionOrchestrator(SessionOrchestrator):
    """Orchestrates sessions with contract and multi-agent support."""

    def __init__(
        self,
        project_dir: Path,
        config: Optional[Config] = None,
        mode: OrchestratorMode = OrchestratorMode.SINGLE_AGENT,
    ):
        super().__init__(project_dir, config)

        self.mode = mode
        self.contract_registry: Optional[ContractRegistry] = None
        self.agent_coordinator: Optional[MultiAgentCoordinator] = None
        self.overseer: Optional[Overseer] = None
        self.quality_scorer: Optional[QualityScorer] = None

        # Initialize based on mode
        if mode >= OrchestratorMode.CONTRACT_BASED:
            self._init_contracts()
        if mode >= OrchestratorMode.MULTI_AGENT:
            self._init_multi_agent()
        if mode >= OrchestratorMode.FULL:
            self._init_overseer()

    async def run_session(self, session_config: SessionConfig) -> SessionResult:
        """Run session with enhanced capabilities.

        Extended lifecycle:
        1-4. (Same as v1) Pre-flight, prompt selection, session start, checkpoint
        5.   [NEW] Load/create contract from feature
        6.   [NEW] Stage context for contract
        7.   [NEW] Route to appropriate agent(s) based on mode
        8-9. (Same as v1) Run agent loop, monitor progress
        10.  [NEW] Quality scoring before acceptance
        11.  [NEW] Producer-Critic loop if enabled
        12-15. (Same as v1) Verification, state update, commit
        """
        ...

    async def _execute_with_quality_loop(
        self,
        contract: Contract,
        staged_context: StagedContext,
    ) -> QualityScoredResult:
        """Execute contract with quality iteration.

        Process:
        1. Producer generates initial implementation
        2. Compile and run tests
        3. Score on security, readability, performance
        4. If score < threshold, iterate with feedback
        5. If max_iterations reached, return best attempt
        """
        ...


class OrchestratorMode(Enum):
    """Operating modes for the orchestrator."""
    SINGLE_AGENT = 1      # v1 behavior - single agent per session
    CONTRACT_BASED = 2    # Single agent with formal contracts
    PRODUCER_CRITIC = 3   # Two agents: producer and critic
    MULTI_AGENT = 4       # Full agent pool with coordination
    FULL = 5              # All features including overseer
```

**Backward Compatibility**:
- `OrchestratorMode.SINGLE_AGENT` provides identical behavior to v1
- Mode selection via config or CLI flag
- Existing tests pass without modification

#### 2.2 Multi-Agent Coordinator

**Purpose**: Manages multiple specialized agents working on decomposed tasks.

**Location**: `src/agent_harness/coordination/coordinator.py`

```python
@dataclass
class AgentAssignment:
    """Assignment of contract to agent."""
    agent_role: AgentRole
    contract_id: str
    runner: AgentRunner
    status: AssignmentStatus
    started_at: datetime
    completed_at: Optional[datetime] = None


class MultiAgentCoordinator:
    """Coordinates multiple agents working on related contracts."""

    def __init__(
        self,
        project_dir: Path,
        config: Config,
        agent_factory: AgentFactory,
    ):
        self.project_dir = project_dir
        self.config = config
        self.agent_factory = agent_factory

        self._assignments: dict[str, AgentAssignment] = {}
        self._completion_queue: asyncio.Queue = asyncio.Queue()

    async def assign_contract(
        self,
        contract: Contract,
        role: AgentRole,
    ) -> AgentAssignment:
        """Assign a contract to an agent of specified role."""
        ...

    async def run_producer_critic_loop(
        self,
        contract: Contract,
        max_iterations: int = 3,
    ) -> ProducerCriticResult:
        """Run producer-critic iteration until acceptance.

        Loop:
        1. Producer generates code
        2. Run tests (automated critic)
        3. Critic reviews code
        4. If "CODE_IS_PERFECT" or max_iterations, exit
        5. Feed critique to producer, goto 1
        """
        ...

    async def decompose_and_execute(
        self,
        contract: Contract,
    ) -> list[ContractResult]:
        """Have PM decompose, then execute subcontracts.

        Process:
        1. PM agent analyzes contract
        2. PM creates subcontracts with dependencies
        3. Execute subcontracts respecting dependencies
        4. Aggregate results
        """
        ...

    def get_assignment_status(self) -> dict[str, AssignmentStatus]:
        """Get status of all active assignments."""
        ...
```

#### 2.3 Overseer

**Purpose**: Async monitor that observes agent behavior and intervenes when needed.

**Location**: `src/agent_harness/oversight/overseer.py`

```python
@dataclass
class OverseerObservation:
    """Observation from overseer analysis."""
    timestamp: datetime
    agent_id: str
    observation_type: ObservationType  # loop, stagnation, inefficiency, danger
    severity: Severity
    description: str
    recommended_action: Optional[str] = None


class Overseer:
    """Monitors agent behavior asynchronously.

    Runs on a separate async task, analyzing agent actions
    without blocking execution. Can recommend or force interventions.
    """

    def __init__(
        self,
        config: OverseerConfig,
        model: str = "claude-haiku-3",  # Cheap model for monitoring
    ):
        self.config = config
        self.model = model
        self._running = False
        self._observations: list[OverseerObservation] = []
        self._agent_runners: dict[str, AgentRunner] = {}

    async def start_monitoring(self) -> None:
        """Start the oversight loop."""
        self._running = True
        asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> list[OverseerObservation]:
        """Stop monitoring and return observations."""
        self._running = False
        return self._observations

    async def register_agent(
        self,
        agent_id: str,
        runner: AgentRunner
    ) -> None:
        """Register an agent for monitoring."""
        self._agent_runners[agent_id] = runner

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            for agent_id, runner in self._agent_runners.items():
                observations = await self._analyze_agent(agent_id, runner)
                self._observations.extend(observations)

                for obs in observations:
                    if obs.severity == Severity.CRITICAL:
                        await self._intervene(agent_id, obs)

            await asyncio.sleep(self.config.check_interval_seconds)

    async def _analyze_agent(
        self,
        agent_id: str,
        runner: AgentRunner
    ) -> list[OverseerObservation]:
        """Analyze agent behavior for issues.

        Detection patterns:
        - Loop detection: Repeated similar tool calls
        - Stagnation: No progress despite token spend
        - Inefficiency: Suboptimal patterns (e.g., file read/write loops)
        - Danger: Potentially harmful operations
        """
        ...

    async def _intervene(
        self,
        agent_id: str,
        observation: OverseerObservation
    ) -> None:
        """Take action based on observation."""
        ...
```

**Overseer Patterns**:
```python
class LoopDetector:
    """Detects repeated action patterns."""

    def detect(self, history: list[ToolCall]) -> Optional[LoopPattern]:
        """Identify loops in tool call history.

        Patterns:
        - Same file read/written multiple times
        - Test run repeatedly with same failures
        - Edit-undo cycles
        """
        ...


class StagnationDetector:
    """Detects lack of meaningful progress."""

    def detect(
        self,
        snapshots: list[ProgressSnapshot]
    ) -> Optional[StagnationPattern]:
        """Identify stagnation despite token usage.

        Indicators:
        - High token spend, no file changes
        - Many tool calls, no test progress
        - Repeated similar responses
        """
        ...
```

### 3. Agent Pool

#### 3.1 Agent Roles

**Location**: `src/agent_harness/agents/roles.py`

```python
class AgentRole(Enum):
    """Specialized agent roles."""
    PROJECT_MANAGER = "pm"
    PRODUCER = "producer"       # Scaffolder
    CRITIC = "critic"           # Reviewer
    TEST_ENGINEER = "tester"
    CLEANUP = "cleanup"


@dataclass
class RoleConfig:
    """Configuration for an agent role."""
    role: AgentRole
    model: str
    system_prompt_template: str
    max_tokens: int
    tools: list[str]            # Allowed tools for this role

    # Role-specific settings
    can_modify_code: bool = True
    can_run_tests: bool = True
    can_create_checkpoints: bool = False


ROLE_CONFIGS: dict[AgentRole, RoleConfig] = {
    AgentRole.PROJECT_MANAGER: RoleConfig(
        role=AgentRole.PROJECT_MANAGER,
        model="claude-sonnet-4",
        system_prompt_template="prompts/pm.md",
        max_tokens=4096,
        tools=["read_file", "list_files", "create_subcontract"],
        can_modify_code=False,
        can_run_tests=False,
        can_create_checkpoints=False,
    ),
    AgentRole.PRODUCER: RoleConfig(
        role=AgentRole.PRODUCER,
        model="claude-sonnet-4",
        system_prompt_template="prompts/producer.md",
        max_tokens=8192,
        tools=["read_file", "write_file", "run_tests", "run_lint", "symbol_search"],
        can_modify_code=True,
        can_run_tests=True,
    ),
    AgentRole.CRITIC: RoleConfig(
        role=AgentRole.CRITIC,
        model="claude-sonnet-4",
        system_prompt_template="prompts/critic.md",
        max_tokens=4096,
        tools=["read_file", "diff_files", "run_tests"],
        can_modify_code=False,  # Critic only reads and comments
        can_run_tests=True,
    ),
    AgentRole.TEST_ENGINEER: RoleConfig(
        role=AgentRole.TEST_ENGINEER,
        model="claude-sonnet-4",
        system_prompt_template="prompts/tester.md",
        max_tokens=4096,
        tools=["read_file", "write_file", "run_tests", "coverage_report"],
        can_modify_code=True,  # Can write test files
    ),
    AgentRole.CLEANUP: RoleConfig(
        role=AgentRole.CLEANUP,
        model="claude-haiku-3",  # Cheaper model for cleanup
        system_prompt_template="prompts/cleanup.md",
        max_tokens=4096,
        tools=["read_file", "write_file", "run_lint", "refactor"],
    ),
}
```

#### 3.2 Agent Factory

**Location**: `src/agent_harness/agents/factory.py`

```python
class AgentFactory:
    """Creates configured agents for specific roles."""

    def __init__(self, project_dir: Path, config: Config):
        self.project_dir = project_dir
        self.config = config
        self.prompt_loader = PromptLoader(project_dir)

    def create_agent(
        self,
        role: AgentRole,
        contract: Contract,
        staged_context: StagedContext,
    ) -> AgentRunner:
        """Create an agent configured for a role and contract.

        Args:
            role: Agent role determining capabilities
            contract: Contract the agent will work on
            staged_context: Pre-built context for the contract

        Returns:
            Configured AgentRunner ready for execution
        """
        role_config = ROLE_CONFIGS[role]

        # Build system prompt from template + context
        system_prompt = self.prompt_loader.load_and_render(
            role_config.system_prompt_template,
            contract=contract,
            context=staged_context,
        )

        # Create runner with role-appropriate model
        runner = AgentRunner(
            model=role_config.model,
            max_tokens=role_config.max_tokens,
        )

        # Configure tool access based on role
        tool_executor = self._create_tool_executor(role_config)

        return runner, tool_executor, system_prompt

    def _create_tool_executor(
        self,
        role_config: RoleConfig
    ) -> ToolExecutor:
        """Create tool executor with role-specific permissions."""
        executor = ToolExecutor(self.project_dir)

        # Register only allowed tools
        all_handlers = create_default_handlers(self.project_dir)
        for tool_name in role_config.tools:
            if tool_name in all_handlers:
                executor.register_handler(tool_name, all_handlers[tool_name])

        return executor
```

#### 3.3 Producer-Critic Protocol

**Location**: `src/agent_harness/agents/producer_critic.py`

```python
@dataclass
class CritiqueResult:
    """Result of critic review."""
    status: CritiqueStatus  # PERFECT, NEEDS_WORK, MAJOR_ISSUES, REJECT
    feedback: str
    specific_issues: list[CodeIssue]
    suggested_fixes: list[str]


@dataclass
class ProducerCriticResult:
    """Result of producer-critic loop."""
    final_status: str
    iterations: int
    final_code: dict[str, str]  # path -> content
    critique_history: list[CritiqueResult]
    quality_score: float


class ProducerCriticProtocol:
    """Implements the producer-critic iteration pattern."""

    PERFECT_SIGNAL = "CODE_IS_PERFECT"

    def __init__(
        self,
        agent_factory: AgentFactory,
        max_iterations: int = 3,
    ):
        self.agent_factory = agent_factory
        self.max_iterations = max_iterations

    async def execute(
        self,
        contract: Contract,
        staged_context: StagedContext,
    ) -> ProducerCriticResult:
        """Run producer-critic loop.

        Flow:
        1. Producer generates initial implementation
        2. Run automated tests (first-pass critic)
        3. If tests fail, feed failures to producer, goto 1
        4. Critic agent reviews code
        5. If PERFECT_SIGNAL, exit with success
        6. Feed critique to producer, goto 1
        7. After max_iterations, return best attempt
        """
        critique_history = []
        best_score = 0.0
        best_code = None

        for iteration in range(self.max_iterations):
            # Producer generates
            producer = self.agent_factory.create_agent(
                AgentRole.PRODUCER,
                contract,
                staged_context,
            )

            # Add critique context if not first iteration
            if critique_history:
                staged_context = self._add_critique_context(
                    staged_context,
                    critique_history[-1]
                )

            code_result = await self._run_producer(producer, contract)

            # Run tests (automated critic)
            test_result = await self._run_tests(code_result)
            if not test_result.passed:
                critique_history.append(
                    self._test_failure_to_critique(test_result)
                )
                continue

            # Critic reviews
            critic = self.agent_factory.create_agent(
                AgentRole.CRITIC,
                contract,
                staged_context,
            )

            critique = await self._run_critic(critic, code_result)
            critique_history.append(critique)

            # Track best
            score = self._score_code(code_result)
            if score > best_score:
                best_score = score
                best_code = code_result

            # Check for perfect signal
            if critique.status == CritiqueStatus.PERFECT:
                return ProducerCriticResult(
                    final_status="accepted",
                    iterations=iteration + 1,
                    final_code=code_result,
                    critique_history=critique_history,
                    quality_score=best_score,
                )

        # Return best attempt
        return ProducerCriticResult(
            final_status="max_iterations",
            iterations=self.max_iterations,
            final_code=best_code,
            critique_history=critique_history,
            quality_score=best_score,
        )
```

### 4. Execution Layer

#### 4.1 Smart Editor with AST Symbol Locator

**Purpose**: Code-aware editing with symbol navigation for efficient code changes.

**Location**: `src/agent_harness/tools/smart_editor.py`

```python
@dataclass
class Symbol:
    """A code symbol (function, class, variable)."""
    name: str
    kind: SymbolKind  # FUNCTION, CLASS, METHOD, VARIABLE, IMPORT
    file_path: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    references: list[SymbolReference] = field(default_factory=list)


class SymbolLocator:
    """Locates and navigates code symbols using AST parsing."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self._symbol_cache: dict[str, list[Symbol]] = {}

    def find_symbol(self, name: str) -> list[Symbol]:
        """Find all symbols matching name."""
        ...

    def get_definition(self, symbol: Symbol) -> str:
        """Get the full definition of a symbol."""
        ...

    def find_references(self, symbol: Symbol) -> list[SymbolReference]:
        """Find all references to a symbol."""
        ...

    def get_related_symbols(self, symbol: Symbol) -> list[Symbol]:
        """Find related symbols (called by, calls to, etc.)."""
        ...

    def refresh_file(self, file_path: str) -> None:
        """Re-parse a file after modification."""
        ...


class SmartEditor:
    """AST-aware code editor for safe modifications."""

    def __init__(self, symbol_locator: SymbolLocator):
        self.symbol_locator = symbol_locator

    def edit_symbol(
        self,
        symbol: Symbol,
        new_content: str,
    ) -> EditResult:
        """Edit a symbol with validation.

        Process:
        1. Locate symbol in AST
        2. Validate new_content parses correctly
        3. Check for breaking changes to references
        4. Apply edit
        5. Refresh symbol cache
        """
        ...

    def rename_symbol(
        self,
        symbol: Symbol,
        new_name: str,
    ) -> RenameResult:
        """Rename a symbol across all references."""
        ...

    def extract_function(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        function_name: str,
    ) -> ExtractResult:
        """Extract code block into a new function."""
        ...
```

#### 4.2 Model Router

**Purpose**: Route tasks to appropriate models based on complexity.

**Location**: `src/agent_harness/routing/model_router.py`

```python
@dataclass
class RoutingDecision:
    """Decision from the router."""
    model: str
    reasoning: str
    estimated_tokens: int
    estimated_cost: float


class ModelRouter:
    """Routes tasks to cost-effective models.

    Strategy:
    - Simple tasks (small files, clear specs): claude-haiku-3
    - Medium tasks (typical features): claude-sonnet-4
    - Complex tasks (architecture, multi-file): claude-opus-4
    """

    MODEL_TIERS = {
        "simple": "claude-haiku-3",
        "medium": "claude-sonnet-4",
        "complex": "claude-opus-4",
    }

    def __init__(self, config: Config):
        self.config = config

    def route(self, contract: Contract) -> RoutingDecision:
        """Determine appropriate model for contract.

        Factors:
        - Number of files involved
        - Estimated code changes
        - Dependency complexity
        - Historical difficulty of similar tasks
        """
        complexity = self._assess_complexity(contract)
        model = self.MODEL_TIERS[complexity]

        return RoutingDecision(
            model=model,
            reasoning=f"Complexity: {complexity}",
            estimated_tokens=self._estimate_tokens(contract),
            estimated_cost=self._estimate_cost(contract, model),
        )

    def _assess_complexity(self, contract: Contract) -> str:
        """Assess task complexity."""
        score = 0

        # File count
        if len(contract.relevant_files) > 5:
            score += 2
        elif len(contract.relevant_files) > 2:
            score += 1

        # Dependencies
        if len(contract.dependencies) > 3:
            score += 2
        elif len(contract.dependencies) > 0:
            score += 1

        # Acceptance criteria complexity
        if len(contract.acceptance_criteria) > 7:
            score += 2
        elif len(contract.acceptance_criteria) > 3:
            score += 1

        if score >= 4:
            return "complex"
        elif score >= 2:
            return "medium"
        return "simple"
```

#### 4.3 Sandbox Execution

**Purpose**: Safe execution environment for running generated code.

**Location**: `src/agent_harness/sandbox/executor.py`

```python
class SandboxConfig:
    """Configuration for sandbox execution."""
    timeout_seconds: int = 30
    memory_limit_mb: int = 512
    network_allowed: bool = False
    filesystem_readonly: bool = True
    allowed_commands: list[str] = field(default_factory=list)


class SandboxExecutor:
    """Executes code in isolated environment.

    Uses subprocess isolation with resource limits.
    For stronger isolation, can integrate with Docker.
    """

    def __init__(self, config: SandboxConfig):
        self.config = config

    async def execute(
        self,
        command: str,
        working_dir: Path,
        env: Optional[dict] = None,
    ) -> SandboxResult:
        """Execute command in sandbox.

        Safety measures:
        1. Command whitelist check
        2. Working directory validation
        3. Resource limits
        4. Timeout enforcement
        5. Output capture and limits
        """
        ...

    async def execute_python(
        self,
        code: str,
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """Execute Python code snippet in sandbox."""
        ...
```

### 5. Verification Layer

#### 5.1 Quality Scorer

**Purpose**: Multi-dimensional quality assessment beyond pass/fail tests.

**Location**: `src/agent_harness/quality/scorer.py`

```python
@dataclass
class QualityScore:
    """Multi-dimensional quality score."""

    # Core dimensions (0-100)
    correctness: float      # Tests pass, meets requirements
    security: float         # No vulnerabilities, safe patterns
    readability: float      # Code clarity, documentation
    maintainability: float  # Modularity, coupling, complexity
    performance: float      # Efficiency indicators

    # Aggregate
    overall: float = field(init=False)

    def __post_init__(self):
        weights = {
            "correctness": 0.35,
            "security": 0.25,
            "readability": 0.15,
            "maintainability": 0.15,
            "performance": 0.10,
        }
        self.overall = sum(
            getattr(self, dim) * weight
            for dim, weight in weights.items()
        )


class QualityScorer:
    """Scores code quality across multiple dimensions."""

    def __init__(self, project_dir: Path, config: QualityConfig):
        self.project_dir = project_dir
        self.config = config

        self.analyzers = [
            CorrectnessAnalyzer(),
            SecurityAnalyzer(),
            ReadabilityAnalyzer(),
            MaintainabilityAnalyzer(),
            PerformanceAnalyzer(),
        ]

    async def score(
        self,
        changed_files: dict[str, str],
        test_results: TestRunResult,
    ) -> QualityScore:
        """Score the quality of code changes.

        Process:
        1. Run each analyzer on changed files
        2. Combine scores with weights
        3. Return comprehensive score
        """
        scores = {}
        for analyzer in self.analyzers:
            scores[analyzer.dimension] = await analyzer.analyze(
                changed_files,
                test_results
            )

        return QualityScore(**scores)

    def meets_threshold(self, score: QualityScore) -> bool:
        """Check if score meets configured thresholds."""
        return (
            score.overall >= self.config.min_overall_score
            and score.correctness >= self.config.min_correctness_score
            and score.security >= self.config.min_security_score
        )


class SecurityAnalyzer:
    """Analyzes code for security issues."""

    PATTERNS = [
        # SQL injection
        (r"execute\([^)]*%", "SQL injection risk"),
        # Command injection
        (r"subprocess\..*shell=True", "Command injection risk"),
        # Hardcoded secrets
        (r"password\s*=\s*['\"][^'\"]+['\"]", "Hardcoded password"),
        # etc.
    ]

    async def analyze(
        self,
        files: dict[str, str],
        test_results: TestRunResult,
    ) -> float:
        """Score security of code changes."""
        issues = []
        for path, content in files.items():
            for pattern, description in self.PATTERNS:
                if re.search(pattern, content):
                    issues.append((path, description))

        # Score based on issue count and severity
        if not issues:
            return 100.0
        # Deduct points per issue
        return max(0, 100 - len(issues) * 15)
```

### 6. Self-Improving Architecture (SICA)

**Purpose**: Allow agents to modify their own tools and improve over time.

**Location**: `src/agent_harness/sica/`

```python
# sica/improvement_tracker.py

@dataclass
class ImprovementProposal:
    """Proposed improvement to harness or tools."""
    id: str
    type: ImprovementType  # TOOL, PROMPT, CONFIG, WORKFLOW
    description: str
    current_behavior: str
    proposed_change: str
    rationale: str
    risk_level: str  # LOW, MEDIUM, HIGH
    requires_approval: bool


class SICAController:
    """Controller for self-improvement capabilities.

    Safety-first approach:
    1. All modifications require human approval by default
    2. Low-risk changes can be auto-approved via config
    3. All changes are versioned and reversible
    4. Improvements are validated before activation
    """

    def __init__(
        self,
        harness_dir: Path,
        config: SICAConfig,
    ):
        self.harness_dir = harness_dir
        self.config = config
        self.proposals: list[ImprovementProposal] = []

    async def propose_improvement(
        self,
        proposal: ImprovementProposal,
    ) -> ProposalResult:
        """Submit an improvement proposal.

        Process:
        1. Validate proposal structure
        2. Assess risk level
        3. If auto-approvable, apply and test
        4. Otherwise, queue for human review
        """
        ...

    async def apply_improvement(
        self,
        proposal_id: str,
    ) -> ApplyResult:
        """Apply an approved improvement.

        Safety:
        1. Create backup
        2. Apply change
        3. Run validation tests
        4. If fails, rollback
        """
        ...

    def list_pending_proposals(self) -> list[ImprovementProposal]:
        """Get proposals awaiting approval."""
        ...


# sica/tool_modifier.py

class ToolModifier:
    """Allows agents to create or modify tools.

    Constraints:
    - New tools must pass security review
    - Modifications versioned and reversible
    - Cannot modify core safety tools
    """

    PROTECTED_TOOLS = ["rollback_checkpoint", "signal_stuck"]

    def create_tool(
        self,
        name: str,
        schema: ToolSchema,
        handler_code: str,
    ) -> ToolCreationResult:
        """Create a new tool from agent specification.

        Process:
        1. Validate schema
        2. Security scan handler_code
        3. Test in sandbox
        4. Register if safe
        """
        ...

    def modify_tool(
        self,
        name: str,
        new_handler_code: str,
    ) -> ToolModificationResult:
        """Modify an existing tool.

        Constraints:
        - Cannot modify protected tools
        - Must maintain backwards compatibility
        - Original version preserved for rollback
        """
        if name in self.PROTECTED_TOOLS:
            return ToolModificationResult(
                success=False,
                error=f"Tool {name} is protected"
            )
        ...
```

---

## Data Flow Diagrams

### Primary Data Flow

```
                          Contract-Based Execution Flow
                          ============================

User/Human                                                    External
    |                                                            |
    | 1. Task Specification                                      |
    v                                                            |
+-------------------+                                            |
| Contract Registry | <-- 2. Validate & Store                   |
+-------------------+                                            |
    |                                                            |
    | 3. Get Next Contract                                       |
    v                                                            |
+-------------------+      +----------------+                    |
| Context Stager    | ---> | task-context/  | (staged files)     |
+-------------------+      +----------------+                    |
    |                                                            |
    | 4. Staged Context                                          |
    v                                                            |
+-------------------+                                            |
| Model Router      | 5. Select Model                            |
+-------------------+                                            |
    |                                                            |
    | 6. Route to Agent Pool                                     |
    v                                                            |
+-------------------+      +----------------+                    |
| Agent Coordinator | ---> | Agent Pool     |                    |
+-------------------+      | - Producer     |                    |
    ^                      | - Critic       | <----------------> | Claude API
    |                      | - Tester       |                    |
    |                      +----------------+                    |
    |                              |                             |
    |                              | 7. Code Changes             |
    |                              v                             |
    |                      +----------------+                    |
    |                      | Smart Editor   |                    |
    |                      | Symbol Locator |                    |
    |                      +----------------+                    |
    |                              |                             |
    |                              | 8. Modified Files           |
    |                              v                             |
    |                      +----------------+                    |
    |                      | Sandbox        | 9. Test Execution  |
    |                      +----------------+                    |
    |                              |                             |
    | 10. Results                  | 11. Quality Score           |
    +<-----------------------------+                             |
                                   |                             |
                                   v                             |
                          +-------------------+                  |
                          | Verification      |                  |
                          | Engine            |                  |
                          +-------------------+                  |
                                   |                             |
                                   | 12. Pass/Fail               |
                                   v                             |
                          +-------------------+                  |
                          | Git Commit        | ---> GitHub      |
                          +-------------------+                  |
```

### Producer-Critic Loop

```
                     Producer-Critic Iteration
                     ========================

                    +------------------------+
                    |      Contract          |
                    +------------------------+
                              |
                              v
              +-----------------------------------+
              |          Iteration Loop          |
              |  +---------------------------+   |
              |  |     Producer Agent        |   |
              |  | (Generates Implementation)|   |
              |  +---------------------------+   |
              |              |                   |
              |              v                   |
              |  +---------------------------+   |
              |  |    Automated Tests        |   |
              |  |    (First-pass Critic)    |   |
              |  +---------------------------+   |
              |         |           |            |
              |      FAIL         PASS           |
              |         |           |            |
              |         v           v            |
              |  [Feedback to   +---------------------------+
              |   Producer]     |      Critic Agent         |
              |         ^       |  (Principal Engineer)     |
              |         |       +---------------------------+
              |         |              |              |
              |         |        NEEDS_WORK     CODE_IS_PERFECT
              |         |              |              |
              |         +--------------+              |
              +-----------------------------------+   |
                                                     v
                                            +----------------+
                                            | Commit & Done  |
                                            +----------------+
```

### Overseer Monitoring

```
                      Overseer Architecture
                      ====================

+------------------+     +------------------+     +------------------+
|  Agent Runner 1  |     |  Agent Runner 2  |     |  Agent Runner N  |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        +------------------------+------------------------+
                                 |
                           Action Stream
                                 |
                                 v
                    +------------------------+
                    |       Overseer         |
                    |  (Async Monitoring)    |
                    |                        |
                    | +--------------------+ |
                    | | Loop Detector      | |
                    | +--------------------+ |
                    | | Stagnation Detector| |
                    | +--------------------+ |
                    | | Danger Detector    | |
                    | +--------------------+ |
                    +------------------------+
                                 |
               +-----------------+-----------------+
               |                 |                 |
          [Low Severity]   [Med Severity]    [High Severity]
               |                 |                 |
               v                 v                 v
            Log Only      Inject Warning     Force Intervention
                                |                  |
                                v                  v
                         [Add to Agent     [Pause Agent /
                          Context]          Rollback]
```

---

## Integration Points

### With Existing Components

| Existing Component | Integration Point | Enhancement |
|--------------------|-------------------|-------------|
| `SessionOrchestrator` | Subclass enhancement | `EnhancedSessionOrchestrator` adds contract and multi-agent support |
| `AgentRunner` | No changes | Used by all agent types, wrapped by factory |
| `ToolExecutor` | Extended | New tools for symbol navigation, smart editing |
| `features.py` | Wrapped | `Feature` objects wrapped as `Contract` for compatibility |
| `verification.py` | Extended | `QualityScorer` adds multi-dimensional assessment |
| `progress_monitor.py` | Replaced by | `Overseer` provides superior monitoring |
| `checkpoint.py` | No changes | Used for rollback on all failures |
| `config.py` | Extended | New config sections for contracts, agents, overseer |

### New Tool Definitions

```python
# tools/definitions.py additions

ENHANCED_TOOLS = [
    ToolSchema(
        name="symbol_search",
        description="Find code symbols (functions, classes) by name",
        parameters={
            "name": {"type": "string", "required": True},
            "kind": {"type": "string", "enum": ["function", "class", "method", "any"]},
        },
    ),
    ToolSchema(
        name="get_symbol_references",
        description="Find all references to a symbol",
        parameters={
            "symbol_name": {"type": "string", "required": True},
            "file_path": {"type": "string", "required": True},
        },
    ),
    ToolSchema(
        name="smart_edit",
        description="Edit a symbol with AST-aware modification",
        parameters={
            "symbol_name": {"type": "string", "required": True},
            "file_path": {"type": "string", "required": True},
            "new_content": {"type": "string", "required": True},
        },
    ),
    ToolSchema(
        name="create_subcontract",
        description="Create a subcontract for task decomposition (PM only)",
        parameters={
            "parent_id": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "acceptance_criteria": {"type": "array", "required": True},
        },
    ),
    ToolSchema(
        name="submit_critique",
        description="Submit code critique (Critic only)",
        parameters={
            "status": {"type": "string", "enum": ["PERFECT", "NEEDS_WORK", "MAJOR_ISSUES"]},
            "feedback": {"type": "string", "required": True},
            "issues": {"type": "array"},
        },
    ),
    ToolSchema(
        name="query_codebase",
        description="Semantic search of codebase for patterns",
        parameters={
            "query": {"type": "string", "required": True},
            "max_results": {"type": "integer", "default": 5},
        },
    ),
]
```

---

## Migration Strategy

### Phase 1: Contract Foundation (Week 1-2)

**Goal**: Introduce contracts without changing agent behavior

```
v1.2 -> v2.0-alpha1
=====================

1. Add Contract dataclass and ContractRegistry
2. Create feature-to-contract adapter
   - load_features() -> internally creates contracts
   - get_next_feature() -> get_next_contract() internally
3. Add context staging infrastructure
   - task-context/ directory
   - ContextStager class (basic implementation)
4. No changes to SessionOrchestrator behavior
5. Contracts are informational only

Validation:
- All existing tests pass
- Session behavior unchanged
- New contract files created alongside features.json
```

### Phase 2: Quality Scoring (Week 3-4)

**Goal**: Add multi-dimensional quality assessment

```
v2.0-alpha1 -> v2.0-alpha2
==========================

1. Add QualityScorer with basic analyzers
   - CorrectnessAnalyzer (wraps test results)
   - SecurityAnalyzer (pattern matching)
   - ReadabilityAnalyzer (basic metrics)
2. Integrate scoring into verification
   - Score computed after tests pass
   - Logged but not blocking
3. Add quality thresholds to config
4. Quality reports in session output

Validation:
- Existing tests pass
- Quality scores computed for all sessions
- No blocking on scores yet
```

### Phase 3: Smart Editor & Symbol Locator (Week 5-6)

**Goal**: Add code navigation capabilities

```
v2.0-alpha2 -> v2.0-beta1
=========================

1. Implement SymbolLocator with Python AST
2. Implement SmartEditor with basic operations
3. Register new tools (symbol_search, smart_edit)
4. Optional: integrate with existing read/write tools

Validation:
- Symbol search returns accurate results
- Smart edits preserve AST validity
- Agent can use new tools in sessions
```

### Phase 4: Model Router (Week 7)

**Goal**: Route tasks to cost-effective models

```
v2.0-beta1 -> v2.0-beta2
========================

1. Add ModelRouter with complexity assessment
2. Integrate with SessionOrchestrator
   - Router suggests model
   - Orchestrator uses suggestion
3. Add routing config section
4. Track routing decisions in logs

Validation:
- Routing decisions logged
- Simple tasks routed to cheaper models
- Cost savings measurable
```

### Phase 5: Producer-Critic Mode (Week 8-9)

**Goal**: Enable two-agent code generation and review

```
v2.0-beta2 -> v2.0-rc1
======================

1. Add AgentFactory with role configs
2. Implement ProducerCriticProtocol
3. Add OrchestratorMode.PRODUCER_CRITIC
4. Create producer and critic prompts
5. Add submit_critique tool

Validation:
- Producer-critic loop executes
- Critic feedback improves code
- Quality scores higher than single-agent
```

### Phase 6: Multi-Agent Coordination (Week 10-11)

**Goal**: Full agent pool with decomposition

```
v2.0-rc1 -> v2.0-rc2
====================

1. Add MultiAgentCoordinator
2. Implement task decomposition
   - PM agent creates subcontracts
   - Subcontracts assigned to specialists
3. Add OrchestratorMode.MULTI_AGENT
4. Dependency tracking between subcontracts

Validation:
- Complex tasks decompose correctly
- Subcontracts execute in order
- Results aggregate properly
```

### Phase 7: Overseer (Week 12)

**Goal**: Async monitoring and intervention

```
v2.0-rc2 -> v2.0
================

1. Implement Overseer with pattern detectors
2. Async monitoring loop
3. Warning injection into agent context
4. Force intervention for critical issues
5. Add OrchestratorMode.FULL

Validation:
- Loops detected and interrupted
- Stagnation triggers warnings
- Dangerous operations blocked
```

### Migration Configuration

```yaml
# .harness.yaml migration settings

migration:
  # Enable enhanced features gradually
  features:
    contracts: true       # Phase 1
    quality_scoring: true # Phase 2
    smart_editor: true    # Phase 3
    model_routing: true   # Phase 4
    producer_critic: false # Phase 5 (opt-in)
    multi_agent: false     # Phase 6 (opt-in)
    overseer: false        # Phase 7 (opt-in)

  # Orchestration mode
  orchestrator_mode: "single_agent"  # single_agent | contract | producer_critic | multi_agent | full

  # Fallback behavior
  on_new_feature_error: "fallback_v1"  # Use v1 behavior on errors
```

---

## Configuration Schema

### Enhanced Configuration Sections

```yaml
# .harness.yaml v2.0

# ... existing sections ...

# NEW: Contract configuration
contracts:
  enabled: true
  storage_dir: ".harness/contracts"
  auto_decompose: false           # Auto-split large contracts
  decompose_threshold_files: 5    # Files count triggering decomposition
  require_acceptance_criteria: true

# NEW: Context staging
context:
  staging_dir: "task-context"
  max_tokens: 100000              # Token budget for staged context
  include_tests: true
  include_similar: true           # Include similar implementations
  vector_search_enabled: false    # Requires vector DB setup

# NEW: Agent pool configuration
agents:
  # Default models per role
  models:
    project_manager: "claude-sonnet-4"
    producer: "claude-sonnet-4"
    critic: "claude-sonnet-4"
    test_engineer: "claude-sonnet-4"
    cleanup: "claude-haiku-3"

  # Producer-critic settings
  producer_critic:
    enabled: false
    max_iterations: 3
    require_perfect: false        # Exit only on CODE_IS_PERFECT

# NEW: Model routing
routing:
  enabled: true
  strategy: "complexity"          # complexity | cost | fixed
  complexity_thresholds:
    simple_max_files: 2
    simple_max_criteria: 3
    complex_min_files: 5
    complex_min_criteria: 7

# NEW: Quality scoring
quality:
  enabled: true
  min_overall_score: 70
  min_correctness_score: 80
  min_security_score: 60
  block_on_low_score: false       # Prevent commit if score too low
  analyzers:
    security: true
    readability: true
    maintainability: true
    performance: false            # Disable performance analysis

# NEW: Overseer
overseer:
  enabled: false
  model: "claude-haiku-3"
  check_interval_seconds: 30
  patterns:
    loop_detection: true
    stagnation_detection: true
    danger_detection: true
  intervention:
    warn_threshold: "medium"      # low | medium | high
    force_stop_threshold: "critical"

# NEW: SICA (Self-improvement)
sica:
  enabled: false
  allow_tool_creation: false
  allow_tool_modification: false
  auto_approve_low_risk: false
  require_human_approval: true
```

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Multi-agent coordination complexity | Medium | High | Phased rollout, single-agent fallback |
| Overseer false positives | Medium | Medium | Tunable thresholds, human override |
| Quality scoring disagreement with tests | Low | Medium | Correctness analyzer weighted highest |
| Context staging token overflow | Medium | Low | Hard token limits, graceful truncation |
| SICA security vulnerabilities | Low | Critical | Disabled by default, sandbox all changes |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Increased API costs from multi-agent | High | Medium | Model routing, cheap models for monitoring |
| Configuration complexity | Medium | Medium | Sensible defaults, mode-based presets |
| Debugging multi-agent issues | Medium | Medium | Comprehensive logging, session replay |
| Backward compatibility breaks | Low | High | Contract adapter, feature wrapper |

### Mitigation Summary

1. **Phased Rollout**: Each phase independently deployable and reversible
2. **Mode System**: Start with `single_agent` mode, upgrade when ready
3. **Fallback Behavior**: On errors, fall back to v1 behavior
4. **Extensive Testing**: Each phase validated before next begins
5. **Feature Flags**: Every enhancement toggleable via config
6. **Monitoring**: Track costs, success rates, and quality scores

---

## Appendix: File Structure

```
agent-harness/
├── src/agent_harness/
│   ├── __init__.py
│   ├── cli.py
│   ├── session.py              # Enhanced with modes
│   ├── agent.py                # No changes
│   ├── features.py             # No changes
│   ├── verification.py         # Extended with quality
│   │
│   ├── contracts/              # NEW
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── models.py
│   │   └── adapter.py          # Feature -> Contract
│   │
│   ├── context/                # NEW
│   │   ├── __init__.py
│   │   ├── staging.py
│   │   └── vector_store.py     # Optional RAG
│   │
│   ├── agents/                 # NEW
│   │   ├── __init__.py
│   │   ├── roles.py
│   │   ├── factory.py
│   │   └── producer_critic.py
│   │
│   ├── coordination/           # NEW
│   │   ├── __init__.py
│   │   └── coordinator.py
│   │
│   ├── oversight/              # NEW
│   │   ├── __init__.py
│   │   ├── overseer.py
│   │   └── patterns.py
│   │
│   ├── quality/                # NEW
│   │   ├── __init__.py
│   │   ├── scorer.py
│   │   └── analyzers/
│   │       ├── correctness.py
│   │       ├── security.py
│   │       ├── readability.py
│   │       ├── maintainability.py
│   │       └── performance.py
│   │
│   ├── routing/                # NEW
│   │   ├── __init__.py
│   │   └── model_router.py
│   │
│   ├── sica/                   # NEW
│   │   ├── __init__.py
│   │   ├── controller.py
│   │   └── tool_modifier.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   ├── definitions.py      # Extended with new tools
│   │   ├── executor.py
│   │   ├── smart_editor.py     # NEW
│   │   └── symbol_locator.py   # NEW
│   │
│   └── prompts/
│       ├── __init__.py
│       ├── builder.py
│       ├── coding.py
│       ├── initializer.py
│       ├── pm.py               # NEW
│       ├── producer.py         # NEW
│       ├── critic.py           # NEW
│       └── tester.py           # NEW
│
├── tests/
│   ├── test_contracts.py       # NEW
│   ├── test_context_staging.py # NEW
│   ├── test_agents.py          # NEW
│   ├── test_coordination.py    # NEW
│   ├── test_overseer.py        # NEW
│   ├── test_quality.py         # NEW
│   └── integration/
│       ├── test_producer_critic.py  # NEW
│       └── test_multi_agent.py      # NEW
│
└── docs/
    └── design/
        └── ENHANCED_ARCHITECTURE_V2.md  # This document
```

---

## Conclusion

This enhanced architecture provides a clear path from the current single-agent system to a sophisticated multi-agent platform with formal contracts, quality scoring, and behavioral oversight. The design prioritizes:

1. **Backward Compatibility**: All existing functionality preserved
2. **Incremental Adoption**: Each capability independently deployable
3. **Loose Coupling**: Components communicate through interfaces
4. **Safety First**: SICA disabled by default, overseer monitors but rarely intervenes
5. **Cost Awareness**: Model routing optimizes for budget

The migration strategy ensures minimal risk with clear validation checkpoints at each phase.
