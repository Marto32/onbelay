"""Lint runner for agent-harness.

Executes linting tools and parses results.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LintIssue:
    """A single lint issue."""

    file: str
    line: int
    column: int
    code: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class LintResult:
    """Result of a lint run."""

    exit_code: int
    errors: int = 0
    warnings: int = 0
    issues: list[LintIssue] = field(default_factory=list)
    raw_output: str = ""
    tool: str = "ruff"

    @property
    def clean(self) -> bool:
        """Check if there are no lint issues."""
        return self.errors == 0 and self.warnings == 0

    @property
    def total_issues(self) -> int:
        """Total number of issues."""
        return self.errors + self.warnings


def run_lint(
    project_dir: Path,
    command: Optional[str] = None,
    timeout: int = 120,
) -> LintResult:
    """
    Run linting and return results.

    Args:
        project_dir: Path to the project directory.
        command: Lint command to run (default: "poetry run ruff check src/").
        timeout: Timeout in seconds (default 120).

    Returns:
        LintResult with issues found.
    """
    if command is None:
        command = "poetry run ruff check src/"

    # Parse command into parts
    cmd_parts = command.split()

    try:
        result = subprocess.run(
            cmd_parts,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        raw_output = result.stdout + result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        return LintResult(
            exit_code=-1,
            raw_output="Lint run timed out",
        )
    except FileNotFoundError:
        return LintResult(
            exit_code=-1,
            raw_output=f"Command not found: {cmd_parts[0]}",
        )

    # Detect tool and parse accordingly
    tool = _detect_tool(command)

    if tool == "ruff":
        return _parse_ruff_output(raw_output, exit_code)
    elif tool == "flake8":
        return _parse_flake8_output(raw_output, exit_code)
    elif tool == "pylint":
        return _parse_pylint_output(raw_output, exit_code)
    else:
        return _parse_generic_output(raw_output, exit_code, tool)


def _detect_tool(command: str) -> str:
    """Detect which lint tool is being used."""
    command_lower = command.lower()

    if "ruff" in command_lower:
        return "ruff"
    elif "flake8" in command_lower:
        return "flake8"
    elif "pylint" in command_lower:
        return "pylint"
    elif "mypy" in command_lower:
        return "mypy"
    else:
        return "unknown"


def _parse_ruff_output(output: str, exit_code: int) -> LintResult:
    """Parse ruff output."""
    issues = []
    errors = 0
    warnings = 0

    # Ruff format: file:line:col: CODE message
    pattern = re.compile(
        r"^(.+?):(\d+):(\d+):\s+([A-Z]+\d+)\s+(.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(output):
        file_path = match.group(1)
        line = int(match.group(2))
        column = int(match.group(3))
        code = match.group(4)
        message = match.group(5)

        # Determine severity from code
        # E = error, W = warning, F = critical
        severity = "error"
        if code.startswith("W"):
            severity = "warning"
            warnings += 1
        else:
            errors += 1

        issues.append(LintIssue(
            file=file_path,
            line=line,
            column=column,
            code=code,
            message=message,
            severity=severity,
        ))

    return LintResult(
        exit_code=exit_code,
        errors=errors,
        warnings=warnings,
        issues=issues,
        raw_output=output,
        tool="ruff",
    )


def _parse_flake8_output(output: str, exit_code: int) -> LintResult:
    """Parse flake8 output."""
    issues = []
    errors = 0
    warnings = 0

    # Flake8 format: file:line:col: CODE message
    pattern = re.compile(
        r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(output):
        file_path = match.group(1)
        line = int(match.group(2))
        column = int(match.group(3))
        code = match.group(4)
        message = match.group(5)

        severity = "warning" if code.startswith("W") else "error"
        if severity == "warning":
            warnings += 1
        else:
            errors += 1

        issues.append(LintIssue(
            file=file_path,
            line=line,
            column=column,
            code=code,
            message=message,
            severity=severity,
        ))

    return LintResult(
        exit_code=exit_code,
        errors=errors,
        warnings=warnings,
        issues=issues,
        raw_output=output,
        tool="flake8",
    )


def _parse_pylint_output(output: str, exit_code: int) -> LintResult:
    """Parse pylint output."""
    issues = []
    errors = 0
    warnings = 0

    # Pylint format: file:line:col: CODE: msg-symbol: message
    pattern = re.compile(
        r"^(.+?):(\d+):(\d+):\s+([CRWEF]\d+):\s+([\w-]+):\s+(.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(output):
        file_path = match.group(1)
        line = int(match.group(2))
        column = int(match.group(3))
        code = match.group(4)
        message = f"{match.group(5)}: {match.group(6)}"

        # C = convention, R = refactor, W = warning, E = error, F = fatal
        severity = "warning" if code.startswith(("C", "R", "W")) else "error"
        if severity == "warning":
            warnings += 1
        else:
            errors += 1

        issues.append(LintIssue(
            file=file_path,
            line=line,
            column=column,
            code=code,
            message=message,
            severity=severity,
        ))

    return LintResult(
        exit_code=exit_code,
        errors=errors,
        warnings=warnings,
        issues=issues,
        raw_output=output,
        tool="pylint",
    )


def _parse_generic_output(
    output: str,
    exit_code: int,
    tool: str,
) -> LintResult:
    """Parse output from unknown lint tools."""
    # Try to find any file:line:col patterns
    issues = []
    errors = 0

    pattern = re.compile(
        r"^(.+?):(\d+):?(\d+)?:?\s+(.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(output):
        file_path = match.group(1)
        line = int(match.group(2))
        column = int(match.group(3)) if match.group(3) else 0
        message = match.group(4)

        errors += 1
        issues.append(LintIssue(
            file=file_path,
            line=line,
            column=column,
            code="",
            message=message,
            severity="error",
        ))

    return LintResult(
        exit_code=exit_code,
        errors=errors,
        warnings=0,
        issues=issues,
        raw_output=output,
        tool=tool,
    )


def run_ruff_fix(
    project_dir: Path,
    path: str = "src/",
    timeout: int = 120,
) -> LintResult:
    """
    Run ruff with auto-fix enabled.

    Args:
        project_dir: Path to the project directory.
        path: Path to lint and fix.
        timeout: Timeout in seconds.

    Returns:
        LintResult after fix attempt.
    """
    command = f"poetry run ruff check --fix {path}"
    return run_lint(project_dir, command, timeout)


def get_issues_for_file(
    result: LintResult,
    file_path: str,
) -> list[LintIssue]:
    """
    Get lint issues for a specific file.

    Args:
        result: LintResult to filter.
        file_path: File path to filter by.

    Returns:
        List of issues for the file.
    """
    return [issue for issue in result.issues if issue.file == file_path]


def get_issues_by_code(
    result: LintResult,
    code: str,
) -> list[LintIssue]:
    """
    Get lint issues with a specific code.

    Args:
        result: LintResult to filter.
        code: Issue code to filter by.

    Returns:
        List of issues with that code.
    """
    return [issue for issue in result.issues if issue.code == code]


def format_lint_summary(result: LintResult) -> str:
    """
    Format a lint result summary for display.

    Args:
        result: LintResult to format.

    Returns:
        Formatted summary string.
    """
    lines = []
    lines.append(f"Lint Results ({result.tool})")

    if result.clean:
        lines.append("  Status: CLEAN - No issues found")
    else:
        lines.append(f"  Errors:   {result.errors}")
        lines.append(f"  Warnings: {result.warnings}")
        lines.append("  Status: ISSUES FOUND")

        # Group by file
        files_with_issues = set(issue.file for issue in result.issues)
        lines.append(f"  Files affected: {len(files_with_issues)}")

        # Show first few issues
        for issue in result.issues[:5]:
            lines.append(f"    {issue.file}:{issue.line}: {issue.code} {issue.message}")

        if len(result.issues) > 5:
            lines.append(f"    ... and {len(result.issues) - 5} more issues")

    return "\n".join(lines)


def get_error_codes_summary(result: LintResult) -> dict[str, int]:
    """
    Get a summary of error codes.

    Args:
        result: LintResult to summarize.

    Returns:
        Dictionary mapping codes to counts.
    """
    counts: dict[str, int] = {}
    for issue in result.issues:
        code = issue.code or "unknown"
        counts[code] = counts.get(code, 0) + 1
    return counts
