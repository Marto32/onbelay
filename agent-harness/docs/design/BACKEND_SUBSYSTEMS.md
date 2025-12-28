# Backend Design: Enhanced Agent Harness Subsystems

## Executive Summary

This document specifies the backend architecture for four new subsystems that enhance the Universal Agent Harness:

1. **Contract Management System** - Formalized specifications as the single source of truth
2. **Context Staging System** - Dedicated workspace for curated agent context
3. **Multi-Attempt Execution Engine** - Generate, score, and select optimal implementations
4. **Agent Routing System** - Intelligent model selection based on task complexity

These systems integrate with the existing `SessionOrchestrator` and `AgentRunner` while maintaining the core principles of loose coupling, observability, and fail-safe operation.

---

## 1. Contract Management System

### 1.1 Overview

Contracts replace the loosely-specified "features" with formalized specifications that serve as binding agreements between the harness and the agent. Each contract defines:
- Exact inputs, outputs, and constraints
- Acceptance criteria (testable)
- Quality thresholds
- Parent/child relationships for decomposition

### 1.2 Data Model

```
/Users/michaelmartorella/code/onbelay/agent-harness/src/agent_harness/contracts/models.py
```

```python
"""Contract data models for formalized specifications."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import hashlib
import json


class ContractStatus(Enum):
    """Contract lifecycle states."""
    DRAFT = "draft"              # Initial creation, not yet approved
    APPROVED = "approved"        # Approved for execution
    IN_PROGRESS = "in_progress"  # Currently being worked on
    REVIEW = "review"            # Implementation submitted, awaiting verification
    COMPLETE = "complete"        # Successfully completed and verified
    FAILED = "failed"            # Failed after max attempts
    BLOCKED = "blocked"          # Dependencies not met
    CANCELLED = "cancelled"      # Manually cancelled


class ContractPriority(Enum):
    """Contract execution priority."""
    CRITICAL = 1    # Must complete first
    HIGH = 2        # High priority
    NORMAL = 3      # Default priority
    LOW = 4         # Can be deferred


class QualityDimension(Enum):
    """Dimensions for quality scoring."""
    CORRECTNESS = "correctness"       # Does it work? Tests pass?
    SECURITY = "security"             # No vulnerabilities introduced
    READABILITY = "readability"       # Code clarity, documentation
    PERFORMANCE = "performance"       # Efficiency, resource usage
    MAINTAINABILITY = "maintainability"  # Modularity, coupling
    TEST_COVERAGE = "test_coverage"   # Adequate test coverage


@dataclass
class QualityThreshold:
    """Minimum quality requirements for contract acceptance."""
    dimension: QualityDimension
    minimum_score: float  # 0.0 - 1.0
    weight: float = 1.0   # Importance weight for composite scoring


@dataclass
class InputSpec:
    """Specification of a contract input."""
    name: str
    description: str
    type_hint: str  # Python type hint as string
    required: bool = True
    default: Optional[Any] = None
    validation: Optional[str] = None  # Python expression for validation
    example: Optional[Any] = None


@dataclass
class OutputSpec:
    """Specification of a contract output."""
    name: str
    description: str
    type_hint: str
    validation: Optional[str] = None  # Python expression for validation
    example: Optional[Any] = None


@dataclass
class AcceptanceCriterion:
    """A single testable acceptance criterion."""
    id: str
    description: str
    test_command: Optional[str] = None  # Command to run for verification
    test_file: Optional[str] = None     # Test file to run
    manual_verification: bool = False   # Requires human review
    automated_check: Optional[str] = None  # Python expression for automated check


@dataclass
class ContractConstraint:
    """Constraints that must be satisfied."""
    id: str
    description: str
    type: str  # "file_limit", "token_limit", "time_limit", "dependency", "style"
    value: Any  # The constraint value


@dataclass
class QualityScore:
    """Quality assessment for a submission."""
    dimension: QualityDimension
    score: float  # 0.0 - 1.0
    reasoning: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class SubmissionResult:
    """Result of a contract submission."""
    submission_id: str
    attempt_number: int
    timestamp: str
    quality_scores: list[QualityScore] = field(default_factory=list)
    composite_score: float = 0.0
    acceptance_results: dict[str, bool] = field(default_factory=dict)  # criterion_id -> passed
    tests_passed: int = 0
    tests_failed: int = 0
    test_output: str = ""
    lint_errors: int = 0
    lint_warnings: int = 0
    accepted: bool = False
    rejection_reason: Optional[str] = None
    files_modified: list[str] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0


@dataclass
class ContractVersion:
    """A version of a contract for history tracking."""
    version: int
    created_at: str
    created_by: str  # "user", "agent", "harness"
    changes: str  # Description of changes
    content_hash: str  # Hash of contract content for change detection


@dataclass
class Contract:
    """A formalized contract specification."""

    # Identity
    id: str  # UUID or sequential ID
    parent_id: Optional[str] = None  # For subcontracts

    # Metadata
    title: str = ""
    description: str = ""
    category: str = "feature"  # "feature", "bugfix", "refactor", "test", "docs"
    priority: ContractPriority = ContractPriority.NORMAL
    status: ContractStatus = ContractStatus.DRAFT

    # Specification
    inputs: list[InputSpec] = field(default_factory=list)
    outputs: list[OutputSpec] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    constraints: list[ContractConstraint] = field(default_factory=list)

    # Quality requirements
    quality_thresholds: list[QualityThreshold] = field(default_factory=list)

    # Dependencies
    depends_on: list[str] = field(default_factory=list)  # Contract IDs
    blocks: list[str] = field(default_factory=list)      # Contracts blocked by this

    # Context
    context_files: list[str] = field(default_factory=list)  # Paths to context files
    related_code: list[str] = field(default_factory=list)   # Relevant code paths

    # Execution
    max_attempts: int = 3
    timeout_minutes: int = 60
    estimated_complexity: str = "medium"  # "trivial", "simple", "medium", "complex", "epic"

    # Tracking
    attempts: list[SubmissionResult] = field(default_factory=list)
    current_attempt: int = 0
    assigned_session: Optional[int] = None
    assigned_model: Optional[str] = None

    # History
    versions: list[ContractVersion] = field(default_factory=list)
    current_version: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    completed_at: Optional[str] = None

    # Subcontracts
    subcontract_ids: list[str] = field(default_factory=list)

    def content_hash(self) -> str:
        """Generate hash of contract content for change detection."""
        content = json.dumps({
            "title": self.title,
            "description": self.description,
            "inputs": [vars(i) for i in self.inputs],
            "outputs": [vars(o) for o in self.outputs],
            "acceptance_criteria": [vars(a) for a in self.acceptance_criteria],
            "constraints": [vars(c) for c in self.constraints],
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def is_ready(self) -> bool:
        """Check if contract is ready for execution."""
        return (
            self.status == ContractStatus.APPROVED and
            len(self.depends_on) == 0 or all(
                dep_status == ContractStatus.COMPLETE
                for dep_status in self.depends_on
            )
        )

    def get_best_submission(self) -> Optional[SubmissionResult]:
        """Get the highest-scoring accepted submission."""
        accepted = [s for s in self.attempts if s.accepted]
        if not accepted:
            return None
        return max(accepted, key=lambda s: s.composite_score)


@dataclass
class ContractFile:
    """Root structure for contracts.json file."""
    schema_version: int = 1
    project: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    contracts: list[Contract] = field(default_factory=list)

    # Aggregate stats
    total_contracts: int = 0
    completed_contracts: int = 0
    failed_contracts: int = 0
    total_attempts: int = 0
    total_cost_usd: float = 0.0
```

### 1.3 Contract Manager Service

```python
"""Contract management service."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
import json
import uuid

from agent_harness.contracts.models import (
    Contract, ContractFile, ContractStatus, ContractPriority,
    SubmissionResult, QualityScore, QualityDimension, QualityThreshold,
    AcceptanceCriterion, ContractVersion,
)
from agent_harness.exceptions import ContractError, ValidationError


@dataclass
class ContractQuery:
    """Query parameters for finding contracts."""
    status: Optional[ContractStatus] = None
    priority: Optional[ContractPriority] = None
    category: Optional[str] = None
    parent_id: Optional[str] = None
    unblocked_only: bool = False
    limit: int = 100


@dataclass
class ContractTransition:
    """Record of a status transition."""
    contract_id: str
    from_status: ContractStatus
    to_status: ContractStatus
    timestamp: str
    reason: str
    triggered_by: str  # "user", "agent", "harness", "scheduler"


class ContractManager:
    """
    Manages contract lifecycle and persistence.

    Responsibilities:
    - CRUD operations for contracts
    - Status transitions with validation
    - Subcontract management
    - Quality scoring and acceptance
    - Dependency resolution
    """

    def __init__(
        self,
        contracts_path: Path,
        on_transition: Optional[Callable[[ContractTransition], None]] = None,
    ):
        self.contracts_path = contracts_path
        self.on_transition = on_transition
        self._contracts_file: Optional[ContractFile] = None
        self._index: dict[str, Contract] = {}

    def load(self) -> ContractFile:
        """Load contracts from file."""
        if not self.contracts_path.exists():
            self._contracts_file = ContractFile()
            return self._contracts_file

        try:
            with open(self.contracts_path) as f:
                data = json.load(f)
            self._contracts_file = self._parse_contract_file(data)
            self._rebuild_index()
        except json.JSONDecodeError as e:
            raise ContractError(f"Invalid JSON in contracts file: {e}")

        return self._contracts_file

    def save(self) -> None:
        """Save contracts to file."""
        if self._contracts_file is None:
            raise ContractError("No contracts loaded")

        self._contracts_file.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._update_stats()

        self.contracts_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.contracts_path, "w") as f:
            json.dump(self._serialize_contract_file(), f, indent=2)

    # --- CRUD Operations ---

    def create_contract(
        self,
        title: str,
        description: str,
        category: str = "feature",
        parent_id: Optional[str] = None,
        **kwargs,
    ) -> Contract:
        """Create a new contract."""
        if self._contracts_file is None:
            self.load()

        contract_id = str(uuid.uuid4())[:8]

        contract = Contract(
            id=contract_id,
            parent_id=parent_id,
            title=title,
            description=description,
            category=category,
            status=ContractStatus.DRAFT,
            **kwargs,
        )

        # Create initial version
        contract.versions.append(ContractVersion(
            version=1,
            created_at=contract.created_at,
            created_by="user",
            changes="Initial creation",
            content_hash=contract.content_hash(),
        ))

        # Link to parent if subcontract
        if parent_id:
            parent = self.get_contract(parent_id)
            if parent:
                parent.subcontract_ids.append(contract_id)

        self._contracts_file.contracts.append(contract)
        self._index[contract_id] = contract

        return contract

    def get_contract(self, contract_id: str) -> Optional[Contract]:
        """Get a contract by ID."""
        return self._index.get(contract_id)

    def query_contracts(self, query: ContractQuery) -> list[Contract]:
        """Query contracts with filters."""
        results = []

        for contract in self._contracts_file.contracts:
            if query.status and contract.status != query.status:
                continue
            if query.priority and contract.priority != query.priority:
                continue
            if query.category and contract.category != query.category:
                continue
            if query.parent_id is not None and contract.parent_id != query.parent_id:
                continue
            if query.unblocked_only and not self._is_unblocked(contract):
                continue

            results.append(contract)

            if len(results) >= query.limit:
                break

        return results

    def get_next_contract(self) -> Optional[Contract]:
        """Get the next contract ready for execution."""
        # Check for in-progress first
        in_progress = self.query_contracts(ContractQuery(
            status=ContractStatus.IN_PROGRESS,
            limit=1,
        ))
        if in_progress:
            return in_progress[0]

        # Get unblocked approved contracts
        candidates = self.query_contracts(ContractQuery(
            status=ContractStatus.APPROVED,
            unblocked_only=True,
        ))

        if not candidates:
            return None

        # Sort by priority then by creation time
        candidates.sort(key=lambda c: (c.priority.value, c.created_at))

        return candidates[0]

    # --- Status Transitions ---

    def transition_status(
        self,
        contract_id: str,
        new_status: ContractStatus,
        reason: str,
        triggered_by: str = "harness",
    ) -> Contract:
        """Transition contract to new status."""
        contract = self.get_contract(contract_id)
        if not contract:
            raise ContractError(f"Contract not found: {contract_id}")

        if not self._is_valid_transition(contract.status, new_status):
            raise ContractError(
                f"Invalid transition: {contract.status.value} -> {new_status.value}"
            )

        old_status = contract.status
        contract.status = new_status
        contract.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if new_status == ContractStatus.COMPLETE:
            contract.completed_at = contract.updated_at

        transition = ContractTransition(
            contract_id=contract_id,
            from_status=old_status,
            to_status=new_status,
            timestamp=contract.updated_at,
            reason=reason,
            triggered_by=triggered_by,
        )

        if self.on_transition:
            self.on_transition(transition)

        return contract

    def _is_valid_transition(
        self,
        from_status: ContractStatus,
        to_status: ContractStatus,
    ) -> bool:
        """Check if status transition is valid."""
        valid_transitions = {
            ContractStatus.DRAFT: {
                ContractStatus.APPROVED,
                ContractStatus.CANCELLED,
            },
            ContractStatus.APPROVED: {
                ContractStatus.IN_PROGRESS,
                ContractStatus.BLOCKED,
                ContractStatus.CANCELLED,
            },
            ContractStatus.IN_PROGRESS: {
                ContractStatus.REVIEW,
                ContractStatus.FAILED,
                ContractStatus.BLOCKED,
                ContractStatus.CANCELLED,
            },
            ContractStatus.REVIEW: {
                ContractStatus.COMPLETE,
                ContractStatus.IN_PROGRESS,
                ContractStatus.FAILED,
            },
            ContractStatus.BLOCKED: {
                ContractStatus.APPROVED,
                ContractStatus.CANCELLED,
            },
            ContractStatus.FAILED: {
                ContractStatus.APPROVED,
                ContractStatus.CANCELLED,
            },
            ContractStatus.COMPLETE: set(),
            ContractStatus.CANCELLED: set(),
        }

        return to_status in valid_transitions.get(from_status, set())

    # --- Subcontract Management ---

    def create_subcontract(
        self,
        parent_id: str,
        title: str,
        description: str,
        **kwargs,
    ) -> Contract:
        """Create a subcontract linked to a parent."""
        parent = self.get_contract(parent_id)
        if not parent:
            raise ContractError(f"Parent contract not found: {parent_id}")

        return self.create_contract(
            title=title,
            description=description,
            parent_id=parent_id,
            category=parent.category,
            priority=parent.priority,
            **kwargs,
        )

    def get_subcontracts(self, parent_id: str) -> list[Contract]:
        """Get all subcontracts of a parent."""
        return self.query_contracts(ContractQuery(parent_id=parent_id))

    def check_subcontracts_complete(self, parent_id: str) -> bool:
        """Check if all subcontracts are complete."""
        subcontracts = self.get_subcontracts(parent_id)
        return all(s.status == ContractStatus.COMPLETE for s in subcontracts)

    # --- Quality Scoring ---

    def submit_for_review(
        self,
        contract_id: str,
        submission: SubmissionResult,
    ) -> tuple[bool, str]:
        """Submit work for review against contract."""
        contract = self.get_contract(contract_id)
        if not contract:
            raise ContractError(f"Contract not found: {contract_id}")

        submission.composite_score = self._calculate_composite_score(
            submission.quality_scores,
            contract.quality_thresholds,
        )

        all_criteria_met = all(submission.acceptance_results.values())
        threshold_met = self._check_thresholds(
            submission.quality_scores,
            contract.quality_thresholds,
        )

        if all_criteria_met and threshold_met and submission.tests_passed > 0:
            submission.accepted = True
            reason = f"Accepted with score {submission.composite_score:.2f}"
        else:
            submission.accepted = False
            reasons = []
            if not all_criteria_met:
                failed = [k for k, v in submission.acceptance_results.items() if not v]
                reasons.append(f"Failed criteria: {failed}")
            if not threshold_met:
                reasons.append("Quality thresholds not met")
            if submission.tests_passed == 0:
                reasons.append("No tests passed")
            reason = "; ".join(reasons)
            submission.rejection_reason = reason

        submission.attempt_number = len(contract.attempts) + 1
        contract.attempts.append(submission)
        contract.current_attempt = submission.attempt_number
        contract.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return submission.accepted, reason

    def _calculate_composite_score(
        self,
        scores: list[QualityScore],
        thresholds: list[QualityThreshold],
    ) -> float:
        """Calculate weighted composite quality score."""
        if not scores:
            return 0.0

        weights = {t.dimension: t.weight for t in thresholds}

        total_weight = 0.0
        weighted_sum = 0.0

        for score in scores:
            weight = weights.get(score.dimension, 1.0)
            weighted_sum += score.score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _check_thresholds(
        self,
        scores: list[QualityScore],
        thresholds: list[QualityThreshold],
    ) -> bool:
        """Check if all quality thresholds are met."""
        score_map = {s.dimension: s.score for s in scores}

        for threshold in thresholds:
            score = score_map.get(threshold.dimension, 0.0)
            if score < threshold.minimum_score:
                return False

        return True

    # --- Dependency Management ---

    def _is_unblocked(self, contract: Contract) -> bool:
        """Check if all dependencies are met."""
        for dep_id in contract.depends_on:
            dep = self.get_contract(dep_id)
            if not dep or dep.status != ContractStatus.COMPLETE:
                return False
        return True

    def update_blocked_contracts(self, completed_id: str) -> list[Contract]:
        """Update contracts blocked by a completed contract."""
        unblocked = []

        for contract in self._contracts_file.contracts:
            if contract.status == ContractStatus.BLOCKED:
                if completed_id in contract.depends_on:
                    if self._is_unblocked(contract):
                        self.transition_status(
                            contract.id,
                            ContractStatus.APPROVED,
                            f"Dependency {completed_id} completed",
                        )
                        unblocked.append(contract)

        return unblocked

    def _rebuild_index(self) -> None:
        """Rebuild contract index."""
        self._index = {c.id: c for c in self._contracts_file.contracts}

    def _update_stats(self) -> None:
        """Update aggregate statistics."""
        cf = self._contracts_file
        cf.total_contracts = len(cf.contracts)
        cf.completed_contracts = sum(
            1 for c in cf.contracts if c.status == ContractStatus.COMPLETE
        )
        cf.failed_contracts = sum(
            1 for c in cf.contracts if c.status == ContractStatus.FAILED
        )
        cf.total_attempts = sum(len(c.attempts) for c in cf.contracts)
        cf.total_cost_usd = sum(
            sum(a.cost_usd for a in c.attempts)
            for c in cf.contracts
        )
```

### 1.4 Integration Points

**With `session.py`:**
```python
# In SessionOrchestrator.run_session():
from agent_harness.contracts.manager import ContractManager

contract_manager = ContractManager(self.harness_dir / "contracts.json")
contract_manager.load()

contract = contract_manager.get_next_contract()
if contract is None:
    result.success = True
    result.message = "All contracts complete!"
    return result

contract_manager.transition_status(
    contract.id,
    ContractStatus.IN_PROGRESS,
    "Session started",
)

# ... run agent with contract context ...

submission = build_submission_from_verification(verification_result)
accepted, reason = contract_manager.submit_for_review(contract.id, submission)

if accepted:
    contract_manager.transition_status(
        contract.id,
        ContractStatus.COMPLETE,
        reason,
    )
    contract_manager.update_blocked_contracts(contract.id)
else:
    if contract.current_attempt >= contract.max_attempts:
        contract_manager.transition_status(
            contract.id,
            ContractStatus.FAILED,
            f"Max attempts ({contract.max_attempts}) exceeded",
        )
    else:
        contract_manager.transition_status(
            contract.id,
            ContractStatus.APPROVED,
            f"Retry {contract.current_attempt + 1}: {reason}",
        )
```

---

## 2. Context Staging System

### 2.1 Overview

The Context Staging System provides a dedicated workspace (`task-context/`) for curating precisely the context an agent needs. It manages:
- Directory structure and conventions
- Context file types and organization
- RAG/vector search integration for large codebases
- Token budget management and pruning

### 2.2 Data Model

```python
"""Context staging data models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import hashlib


class ContextType(Enum):
    """Types of context files."""
    CODE_SNIPPET = "code_snippet"
    API_DEFINITION = "api_definition"
    STYLE_GUIDE = "style_guide"
    EXAMPLE = "example"
    DOCUMENTATION = "documentation"
    TEST_EXAMPLE = "test_example"
    ERROR_CONTEXT = "error_context"
    SCHEMA = "schema"
    DEPENDENCY = "dependency"
    CUSTOM = "custom"


class ContextPriority(Enum):
    """Priority for context inclusion when pruning."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class ContextSource(Enum):
    """Source of context file."""
    MANUAL = "manual"
    EXTRACTED = "extracted"
    GENERATED = "generated"
    RAG = "rag"


@dataclass
class ContextFile:
    """A single context file."""
    id: str
    filename: str
    type: ContextType
    priority: ContextPriority
    source: ContextSource
    content: str
    content_hash: str
    token_count: int
    description: str = ""
    source_path: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 1.0
    related_contracts: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    last_used: Optional[str] = None
    use_count: int = 0


@dataclass
class ContextBundle:
    """A curated bundle of context for a specific task."""
    id: str
    contract_id: Optional[str] = None
    name: str = ""
    description: str = ""
    file_ids: list[str] = field(default_factory=list)
    token_budget: int = 50000
    token_used: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


@dataclass
class RAGIndex:
    """Index metadata for RAG/vector search."""
    indexed_paths: list[str] = field(default_factory=list)
    last_indexed: Optional[str] = None
    total_chunks: int = 0
    embedding_model: str = "text-embedding-3-small"
    index_path: str = ".harness/rag_index"


@dataclass
class ContextStaging:
    """Root structure for context staging."""
    schema_version: int = 1
    project: str = ""
    files: list[ContextFile] = field(default_factory=list)
    bundles: list[ContextBundle] = field(default_factory=list)
    rag_index: Optional[RAGIndex] = None
    default_token_budget: int = 50000
    max_token_budget: int = 150000
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
```

### 2.3 Context Manager Service

```python
"""Context staging service."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
import hashlib
import json
import uuid

from agent_harness.context_staging.models import (
    ContextFile, ContextBundle, ContextStaging, ContextType,
    ContextPriority, ContextSource, RAGIndex,
)


@dataclass
class TokenCounter:
    """Token counting interface."""

    def count(self, text: str) -> int:
        """Count tokens in text (approximation: ~4 chars per token)."""
        return len(text) // 4


@dataclass
class ExtractionResult:
    """Result of extracting context from codebase."""
    files_scanned: int
    files_extracted: int
    total_tokens: int
    context_files: list[ContextFile]


class ContextStagingManager:
    """
    Manages context staging workspace.

    Directory structure:
    task-context/
    ├── staging.json
    ├── code/
    ├── api/
    ├── styles/
    ├── examples/
    ├── docs/
    └── bundles/
    """

    def __init__(
        self,
        context_dir: Path,
        project_dir: Path,
        token_counter: Optional[TokenCounter] = None,
    ):
        self.context_dir = context_dir
        self.project_dir = project_dir
        self.token_counter = token_counter or TokenCounter()
        self._staging: Optional[ContextStaging] = None
        self._file_index: dict[str, ContextFile] = {}

    def initialize(self) -> None:
        """Initialize context staging directory structure."""
        dirs = [
            self.context_dir,
            self.context_dir / "code",
            self.context_dir / "api",
            self.context_dir / "styles",
            self.context_dir / "examples",
            self.context_dir / "docs",
            self.context_dir / "bundles",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        self._staging = ContextStaging()
        self.save()

    def load(self) -> ContextStaging:
        """Load context staging from file."""
        staging_path = self.context_dir / "staging.json"

        if not staging_path.exists():
            self.initialize()
            return self._staging

        with open(staging_path) as f:
            data = json.load(f)

        self._staging = self._parse_staging(data)
        self._rebuild_index()
        return self._staging

    def save(self) -> None:
        """Save context staging to file."""
        if self._staging is None:
            raise ValueError("No staging loaded")

        self._staging.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        staging_path = self.context_dir / "staging.json"
        with open(staging_path, "w") as f:
            json.dump(self._serialize_staging(), f, indent=2)

    def add_context(
        self,
        content: str,
        context_type: ContextType,
        filename: str,
        description: str = "",
        priority: ContextPriority = ContextPriority.MEDIUM,
        source: ContextSource = ContextSource.MANUAL,
        source_path: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> ContextFile:
        """Add a context file to staging."""
        if self._staging is None:
            self.load()

        context_id = str(uuid.uuid4())[:8]
        token_count = self.token_counter.count(content)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        context_file = ContextFile(
            id=context_id,
            filename=filename,
            type=context_type,
            priority=priority,
            source=source,
            content=content,
            content_hash=content_hash,
            token_count=token_count,
            description=description,
            source_path=source_path,
            tags=tags or [],
        )

        subdir = self._get_subdir_for_type(context_type)
        content_path = self.context_dir / subdir / f"{filename}.ctx"
        content_path.write_text(content)

        self._staging.files.append(context_file)
        self._file_index[context_id] = context_file

        return context_file

    def get_context(self, context_id: str) -> Optional[ContextFile]:
        """Get a context file by ID."""
        return self._file_index.get(context_id)

    def _get_subdir_for_type(self, context_type: ContextType) -> str:
        """Get subdirectory for context type."""
        mapping = {
            ContextType.CODE_SNIPPET: "code",
            ContextType.API_DEFINITION: "api",
            ContextType.STYLE_GUIDE: "styles",
            ContextType.EXAMPLE: "examples",
            ContextType.TEST_EXAMPLE: "examples",
            ContextType.DOCUMENTATION: "docs",
            ContextType.ERROR_CONTEXT: "docs",
            ContextType.SCHEMA: "api",
            ContextType.DEPENDENCY: "docs",
            ContextType.CUSTOM: "docs",
        }
        return mapping.get(context_type, "docs")

    def extract_from_codebase(
        self,
        patterns: list[str],
        max_files: int = 50,
        max_tokens_per_file: int = 2000,
    ) -> ExtractionResult:
        """Extract relevant context from codebase."""
        import fnmatch

        context_files = []
        files_scanned = 0
        total_tokens = 0

        for pattern in patterns:
            for path in self.project_dir.rglob("*"):
                if not path.is_file():
                    continue

                if any(part.startswith(".") for part in path.parts):
                    continue
                if any(part in ["node_modules", "__pycache__", "venv", ".venv"]
                       for part in path.parts):
                    continue

                files_scanned += 1

                if fnmatch.fnmatch(path.name, pattern):
                    try:
                        content = path.read_text()
                        token_count = self.token_counter.count(content)

                        if token_count > max_tokens_per_file:
                            chars_to_keep = max_tokens_per_file * 4
                            content = content[:chars_to_keep] + "\n\n... [truncated]"
                            token_count = max_tokens_per_file

                        relative_path = path.relative_to(self.project_dir)

                        ctx_file = self.add_context(
                            content=content,
                            context_type=self._infer_type(path),
                            filename=path.name,
                            description=f"Extracted from {relative_path}",
                            priority=ContextPriority.MEDIUM,
                            source=ContextSource.EXTRACTED,
                            source_path=str(relative_path),
                        )

                        context_files.append(ctx_file)
                        total_tokens += token_count

                        if len(context_files) >= max_files:
                            break

                    except (UnicodeDecodeError, PermissionError):
                        continue

            if len(context_files) >= max_files:
                break

        return ExtractionResult(
            files_scanned=files_scanned,
            files_extracted=len(context_files),
            total_tokens=total_tokens,
            context_files=context_files,
        )

    def _infer_type(self, path: Path) -> ContextType:
        """Infer context type from file path."""
        suffix = path.suffix.lower()
        name = path.name.lower()

        if "test" in name or suffix == ".test.py":
            return ContextType.TEST_EXAMPLE
        if suffix in [".md", ".rst", ".txt"]:
            return ContextType.DOCUMENTATION
        if suffix in [".yaml", ".yml"] and "openapi" in name:
            return ContextType.API_DEFINITION
        if suffix == ".graphql":
            return ContextType.API_DEFINITION
        if suffix in [".sql"]:
            return ContextType.SCHEMA
        if "style" in name or "lint" in name:
            return ContextType.STYLE_GUIDE
        if "example" in name or "sample" in name:
            return ContextType.EXAMPLE

        return ContextType.CODE_SNIPPET

    def create_bundle(
        self,
        name: str,
        contract_id: Optional[str] = None,
        token_budget: Optional[int] = None,
    ) -> ContextBundle:
        """Create a new context bundle."""
        if self._staging is None:
            self.load()

        bundle = ContextBundle(
            id=str(uuid.uuid4())[:8],
            contract_id=contract_id,
            name=name,
            token_budget=token_budget or self._staging.default_token_budget,
        )

        self._staging.bundles.append(bundle)
        return bundle

    def add_to_bundle(
        self,
        bundle_id: str,
        context_id: str,
    ) -> tuple[bool, str]:
        """Add context file to bundle."""
        bundle = self._find_bundle(bundle_id)
        if not bundle:
            return False, f"Bundle not found: {bundle_id}"

        context_file = self.get_context(context_id)
        if not context_file:
            return False, f"Context file not found: {context_id}"

        if bundle.token_used + context_file.token_count > bundle.token_budget:
            return False, (
                f"Would exceed token budget: {bundle.token_used} + "
                f"{context_file.token_count} > {bundle.token_budget}"
            )

        bundle.file_ids.append(context_id)
        bundle.token_used += context_file.token_count

        return True, "Added to bundle"

    def build_context_string(
        self,
        bundle_id: str,
        include_metadata: bool = True,
    ) -> str:
        """Build the full context string for a bundle."""
        bundle = self._find_bundle(bundle_id)
        if not bundle:
            raise ValueError(f"Bundle not found: {bundle_id}")

        parts = []

        for file_id in bundle.file_ids:
            context_file = self.get_context(file_id)
            if not context_file:
                continue

            if include_metadata:
                parts.append(f"=== {context_file.filename} ===")
                if context_file.description:
                    parts.append(f"Description: {context_file.description}")
                parts.append(f"Type: {context_file.type.value}")
                parts.append("")

            parts.append(context_file.content)
            parts.append("")

            context_file.last_used = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            context_file.use_count += 1

        return "\n".join(parts)

    def _find_bundle(self, bundle_id: str) -> Optional[ContextBundle]:
        """Find bundle by ID."""
        for bundle in self._staging.bundles:
            if bundle.id == bundle_id:
                return bundle
        return None

    def prune_bundle_to_budget(
        self,
        bundle_id: str,
        target_tokens: Optional[int] = None,
    ) -> list[str]:
        """Prune bundle to fit within token budget."""
        bundle = self._find_bundle(bundle_id)
        if not bundle:
            raise ValueError(f"Bundle not found: {bundle_id}")

        target = target_tokens or bundle.token_budget
        removed = []

        files_with_priority = []
        for file_id in bundle.file_ids:
            context_file = self.get_context(file_id)
            if context_file:
                files_with_priority.append((file_id, context_file))

        files_with_priority.sort(key=lambda x: x[1].priority.value, reverse=True)

        while bundle.token_used > target and files_with_priority:
            file_id, context_file = files_with_priority.pop()

            if context_file.priority == ContextPriority.CRITICAL:
                continue

            bundle.file_ids.remove(file_id)
            bundle.token_used -= context_file.token_count
            removed.append(file_id)

        return removed

    def auto_curate_for_contract(
        self,
        contract,
        token_budget: int = 50000,
    ) -> ContextBundle:
        """Automatically curate context for a contract."""
        bundle = self.create_bundle(
            name=f"auto_{contract.id}",
            contract_id=contract.id,
            token_budget=token_budget,
        )

        for ctx_path in contract.context_files:
            for ctx_file in self._staging.files:
                if ctx_file.source_path == ctx_path:
                    self.add_to_bundle(bundle.id, ctx_file.id)
                    break

        for code_path in contract.related_code:
            for ctx_file in self._staging.files:
                if ctx_file.source_path and code_path in ctx_file.source_path:
                    self.add_to_bundle(bundle.id, ctx_file.id)

        remaining_budget = token_budget - bundle.token_used

        for ctx_file in sorted(
            self._staging.files,
            key=lambda f: f.priority.value,
        ):
            if ctx_file.id in bundle.file_ids:
                continue
            if ctx_file.token_count <= remaining_budget:
                self.add_to_bundle(bundle.id, ctx_file.id)
                remaining_budget -= ctx_file.token_count

        return bundle

    def _rebuild_index(self) -> None:
        """Rebuild file index."""
        self._file_index = {f.id: f for f in self._staging.files}
```

### 2.4 Integration Points

**With `session.py` and prompts:**
```python
# In SessionOrchestrator.run_session():
from agent_harness.context_staging.manager import ContextStagingManager

context_staging = ContextStagingManager(
    context_dir=self.project_dir / "task-context",
    project_dir=self.project_dir,
)
context_staging.load()

bundle = context_staging.auto_curate_for_contract(
    contract,
    token_budget=self.config.context.max_context_tokens,
)

staged_context = context_staging.build_context_string(bundle.id)

orientation = generate_orientation_summary(self.project_dir, state, features)
system_prompt = build_system_prompt(prompt_type, self.config)
system_prompt += f"\n\n=== STAGED CONTEXT ===\n{staged_context}"
```

---

## 3. Multi-Attempt Execution Engine

### 3.1 Overview

The Multi-Attempt Execution Engine transforms the simple "run agent, verify, commit" flow into a more sophisticated process that:
- Generates multiple implementation approaches
- Scores each approach across multiple dimensions
- Runs tests and static analysis on each
- Selects the best approach or synthesizes elements

### 3.2 Data Model

```python
"""Multi-attempt execution data models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ApproachStrategy(Enum):
    """Strategies for generating implementation approaches."""
    SINGLE = "single"
    PARALLEL = "parallel"
    ITERATIVE = "iterative"
    COMPETITIVE = "competitive"


class SelectionStrategy(Enum):
    """Strategies for selecting final implementation."""
    BEST_SCORE = "best_score"
    FIRST_PASSING = "first_passing"
    ENSEMBLE = "ensemble"
    HUMAN_REVIEW = "human_review"


@dataclass
class ApproachConfig:
    """Configuration for approach generation."""
    strategy: ApproachStrategy = ApproachStrategy.SINGLE
    max_approaches: int = 3
    parallel_execution: bool = False
    max_tokens_per_approach: int = 100000
    timeout_per_approach: int = 30
    selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE
    require_tests_pass: bool = True
    minimum_score: float = 0.6


@dataclass
class CodeDiff:
    """A diff representing code changes."""
    file_path: str
    original_content: Optional[str]
    new_content: str
    additions: int = 0
    deletions: int = 0

    def is_new_file(self) -> bool:
        return self.original_content is None


@dataclass
class StaticAnalysisResult:
    """Result of static analysis on code."""
    tool: str
    errors: int = 0
    warnings: int = 0
    issues: list[dict] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of running tests."""
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    coverage_percent: Optional[float] = None
    output: str = ""


@dataclass
class ApproachScore:
    """Scores for a single approach."""
    correctness: float = 0.0
    security: float = 0.0
    readability: float = 0.0
    performance: float = 0.0
    maintainability: float = 0.0
    test_coverage: float = 0.0
    composite: float = 0.0
    reasoning: dict[str, str] = field(default_factory=dict)


@dataclass
class Approach:
    """A single implementation approach."""
    id: str
    approach_number: int
    strategy_description: str
    rationale: str
    diffs: list[CodeDiff] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    test_result: Optional[TestResult] = None
    static_analysis: list[StaticAnalysisResult] = field(default_factory=list)
    scores: Optional[ApproachScore] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    model_used: str = ""
    completed: bool = False
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


@dataclass
class ExecutionAttempt:
    """A complete execution attempt for a contract."""
    id: str
    contract_id: str
    attempt_number: int
    config: ApproachConfig = field(default_factory=ApproachConfig)
    approaches: list[Approach] = field(default_factory=list)
    selected_approach_id: Optional[str] = None
    selection_reason: str = ""
    final_test_result: Optional[TestResult] = None
    final_static_analysis: list[StaticAnalysisResult] = field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    completed_at: Optional[str] = None
    success: bool = False
```

### 3.3 Multi-Attempt Executor Service

```python
"""Multi-attempt execution engine."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
import uuid

from agent_harness.multi_attempt.models import (
    Approach, ApproachConfig, ApproachStrategy, ApproachScore,
    CodeDiff, ExecutionAttempt, SelectionStrategy, StaticAnalysisResult,
    TestResult,
)
from agent_harness.agent import AgentRunner, AgentSession
from agent_harness.contracts.models import Contract


@dataclass
class ScoringWeights:
    """Weights for composite scoring."""
    correctness: float = 0.35
    security: float = 0.15
    readability: float = 0.15
    performance: float = 0.10
    maintainability: float = 0.15
    test_coverage: float = 0.10


class MultiAttemptExecutor:
    """
    Executes contracts with multiple implementation approaches.

    Flow:
    1. Generate approach prompts based on strategy
    2. Execute each approach (parallel or sequential)
    3. Run tests and static analysis on each
    4. Score each approach
    5. Select best approach
    6. Apply selected changes
    """

    def __init__(
        self,
        project_dir: Path,
        agent_runner: AgentRunner,
        scoring_weights: Optional[ScoringWeights] = None,
    ):
        self.project_dir = project_dir
        self.agent_runner = agent_runner
        self.scoring_weights = scoring_weights or ScoringWeights()

    async def execute_contract(
        self,
        contract: Contract,
        config: ApproachConfig,
        context: str,
        system_prompt: str,
        on_approach_complete: Optional[Callable[[Approach], None]] = None,
    ) -> ExecutionAttempt:
        """Execute a contract with multiple approaches."""
        attempt = ExecutionAttempt(
            id=str(uuid.uuid4())[:8],
            contract_id=contract.id,
            attempt_number=contract.current_attempt + 1,
            config=config,
        )

        if config.strategy == ApproachStrategy.SINGLE:
            approaches = await self._execute_single(
                contract, context, system_prompt, config
            )
        elif config.strategy == ApproachStrategy.PARALLEL:
            approaches = await self._execute_parallel(
                contract, context, system_prompt, config
            )
        elif config.strategy == ApproachStrategy.ITERATIVE:
            approaches = await self._execute_iterative(
                contract, context, system_prompt, config
            )
        else:
            approaches = await self._execute_single(
                contract, context, system_prompt, config
            )

        attempt.approaches = approaches

        if on_approach_complete:
            for approach in approaches:
                on_approach_complete(approach)

        selected = self._select_approach(approaches, config)
        if selected:
            attempt.selected_approach_id = selected.id
            attempt.selection_reason = f"Selected based on {config.selection_strategy.value}"
            attempt.success = selected.test_result and selected.test_result.failed == []

        attempt.total_tokens = sum(a.tokens_used for a in approaches)
        attempt.total_cost_usd = sum(a.cost_usd for a in approaches)
        attempt.total_duration_seconds = sum(a.duration_seconds for a in approaches)
        attempt.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return attempt

    async def _execute_single(
        self,
        contract: Contract,
        context: str,
        system_prompt: str,
        config: ApproachConfig,
    ) -> list[Approach]:
        """Execute single approach."""
        approach = await self._run_approach(
            contract=contract,
            context=context,
            system_prompt=system_prompt,
            approach_number=1,
            strategy_hint=None,
            config=config,
        )
        return [approach]

    async def _execute_parallel(
        self,
        contract: Contract,
        context: str,
        system_prompt: str,
        config: ApproachConfig,
    ) -> list[Approach]:
        """Execute multiple approaches in parallel."""
        strategy_hints = [
            "Focus on simplicity and readability",
            "Focus on performance and efficiency",
            "Focus on extensibility and maintainability",
        ][:config.max_approaches]

        if config.parallel_execution:
            tasks = [
                self._run_approach(
                    contract=contract,
                    context=context,
                    system_prompt=system_prompt,
                    approach_number=i + 1,
                    strategy_hint=hint,
                    config=config,
                )
                for i, hint in enumerate(strategy_hints)
            ]
            return await asyncio.gather(*tasks)
        else:
            approaches = []
            for i, hint in enumerate(strategy_hints):
                approach = await self._run_approach(
                    contract=contract,
                    context=context,
                    system_prompt=system_prompt,
                    approach_number=i + 1,
                    strategy_hint=hint,
                    config=config,
                )
                approaches.append(approach)
            return approaches

    async def _execute_iterative(
        self,
        contract: Contract,
        context: str,
        system_prompt: str,
        config: ApproachConfig,
    ) -> list[Approach]:
        """Execute iteratively, learning from each attempt."""
        approaches = []
        previous_feedback = ""

        for i in range(config.max_approaches):
            approach = await self._run_approach(
                contract=contract,
                context=context,
                system_prompt=system_prompt,
                approach_number=i + 1,
                strategy_hint=previous_feedback if previous_feedback else None,
                config=config,
            )
            approaches.append(approach)

            if approach.test_result and approach.test_result.failed:
                previous_feedback = (
                    f"Previous attempt failed tests: {approach.test_result.failed[:3]}. "
                    f"Try a different approach."
                )
            elif approach.scores and approach.scores.composite < config.minimum_score:
                weak_areas = self._identify_weak_areas(approach.scores)
                previous_feedback = f"Previous attempt scored low on: {weak_areas}. Improve these areas."
            else:
                break

        return approaches

    async def _run_approach(
        self,
        contract: Contract,
        context: str,
        system_prompt: str,
        approach_number: int,
        strategy_hint: Optional[str],
        config: ApproachConfig,
    ) -> Approach:
        """Run a single approach."""
        start_time = datetime.now(timezone.utc)

        approach = Approach(
            id=str(uuid.uuid4())[:8],
            approach_number=approach_number,
            strategy_description="",
            rationale="",
        )

        try:
            user_prompt = self._build_approach_prompt(
                contract, context, strategy_hint
            )

            session = await self.agent_runner.run_conversation(
                initial_message=user_prompt,
                system_prompt=system_prompt,
                session_type="coding",
                max_turns=config.max_tokens_per_approach // 4000,
            )

            approach.tokens_used = session.total_usage.total_tokens
            approach.model_used = session.model

            approach.diffs = self._parse_diffs_from_session(session)
            approach.files_modified = [d.file_path for d in approach.diffs if not d.is_new_file()]
            approach.files_created = [d.file_path for d in approach.diffs if d.is_new_file()]

            await self._apply_diffs_temporarily(approach.diffs)
            approach.test_result = await self._run_tests(contract)
            approach.static_analysis = await self._run_static_analysis()
            approach.scores = self._score_approach(approach)
            await self._revert_diffs(approach.diffs)

            approach.completed = True

        except Exception as e:
            approach.error = str(e)
            approach.completed = False

        end_time = datetime.now(timezone.utc)
        approach.duration_seconds = (end_time - start_time).total_seconds()

        return approach

    def _build_approach_prompt(
        self,
        contract: Contract,
        context: str,
        strategy_hint: Optional[str],
    ) -> str:
        """Build prompt for an approach."""
        parts = [
            "=== CONTRACT ===",
            f"Title: {contract.title}",
            f"Description: {contract.description}",
            "",
            "=== ACCEPTANCE CRITERIA ===",
        ]

        for criterion in contract.acceptance_criteria:
            parts.append(f"- {criterion.description}")

        parts.append("")
        parts.append("=== CONTEXT ===")
        parts.append(context)

        if strategy_hint:
            parts.append("")
            parts.append("=== APPROACH GUIDANCE ===")
            parts.append(strategy_hint)

        parts.append("")
        parts.append("Implement this contract. Show your work with code diffs.")

        return "\n".join(parts)

    def _score_approach(self, approach: Approach) -> ApproachScore:
        """Score an approach across all dimensions."""
        scores = ApproachScore()

        if approach.test_result:
            total_tests = len(approach.test_result.passed) + len(approach.test_result.failed)
            if total_tests > 0:
                scores.correctness = len(approach.test_result.passed) / total_tests
            scores.reasoning["correctness"] = (
                f"{len(approach.test_result.passed)}/{total_tests} tests passed"
            )

        security_issues = sum(
            1 for sa in approach.static_analysis
            for issue in sa.issues
            if "security" in issue.get("category", "").lower()
        )
        scores.security = 1.0 - min(security_issues * 0.1, 1.0)
        scores.reasoning["security"] = f"{security_issues} security issues found"

        lint_warnings = sum(sa.warnings for sa in approach.static_analysis)
        scores.readability = 1.0 - min(lint_warnings * 0.05, 0.5)
        scores.reasoning["readability"] = f"{lint_warnings} lint warnings"

        scores.performance = 0.7
        scores.reasoning["performance"] = "Not analyzed"

        files_touched = len(approach.files_modified) + len(approach.files_created)
        scores.maintainability = 1.0 - min(files_touched * 0.1, 0.5)
        scores.reasoning["maintainability"] = f"{files_touched} files touched"

        if approach.test_result and approach.test_result.coverage_percent:
            scores.test_coverage = approach.test_result.coverage_percent / 100.0
        else:
            scores.test_coverage = 0.5
        scores.reasoning["test_coverage"] = "Not measured"

        scores.composite = (
            scores.correctness * self.scoring_weights.correctness +
            scores.security * self.scoring_weights.security +
            scores.readability * self.scoring_weights.readability +
            scores.performance * self.scoring_weights.performance +
            scores.maintainability * self.scoring_weights.maintainability +
            scores.test_coverage * self.scoring_weights.test_coverage
        )

        return scores

    def _select_approach(
        self,
        approaches: list[Approach],
        config: ApproachConfig,
    ) -> Optional[Approach]:
        """Select the best approach."""
        if not approaches:
            return None

        completed = [a for a in approaches if a.completed]
        if not completed:
            return None

        if config.require_tests_pass:
            passing = [
                a for a in completed
                if a.test_result and len(a.test_result.failed) == 0
            ]
            if passing:
                completed = passing

        above_threshold = [
            a for a in completed
            if a.scores and a.scores.composite >= config.minimum_score
        ]
        if above_threshold:
            completed = above_threshold

        if not completed:
            return None

        if config.selection_strategy == SelectionStrategy.BEST_SCORE:
            return max(completed, key=lambda a: a.scores.composite if a.scores else 0)
        elif config.selection_strategy == SelectionStrategy.FIRST_PASSING:
            return completed[0]
        else:
            return max(completed, key=lambda a: a.scores.composite if a.scores else 0)

    def _identify_weak_areas(self, scores: ApproachScore) -> str:
        """Identify areas that scored below average."""
        weak = []
        threshold = 0.6

        if scores.correctness < threshold:
            weak.append("correctness")
        if scores.security < threshold:
            weak.append("security")
        if scores.readability < threshold:
            weak.append("readability")
        if scores.maintainability < threshold:
            weak.append("maintainability")

        return ", ".join(weak) if weak else "none"

    async def apply_selected_approach(
        self,
        attempt: ExecutionAttempt,
    ) -> bool:
        """Apply the selected approach permanently."""
        if not attempt.selected_approach_id:
            return False

        selected = None
        for approach in attempt.approaches:
            if approach.id == attempt.selected_approach_id:
                selected = approach
                break

        if not selected:
            return False

        for diff in selected.diffs:
            path = self.project_dir / diff.file_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(diff.new_content)

        return True
```

### 3.4 Integration Points

**With `session.py`:**
```python
# In SessionOrchestrator.run_session():
from agent_harness.multi_attempt.executor import MultiAttemptExecutor, ApproachConfig

approach_config = ApproachConfig(
    strategy=ApproachStrategy.ITERATIVE,
    max_approaches=3,
    require_tests_pass=True,
    minimum_score=0.7,
)

executor = MultiAttemptExecutor(
    project_dir=self.project_dir,
    agent_runner=self.agent_runner,
    scoring_weights=ScoringWeights(),
)

attempt = await executor.execute_contract(
    contract=contract,
    config=approach_config,
    context=staged_context,
    system_prompt=system_prompt,
)

if attempt.success and attempt.selected_approach_id:
    await executor.apply_selected_approach(attempt)
    contract_manager.submit_for_review(contract.id, build_submission(attempt))
```

---

## 4. Agent Routing System

### 4.1 Overview

The Agent Routing System intelligently selects the appropriate model based on:
- Task complexity assessment
- Cost optimization
- Previous performance data
- Fallback strategies

### 4.2 Data Model

```python
"""Agent routing data models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ComplexityLevel(Enum):
    """Task complexity levels."""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EPIC = "epic"


class ModelTier(Enum):
    """Model performance/cost tiers."""
    FAST = "fast"
    BALANCED = "balanced"
    POWERFUL = "powerful"
    REASONING = "reasoning"


@dataclass
class ModelConfig:
    """Configuration for a model."""
    model_id: str
    tier: ModelTier
    max_tokens: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    supports_tools: bool = True
    supports_vision: bool = False
    context_window: int = 200000


@dataclass
class ComplexityAssessment:
    """Assessment of task complexity."""
    level: ComplexityLevel
    score: float
    estimated_files: int = 0
    estimated_tokens: int = 0
    requires_reasoning: bool = False
    requires_context: bool = False
    has_dependencies: bool = False
    factors: list[str] = field(default_factory=list)
    confidence: float = 0.8


@dataclass
class RoutingDecision:
    """Decision on which model to use."""
    selected_model: str
    tier: ModelTier
    reason: str
    alternatives: list[tuple[str, str]] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    fallback_models: list[str] = field(default_factory=list)


@dataclass
class ModelPerformance:
    """Historical performance data for a model."""
    model_id: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    average_score: float = 0.0
    average_attempts: float = 0.0
    total_cost_usd: float = 0.0
    average_cost_per_task: float = 0.0
    average_duration_seconds: float = 0.0
    performance_by_complexity: dict[str, dict] = field(default_factory=dict)


@dataclass
class RoutingConfig:
    """Configuration for the routing system."""
    complexity_model_mapping: dict[str, str] = field(default_factory=lambda: {
        "trivial": "claude-3-haiku-20240307",
        "simple": "claude-3-haiku-20240307",
        "medium": "claude-sonnet-4-20250514",
        "complex": "claude-sonnet-4-20250514",
        "epic": "claude-3-opus-20240229",
    })
    max_cost_per_task: float = 10.0
    prefer_cheaper_if_within: float = 0.1
    enable_fallback: bool = True
    max_fallback_attempts: int = 2
    escalate_on_failure: bool = True
    use_performance_history: bool = True
    minimum_history_for_learning: int = 10
```

### 4.3 Agent Router Service

```python
"""Agent routing service."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import json

from agent_harness.routing.models import (
    ComplexityAssessment, ComplexityLevel, ModelConfig, ModelPerformance,
    ModelTier, RoutingConfig, RoutingDecision,
)
from agent_harness.contracts.models import Contract


AVAILABLE_MODELS: dict[str, ModelConfig] = {
    "claude-3-haiku-20240307": ModelConfig(
        model_id="claude-3-haiku-20240307",
        tier=ModelTier.FAST,
        max_tokens=4096,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        context_window=200000,
    ),
    "claude-sonnet-4-20250514": ModelConfig(
        model_id="claude-sonnet-4-20250514",
        tier=ModelTier.BALANCED,
        max_tokens=8192,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        context_window=200000,
    ),
    "claude-3-opus-20240229": ModelConfig(
        model_id="claude-3-opus-20240229",
        tier=ModelTier.POWERFUL,
        max_tokens=4096,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        context_window=200000,
    ),
}


class AgentRouter:
    """
    Routes tasks to appropriate models based on complexity.

    Responsibilities:
    - Assess task complexity
    - Select optimal model
    - Manage fallback strategies
    - Track performance history
    - Optimize for cost/quality tradeoff
    """

    def __init__(
        self,
        config: RoutingConfig,
        performance_path: Optional[Path] = None,
    ):
        self.config = config
        self.performance_path = performance_path
        self._performance: dict[str, ModelPerformance] = {}

        if performance_path and performance_path.exists():
            self._load_performance()

    def assess_complexity(
        self,
        contract: Contract,
        context_tokens: int = 0,
    ) -> ComplexityAssessment:
        """Assess the complexity of a contract."""
        factors = []
        score = 0.0

        desc_lower = contract.description.lower()

        complex_keywords = [
            "algorithm", "architecture", "refactor", "migration",
            "security", "authentication", "authorization", "encryption",
            "performance", "optimization", "concurrent", "async",
            "database", "schema", "api", "integration",
        ]

        simple_keywords = [
            "add", "remove", "update", "fix", "rename", "format",
            "comment", "documentation", "typo", "simple",
        ]

        complex_count = sum(1 for kw in complex_keywords if kw in desc_lower)
        simple_count = sum(1 for kw in simple_keywords if kw in desc_lower)

        if complex_count > 2:
            score += 0.3
            factors.append(f"Contains {complex_count} complex keywords")
        if simple_count > 2:
            score -= 0.2
            factors.append(f"Contains {simple_count} simplicity indicators")

        criteria_count = len(contract.acceptance_criteria)
        if criteria_count > 5:
            score += 0.2
            factors.append(f"{criteria_count} acceptance criteria")
        elif criteria_count <= 2:
            score -= 0.1
            factors.append(f"Only {criteria_count} acceptance criteria")

        if contract.depends_on:
            score += 0.1 * len(contract.depends_on)
            factors.append(f"Has {len(contract.depends_on)} dependencies")

        estimated_files = len(contract.related_code)
        if estimated_files > 5:
            score += 0.2
            factors.append(f"Touches {estimated_files} files")
        elif estimated_files <= 1:
            score -= 0.1
            factors.append("Single file change")

        requires_context = context_tokens > 30000
        if requires_context:
            score += 0.1
            factors.append("Requires significant context")

        reasoning_indicators = [
            "design", "decide", "choose", "evaluate", "compare",
            "tradeoff", "trade-off", "approach", "strategy",
        ]
        requires_reasoning = any(ind in desc_lower for ind in reasoning_indicators)
        if requires_reasoning:
            score += 0.15
            factors.append("Requires reasoning/decision-making")

        score = max(0.0, min(1.0, score + 0.5))

        if score < 0.2:
            level = ComplexityLevel.TRIVIAL
        elif score < 0.4:
            level = ComplexityLevel.SIMPLE
        elif score < 0.6:
            level = ComplexityLevel.MEDIUM
        elif score < 0.8:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.EPIC

        if contract.estimated_complexity:
            estimate_map = {
                "trivial": ComplexityLevel.TRIVIAL,
                "simple": ComplexityLevel.SIMPLE,
                "medium": ComplexityLevel.MEDIUM,
                "complex": ComplexityLevel.COMPLEX,
                "epic": ComplexityLevel.EPIC,
            }
            if contract.estimated_complexity in estimate_map:
                level = estimate_map[contract.estimated_complexity]
                factors.append(f"Contract specifies: {contract.estimated_complexity}")

        return ComplexityAssessment(
            level=level,
            score=score,
            estimated_files=estimated_files,
            estimated_tokens=context_tokens,
            requires_reasoning=requires_reasoning,
            requires_context=requires_context,
            has_dependencies=bool(contract.depends_on),
            factors=factors,
        )

    def select_model(
        self,
        assessment: ComplexityAssessment,
        budget_remaining: Optional[float] = None,
    ) -> RoutingDecision:
        """Select the optimal model for a task."""
        base_model = self.config.complexity_model_mapping.get(
            assessment.level.value,
            "claude-sonnet-4-20250514"
        )

        alternatives = []

        if self.config.use_performance_history and self._has_sufficient_history():
            recommended = self._recommend_from_history(assessment.level)
            if recommended and recommended != base_model:
                alternatives.append((base_model, "Default for complexity"))
                base_model = recommended

        model_config = AVAILABLE_MODELS.get(base_model)
        if model_config and budget_remaining is not None:
            estimated_cost = self._estimate_cost(model_config, assessment)

            if estimated_cost > budget_remaining:
                cheaper = self._find_cheaper_model(budget_remaining, assessment)
                if cheaper:
                    alternatives.append((base_model, f"Over budget (${estimated_cost:.2f})"))
                    base_model = cheaper

        if assessment.requires_reasoning and assessment.level in [
            ComplexityLevel.COMPLEX, ComplexityLevel.EPIC
        ]:
            if "opus" not in base_model.lower():
                alternatives.append((base_model, "Reasoning may need more capability"))
                opus_cost = self._estimate_cost(
                    AVAILABLE_MODELS["claude-3-opus-20240229"],
                    assessment
                )
                if budget_remaining is None or opus_cost <= budget_remaining:
                    base_model = "claude-3-opus-20240229"

        fallbacks = self._build_fallback_chain(base_model, assessment)

        final_config = AVAILABLE_MODELS.get(base_model)
        estimated_cost = self._estimate_cost(final_config, assessment) if final_config else 0.0

        return RoutingDecision(
            selected_model=base_model,
            tier=final_config.tier if final_config else ModelTier.BALANCED,
            reason=self._build_selection_reason(assessment, base_model),
            alternatives=alternatives,
            estimated_cost_usd=estimated_cost,
            fallback_models=fallbacks,
        )

    def _estimate_cost(
        self,
        model: ModelConfig,
        assessment: ComplexityAssessment,
    ) -> float:
        """Estimate cost for a task with a model."""
        token_multipliers = {
            ComplexityLevel.TRIVIAL: 0.5,
            ComplexityLevel.SIMPLE: 1.0,
            ComplexityLevel.MEDIUM: 2.0,
            ComplexityLevel.COMPLEX: 3.0,
            ComplexityLevel.EPIC: 5.0,
        }

        multiplier = token_multipliers.get(assessment.level, 2.0)
        estimated_input = assessment.estimated_tokens + int(10000 * multiplier)
        estimated_output = int(5000 * multiplier)

        input_cost = (estimated_input / 1000) * model.cost_per_1k_input
        output_cost = (estimated_output / 1000) * model.cost_per_1k_output

        return input_cost + output_cost

    def _find_cheaper_model(
        self,
        budget: float,
        assessment: ComplexityAssessment,
    ) -> Optional[str]:
        """Find a cheaper model that fits budget."""
        candidates = []

        for model_id, config in AVAILABLE_MODELS.items():
            cost = self._estimate_cost(config, assessment)
            if cost <= budget:
                candidates.append((model_id, config.tier.value, cost))

        if not candidates:
            return None

        tier_order = {"fast": 0, "balanced": 1, "powerful": 2, "reasoning": 3}
        candidates.sort(key=lambda x: tier_order.get(x[1], 0), reverse=True)

        return candidates[0][0]

    def _build_fallback_chain(
        self,
        primary: str,
        assessment: ComplexityAssessment,
    ) -> list[str]:
        """Build fallback model chain."""
        if not self.config.enable_fallback:
            return []

        fallbacks = []

        if self.config.escalate_on_failure:
            model_order = [
                "claude-3-haiku-20240307",
                "claude-sonnet-4-20250514",
                "claude-3-opus-20240229",
            ]

            primary_idx = model_order.index(primary) if primary in model_order else -1

            for i in range(primary_idx + 1, len(model_order)):
                if len(fallbacks) < self.config.max_fallback_attempts:
                    fallbacks.append(model_order[i])

        return fallbacks

    def _build_selection_reason(
        self,
        assessment: ComplexityAssessment,
        model: str,
    ) -> str:
        """Build human-readable selection reason."""
        parts = [
            f"Complexity: {assessment.level.value} (score: {assessment.score:.2f})",
        ]

        if assessment.requires_reasoning:
            parts.append("requires reasoning")
        if assessment.has_dependencies:
            parts.append("has dependencies")
        if assessment.estimated_files > 3:
            parts.append(f"touches {assessment.estimated_files} files")

        return f"Selected {model}: " + ", ".join(parts)

    def record_performance(
        self,
        model_id: str,
        complexity: ComplexityLevel,
        success: bool,
        score: float,
        attempts: int,
        cost_usd: float,
        duration_seconds: float,
    ) -> None:
        """Record performance data for learning."""
        if model_id not in self._performance:
            self._performance[model_id] = ModelPerformance(model_id=model_id)

        perf = self._performance[model_id]

        perf.total_tasks += 1
        if success:
            perf.successful_tasks += 1
        else:
            perf.failed_tasks += 1

        n = perf.total_tasks
        perf.average_score = ((perf.average_score * (n-1)) + score) / n
        perf.average_attempts = ((perf.average_attempts * (n-1)) + attempts) / n
        perf.total_cost_usd += cost_usd
        perf.average_cost_per_task = perf.total_cost_usd / n
        perf.average_duration_seconds = ((perf.average_duration_seconds * (n-1)) + duration_seconds) / n

        complexity_key = complexity.value
        if complexity_key not in perf.performance_by_complexity:
            perf.performance_by_complexity[complexity_key] = {
                "total": 0, "successful": 0, "average_score": 0.0
            }

        by_complexity = perf.performance_by_complexity[complexity_key]
        by_complexity["total"] += 1
        if success:
            by_complexity["successful"] += 1
        by_complexity["average_score"] = (
            (by_complexity["average_score"] * (by_complexity["total"] - 1) + score) /
            by_complexity["total"]
        )

        if self.performance_path:
            self._save_performance()

    def _has_sufficient_history(self) -> bool:
        """Check if we have enough history for learning."""
        total_tasks = sum(p.total_tasks for p in self._performance.values())
        return total_tasks >= self.config.minimum_history_for_learning

    def _recommend_from_history(
        self,
        complexity: ComplexityLevel,
    ) -> Optional[str]:
        """Recommend model based on historical performance."""
        complexity_key = complexity.value
        best_model = None
        best_score = 0.0

        for model_id, perf in self._performance.items():
            if complexity_key in perf.performance_by_complexity:
                by_complexity = perf.performance_by_complexity[complexity_key]
                if by_complexity["total"] >= 5:
                    success_rate = by_complexity["successful"] / by_complexity["total"]
                    avg_score = by_complexity["average_score"]
                    combined = (success_rate * 0.6) + (avg_score * 0.4)

                    if combined > best_score:
                        best_score = combined
                        best_model = model_id

        return best_model

    async def execute_with_fallback(
        self,
        decision: RoutingDecision,
        execute_fn: Callable[[str], bool],
    ) -> tuple[str, bool]:
        """Execute with automatic fallback on failure."""
        if execute_fn(decision.selected_model):
            return decision.selected_model, True

        for fallback_model in decision.fallback_models:
            if execute_fn(fallback_model):
                return fallback_model, True

        return decision.selected_model, False
```

### 4.4 Integration Points

**With `session.py`:**
```python
# In SessionOrchestrator.run_session():
from agent_harness.routing.router import AgentRouter, RoutingConfig

routing_config = RoutingConfig(
    use_performance_history=True,
    escalate_on_failure=True,
)
router = AgentRouter(
    config=routing_config,
    performance_path=self.harness_dir / "model_performance.json",
)

assessment = router.assess_complexity(
    contract,
    context_tokens=bundle.token_used,
)

budget_remaining = self.config.costs.per_session_usd - current_cost
decision = router.select_model(assessment, budget_remaining)

self.agent_runner = AgentRunner(
    model=decision.selected_model,
    max_tokens=AVAILABLE_MODELS[decision.selected_model].max_tokens,
)

# After execution
router.record_performance(
    model_id=decision.selected_model,
    complexity=assessment.level,
    success=attempt.success,
    score=selected_approach.scores.composite if selected_approach.scores else 0.0,
    attempts=len(attempt.approaches),
    cost_usd=attempt.total_cost_usd,
    duration_seconds=attempt.total_duration_seconds,
)
```

---

## 5. Storage and Persistence

### 5.1 File Structure

```
project-root/
├── .harness/
│   ├── contracts.json
│   ├── model_performance.json
│   ├── attempt_history.json
│   ├── session_state.json
│   ├── costs.yaml
│   └── logs/
│       └── routing_decisions.jsonl
│
├── task-context/
│   ├── staging.json
│   ├── code/
│   ├── api/
│   ├── styles/
│   ├── examples/
│   ├── docs/
│   └── bundles/
│
└── features.json
```

### 5.2 Migration Strategy

```python
def migrate_features_to_contracts(
    features_file: FeaturesFile,
) -> ContractFile:
    """Migrate legacy features to contracts."""
    contract_file = ContractFile(
        project=features_file.project,
    )

    for feature in features_file.features:
        contract = Contract(
            id=str(feature.id),
            title=feature.description[:50],
            description=feature.description,
            category=feature.category,
            status=(
                ContractStatus.COMPLETE if feature.passes
                else ContractStatus.APPROVED
            ),
            acceptance_criteria=[
                AcceptanceCriterion(
                    id=f"test_{feature.id}",
                    description=f"Tests in {feature.test_file} pass",
                    test_file=feature.test_file,
                )
            ],
            depends_on=[str(d) for d in feature.depends_on],
            estimated_complexity=feature.size_estimate,
        )
        contract_file.contracts.append(contract)

    return contract_file
```

---

## 6. Configuration Extensions

Add to `.harness.yaml`:

```yaml
# Contract management
contracts:
  max_attempts_per_contract: 3
  quality_thresholds:
    correctness: 0.8
    security: 0.9
    readability: 0.6
    performance: 0.5
  auto_approve_drafts: false

# Context staging
context_staging:
  enabled: true
  default_token_budget: 50000
  max_token_budget: 150000
  auto_extract_patterns:
    - "*.py"
    - "*.md"
    - "tests/*.py"
  rag_enabled: false
  rag_embedding_model: "text-embedding-3-small"

# Multi-attempt execution
multi_attempt:
  enabled: true
  default_strategy: "iterative"
  max_approaches: 3
  parallel_execution: false
  selection_strategy: "best_score"
  require_tests_pass: true
  minimum_score: 0.7

# Agent routing
routing:
  complexity_model_mapping:
    trivial: "claude-3-haiku-20240307"
    simple: "claude-3-haiku-20240307"
    medium: "claude-sonnet-4-20250514"
    complex: "claude-sonnet-4-20250514"
    epic: "claude-3-opus-20240229"
  enable_fallback: true
  escalate_on_failure: true
  use_performance_history: true
  prefer_cheaper_threshold: 0.1
```

---

## 7. Key Design Decisions

### 7.1 Loose Coupling Enforcement

Each subsystem:
- Has its own data models in dedicated modules
- Communicates through well-defined interfaces
- Can be enabled/disabled independently via config
- Has no direct database access from business logic

### 7.2 Complexity Resistance

- Contracts replace loosely-defined features with structured specifications
- Context staging prevents ad-hoc context gathering
- Multi-attempt execution is optional (single approach by default)
- Routing falls back to simple complexity mapping if no history

### 7.3 Observability

All subsystems emit structured events:
- Contract transitions logged with full context
- Routing decisions logged with alternatives considered
- Attempt history preserved for learning
- Context bundle composition logged

### 7.4 Backward Compatibility

- Features can be migrated to contracts
- Context staging is additive
- Single-attempt execution remains the default
- Simple complexity mapping works without performance history

---

## 8. Implementation Sequence

**Phase 1: Contract Management**
1. Data models (`contracts/models.py`)
2. Contract manager service (`contracts/manager.py`)
3. Migration from features.json
4. Integration with session.py

**Phase 2: Context Staging**
1. Data models (`context_staging/models.py`)
2. Context manager service (`context_staging/manager.py`)
3. Extraction utilities
4. Integration with prompt building

**Phase 3: Multi-Attempt Execution**
1. Data models (`multi_attempt/models.py`)
2. Executor service (`multi_attempt/executor.py`)
3. Scoring system
4. Integration with session loop

**Phase 4: Agent Routing**
1. Data models (`routing/models.py`)
2. Router service (`routing/router.py`)
3. Performance tracking
4. Integration with agent initialization
