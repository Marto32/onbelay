"""Tool executor for agent harness.

Handles execution of tool calls from the agent and returns results.
"""

import asyncio
import inspect
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Union

from agent_harness.tools.definitions import get_tool_by_name
from agent_harness.tools.schemas import ToolSchema, validate_tool_input


@dataclass
class ToolExecutionResult:
    """Result of a tool execution."""

    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response.

        Returns:
            Dictionary representation of result.
        """
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


# Type aliases for tool handlers (sync and async)
SyncToolHandler = Callable[[dict[str, Any]], ToolExecutionResult]
AsyncToolHandler = Callable[[dict[str, Any]], Awaitable[ToolExecutionResult]]
ToolHandler = Union[SyncToolHandler, AsyncToolHandler]


class ToolExecutor:
    """Executes tool calls from the agent.

    Maintains registered handlers for each tool and executes
    them when called by the agent.
    """

    def __init__(self, project_dir: Path):
        """Initialize executor.

        Args:
            project_dir: Path to project directory.
        """
        self.project_dir = project_dir
        self.handlers: dict[str, ToolHandler] = {}
        self.execution_log: list[ToolExecutionResult] = []

    def register_handler(self, tool_name: str, handler: ToolHandler) -> None:
        """Register a handler for a tool.

        Args:
            tool_name: Name of the tool.
            handler: Function to handle tool execution.
        """
        self.handlers[tool_name] = handler

    def execute_sync_from_async_context(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        validate: bool = True,
    ) -> ToolExecutionResult:
        """Execute tool synchronously from within an async context.

        This is a special method for calling async tool execution from
        sync callbacks that are themselves called from async code.
        Uses asyncio.create_task() to schedule the async execution.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            validate: Whether to validate arguments against schema.

        Returns:
            ToolExecutionResult with result or error.
        """
        # Create a task and run it in the current event loop
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context - create a coroutine and run it
            # We need to use a new event loop in a thread for this
            import concurrent.futures
            import threading

            result_holder = []
            def run_in_thread():
                # Create new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(
                        self.execute_async(tool_name, arguments, validate)
                    )
                    result_holder.append(result)
                finally:
                    new_loop.close()

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()

            return result_holder[0] if result_holder else ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error="Thread execution failed"
            )
        else:
            # No loop running - use asyncio.run()
            return asyncio.run(self.execute_async(tool_name, arguments, validate))


    async def execute_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        validate: bool = True,
    ) -> ToolExecutionResult:
        """Execute a tool call (async).

        Supports both synchronous and asynchronous tool handlers.
        Sync handlers are executed in a thread pool to avoid blocking.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            validate: Whether to validate arguments against schema.

        Returns:
            ToolExecutionResult with result or error.
        """
        start_time = datetime.now()

        # Check if tool exists
        schema = get_tool_by_name(tool_name)
        if schema is None:
            result = ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
            )
            self.execution_log.append(result)
            return result

        # Validate arguments
        if validate:
            validation_errors = validate_tool_input(schema, arguments)
            if validation_errors:
                result = ToolExecutionResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Validation errors: {'; '.join(validation_errors)}",
                )
                self.execution_log.append(result)
                return result

        # Check if handler is registered
        handler = self.handlers.get(tool_name)
        if handler is None:
            result = ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"No handler registered for tool: {tool_name}",
            )
            self.execution_log.append(result)
            return result

        # Execute handler (async or sync)
        try:
            # Check if handler is async
            if inspect.iscoroutinefunction(handler):
                result = await handler(arguments)
            else:
                # Run sync handler in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, handler, arguments)

            end_time = datetime.now()
            result.execution_time_ms = (end_time - start_time).total_seconds() * 1000
        except Exception as e:
            end_time = datetime.now()
            result = ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time_ms=(end_time - start_time).total_seconds() * 1000,
            )

        self.execution_log.append(result)
        return result

    def get_execution_log(self) -> list[ToolExecutionResult]:
        """Get the execution log.

        Returns:
            List of all tool execution results.
        """
        return self.execution_log

    def clear_execution_log(self) -> None:
        """Clear the execution log."""
        self.execution_log = []


def validate_tool_arguments(
    tool_name: str,
    arguments: dict[str, Any],
) -> list[str]:
    """Validate tool arguments against schema.

    Args:
        tool_name: Name of the tool.
        arguments: Tool arguments to validate.

    Returns:
        List of validation error messages (empty if valid).
    """
    schema = get_tool_by_name(tool_name)
    if schema is None:
        return [f"Unknown tool: {tool_name}"]

    return validate_tool_input(schema, arguments)




async def execute_tool_async(
    tool_name: str,
    arguments: dict[str, Any],
    executor: ToolExecutor,
) -> ToolExecutionResult:
    """Execute a tool using the provided executor (async).

    Convenience function for simple tool execution.

    Args:
        tool_name: Name of the tool to execute.
        arguments: Tool arguments.
        executor: ToolExecutor instance.

    Returns:
        ToolExecutionResult.
    """
    return await executor.execute_async(tool_name, arguments)


def create_default_handlers(project_dir: Path) -> dict[str, ToolHandler]:
    """Create default tool handlers.

    Args:
        project_dir: Path to project directory.

    Returns:
        Dictionary of tool name to handler function.

    Note:
        This provides stub handlers. Real implementations should be
        provided by the session lifecycle module.
    """
    handlers: dict[str, ToolHandler] = {}

    def run_tests_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for run_tests."""
        return ToolExecutionResult(
            tool_name="run_tests",
            success=True,
            result={"message": "Tests executed", "passed": True},
            metadata={"test_file": args.get("test_file")},
        )

    def run_lint_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for run_lint."""
        return ToolExecutionResult(
            tool_name="run_lint",
            success=True,
            result={"message": "Lint executed", "errors": 0, "warnings": 0},
            metadata={"path": args.get("path")},
        )

    def update_progress_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for update_progress."""
        return ToolExecutionResult(
            tool_name="update_progress",
            success=True,
            result={"message": "Progress updated"},
            metadata={"what_done": args.get("what_done", [])},
        )

    def mark_feature_complete_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for mark_feature_complete."""
        return ToolExecutionResult(
            tool_name="mark_feature_complete",
            success=True,
            result={"message": f"Feature {args['feature_id']} marked complete"},
            metadata={"feature_id": args["feature_id"]},
        )

    def get_feature_status_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for get_feature_status."""
        return ToolExecutionResult(
            tool_name="get_feature_status",
            success=True,
            result={"features": [], "total": 0, "passing": 0},
            metadata={"feature_id": args.get("feature_id")},
        )

    def create_checkpoint_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for create_checkpoint."""
        return ToolExecutionResult(
            tool_name="create_checkpoint",
            success=True,
            result={"checkpoint_id": "stub-checkpoint-id"},
            metadata={"description": args.get("description")},
        )

    def rollback_checkpoint_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for rollback_checkpoint."""
        return ToolExecutionResult(
            tool_name="rollback_checkpoint",
            success=True,
            result={"message": f"Rolled back to {args['checkpoint_id']}"},
            metadata={"checkpoint_id": args["checkpoint_id"]},
        )

    def signal_stuck_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for signal_stuck."""
        return ToolExecutionResult(
            tool_name="signal_stuck",
            success=True,
            result={"message": "Stuck signal recorded"},
            metadata={"problem": args.get("problem_description")},
        )

    def check_file_sizes_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for check_file_sizes."""
        return ToolExecutionResult(
            tool_name="check_file_sizes",
            success=True,
            result={"oversized_files": [], "total_files": 0},
            metadata={"path": args.get("path")},
        )

    def create_features_file_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for create_features_file."""
        return ToolExecutionResult(
            tool_name="create_features_file",
            success=True,
            result={"message": "Features file created"},
            metadata={
                "project_name": args.get("project_name"),
                "feature_count": len(args.get("features", [])),
            },
        )

    def create_init_scripts_handler(args: dict[str, Any]) -> ToolExecutionResult:
        """Stub handler for create_init_scripts."""
        return ToolExecutionResult(
            tool_name="create_init_scripts",
            success=True,
            result={"message": "Init scripts created"},
            metadata={
                "init_commands": len(args.get("init_commands", [])),
                "reset_commands": len(args.get("reset_commands", [])),
            },
        )

    handlers["run_tests"] = run_tests_handler
    handlers["run_lint"] = run_lint_handler
    handlers["update_progress"] = update_progress_handler
    handlers["mark_feature_complete"] = mark_feature_complete_handler
    handlers["get_feature_status"] = get_feature_status_handler
    handlers["create_checkpoint"] = create_checkpoint_handler
    handlers["rollback_checkpoint"] = rollback_checkpoint_handler
    handlers["signal_stuck"] = signal_stuck_handler
    handlers["check_file_sizes"] = check_file_sizes_handler
    handlers["create_features_file"] = create_features_file_handler
    handlers["create_init_scripts"] = create_init_scripts_handler

    return handlers
