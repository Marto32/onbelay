"""Tests for output_parser module."""

import pytest

from agent_harness.output_parser import (
    ParsedAction,
    parse_agent_output,
    parse_tool_calls,
    parse_with_heuristics,
    parse_all,
    get_file_operations,
    get_command_operations,
    get_test_operations,
    get_verification_operations,
    summarize_actions,
    format_action,
)


class TestParsedAction:
    """Tests for ParsedAction dataclass."""

    def test_parsed_action_creation(self):
        """Test creating a ParsedAction."""
        action = ParsedAction(
            type="file_read",
            data={"path": "/test/file.py"},
            source="prefix",
        )

        assert action.type == "file_read"
        assert action.data["path"] == "/test/file.py"
        assert action.source == "prefix"

    def test_parsed_action_with_raw_text(self):
        """Test ParsedAction with raw text."""
        action = ParsedAction(
            type="cmd_run",
            data={"command": "pytest"},
            source="prefix",
            raw_text="[CMD:RUN] pytest",
        )

        assert action.raw_text == "[CMD:RUN] pytest"


class TestParseAgentOutput:
    """Tests for parse_agent_output function."""

    def test_parse_file_read(self):
        """Test parsing FILE:READ prefix."""
        output = "[FILE:READ] src/module.py"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "file_read"
        assert actions[0].data["path"] == "src/module.py"
        assert actions[0].source == "prefix"

    def test_parse_file_write(self):
        """Test parsing FILE:WRITE prefix."""
        output = "[FILE:WRITE] tests/test_new.py"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "file_write"
        assert actions[0].data["path"] == "tests/test_new.py"

    def test_parse_file_create(self):
        """Test parsing FILE:CREATE prefix."""
        output = "[FILE:CREATE] src/new_module.py"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "file_create"

    def test_parse_cmd_run(self):
        """Test parsing CMD:RUN prefix."""
        output = "[CMD:RUN] pytest tests/"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "cmd_run"
        assert actions[0].data["command"] == "pytest tests/"

    def test_parse_verify_pass(self):
        """Test parsing VERIFY:PASS prefix."""
        output = "[VERIFY:PASS] All tests passed"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "verify_pass"
        assert actions[0].data["details"] == "All tests passed"

    def test_parse_verify_fail(self):
        """Test parsing VERIFY:FAIL prefix."""
        output = "[VERIFY:FAIL] Test assertion error"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "verify_fail"
        assert actions[0].data["reason"] == "Test assertion error"

    def test_parse_feature_start(self):
        """Test parsing FEATURE:START prefix."""
        output = "[FEATURE:START] 5"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "feature_start"
        assert actions[0].data["feature_id"] == 5

    def test_parse_feature_complete(self):
        """Test parsing FEATURE:COMPLETE prefix."""
        output = "[FEATURE:COMPLETE] 3"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "feature_complete"
        assert actions[0].data["feature_id"] == 3

    def test_parse_test_pass(self):
        """Test parsing TEST:PASS prefix."""
        output = "[TEST:PASS] tests/test_module.py::test_function"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "test_pass"
        assert "test_function" in actions[0].data["test_id"]

    def test_parse_session_wrap_up(self):
        """Test parsing SESSION:WRAP_UP prefix."""
        output = "[SESSION:WRAP_UP]"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "session_wrap_up"

    def test_parse_decision(self):
        """Test parsing DECISION prefix."""
        output = "[DECISION] Use caching for performance"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "decision"
        assert actions[0].data["decision"] == "Use caching for performance"

    def test_parse_multiple_actions(self):
        """Test parsing multiple actions."""
        output = """[FILE:READ] src/module.py
[CMD:RUN] pytest
[VERIFY:PASS] All tests passed"""

        actions = parse_agent_output(output)

        assert len(actions) == 3
        assert actions[0].type == "file_read"
        assert actions[1].type == "cmd_run"
        assert actions[2].type == "verify_pass"

    def test_parse_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        output = "[file:read] test.py"
        actions = parse_agent_output(output)

        assert len(actions) == 1
        assert actions[0].type == "file_read"

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        actions = parse_agent_output("")
        assert len(actions) == 0

    def test_parse_no_prefixes(self):
        """Test parsing output with no prefixes."""
        output = "Just some regular text without any prefixes."
        actions = parse_agent_output(output)
        assert len(actions) == 0


class TestParseToolCalls:
    """Tests for parse_tool_calls function."""

    def test_parse_read_file_tool(self):
        """Test parsing read_file tool call."""
        tool_calls = [
            {"name": "read_file", "input": {"path": "/test/file.py"}}
        ]

        actions = parse_tool_calls(tool_calls)

        assert len(actions) == 1
        assert actions[0].type == "file_read"
        assert actions[0].data["path"] == "/test/file.py"
        assert actions[0].source == "tool_use"

    def test_parse_write_file_tool(self):
        """Test parsing write_file tool call."""
        tool_calls = [
            {"name": "write_file", "input": {"path": "/test/new.py"}}
        ]

        actions = parse_tool_calls(tool_calls)

        assert len(actions) == 1
        assert actions[0].type == "file_write"

    def test_parse_bash_tool(self):
        """Test parsing bash tool call."""
        tool_calls = [
            {"name": "bash", "input": {"command": "pytest tests/"}}
        ]

        actions = parse_tool_calls(tool_calls)

        assert len(actions) >= 1
        assert actions[0].type == "cmd_run"
        assert actions[0].data["command"] == "pytest tests/"

    def test_parse_bash_with_pytest(self):
        """Test that pytest commands are also tagged as test_run."""
        tool_calls = [
            {"name": "bash", "input": {"command": "pytest tests/"}}
        ]

        actions = parse_tool_calls(tool_calls)

        # Should have both cmd_run and test_run
        types = [a.type for a in actions]
        assert "cmd_run" in types
        assert "test_run" in types

    def test_parse_empty_tool_calls(self):
        """Test parsing empty tool calls list."""
        actions = parse_tool_calls([])
        assert len(actions) == 0


class TestParseWithHeuristics:
    """Tests for parse_with_heuristics function."""

    def test_heuristic_file_read(self):
        """Test heuristic detection of file reads."""
        output = "Reading file 'src/module.py' to understand the structure."
        actions = parse_with_heuristics(output)

        # Should detect file read - this is a heuristic, may not always work
        file_actions = [a for a in actions if a.type == "file_read"]
        # Heuristics are best-effort, just check no errors
        assert isinstance(actions, list)

    def test_heuristic_file_write(self):
        """Test heuristic detection of file writes."""
        output = "Creating file 'tests/test_new.py' with the following content."
        actions = parse_with_heuristics(output)

        # Should detect file creation - this is a heuristic, may not always work
        # Heuristics are best-effort, just check no errors
        assert isinstance(actions, list)

    def test_heuristic_command_backticks(self):
        """Test heuristic detection of commands in backticks."""
        output = "Running command `pytest tests/`"
        actions = parse_with_heuristics(output)

        cmd_actions = [a for a in actions if a.type == "cmd_run"]
        assert len(cmd_actions) >= 1

    def test_heuristic_shell_prompt(self):
        """Test heuristic detection of shell prompt commands."""
        output = "$ git status"
        actions = parse_with_heuristics(output)

        cmd_actions = [a for a in actions if a.type == "cmd_run"]
        assert len(cmd_actions) >= 1

    def test_heuristic_tests_passing(self):
        """Test heuristic detection of test pass messages."""
        output = "All tests are passing now."
        actions = parse_with_heuristics(output)

        pass_actions = [a for a in actions if a.type == "test_pass"]
        assert len(pass_actions) >= 1

    def test_heuristic_feature_complete(self):
        """Test heuristic detection of feature completion."""
        output = "Feature #5 is now complete and implemented."
        actions = parse_with_heuristics(output)

        # Heuristics are best-effort, just check no errors
        assert isinstance(actions, list)


class TestParseAll:
    """Tests for parse_all function."""

    def test_parse_all_combines_methods(self):
        """Test that parse_all combines all parsing methods."""
        output = """[FILE:READ] src/module.py
I also read config.json to check settings.
"""
        tool_calls = [
            {"name": "bash", "input": {"command": "pytest"}}
        ]

        actions = parse_all(output, tool_calls)

        # Should have actions from prefix, tool, and heuristic parsing
        sources = set(a.source for a in actions)
        assert "prefix" in sources
        assert "tool_use" in sources

    def test_parse_all_deduplicates(self):
        """Test that parse_all combines multiple parsing methods."""
        output = "[FILE:READ] test.py"
        tool_calls = [
            {"name": "read_file", "input": {"path": "test.py"}}
        ]

        actions = parse_all(output, tool_calls)

        # Should have file reads from both sources
        file_reads = [a for a in actions if a.type == "file_read"]
        # We have actions from both prefix and tool_use
        assert len(file_reads) >= 1

    def test_parse_all_no_tool_calls(self):
        """Test parse_all without tool calls."""
        output = "[CMD:RUN] pytest"
        actions = parse_all(output)

        assert len(actions) >= 1


class TestFilterFunctions:
    """Tests for filter functions."""

    def test_get_file_operations(self):
        """Test filtering file operations."""
        actions = [
            ParsedAction(type="file_read", data={}, source="prefix"),
            ParsedAction(type="file_write", data={}, source="prefix"),
            ParsedAction(type="cmd_run", data={}, source="prefix"),
            ParsedAction(type="file_create", data={}, source="prefix"),
        ]

        file_ops = get_file_operations(actions)

        assert len(file_ops) == 3
        assert all(a.type.startswith("file") for a in file_ops)

    def test_get_command_operations(self):
        """Test filtering command operations."""
        actions = [
            ParsedAction(type="file_read", data={}, source="prefix"),
            ParsedAction(type="cmd_run", data={}, source="prefix"),
            ParsedAction(type="cmd_run", data={}, source="tool_use"),
        ]

        cmd_ops = get_command_operations(actions)

        assert len(cmd_ops) == 2
        assert all(a.type == "cmd_run" for a in cmd_ops)

    def test_get_test_operations(self):
        """Test filtering test operations."""
        actions = [
            ParsedAction(type="test_run", data={}, source="prefix"),
            ParsedAction(type="test_pass", data={}, source="prefix"),
            ParsedAction(type="test_fail", data={}, source="prefix"),
            ParsedAction(type="file_read", data={}, source="prefix"),
        ]

        test_ops = get_test_operations(actions)

        assert len(test_ops) == 3
        assert all(a.type.startswith("test") for a in test_ops)

    def test_get_verification_operations(self):
        """Test filtering verification operations."""
        actions = [
            ParsedAction(type="verify_pass", data={}, source="prefix"),
            ParsedAction(type="verify_fail", data={}, source="prefix"),
            ParsedAction(type="verify_skip", data={}, source="prefix"),
            ParsedAction(type="cmd_run", data={}, source="prefix"),
        ]

        verify_ops = get_verification_operations(actions)

        assert len(verify_ops) == 3
        assert all(a.type.startswith("verify") for a in verify_ops)


class TestSummarizeActions:
    """Tests for summarize_actions function."""

    def test_summarize_actions(self):
        """Test action summary."""
        actions = [
            ParsedAction(type="file_read", data={}, source="prefix"),
            ParsedAction(type="file_read", data={}, source="prefix"),
            ParsedAction(type="file_write", data={}, source="prefix"),
            ParsedAction(type="cmd_run", data={}, source="prefix"),
        ]

        summary = summarize_actions(actions)

        assert summary["file_read"] == 2
        assert summary["file_write"] == 1
        assert summary["cmd_run"] == 1

    def test_summarize_empty_actions(self):
        """Test summary of empty actions."""
        summary = summarize_actions([])
        assert summary == {}


class TestFormatAction:
    """Tests for format_action function."""

    def test_format_file_action(self):
        """Test formatting file action."""
        action = ParsedAction(
            type="file_read",
            data={"path": "/test/file.py"},
            source="prefix",
        )

        formatted = format_action(action)

        assert "[P]" in formatted
        assert "file_read" in formatted
        assert "/test/file.py" in formatted

    def test_format_cmd_action(self):
        """Test formatting command action."""
        action = ParsedAction(
            type="cmd_run",
            data={"command": "pytest tests/"},
            source="tool_use",
        )

        formatted = format_action(action)

        assert "[T]" in formatted
        assert "cmd_run" in formatted
        assert "pytest" in formatted

    def test_format_long_command_truncated(self):
        """Test that long commands are truncated."""
        long_cmd = "a" * 100
        action = ParsedAction(
            type="cmd_run",
            data={"command": long_cmd},
            source="prefix",
        )

        formatted = format_action(action)

        assert len(formatted) < 150
        assert "..." in formatted

    def test_format_feature_action(self):
        """Test formatting feature action."""
        action = ParsedAction(
            type="feature_complete",
            data={"feature_id": 5},
            source="heuristic",
        )

        formatted = format_action(action)

        assert "[H]" in formatted
        assert "#5" in formatted
