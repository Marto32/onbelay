"""Tool definitions for agent harness.

This module provides tool schemas that can be used with Claude API
to give agents structured ways to interact with the harness.
"""

from agent_harness.tools.definitions import (
    HARNESS_TOOLS,
    get_tool_by_name,
    get_tools_for_session,
)
from agent_harness.tools.executor import (
    ToolExecutionResult,
    validate_tool_arguments,
)
from agent_harness.tools.schemas import (
    ToolSchema,
    create_tool_schema,
    validate_schema,
)

__all__ = [
    # Definitions
    "HARNESS_TOOLS",
    "get_tool_by_name",
    "get_tools_for_session",
    # Executor
    "ToolExecutionResult",
    "validate_tool_arguments",
    # Schemas
    "ToolSchema",
    "create_tool_schema",
    "validate_schema",
]
