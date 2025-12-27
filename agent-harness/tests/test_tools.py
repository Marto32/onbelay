"""Tests for tools module."""

from pathlib import Path

import pytest

from agent_harness.tools.definitions import (
    HARNESS_TOOLS,
    get_tool_by_name,
    get_tools_as_api_format,
    get_tools_for_session,
)
from agent_harness.tools.executor import (
    ToolExecutionResult,
    ToolExecutor,
    create_default_handlers,
    validate_tool_arguments,
)
from agent_harness.tools.schemas import (
    PropertySchema,
    ToolSchema,
    create_tool_schema,
    validate_schema,
    validate_tool_input,
)


class TestPropertySchema:
    """Tests for PropertySchema."""

    def test_basic_property(self):
        """Basic property creation."""
        prop = PropertySchema(type="string", description="A test property")
        assert prop.type == "string"
        assert prop.description == "A test property"
        assert prop.enum is None

    def test_enum_property(self):
        """Property with enum values."""
        prop = PropertySchema(
            type="string",
            description="Status",
            enum=["pending", "complete", "failed"],
        )
        assert prop.enum == ["pending", "complete", "failed"]

    def test_default_value(self):
        """Property with default value."""
        prop = PropertySchema(
            type="boolean",
            description="Verbose",
            default=False,
        )
        assert prop.default is False

    def test_array_items(self):
        """Property with array items."""
        prop = PropertySchema(
            type="array",
            description="List of items",
            items={"type": "string"},
        )
        assert prop.items == {"type": "string"}


class TestToolSchema:
    """Tests for ToolSchema."""

    def test_basic_schema(self):
        """Basic schema creation."""
        schema = ToolSchema(
            name="test_tool",
            description="A test tool",
        )
        assert schema.name == "test_tool"
        assert schema.description == "A test tool"
        assert schema.properties == {}
        assert schema.required == []

    def test_schema_with_properties(self):
        """Schema with properties."""
        schema = ToolSchema(
            name="test_tool",
            description="A test tool",
            properties={
                "name": PropertySchema(type="string", description="Name"),
                "count": PropertySchema(type="integer", description="Count"),
            },
            required=["name"],
        )
        assert "name" in schema.properties
        assert "count" in schema.properties
        assert schema.required == ["name"]

    def test_to_dict(self):
        """Convert schema to API format."""
        schema = ToolSchema(
            name="my_tool",
            description="My tool description",
            properties={
                "path": PropertySchema(type="string", description="File path"),
                "verbose": PropertySchema(
                    type="boolean",
                    description="Verbose output",
                    default=False,
                ),
            },
            required=["path"],
        )
        api_format = schema.to_dict()

        assert api_format["name"] == "my_tool"
        assert api_format["description"] == "My tool description"
        assert api_format["input_schema"]["type"] == "object"
        assert api_format["input_schema"]["required"] == ["path"]
        assert "path" in api_format["input_schema"]["properties"]
        assert api_format["input_schema"]["properties"]["verbose"]["default"] is False


class TestCreateToolSchema:
    """Tests for create_tool_schema helper."""

    def test_simple_schema(self):
        """Create simple schema."""
        schema = create_tool_schema(
            name="simple_tool",
            description="Simple description",
        )
        assert schema.name == "simple_tool"
        assert schema.description == "Simple description"

    def test_schema_with_properties(self):
        """Create schema with properties."""
        schema = create_tool_schema(
            name="complex_tool",
            description="Complex tool",
            properties={
                "input": {"type": "string", "description": "Input value"},
                "output": {"type": "string", "description": "Output value"},
            },
            required=["input"],
        )
        assert "input" in schema.properties
        assert "output" in schema.properties
        assert schema.required == ["input"]

    def test_schema_with_enum(self):
        """Create schema with enum property."""
        schema = create_tool_schema(
            name="enum_tool",
            description="Tool with enum",
            properties={
                "mode": {
                    "type": "string",
                    "description": "Operation mode",
                    "enum": ["fast", "slow", "balanced"],
                },
            },
        )
        assert schema.properties["mode"].enum == ["fast", "slow", "balanced"]


class TestValidateSchema:
    """Tests for validate_schema."""

    def test_valid_schema(self):
        """Valid schema should return no errors."""
        schema = create_tool_schema(
            name="valid_tool",
            description="A valid tool",
            properties={"arg": {"type": "string", "description": "An argument"}},
            required=["arg"],
        )
        errors = validate_schema(schema)
        assert errors == []

    def test_missing_name(self):
        """Missing name should error."""
        schema = ToolSchema(name="", description="Description")
        errors = validate_schema(schema)
        assert any("name" in e.lower() for e in errors)

    def test_missing_description(self):
        """Missing description should error."""
        schema = ToolSchema(name="tool", description="")
        errors = validate_schema(schema)
        assert any("description" in e.lower() for e in errors)

    def test_invalid_name_characters(self):
        """Invalid characters in name should error."""
        schema = ToolSchema(name="my-tool!", description="Description")
        errors = validate_schema(schema)
        assert any("invalid characters" in e.lower() for e in errors)

    def test_required_not_in_properties(self):
        """Required field not in properties should error."""
        schema = ToolSchema(
            name="tool",
            description="Description",
            required=["missing_field"],
        )
        errors = validate_schema(schema)
        assert any("missing_field" in e for e in errors)

    def test_invalid_property_type(self):
        """Invalid property type should error."""
        schema = ToolSchema(
            name="tool",
            description="Description",
            properties={
                "bad": PropertySchema(type="invalid_type", description="Bad"),
            },
        )
        errors = validate_schema(schema)
        assert any("invalid type" in e.lower() for e in errors)

    def test_array_missing_items(self):
        """Array type without items should error."""
        schema = ToolSchema(
            name="tool",
            description="Description",
            properties={
                "list": PropertySchema(type="array", description="A list"),
            },
        )
        errors = validate_schema(schema)
        assert any("items" in e.lower() for e in errors)


class TestValidateToolInput:
    """Tests for validate_tool_input."""

    def test_valid_input(self):
        """Valid input should return no errors."""
        schema = create_tool_schema(
            name="tool",
            description="Tool",
            properties={
                "name": {"type": "string", "description": "Name"},
                "count": {"type": "integer", "description": "Count"},
            },
            required=["name"],
        )
        errors = validate_tool_input(schema, {"name": "test", "count": 5})
        assert errors == []

    def test_missing_required_field(self):
        """Missing required field should error."""
        schema = create_tool_schema(
            name="tool",
            description="Tool",
            properties={"name": {"type": "string", "description": "Name"}},
            required=["name"],
        )
        errors = validate_tool_input(schema, {})
        assert any("Missing required" in e for e in errors)

    def test_wrong_type(self):
        """Wrong type should error."""
        schema = create_tool_schema(
            name="tool",
            description="Tool",
            properties={"count": {"type": "integer", "description": "Count"}},
        )
        errors = validate_tool_input(schema, {"count": "not an integer"})
        assert any("expected integer" in e.lower() for e in errors)

    def test_enum_invalid_value(self):
        """Invalid enum value should error."""
        schema = create_tool_schema(
            name="tool",
            description="Tool",
            properties={
                "mode": {
                    "type": "string",
                    "description": "Mode",
                    "enum": ["a", "b", "c"],
                },
            },
        )
        errors = validate_tool_input(schema, {"mode": "d"})
        assert any("not in allowed values" in e for e in errors)

    def test_extra_fields_allowed(self):
        """Extra fields should be allowed (no error)."""
        schema = create_tool_schema(
            name="tool",
            description="Tool",
            properties={"name": {"type": "string", "description": "Name"}},
        )
        errors = validate_tool_input(schema, {"name": "test", "extra": "value"})
        assert errors == []


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_harness_tools_not_empty(self):
        """HARNESS_TOOLS should contain tools."""
        assert len(HARNESS_TOOLS) > 0

    def test_all_tools_are_valid_schemas(self):
        """All defined tools should be valid schemas."""
        for name, schema in HARNESS_TOOLS.items():
            errors = validate_schema(schema)
            assert errors == [], f"Tool '{name}' has validation errors: {errors}"

    def test_get_tool_by_name_exists(self):
        """get_tool_by_name should return schema for existing tool."""
        schema = get_tool_by_name("run_tests")
        assert schema is not None
        assert schema.name == "run_tests"

    def test_get_tool_by_name_not_exists(self):
        """get_tool_by_name should return None for non-existing tool."""
        schema = get_tool_by_name("nonexistent_tool")
        assert schema is None

    def test_get_tools_for_coding_session(self):
        """get_tools_for_session should return coding tools."""
        tools = get_tools_for_session("coding")
        tool_names = [t.name for t in tools]
        assert "run_tests" in tool_names
        assert "mark_feature_complete" in tool_names
        assert "update_progress" in tool_names

    def test_get_tools_for_cleanup_session(self):
        """get_tools_for_session should return cleanup tools."""
        tools = get_tools_for_session("cleanup")
        tool_names = [t.name for t in tools]
        assert "run_lint" in tool_names
        assert "check_file_sizes" in tool_names
        # Cleanup should not have mark_feature_complete
        assert "mark_feature_complete" not in tool_names

    def test_get_tools_for_init_session(self):
        """get_tools_for_session should return init tools."""
        tools = get_tools_for_session("init")
        tool_names = [t.name for t in tools]
        assert "create_features_file" in tool_names
        assert "create_init_scripts" in tool_names

    def test_get_tools_for_unknown_session(self):
        """Unknown session should return basic tools."""
        tools = get_tools_for_session("unknown")
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "update_progress" in tool_names

    def test_get_tools_as_api_format(self):
        """get_tools_as_api_format should return proper format."""
        api_tools = get_tools_as_api_format("coding")
        assert isinstance(api_tools, list)
        for tool in api_tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool


class TestToolExecutionResult:
    """Tests for ToolExecutionResult."""

    def test_success_result(self):
        """Success result creation."""
        result = ToolExecutionResult(
            tool_name="test_tool",
            success=True,
            result={"data": "value"},
        )
        assert result.success is True
        assert result.error is None

    def test_error_result(self):
        """Error result creation."""
        result = ToolExecutionResult(
            tool_name="test_tool",
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_to_dict(self):
        """Convert result to dictionary."""
        result = ToolExecutionResult(
            tool_name="test_tool",
            success=True,
            result={"key": "value"},
            execution_time_ms=50.5,
            metadata={"extra": "info"},
        )
        d = result.to_dict()
        assert d["tool_name"] == "test_tool"
        assert d["success"] is True
        assert d["result"] == {"key": "value"}
        assert d["execution_time_ms"] == 50.5
        assert d["metadata"] == {"extra": "info"}


class TestToolExecutor:
    """Tests for ToolExecutor."""

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, tmp_path):
        """Executing unknown tool should fail."""
        executor = ToolExecutor(tmp_path)
        result = await executor.execute_async("unknown_tool", {})
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_without_handler(self, tmp_path):
        """Executing without handler should fail."""
        executor = ToolExecutor(tmp_path)
        result = await executor.execute_async("run_tests", {})
        assert result.success is False
        assert "No handler registered" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_handler(self, tmp_path):
        """Executing with handler should succeed."""
        executor = ToolExecutor(tmp_path)

        def handler(args):
            return ToolExecutionResult(
                tool_name="run_tests",
                success=True,
                result={"passed": True},
            )

        executor.register_handler("run_tests", handler)
        result = await executor.execute_async("run_tests", {})
        assert result.success is True
        assert result.result["passed"] is True

    @pytest.mark.asyncio
    async def test_execute_validation_failure(self, tmp_path):
        """Validation failure should prevent execution."""
        executor = ToolExecutor(tmp_path)
        executor.register_handler(
            "mark_feature_complete",
            lambda args: ToolExecutionResult(
                tool_name="mark_feature_complete",
                success=True,
            ),
        )
        # Missing required fields
        result = await executor.execute_async("mark_feature_complete", {})
        assert result.success is False
        assert "Validation errors" in result.error

    @pytest.mark.asyncio
    async def test_execute_handler_exception(self, tmp_path):
        """Handler exception should be caught."""
        executor = ToolExecutor(tmp_path)

        def bad_handler(args):
            raise ValueError("Handler crashed")

        executor.register_handler("run_tests", bad_handler)
        result = await executor.execute_async("run_tests", {})
        assert result.success is False
        assert "Execution error" in result.error
        assert "Handler crashed" in result.error

    @pytest.mark.asyncio
    async def test_execution_log(self, tmp_path):
        """Execution log should track all executions."""
        executor = ToolExecutor(tmp_path)
        await executor.execute_async("unknown1", {})
        await executor.execute_async("unknown2", {})

        log = executor.get_execution_log()
        assert len(log) == 2
        assert log[0].tool_name == "unknown1"
        assert log[1].tool_name == "unknown2"

    @pytest.mark.asyncio
    async def test_clear_execution_log(self, tmp_path):
        """Clear execution log should work."""
        executor = ToolExecutor(tmp_path)
        await executor.execute_async("unknown", {})
        assert len(executor.get_execution_log()) == 1

        executor.clear_execution_log()
        assert len(executor.get_execution_log()) == 0

    @pytest.mark.asyncio
    async def test_execution_time_measured(self, tmp_path):
        """Execution time should be measured."""
        executor = ToolExecutor(tmp_path)

        def slow_handler(args):
            import time

            time.sleep(0.01)  # 10ms
            return ToolExecutionResult(
                tool_name="run_tests",
                success=True,
            )

        executor.register_handler("run_tests", slow_handler)
        result = await executor.execute_async("run_tests", {})
        assert result.execution_time_ms >= 10


class TestValidateToolArguments:
    """Tests for validate_tool_arguments helper."""

    def test_unknown_tool(self):
        """Unknown tool should return error."""
        errors = validate_tool_arguments("unknown_tool", {})
        assert len(errors) == 1
        assert "Unknown tool" in errors[0]

    def test_valid_arguments(self):
        """Valid arguments should return no errors."""
        errors = validate_tool_arguments("run_tests", {})
        assert errors == []

    def test_invalid_arguments(self):
        """Invalid arguments should return errors."""
        errors = validate_tool_arguments(
            "mark_feature_complete",
            {"feature_id": "not an integer"},  # Should be integer
        )
        assert len(errors) > 0


class TestCreateDefaultHandlers:
    """Tests for create_default_handlers."""

    def test_creates_handlers_for_all_tools(self, tmp_path):
        """Should create handlers for all tools."""
        handlers = create_default_handlers(tmp_path)
        assert "run_tests" in handlers
        assert "run_lint" in handlers
        assert "update_progress" in handlers
        assert "mark_feature_complete" in handlers
        assert "create_checkpoint" in handlers

    def test_handlers_return_success(self, tmp_path):
        """Default handlers should return success."""
        handlers = create_default_handlers(tmp_path)

        result = handlers["run_tests"]({"verbose": True})
        assert result.success is True

        result = handlers["update_progress"](
            {"what_done": ["task1"], "current_state": "in progress"}
        )
        assert result.success is True

    def test_mark_feature_complete_handler(self, tmp_path):
        """mark_feature_complete handler should work."""
        handlers = create_default_handlers(tmp_path)
        result = handlers["mark_feature_complete"](
            {"feature_id": 1, "evidence": "Tests pass"}
        )
        assert result.success is True
        assert "1" in result.result["message"]

    def test_create_features_file_handler(self, tmp_path):
        """create_features_file handler should work."""
        handlers = create_default_handlers(tmp_path)
        result = handlers["create_features_file"](
            {
                "project_name": "test",
                "features": [{"id": 1}],
                "init_mode": "new",
            }
        )
        assert result.success is True
        assert result.metadata["feature_count"] == 1
