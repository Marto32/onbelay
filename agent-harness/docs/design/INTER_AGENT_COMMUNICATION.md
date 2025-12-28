# Inter-Agent Communication and Coordination System

## Design Document v1.0

---

## Executive Summary

This document specifies the Inter-Agent Communication and Coordination System for the Universal Agent Harness multi-agent orchestration layer. The system enables specialized agents to:

1. **Share State** - Files modified, decisions made, context accumulated
2. **Pass Messages** - Synchronous Producer-Critic handoffs, async notifications
3. **Coordinate** - Prevent simultaneous file edits, manage execution tokens
4. **Observe** - Overseer monitors all agents in real-time without blocking

### Design Principles

1. **Hybrid Persistence** - In-memory asyncio queues for fast handoffs, SQLite for durability
2. **WAL Mode Concurrency** - SQLite WAL enables concurrent reads during writes
3. **Crash Recovery** - Every state change persisted before acknowledgment
4. **Loose Coupling** - Agents communicate through message contracts, not shared objects
5. **Observable** - All inter-agent communication logged and auditable
6. **Turn-Based Coordination** - Execution tokens prevent resource conflicts

### Relationship to Existing Architecture

This system integrates between the Multi-Agent Orchestration Layer and the existing SessionOrchestrator:

```
                          MULTI-AGENT ORCHESTRATION LAYER
+--------------------------------------------------------------------------------+
|  +------------------+  +------------------+  +------------------+               |
|  | Project Manager  |  |    Scaffolder    |  |    Reviewer      |               |
|  +--------+---------+  +--------+---------+  +--------+---------+               |
|           |                     |                     |                         |
|           +---------------------+---------------------+                         |
|                                 |                                               |
|  +--------------------------------------------------------------------------+  |
|  |              INTER-AGENT COMMUNICATION LAYER (THIS DOCUMENT)              |  |
|  |                                                                           |  |
|  |  +-------------+  +-------------+  +-------------+  +-------------+       |  |
|  |  | MessageBus  |  | StateStore  |  |  EventLog   |  | Coordinator |       |  |
|  |  +------+------+  +------+------+  +------+------+  +------+------+       |  |
|  |         |                |                |                |              |  |
|  |         +----------------+----------------+----------------+              |  |
|  |                          |                                                |  |
|  |  +--------------------------------------------------------------------------+
|  |  |                      SQLite Database (WAL mode)                       |  |
|  |  |  +------------+  +------------+  +------------+  +------------+       |  |
|  |  |  | messages   |  |shared_state|  | event_log  |  |agent_status|       |  |
|  |  |  +------------+  +------------+  +------------+  +------------+       |  |
|  |  +--------------------------------------------------------------------------+
|  +--------------------------------------------------------------------------+  |
+--------------------------------------------------------------------------------+
                                 |
                                 v
+--------------------------------------------------------------------------------+
|                        EXISTING HARNESS LAYER                                   |
|  +------------------+  +------------------+  +------------------+               |
|  |SessionOrchestrator|  |   AgentRunner   |  |  ToolExecutor   |               |
|  +------------------+  +------------------+  +------------------+               |
+--------------------------------------------------------------------------------+
```

---

## 1. Architecture Overview

### 1.1 Component Summary

| Component | Purpose | Persistence |
|-----------|---------|-------------|
| **MessageBus** | Route messages between agents | In-memory queues + SQLite |
| **StateStore** | Shared key-value state with versioning | SQLite |
| **EventLog** | Append-only audit trail for Overseer | SQLite |
| **Coordinator** | File locks, execution tokens, turn management | SQLite |

### 1.2 Communication Patterns

```
SYNCHRONOUS (Turn-Based)                    ASYNCHRONOUS (Event-Driven)
+---------------------------+               +---------------------------+
|                           |               |                           |
|  Scaffolder               |               |  Any Agent                |
|     |                     |               |     |                     |
|     | submit_for_review() |               |     | broadcast_event()   |
|     |                     |               |     |                     |
|     v                     |               |     v                     |
|  [WAIT for token]         |               |  EventLog                 |
|     |                     |               |     |                     |
|     v                     |               |     | (async fanout)      |
|  Reviewer                 |               |     v                     |
|     |                     |               |  Overseer (subscriber)    |
|     | feedback            |               |  PM (subscriber)          |
|     |                     |               |  ... (other subscribers)  |
|     v                     |               |                           |
|  [RELEASE token]          |               +---------------------------+
|     |                     |
|     v                     |
|  Scaffolder (resumes)     |
|                           |
+---------------------------+
```

### 1.3 Data Flow

```
+-------------+     +-------------+     +-------------+
|   Agent A   |---->| MessageBus  |---->|   Agent B   |
+-------------+     +------+------+     +-------------+
                           |
                    +------v------+
                    |   SQLite    |  (messages table - for recovery)
                    +-------------+

+-------------+     +-------------+
|   Agent A   |---->| StateStore  |<----|   Agent B   |
+-------------+     +------+------+     +-------------+
                           |
                    +------v------+
                    |   SQLite    |  (shared_state table - versioned)
                    +-------------+

+-------------+     +-------------+     +-------------+
| Any Agent   |---->|  EventLog   |---->|  Overseer   |
+-------------+     +------+------+     +-------------+
                           |
                    +------v------+
                    |   SQLite    |  (event_log table - append-only)
                    +-------------+
```

---

## 2. SQLite Schema

### 2.1 Database Configuration

```sql
-- Enable WAL mode for concurrent access
PRAGMA journal_mode = WAL;

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Optimize for concurrent reads
PRAGMA synchronous = NORMAL;

-- Memory-map for performance (64MB)
PRAGMA mmap_size = 67108864;
```

### 2.2 Schema Definition

```sql
-- ============================================================================
-- MESSAGE QUEUE
-- Persistent message queue for inter-agent communication
-- ============================================================================

CREATE TABLE messages (
    id              TEXT PRIMARY KEY,           -- UUID
    session_id      INTEGER NOT NULL,           -- Links to harness session

    -- Routing
    from_agent_id   TEXT NOT NULL,              -- Sender agent UUID
    from_role       TEXT NOT NULL,              -- AgentRole enum value
    to_agent_id     TEXT,                       -- Recipient (NULL = broadcast)
    to_role         TEXT,                       -- Target role (for role-based routing)

    -- Content
    message_type    TEXT NOT NULL,              -- MessageType enum value
    subject         TEXT NOT NULL DEFAULT '',
    body            TEXT NOT NULL DEFAULT '',
    payload         TEXT NOT NULL DEFAULT '{}', -- JSON-serialized payload

    -- Threading
    subcontract_id  TEXT,                       -- Links to subcontract
    in_reply_to     TEXT REFERENCES messages(id),
    thread_root_id  TEXT REFERENCES messages(id),

    -- Delivery
    priority        INTEGER NOT NULL DEFAULT 0, -- Higher = more urgent
    requires_response BOOLEAN NOT NULL DEFAULT FALSE,

    -- Status
    status          TEXT NOT NULL DEFAULT 'pending', -- pending, delivered, read, processed, failed
    read_at         TEXT,                       -- ISO timestamp
    processed_at    TEXT,                       -- ISO timestamp
    error           TEXT,                       -- Error message if failed

    -- Metadata
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT,                       -- Optional TTL

    -- Indexes for common queries
    CONSTRAINT valid_status CHECK (status IN ('pending', 'delivered', 'read', 'processed', 'failed'))
);

CREATE INDEX idx_messages_to_agent ON messages(to_agent_id, status);
CREATE INDEX idx_messages_to_role ON messages(to_role, status);
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_subcontract ON messages(subcontract_id);
CREATE INDEX idx_messages_thread ON messages(thread_root_id);
CREATE INDEX idx_messages_created ON messages(created_at);

-- ============================================================================
-- SHARED STATE
-- Versioned key-value store for shared state between agents
-- ============================================================================

CREATE TABLE shared_state (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Key identification
    namespace       TEXT NOT NULL,              -- e.g., 'session', 'subcontract', 'agent'
    key             TEXT NOT NULL,              -- State key

    -- Value
    value           TEXT NOT NULL,              -- JSON-serialized value
    value_type      TEXT NOT NULL DEFAULT 'json', -- json, string, integer, boolean

    -- Versioning
    version         INTEGER NOT NULL DEFAULT 1,
    previous_version_id INTEGER REFERENCES shared_state(id),

    -- Ownership
    owner_agent_id  TEXT,                       -- NULL = shared, otherwise exclusive
    session_id      INTEGER,
    subcontract_id  TEXT,

    -- Metadata
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT NOT NULL,              -- Agent ID that created this version
    expires_at      TEXT,                       -- Optional TTL

    UNIQUE(namespace, key, version)
);

CREATE INDEX idx_state_namespace_key ON shared_state(namespace, key);
CREATE INDEX idx_state_session ON shared_state(session_id);
CREATE INDEX idx_state_owner ON shared_state(owner_agent_id);

-- View for current state (latest version of each key)
CREATE VIEW current_state AS
SELECT s1.*
FROM shared_state s1
INNER JOIN (
    SELECT namespace, key, MAX(version) as max_version
    FROM shared_state
    GROUP BY namespace, key
) s2 ON s1.namespace = s2.namespace
    AND s1.key = s2.key
    AND s1.version = s2.max_version;

-- ============================================================================
-- EVENT LOG
-- Append-only log for Overseer monitoring and debugging
-- ============================================================================

CREATE TABLE event_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,

    -- Event identification
    event_type      TEXT NOT NULL,              -- EventType enum value
    event_category  TEXT NOT NULL,              -- 'agent', 'message', 'state', 'coordination', 'system'

    -- Source
    source_agent_id TEXT,
    source_role     TEXT,

    -- Event data
    summary         TEXT NOT NULL,              -- Human-readable summary
    details         TEXT NOT NULL DEFAULT '{}', -- JSON-serialized details

    -- Context
    subcontract_id  TEXT,
    related_message_id TEXT REFERENCES messages(id),
    related_state_id INTEGER REFERENCES shared_state(id),

    -- Severity
    severity        TEXT NOT NULL DEFAULT 'info', -- debug, info, warning, error, critical

    -- Timing
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT valid_severity CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical'))
);

CREATE INDEX idx_events_session ON event_log(session_id);
CREATE INDEX idx_events_type ON event_log(event_type);
CREATE INDEX idx_events_agent ON event_log(source_agent_id);
CREATE INDEX idx_events_severity ON event_log(severity);
CREATE INDEX idx_events_created ON event_log(created_at);
CREATE INDEX idx_events_subcontract ON event_log(subcontract_id);

-- ============================================================================
-- AGENT STATUS
-- Real-time status and heartbeats for all active agents
-- ============================================================================

CREATE TABLE agent_status (
    agent_id        TEXT PRIMARY KEY,
    session_id      INTEGER NOT NULL,

    -- Identity
    role            TEXT NOT NULL,              -- AgentRole enum value
    display_name    TEXT,

    -- Assignment
    subcontract_id  TEXT,

    -- Status
    status          TEXT NOT NULL DEFAULT 'initializing', -- initializing, active, waiting, blocked, completed, failed, terminated
    current_activity TEXT,                      -- Human-readable current action

    -- Metrics
    turns_completed INTEGER NOT NULL DEFAULT 0,
    tokens_used     INTEGER NOT NULL DEFAULT 0,
    files_modified  INTEGER NOT NULL DEFAULT 0,
    tool_calls      INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,

    -- Progress
    last_tool_call  TEXT,                       -- Name of last tool called
    last_file_modified TEXT,                    -- Path of last file modified
    progress_percent REAL,                      -- 0.0 to 1.0

    -- Timing
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_activity_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_heartbeat_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,

    -- Health
    heartbeat_interval_ms INTEGER NOT NULL DEFAULT 5000,
    missed_heartbeats INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT valid_status CHECK (status IN ('initializing', 'active', 'waiting', 'blocked', 'completed', 'failed', 'terminated'))
);

CREATE INDEX idx_agent_status_session ON agent_status(session_id);
CREATE INDEX idx_agent_status_role ON agent_status(role);
CREATE INDEX idx_agent_status_status ON agent_status(status);

-- ============================================================================
-- FILE LOCKS
-- Prevent concurrent modifications to the same files
-- ============================================================================

CREATE TABLE file_locks (
    file_path       TEXT PRIMARY KEY,

    -- Lock holder
    agent_id        TEXT NOT NULL REFERENCES agent_status(agent_id),
    session_id      INTEGER NOT NULL,

    -- Lock type
    lock_type       TEXT NOT NULL DEFAULT 'exclusive', -- exclusive, shared

    -- Metadata
    reason          TEXT,                       -- Why the lock was acquired
    acquired_at     TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT,                       -- Optional TTL for abandoned lock detection

    CONSTRAINT valid_lock_type CHECK (lock_type IN ('exclusive', 'shared'))
);

CREATE INDEX idx_locks_agent ON file_locks(agent_id);
CREATE INDEX idx_locks_session ON file_locks(session_id);
CREATE INDEX idx_locks_expires ON file_locks(expires_at);

-- ============================================================================
-- EXECUTION TOKENS
-- Turn-based execution control
-- ============================================================================

CREATE TABLE execution_tokens (
    token_id        TEXT PRIMARY KEY,
    session_id      INTEGER NOT NULL,

    -- Token type
    token_type      TEXT NOT NULL,              -- 'producer_critic', 'file_write', 'test_run', 'review'
    scope           TEXT,                       -- subcontract_id or other scope identifier

    -- Current holder
    holder_agent_id TEXT REFERENCES agent_status(agent_id),
    holder_role     TEXT,

    -- Queue
    waiting_agents  TEXT NOT NULL DEFAULT '[]', -- JSON array of {agent_id, role, requested_at}

    -- Status
    status          TEXT NOT NULL DEFAULT 'available', -- available, held, contested

    -- Timing
    acquired_at     TEXT,
    last_released_at TEXT,
    max_hold_seconds INTEGER NOT NULL DEFAULT 1800, -- 30 min default

    CONSTRAINT valid_token_status CHECK (status IN ('available', 'held', 'contested'))
);

CREATE INDEX idx_tokens_session ON execution_tokens(session_id);
CREATE INDEX idx_tokens_holder ON execution_tokens(holder_agent_id);
CREATE INDEX idx_tokens_type ON execution_tokens(token_type);

-- ============================================================================
-- CHECKPOINTS FOR CRASH RECOVERY
-- Tracks what messages/state were processed before crash
-- ============================================================================

CREATE TABLE recovery_checkpoints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,

    -- Checkpoint data
    checkpoint_type TEXT NOT NULL,              -- 'message_processed', 'state_committed', 'token_released'
    reference_id    TEXT NOT NULL,              -- ID of the processed item
    agent_id        TEXT,

    -- State snapshot
    agent_state     TEXT,                       -- JSON snapshot of agent state at checkpoint

    -- Timing
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_checkpoints_session ON recovery_checkpoints(session_id);
CREATE INDEX idx_checkpoints_agent ON recovery_checkpoints(agent_id);
CREATE INDEX idx_checkpoints_type ON recovery_checkpoints(checkpoint_type);
```

---

## 3. Python Dataclass Models

### 3.1 Message Types

```python
# src/agent_harness/multi_agent/communication/models.py

"""Inter-agent communication data models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import json
import uuid


class MessageType(Enum):
    """Types of inter-agent messages."""

    # Task lifecycle
    TASK_ASSIGNMENT = "task_assignment"
    TASK_ACCEPTED = "task_accepted"
    TASK_REJECTED = "task_rejected"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_BLOCKED = "task_blocked"
    TASK_FAILED = "task_failed"

    # Producer-Critic handoffs
    SUBMIT_FOR_REVIEW = "submit_for_review"
    REVIEW_FEEDBACK = "review_feedback"
    REVIEW_APPROVED = "review_approved"
    REVIEW_REJECTED = "review_rejected"
    REVISION_REQUESTED = "revision_requested"

    # Coordination
    REQUEST_TOKEN = "request_token"
    TOKEN_GRANTED = "token_granted"
    TOKEN_DENIED = "token_denied"
    TOKEN_RELEASED = "token_released"

    # File coordination
    REQUEST_FILE_LOCK = "request_file_lock"
    FILE_LOCK_GRANTED = "file_lock_granted"
    FILE_LOCK_DENIED = "file_lock_denied"
    FILE_LOCK_RELEASED = "file_lock_released"

    # Clarification
    REQUEST_CLARIFICATION = "request_clarification"
    PROVIDE_CLARIFICATION = "provide_clarification"
    REQUEST_INPUT = "request_input"
    PROVIDE_INPUT = "provide_input"

    # Control
    NUDGE = "nudge"
    HALT = "halt"
    RESUME = "resume"
    TERMINATE = "terminate"
    ESCALATE = "escalate"

    # Broadcast
    STATE_CHANGED = "state_changed"
    FILE_MODIFIED = "file_modified"
    TEST_RESULT = "test_result"
    ERROR_OCCURRED = "error_occurred"


class MessageStatus(Enum):
    """Message delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    READ = "read"
    PROCESSED = "processed"
    FAILED = "failed"


class AgentRole(Enum):
    """Agent role identifiers."""
    PROJECT_MANAGER = "project_manager"
    SCAFFOLDER = "scaffolder"
    TEST_ENGINEER = "test_engineer"
    REVIEWER = "reviewer"
    OVERSEER = "overseer"


class AgentStatus(Enum):
    """Agent execution status."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class EventCategory(Enum):
    """Event log categories."""
    AGENT = "agent"
    MESSAGE = "message"
    STATE = "state"
    COORDINATION = "coordination"
    SYSTEM = "system"


class EventSeverity(Enum):
    """Event severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LockType(Enum):
    """File lock types."""
    EXCLUSIVE = "exclusive"
    SHARED = "shared"


class TokenType(Enum):
    """Execution token types."""
    PRODUCER_CRITIC = "producer_critic"
    FILE_WRITE = "file_write"
    TEST_RUN = "test_run"
    REVIEW = "review"


class TokenStatus(Enum):
    """Execution token status."""
    AVAILABLE = "available"
    HELD = "held"
    CONTESTED = "contested"


# =============================================================================
# Core Message Model
# =============================================================================

@dataclass
class AgentMessage:
    """A message between agents."""

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: int = 0

    # Routing
    from_agent_id: str = ""
    from_role: AgentRole = AgentRole.PROJECT_MANAGER
    to_agent_id: Optional[str] = None  # None = broadcast
    to_role: Optional[AgentRole] = None  # For role-based routing

    # Content
    message_type: MessageType = MessageType.TASK_ASSIGNMENT
    subject: str = ""
    body: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    # Threading
    subcontract_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    thread_root_id: Optional[str] = None

    # Delivery
    priority: int = 0  # Higher = more urgent
    requires_response: bool = False

    # Status
    status: MessageStatus = MessageStatus.PENDING
    read_at: Optional[str] = None
    processed_at: Optional[str] = None
    error: Optional[str] = None

    # Metadata
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    expires_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "from_agent_id": self.from_agent_id,
            "from_role": self.from_role.value,
            "to_agent_id": self.to_agent_id,
            "to_role": self.to_role.value if self.to_role else None,
            "message_type": self.message_type.value,
            "subject": self.subject,
            "body": self.body,
            "payload": json.dumps(self.payload),
            "subcontract_id": self.subcontract_id,
            "in_reply_to": self.in_reply_to,
            "thread_root_id": self.thread_root_id,
            "priority": self.priority,
            "requires_response": self.requires_response,
            "status": self.status.value,
            "read_at": self.read_at,
            "processed_at": self.processed_at,
            "error": self.error,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMessage":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            session_id=data.get("session_id", 0),
            from_agent_id=data["from_agent_id"],
            from_role=AgentRole(data["from_role"]),
            to_agent_id=data.get("to_agent_id"),
            to_role=AgentRole(data["to_role"]) if data.get("to_role") else None,
            message_type=MessageType(data["message_type"]),
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            payload=json.loads(data.get("payload", "{}")),
            subcontract_id=data.get("subcontract_id"),
            in_reply_to=data.get("in_reply_to"),
            thread_root_id=data.get("thread_root_id"),
            priority=data.get("priority", 0),
            requires_response=data.get("requires_response", False),
            status=MessageStatus(data.get("status", "pending")),
            read_at=data.get("read_at"),
            processed_at=data.get("processed_at"),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            expires_at=data.get("expires_at"),
        )

    def to_agent_prompt(self) -> str:
        """Format message for inclusion in agent prompt."""
        lines = [
            "---",
            f"FROM: {self.from_role.value} ({self.from_agent_id[:8] if self.from_agent_id else 'system'})",
            f"TYPE: {self.message_type.value}",
            f"SUBJECT: {self.subject}",
            f"TIME: {self.created_at}",
            "---",
            "",
            self.body,
        ]

        if self.payload:
            lines.append("")
            lines.append("PAYLOAD:")
            lines.append(json.dumps(self.payload, indent=2))

        return "\n".join(lines)


# =============================================================================
# Shared State Model
# =============================================================================

@dataclass
class SharedStateEntry:
    """A versioned shared state entry."""

    id: Optional[int] = None

    # Key identification
    namespace: str = "session"  # session, subcontract, agent, global
    key: str = ""

    # Value
    value: Any = None
    value_type: str = "json"  # json, string, integer, boolean

    # Versioning
    version: int = 1
    previous_version_id: Optional[int] = None

    # Ownership
    owner_agent_id: Optional[str] = None  # None = shared
    session_id: Optional[int] = None
    subcontract_id: Optional[str] = None

    # Metadata
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    created_by: str = ""
    expires_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "namespace": self.namespace,
            "key": self.key,
            "value": json.dumps(self.value) if self.value_type == "json" else str(self.value),
            "value_type": self.value_type,
            "version": self.version,
            "previous_version_id": self.previous_version_id,
            "owner_agent_id": self.owner_agent_id,
            "session_id": self.session_id,
            "subcontract_id": self.subcontract_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SharedStateEntry":
        """Deserialize from dictionary."""
        value_type = data.get("value_type", "json")
        raw_value = data.get("value", "{}")

        if value_type == "json":
            value = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
        elif value_type == "integer":
            value = int(raw_value)
        elif value_type == "boolean":
            value = raw_value.lower() == "true" if isinstance(raw_value, str) else bool(raw_value)
        else:
            value = raw_value

        return cls(
            id=data.get("id"),
            namespace=data.get("namespace", "session"),
            key=data.get("key", ""),
            value=value,
            value_type=value_type,
            version=data.get("version", 1),
            previous_version_id=data.get("previous_version_id"),
            owner_agent_id=data.get("owner_agent_id"),
            session_id=data.get("session_id"),
            subcontract_id=data.get("subcontract_id"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            created_by=data.get("created_by", ""),
            expires_at=data.get("expires_at"),
        )


# =============================================================================
# Event Log Model
# =============================================================================

@dataclass
class EventLogEntry:
    """An event log entry for audit and monitoring."""

    id: Optional[int] = None
    session_id: int = 0

    # Event identification
    event_type: str = ""
    event_category: EventCategory = EventCategory.SYSTEM

    # Source
    source_agent_id: Optional[str] = None
    source_role: Optional[AgentRole] = None

    # Event data
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    # Context
    subcontract_id: Optional[str] = None
    related_message_id: Optional[str] = None
    related_state_id: Optional[int] = None

    # Severity
    severity: EventSeverity = EventSeverity.INFO

    # Timing
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "event_category": self.event_category.value,
            "source_agent_id": self.source_agent_id,
            "source_role": self.source_role.value if self.source_role else None,
            "summary": self.summary,
            "details": json.dumps(self.details),
            "subcontract_id": self.subcontract_id,
            "related_message_id": self.related_message_id,
            "related_state_id": self.related_state_id,
            "severity": self.severity.value,
            "created_at": self.created_at,
        }


# =============================================================================
# Agent Status Model
# =============================================================================

@dataclass
class AgentStatusEntry:
    """Real-time status for an active agent."""

    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: int = 0

    # Identity
    role: AgentRole = AgentRole.SCAFFOLDER
    display_name: Optional[str] = None

    # Assignment
    subcontract_id: Optional[str] = None

    # Status
    status: AgentStatus = AgentStatus.INITIALIZING
    current_activity: Optional[str] = None

    # Metrics
    turns_completed: int = 0
    tokens_used: int = 0
    files_modified: int = 0
    tool_calls: int = 0
    error_count: int = 0

    # Progress
    last_tool_call: Optional[str] = None
    last_file_modified: Optional[str] = None
    progress_percent: Optional[float] = None

    # Timing
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    last_activity_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    last_heartbeat_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    completed_at: Optional[str] = None

    # Health
    heartbeat_interval_ms: int = 5000
    missed_heartbeats: int = 0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "role": self.role.value,
            "display_name": self.display_name,
            "subcontract_id": self.subcontract_id,
            "status": self.status.value,
            "current_activity": self.current_activity,
            "turns_completed": self.turns_completed,
            "tokens_used": self.tokens_used,
            "files_modified": self.files_modified,
            "tool_calls": self.tool_calls,
            "error_count": self.error_count,
            "last_tool_call": self.last_tool_call,
            "last_file_modified": self.last_file_modified,
            "progress_percent": self.progress_percent,
            "started_at": self.started_at,
            "last_activity_at": self.last_activity_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "completed_at": self.completed_at,
            "heartbeat_interval_ms": self.heartbeat_interval_ms,
            "missed_heartbeats": self.missed_heartbeats,
        }


# =============================================================================
# File Lock Model
# =============================================================================

@dataclass
class FileLock:
    """A file lock entry."""

    file_path: str = ""
    agent_id: str = ""
    session_id: int = 0

    lock_type: LockType = LockType.EXCLUSIVE
    reason: Optional[str] = None

    acquired_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    expires_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "file_path": self.file_path,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "lock_type": self.lock_type.value,
            "reason": self.reason,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
        }


# =============================================================================
# Execution Token Model
# =============================================================================

@dataclass
class WaitingAgent:
    """An agent waiting for a token."""
    agent_id: str
    role: AgentRole
    requested_at: str


@dataclass
class ExecutionToken:
    """An execution token for turn-based coordination."""

    token_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: int = 0

    # Token type
    token_type: TokenType = TokenType.PRODUCER_CRITIC
    scope: Optional[str] = None  # subcontract_id or other scope

    # Current holder
    holder_agent_id: Optional[str] = None
    holder_role: Optional[AgentRole] = None

    # Queue
    waiting_agents: list[WaitingAgent] = field(default_factory=list)

    # Status
    status: TokenStatus = TokenStatus.AVAILABLE

    # Timing
    acquired_at: Optional[str] = None
    last_released_at: Optional[str] = None
    max_hold_seconds: int = 1800  # 30 minutes default

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "token_id": self.token_id,
            "session_id": self.session_id,
            "token_type": self.token_type.value,
            "scope": self.scope,
            "holder_agent_id": self.holder_agent_id,
            "holder_role": self.holder_role.value if self.holder_role else None,
            "waiting_agents": json.dumps([
                {"agent_id": w.agent_id, "role": w.role.value, "requested_at": w.requested_at}
                for w in self.waiting_agents
            ]),
            "status": self.status.value,
            "acquired_at": self.acquired_at,
            "last_released_at": self.last_released_at,
            "max_hold_seconds": self.max_hold_seconds,
        }


# =============================================================================
# Recovery Checkpoint Model
# =============================================================================

@dataclass
class RecoveryCheckpoint:
    """A checkpoint for crash recovery."""

    id: Optional[int] = None
    session_id: int = 0

    checkpoint_type: str = ""  # message_processed, state_committed, token_released
    reference_id: str = ""
    agent_id: Optional[str] = None

    agent_state: Optional[dict] = None

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "checkpoint_type": self.checkpoint_type,
            "reference_id": self.reference_id,
            "agent_id": self.agent_id,
            "agent_state": json.dumps(self.agent_state) if self.agent_state else None,
            "created_at": self.created_at,
        }
```

---

## 4. Service Interfaces

### 4.1 MessageBus

```python
# src/agent_harness/multi_agent/communication/message_bus.py

"""Message bus for inter-agent communication."""

import asyncio
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import AsyncIterator, Callable, Optional
import json

from .models import (
    AgentMessage, AgentRole, MessageStatus, MessageType,
    EventLogEntry, EventCategory, EventSeverity,
)


@dataclass
class MessageBusConfig:
    """Configuration for the message bus."""

    # Database
    db_path: Path = Path(".harness/communication.db")

    # In-memory queue settings
    max_queue_size: int = 1000
    default_timeout_seconds: float = 30.0

    # Persistence
    persist_all_messages: bool = True
    persist_interval_seconds: float = 1.0

    # Cleanup
    message_retention_hours: int = 24
    cleanup_interval_seconds: float = 3600.0


class MessageBus:
    """
    Hybrid message bus combining in-memory queues with SQLite persistence.

    Features:
    - Fast in-memory asyncio queues for active communication
    - SQLite persistence for crash recovery and audit
    - Support for both direct (agent-to-agent) and broadcast messages
    - Priority-based message ordering
    - Message threading and reply tracking

    Usage:
        bus = MessageBus(config, db_connection)
        await bus.initialize()

        # Send a message
        await bus.send(AgentMessage(
            from_agent_id="agent-1",
            from_role=AgentRole.SCAFFOLDER,
            to_agent_id="agent-2",
            message_type=MessageType.SUBMIT_FOR_REVIEW,
            subject="Code review request",
            body="Please review the changes in src/auth.py",
        ))

        # Receive messages
        msg = await bus.receive("agent-2", timeout=30.0)
    """

    def __init__(
        self,
        config: MessageBusConfig,
        db_path: Optional[Path] = None,
        on_event: Optional[Callable[[EventLogEntry], None]] = None,
    ):
        self.config = config
        self.db_path = db_path or config.db_path
        self.on_event = on_event

        # In-memory queues by agent_id
        self._queues: dict[str, asyncio.PriorityQueue] = defaultdict(
            lambda: asyncio.PriorityQueue(maxsize=config.max_queue_size)
        )

        # Role-based queues for broadcast
        self._role_queues: dict[AgentRole, asyncio.PriorityQueue] = {
            role: asyncio.PriorityQueue(maxsize=config.max_queue_size)
            for role in AgentRole
        }

        # Subscribers for message types (async callbacks)
        self._subscribers: dict[MessageType, list[Callable]] = defaultdict(list)

        # Database connection
        self._conn: Optional[sqlite3.Connection] = None

        # Background tasks
        self._persist_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Pending messages for batch persistence
        self._pending_persist: list[AgentMessage] = []
        self._persist_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the message bus."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,  # Autocommit for WAL mode
        )
        self._conn.row_factory = sqlite3.Row

        # Enable WAL mode
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")

        # Start background tasks
        if self.config.persist_all_messages:
            self._persist_task = asyncio.create_task(self._persist_loop())

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self._log_event(
            "message_bus_initialized",
            EventCategory.SYSTEM,
            "Message bus initialized",
            {"db_path": str(self.db_path)},
            EventSeverity.INFO,
        )

    async def shutdown(self) -> None:
        """Shutdown the message bus gracefully."""
        # Cancel background tasks
        if self._persist_task:
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Flush pending messages
        await self._flush_pending()

        # Close database
        if self._conn:
            self._conn.close()

    # =========================================================================
    # Core Messaging
    # =========================================================================

    async def send(self, message: AgentMessage) -> str:
        """
        Send a message to an agent or broadcast.

        Args:
            message: The message to send.

        Returns:
            The message ID.
        """
        # Ensure message has an ID
        if not message.id:
            message.id = str(uuid.uuid4())

        # Set thread root if this is a reply
        if message.in_reply_to and not message.thread_root_id:
            parent = await self.get_message(message.in_reply_to)
            if parent:
                message.thread_root_id = parent.thread_root_id or parent.id

        # Persist to database first (for crash recovery)
        if self.config.persist_all_messages:
            async with self._persist_lock:
                self._pending_persist.append(message)

        # Route to appropriate queue(s)
        if message.to_agent_id:
            # Direct message
            queue = self._queues[message.to_agent_id]
            await queue.put((-message.priority, message.created_at, message))
        elif message.to_role:
            # Role-based routing
            queue = self._role_queues[message.to_role]
            await queue.put((-message.priority, message.created_at, message))
        else:
            # Broadcast to all subscribers
            for callback in self._subscribers.get(message.message_type, []):
                try:
                    await callback(message)
                except Exception as e:
                    self._log_event(
                        "subscriber_error",
                        EventCategory.MESSAGE,
                        f"Subscriber error: {e}",
                        {"message_id": message.id, "error": str(e)},
                        EventSeverity.ERROR,
                    )

        self._log_event(
            "message_sent",
            EventCategory.MESSAGE,
            f"Message sent: {message.message_type.value}",
            {
                "message_id": message.id,
                "from_agent": message.from_agent_id,
                "to_agent": message.to_agent_id,
                "to_role": message.to_role.value if message.to_role else None,
                "type": message.message_type.value,
            },
            EventSeverity.DEBUG,
        )

        return message.id

    async def receive(
        self,
        agent_id: str,
        timeout: Optional[float] = None,
        filter_types: Optional[list[MessageType]] = None,
    ) -> Optional[AgentMessage]:
        """
        Receive a message for an agent.

        Args:
            agent_id: The agent ID to receive for.
            timeout: Optional timeout in seconds.
            filter_types: Optional list of message types to accept.

        Returns:
            The next message, or None if timeout.
        """
        timeout = timeout or self.config.default_timeout_seconds
        queue = self._queues[agent_id]

        try:
            while True:
                _, _, message = await asyncio.wait_for(
                    queue.get(),
                    timeout=timeout,
                )

                # Apply filter if specified
                if filter_types and message.message_type not in filter_types:
                    # Put back and try again
                    await queue.put((-message.priority, message.created_at, message))
                    await asyncio.sleep(0.01)  # Small delay to prevent tight loop
                    continue

                # Mark as delivered
                message.status = MessageStatus.DELIVERED
                await self._update_message_status(message.id, MessageStatus.DELIVERED)

                return message

        except asyncio.TimeoutError:
            return None

    async def receive_by_role(
        self,
        role: AgentRole,
        agent_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[AgentMessage]:
        """
        Receive a message sent to a role.

        Args:
            role: The role to receive for.
            agent_id: The specific agent claiming the message.
            timeout: Optional timeout in seconds.

        Returns:
            The next message, or None if timeout.
        """
        timeout = timeout or self.config.default_timeout_seconds
        queue = self._role_queues[role]

        try:
            _, _, message = await asyncio.wait_for(
                queue.get(),
                timeout=timeout,
            )

            # Update message with actual recipient
            message.to_agent_id = agent_id
            message.status = MessageStatus.DELIVERED
            await self._update_message_status(message.id, MessageStatus.DELIVERED)

            return message

        except asyncio.TimeoutError:
            return None

    async def receive_all(
        self,
        agent_id: str,
        max_messages: int = 100,
    ) -> list[AgentMessage]:
        """
        Receive all pending messages for an agent.

        Args:
            agent_id: The agent ID to receive for.
            max_messages: Maximum number of messages to return.

        Returns:
            List of messages.
        """
        messages = []
        queue = self._queues[agent_id]

        while len(messages) < max_messages and not queue.empty():
            try:
                _, _, message = queue.get_nowait()
                message.status = MessageStatus.DELIVERED
                messages.append(message)
            except asyncio.QueueEmpty:
                break

        return messages

    async def mark_read(self, message_id: str) -> None:
        """Mark a message as read."""
        await self._update_message_status(
            message_id,
            MessageStatus.READ,
            read_at=datetime.now(timezone.utc).isoformat(),
        )

    async def mark_processed(self, message_id: str) -> None:
        """Mark a message as processed."""
        await self._update_message_status(
            message_id,
            MessageStatus.PROCESSED,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )

    # =========================================================================
    # Subscriptions
    # =========================================================================

    def subscribe(
        self,
        message_type: MessageType,
        callback: Callable[[AgentMessage], None],
    ) -> None:
        """
        Subscribe to a message type.

        Args:
            message_type: The type to subscribe to.
            callback: Async callback function.
        """
        self._subscribers[message_type].append(callback)

    def unsubscribe(
        self,
        message_type: MessageType,
        callback: Callable[[AgentMessage], None],
    ) -> None:
        """Unsubscribe from a message type."""
        if callback in self._subscribers[message_type]:
            self._subscribers[message_type].remove(callback)

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def get_message(self, message_id: str) -> Optional[AgentMessage]:
        """Get a message by ID."""
        cursor = self._conn.execute(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,),
        )
        row = cursor.fetchone()

        if row:
            return AgentMessage.from_dict(dict(row))
        return None

    async def get_thread(self, thread_root_id: str) -> list[AgentMessage]:
        """Get all messages in a thread."""
        cursor = self._conn.execute(
            """
            SELECT * FROM messages
            WHERE thread_root_id = ? OR id = ?
            ORDER BY created_at ASC
            """,
            (thread_root_id, thread_root_id),
        )

        return [AgentMessage.from_dict(dict(row)) for row in cursor.fetchall()]

    async def get_conversation(
        self,
        subcontract_id: str,
        limit: int = 100,
    ) -> list[AgentMessage]:
        """Get all messages for a subcontract."""
        cursor = self._conn.execute(
            """
            SELECT * FROM messages
            WHERE subcontract_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (subcontract_id, limit),
        )

        return [AgentMessage.from_dict(dict(row)) for row in cursor.fetchall()]

    async def get_pending_count(self, agent_id: str) -> int:
        """Get count of pending messages for an agent."""
        return self._queues[agent_id].qsize()

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _update_message_status(
        self,
        message_id: str,
        status: MessageStatus,
        **kwargs,
    ) -> None:
        """Update message status in database."""
        updates = ["status = ?"]
        values = [status.value]

        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(value)

        values.append(message_id)

        self._conn.execute(
            f"UPDATE messages SET {', '.join(updates)} WHERE id = ?",
            values,
        )

    async def _persist_loop(self) -> None:
        """Background task to persist messages to database."""
        while True:
            await asyncio.sleep(self.config.persist_interval_seconds)
            await self._flush_pending()

    async def _flush_pending(self) -> None:
        """Flush pending messages to database."""
        async with self._persist_lock:
            if not self._pending_persist:
                return

            messages = self._pending_persist
            self._pending_persist = []

        cursor = self._conn.cursor()
        for message in messages:
            data = message.to_dict()
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))

            cursor.execute(
                f"INSERT OR REPLACE INTO messages ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )

        self._conn.commit()

    async def _cleanup_loop(self) -> None:
        """Background task to clean up old messages."""
        while True:
            await asyncio.sleep(self.config.cleanup_interval_seconds)

            cutoff = datetime.now(timezone.utc) - timedelta(
                hours=self.config.message_retention_hours
            )

            self._conn.execute(
                """
                DELETE FROM messages
                WHERE status = 'processed'
                AND created_at < ?
                """,
                (cutoff.isoformat(),),
            )

    def _log_event(
        self,
        event_type: str,
        category: EventCategory,
        summary: str,
        details: dict,
        severity: EventSeverity,
    ) -> None:
        """Log an event."""
        if self.on_event:
            event = EventLogEntry(
                event_type=event_type,
                event_category=category,
                summary=summary,
                details=details,
                severity=severity,
            )
            self.on_event(event)
```

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Create inter-agent communication design document", "status": "completed", "activeForm": "Creating inter-agent communication design document"}, {"content": "Define SQLite schema for message queue, shared state, and event log", "status": "completed", "activeForm": "Defining SQLite schema for persistence"}, {"content": "Design Python dataclass models for communication primitives", "status": "completed", "activeForm": "Designing Python dataclass models"}, {"content": "Specify service interfaces (MessageBus, StateStore, EventLog, Coordinator)", "status": "in_progress", "activeForm": "Specifying service interfaces"}, {"content": "Document integration points with SessionOrchestrator", "status": "pending", "activeForm": "Documenting integration points"}, {"content": "Design error handling and crash recovery strategies", "status": "pending", "activeForm": "Designing error handling and recovery"}]