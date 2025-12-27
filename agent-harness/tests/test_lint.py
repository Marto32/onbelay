"""Tests for lint.py - Lint runner."""

import pytest
from pathlib import Path

from agent_harness.lint import (
    LintIssue,
    LintResult,
    run_lint,
    run_ruff_fix,
    get_issues_for_file,
    get_issues_by_code,
    format_lint_summary,
    get_error_codes_summary,
    _parse_ruff_output,
    _parse_flake8_output,
    _parse_pylint_output,
    _detect_tool,
)


class TestLintIssue:
    """Tests for LintIssue dataclass."""

    def test_create_issue(self):
        """Test creating a lint issue."""
        issue = LintIssue(
            file="src/main.py",
            line=10,
            column=5,
            code="E501",
            message="Line too long",
            severity="error",
        )
        assert issue.file == "src/main.py"
        assert issue.line == 10
        assert issue.code == "E501"


class TestLintResult:
    """Tests for LintResult dataclass."""

    def test_clean_result(self):
        """Test clean lint result."""
        result = LintResult(exit_code=0, errors=0, warnings=0)
        assert result.clean is True
        assert result.total_issues == 0

    def test_result_with_issues(self):
        """Test lint result with issues."""
        result = LintResult(exit_code=1, errors=5, warnings=3)
        assert result.clean is False
        assert result.total_issues == 8


class TestDetectTool:
    """Tests for tool detection."""

    def test_detect_ruff(self):
        """Test detecting ruff."""
        assert _detect_tool("poetry run ruff check src/") == "ruff"
        assert _detect_tool("ruff check .") == "ruff"

    def test_detect_flake8(self):
        """Test detecting flake8."""
        assert _detect_tool("flake8 src/") == "flake8"
        assert _detect_tool("poetry run flake8") == "flake8"

    def test_detect_pylint(self):
        """Test detecting pylint."""
        assert _detect_tool("pylint src/") == "pylint"

    def test_detect_unknown(self):
        """Test detecting unknown tool."""
        assert _detect_tool("custom_linter src/") == "unknown"


class TestParseRuffOutput:
    """Tests for parsing ruff output."""

    def test_parse_ruff_clean(self):
        """Test parsing clean ruff output."""
        output = ""
        result = _parse_ruff_output(output, exit_code=0)

        assert result.clean is True
        assert result.tool == "ruff"

    def test_parse_ruff_with_errors(self):
        """Test parsing ruff output with errors."""
        output = """
src/main.py:10:5: E501 Line too long (120 > 100)
src/main.py:15:1: F401 'os' imported but unused
src/utils.py:5:10: W291 trailing whitespace
"""
        result = _parse_ruff_output(output, exit_code=1)

        assert len(result.issues) == 3
        assert result.errors == 2  # E501 and F401
        assert result.warnings == 1  # W291

        # Check specific issue
        e501 = next(i for i in result.issues if i.code == "E501")
        assert e501.file == "src/main.py"
        assert e501.line == 10
        assert e501.column == 5
        assert "too long" in e501.message

    def test_parse_ruff_multiline(self):
        """Test parsing ruff output with multiple files."""
        output = """
src/module1.py:1:1: F401 'unused' imported but unused
src/module2.py:5:1: E302 expected 2 blank lines, found 1
"""
        result = _parse_ruff_output(output, exit_code=1)

        assert len(result.issues) == 2
        files = {i.file for i in result.issues}
        assert "src/module1.py" in files
        assert "src/module2.py" in files


class TestParseFlake8Output:
    """Tests for parsing flake8 output."""

    def test_parse_flake8_with_errors(self):
        """Test parsing flake8 output."""
        output = """
src/main.py:10:5: E501 line too long (120 > 100 characters)
src/main.py:15:1: W503 line break before binary operator
"""
        result = _parse_flake8_output(output, exit_code=1)

        assert len(result.issues) == 2
        assert result.errors == 1  # E501
        assert result.warnings == 1  # W503


class TestParsePylintOutput:
    """Tests for parsing pylint output."""

    def test_parse_pylint_with_errors(self):
        """Test parsing pylint output."""
        output = """
src/main.py:10:0: C0111: missing-docstring: Missing module docstring
src/main.py:15:4: E1101: no-member: Instance has no 'foo' member
"""
        result = _parse_pylint_output(output, exit_code=1)

        assert len(result.issues) == 2
        assert result.warnings == 1  # C0111 (convention)
        assert result.errors == 1  # E1101 (error)


class TestGetIssuesForFile:
    """Tests for filtering issues by file."""

    def test_get_issues_for_file(self):
        """Test filtering issues by file."""
        result = LintResult(
            exit_code=1,
            issues=[
                LintIssue("src/a.py", 1, 1, "E001", "Error 1", "error"),
                LintIssue("src/a.py", 2, 1, "E002", "Error 2", "error"),
                LintIssue("src/b.py", 1, 1, "E003", "Error 3", "error"),
            ],
        )

        issues = get_issues_for_file(result, "src/a.py")

        assert len(issues) == 2
        assert all(i.file == "src/a.py" for i in issues)


class TestGetIssuesByCode:
    """Tests for filtering issues by code."""

    def test_get_issues_by_code(self):
        """Test filtering issues by code."""
        result = LintResult(
            exit_code=1,
            issues=[
                LintIssue("src/a.py", 1, 1, "E501", "Line too long", "error"),
                LintIssue("src/b.py", 2, 1, "E501", "Line too long", "error"),
                LintIssue("src/c.py", 1, 1, "E302", "Blank lines", "error"),
            ],
        )

        issues = get_issues_by_code(result, "E501")

        assert len(issues) == 2
        assert all(i.code == "E501" for i in issues)


class TestFormatLintSummary:
    """Tests for format_lint_summary function."""

    def test_format_clean_summary(self):
        """Test formatting clean summary."""
        result = LintResult(exit_code=0, errors=0, warnings=0, tool="ruff")

        summary = format_lint_summary(result)

        assert "ruff" in summary
        assert "CLEAN" in summary

    def test_format_summary_with_issues(self):
        """Test formatting summary with issues."""
        result = LintResult(
            exit_code=1,
            errors=5,
            warnings=3,
            issues=[
                LintIssue("src/a.py", 1, 1, "E501", "Line too long", "error"),
                LintIssue("src/b.py", 2, 1, "E302", "Blank lines", "error"),
            ],
            tool="ruff",
        )

        summary = format_lint_summary(result)

        assert "Errors:   5" in summary
        assert "Warnings: 3" in summary
        assert "ISSUES FOUND" in summary
        assert "E501" in summary


class TestGetErrorCodesSummary:
    """Tests for get_error_codes_summary function."""

    def test_get_error_codes_summary(self):
        """Test getting error codes summary."""
        result = LintResult(
            exit_code=1,
            issues=[
                LintIssue("a.py", 1, 1, "E501", "Line too long", "error"),
                LintIssue("b.py", 1, 1, "E501", "Line too long", "error"),
                LintIssue("c.py", 1, 1, "E501", "Line too long", "error"),
                LintIssue("d.py", 1, 1, "E302", "Blank lines", "error"),
            ],
        )

        summary = get_error_codes_summary(result)

        assert summary["E501"] == 3
        assert summary["E302"] == 1


class TestRunLint:
    """Integration tests for run_lint function."""

    def test_run_lint_on_clean_code(self, tmp_path):
        """Test running lint on clean code."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "clean.py").write_text('"""Clean module."""\n\n\ndef hello():\n    """Say hello."""\n    return "hello"\n')

        # Just verify it runs without crashing
        result = run_lint(tmp_path, command="ruff check src/")
        assert isinstance(result, LintResult)
