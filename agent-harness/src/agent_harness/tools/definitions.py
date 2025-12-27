"""Tool definitions for agent harness.

Defines the tools available to agents during different session types.
"""

from typing import Optional

from agent_harness.tools.schemas import ToolSchema, create_tool_schema


# =============================================================================
# Core Harness Tools
# =============================================================================

MARK_FEATURE_COMPLETE = create_tool_schema(
    name="mark_feature_complete",
    description=(
        "Mark a feature as complete in features.json. "
        "Only call this after all tests pass and verification steps are done."
    ),
    properties={
        "feature_id": {
            "type": "integer",
            "description": "The ID of the feature to mark complete",
        },
        "evidence": {
            "type": "string",
            "description": "Evidence of completion (test output, verification results)",
        },
    },
    required=["feature_id", "evidence"],
)

UPDATE_PROGRESS = create_tool_schema(
    name="update_progress",
    description=(
        "Add an entry to claude-progress.txt documenting session work. "
        "Call at the end of each session or when significant progress is made."
    ),
    properties={
        "what_done": {
            "type": "array",
            "description": "List of completed items",
            "items": {"type": "string"},
        },
        "current_state": {
            "type": "string",
            "description": "Current state of the work",
        },
        "blockers": {
            "type": "array",
            "description": "Any blockers encountered",
            "items": {"type": "string"},
        },
        "decisions": {
            "type": "array",
            "description": "Important decisions made",
            "items": {"type": "string"},
        },
        "next_steps": {
            "type": "array",
            "description": "Suggested next steps",
            "items": {"type": "string"},
        },
    },
    required=["what_done", "current_state"],
)

RUN_TESTS = create_tool_schema(
    name="run_tests",
    description=(
        "Run tests for a specific feature or the entire project. "
        "Returns test results including pass/fail counts and output."
    ),
    properties={
        "test_file": {
            "type": "string",
            "description": "Specific test file to run (optional, runs all if omitted)",
        },
        "verbose": {
            "type": "boolean",
            "description": "Include verbose test output",
            "default": False,
        },
        "coverage": {
            "type": "boolean",
            "description": "Generate coverage report",
            "default": False,
        },
    },
    required=[],
)

RUN_LINT = create_tool_schema(
    name="run_lint",
    description=(
        "Run linting on the codebase. "
        "Returns lint errors and warnings that need to be fixed."
    ),
    properties={
        "path": {
            "type": "string",
            "description": "Specific path to lint (optional, lints all if omitted)",
        },
        "fix": {
            "type": "boolean",
            "description": "Attempt to auto-fix issues",
            "default": False,
        },
    },
    required=[],
)

CREATE_CHECKPOINT = create_tool_schema(
    name="create_checkpoint",
    description=(
        "Create a checkpoint of current state for potential rollback. "
        "Useful before making risky changes."
    ),
    properties={
        "description": {
            "type": "string",
            "description": "Description of checkpoint (what state is being saved)",
        },
    },
    required=["description"],
)

ROLLBACK_CHECKPOINT = create_tool_schema(
    name="rollback_checkpoint",
    description=(
        "Rollback to a previous checkpoint. "
        "Use when changes have broken something and need to be undone."
    ),
    properties={
        "checkpoint_id": {
            "type": "string",
            "description": "ID of checkpoint to rollback to",
        },
    },
    required=["checkpoint_id"],
)

GET_FEATURE_STATUS = create_tool_schema(
    name="get_feature_status",
    description=(
        "Get the current status of a specific feature or all features. "
        "Returns feature details, pass status, and dependencies."
    ),
    properties={
        "feature_id": {
            "type": "integer",
            "description": "Specific feature ID (optional, returns all if omitted)",
        },
    },
    required=[],
)

SIGNAL_STUCK = create_tool_schema(
    name="signal_stuck",
    description=(
        "Signal that you are stuck and need help. "
        "The harness will adjust approach in the next session."
    ),
    properties={
        "problem_description": {
            "type": "string",
            "description": "Description of what you're stuck on",
        },
        "attempted_solutions": {
            "type": "array",
            "description": "What you've already tried",
            "items": {"type": "string"},
        },
        "suggested_help": {
            "type": "string",
            "description": "What kind of help might unblock you",
        },
    },
    required=["problem_description"],
)

# =============================================================================
# File Size Tools
# =============================================================================

CHECK_FILE_SIZES = create_tool_schema(
    name="check_file_sizes",
    description=(
        "Check source file sizes and identify oversized files. "
        "Returns files exceeding the configured line limit."
    ),
    properties={
        "path": {
            "type": "string",
            "description": "Path to check (defaults to project root)",
        },
        "limit": {
            "type": "integer",
            "description": "Line count limit (defaults to config value)",
        },
    },
    required=[],
)

# =============================================================================
# Init Session Tools
# =============================================================================

CREATE_FEATURES_FILE = create_tool_schema(
    name="create_features_file",
    description=(
        "Create the features.json file with extracted features from specification. "
        "Only used during initialization."
    ),
    properties={
        "project_name": {
            "type": "string",
            "description": "Name of the project",
        },
        "features": {
            "type": "array",
            "description": "List of feature objects",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "test_file": {"type": "string"},
                    "verification_steps": {"type": "array", "items": {"type": "string"}},
                    "size_estimate": {"type": "string", "enum": ["small", "medium", "large"]},
                    "depends_on": {"type": "array", "items": {"type": "integer"}},
                },
            },
        },
        "init_mode": {
            "type": "string",
            "description": "Whether this is a new or adopt initialization",
            "enum": ["new", "adopt"],
        },
    },
    required=["project_name", "features", "init_mode"],
)

CREATE_INIT_SCRIPTS = create_tool_schema(
    name="create_init_scripts",
    description=(
        "Create init.sh and reset.sh scripts for project setup. "
        "Only used during initialization."
    ),
    properties={
        "init_commands": {
            "type": "array",
            "description": "Commands for init.sh (setup)",
            "items": {"type": "string"},
        },
        "reset_commands": {
            "type": "array",
            "description": "Commands for reset.sh (restore clean state)",
            "items": {"type": "string"},
        },
    },
    required=["init_commands", "reset_commands"],
)

# =============================================================================
# Tool Collections
# =============================================================================

# All harness tools
HARNESS_TOOLS: dict[str, ToolSchema] = {
    "mark_feature_complete": MARK_FEATURE_COMPLETE,
    "update_progress": UPDATE_PROGRESS,
    "run_tests": RUN_TESTS,
    "run_lint": RUN_LINT,
    "create_checkpoint": CREATE_CHECKPOINT,
    "rollback_checkpoint": ROLLBACK_CHECKPOINT,
    "get_feature_status": GET_FEATURE_STATUS,
    "signal_stuck": SIGNAL_STUCK,
    "check_file_sizes": CHECK_FILE_SIZES,
    "create_features_file": CREATE_FEATURES_FILE,
    "create_init_scripts": CREATE_INIT_SCRIPTS,
}

# Tools for each session type
CODING_TOOLS = [
    "mark_feature_complete",
    "update_progress",
    "run_tests",
    "run_lint",
    "create_checkpoint",
    "rollback_checkpoint",
    "get_feature_status",
    "signal_stuck",
]

CONTINUATION_TOOLS = [
    "mark_feature_complete",
    "update_progress",
    "run_tests",
    "run_lint",
    "create_checkpoint",
    "rollback_checkpoint",
    "get_feature_status",
    "signal_stuck",
]

CLEANUP_TOOLS = [
    "update_progress",
    "run_tests",
    "run_lint",
    "check_file_sizes",
    "create_checkpoint",
    "rollback_checkpoint",
]

INIT_TOOLS = [
    "create_features_file",
    "create_init_scripts",
    "update_progress",
]


def get_tool_by_name(name: str) -> Optional[ToolSchema]:
    """Get a tool schema by name.

    Args:
        name: Tool name.

    Returns:
        ToolSchema if found, None otherwise.
    """
    return HARNESS_TOOLS.get(name)


def get_tools_for_session(session_type: str) -> list[ToolSchema]:
    """Get tools available for a session type.

    Args:
        session_type: Type of session ("coding", "continuation", "cleanup", "init").

    Returns:
        List of ToolSchema objects for the session type.
    """
    tool_names: list[str] = []

    if session_type == "coding":
        tool_names = CODING_TOOLS
    elif session_type == "continuation":
        tool_names = CONTINUATION_TOOLS
    elif session_type == "cleanup":
        tool_names = CLEANUP_TOOLS
    elif session_type == "init":
        tool_names = INIT_TOOLS
    else:
        # Unknown session type - return core tools
        tool_names = ["update_progress", "run_tests", "run_lint", "signal_stuck"]

    return [HARNESS_TOOLS[name] for name in tool_names if name in HARNESS_TOOLS]


def get_tools_as_api_format(session_type: str) -> list[dict]:
    """Get tools in Claude API format for a session type.

    Args:
        session_type: Type of session.

    Returns:
        List of tool definitions in Claude API format.
    """
    tools = get_tools_for_session(session_type)
    return [tool.to_dict() for tool in tools]
