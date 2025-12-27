"""Test runner for agent-harness.

Executes pytest and parses results.
"""

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TestResult:
    """Result for a single test."""

    test_id: str  # file::test_name format
    status: str  # "passed", "failed", "error", "skipped"
    duration: float = 0.0
    error_message: Optional[str] = None


@dataclass
class TestRunResult:
    """Result of a test run."""

    exit_code: int
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    total: int = 0
    duration: float = 0.0
    raw_output: str = ""
    results: list[TestResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        """Check if all tests passed."""
        return len(self.failed) == 0 and len(self.errors) == 0

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        if self.total == 0:
            return 0.0
        return len(self.passed) / self.total


def run_tests(
    project_dir: Path,
    test_path: Optional[str] = None,
    timeout: int = 300,
    extra_args: Optional[list[str]] = None,
    use_json_report: bool = True,
) -> TestRunResult:
    """
    Run pytest and return structured results.

    Args:
        project_dir: Path to the project directory.
        test_path: Specific test file or directory (optional).
        timeout: Timeout in seconds (default 300).
        extra_args: Additional pytest arguments (optional).
        use_json_report: Use JSON report for parsing (default True).

    Returns:
        TestRunResult with test outcomes.
    """
    # Build command
    cmd = ["poetry", "run", "pytest"]

    if test_path:
        cmd.append(test_path)

    # Add standard args
    cmd.extend(["-v", "--tb=short"])

    # Add JSON report if enabled
    json_report_path = None
    if use_json_report:
        json_report_path = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ).name
        cmd.extend(["--json-report", f"--json-report-file={json_report_path}"])

    if extra_args:
        cmd.extend(extra_args)

    # Run pytest
    try:
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        raw_output = result.stdout + result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        return TestRunResult(
            exit_code=-1,
            raw_output="Test run timed out",
            total=0,
        )
    except FileNotFoundError:
        # Try without poetry
        cmd[0:2] = ["pytest"]
        try:
            result = subprocess.run(
                cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            raw_output = result.stdout + result.stderr
            exit_code = result.returncode
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return TestRunResult(
                exit_code=-1,
                raw_output="Failed to run pytest",
                total=0,
            )

    # Parse results
    if use_json_report and json_report_path:
        try:
            return _parse_json_report(json_report_path, exit_code, raw_output)
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Fall back to parsing output

    return _parse_pytest_output(raw_output, exit_code)


def run_single_test(
    project_dir: Path,
    test_id: str,
    timeout: int = 60,
) -> TestResult:
    """
    Run a single test and return the result.

    Args:
        project_dir: Path to the project directory.
        test_id: Test identifier (file::test_name format).
        timeout: Timeout in seconds.

    Returns:
        TestResult for the test.
    """
    result = run_tests(
        project_dir,
        test_path=test_id,
        timeout=timeout,
        use_json_report=False,
    )

    if result.passed and test_id in result.passed:
        return TestResult(test_id=test_id, status="passed", duration=result.duration)
    elif result.failed and test_id in result.failed:
        return TestResult(test_id=test_id, status="failed", error_message=result.raw_output)
    elif result.errors:
        return TestResult(test_id=test_id, status="error", error_message=result.raw_output)
    else:
        return TestResult(test_id=test_id, status="unknown", error_message=result.raw_output)


def _parse_json_report(
    report_path: str,
    exit_code: int,
    raw_output: str,
) -> TestRunResult:
    """Parse pytest JSON report."""
    with open(report_path) as f:
        report = json.load(f)

    passed = []
    failed = []
    errors = []
    skipped = []
    results = []
    duration = report.get("duration", 0.0)

    for test in report.get("tests", []):
        test_id = test.get("nodeid", "")
        outcome = test.get("outcome", "")
        test_duration = test.get("call", {}).get("duration", 0.0)

        result = TestResult(
            test_id=test_id,
            status=outcome,
            duration=test_duration,
        )

        if outcome == "passed":
            passed.append(test_id)
        elif outcome == "failed":
            failed.append(test_id)
            result.error_message = test.get("call", {}).get("longrepr", "")
        elif outcome == "error":
            errors.append(test_id)
            result.error_message = test.get("call", {}).get("longrepr", "")
        elif outcome == "skipped":
            skipped.append(test_id)

        results.append(result)

    return TestRunResult(
        exit_code=exit_code,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        total=len(results),
        duration=duration,
        raw_output=raw_output,
        results=results,
    )


def _parse_pytest_output(output: str, exit_code: int) -> TestRunResult:
    """Parse pytest output to extract test results."""
    passed = []
    failed = []
    errors = []
    skipped = []
    duration = 0.0

    # Parse individual test lines
    # Pattern: tests/test_file.py::test_name PASSED/FAILED/SKIPPED
    test_pattern = re.compile(
        r"^([\w/\.\[\]-]+::\w+(?:\[[\w\-]+\])?)\s+(PASSED|FAILED|ERROR|SKIPPED)",
        re.MULTILINE,
    )

    for match in test_pattern.finditer(output):
        test_id = match.group(1)
        status = match.group(2)

        if status == "PASSED":
            passed.append(test_id)
        elif status == "FAILED":
            failed.append(test_id)
        elif status == "ERROR":
            errors.append(test_id)
        elif status == "SKIPPED":
            skipped.append(test_id)

    # Parse summary line
    # Pattern: === X passed, Y failed in Z.ZZs ===
    summary_pattern = re.compile(
        r"=+ (?:(\d+) passed)?(?:,\s*)?(?:(\d+) failed)?(?:,\s*)?(?:(\d+) error)?(?:,\s*)?(?:(\d+) skipped)?.* in ([\d.]+)s",
        re.IGNORECASE,
    )

    summary_match = summary_pattern.search(output)
    if summary_match:
        duration = float(summary_match.group(5)) if summary_match.group(5) else 0.0

    # If no individual tests found, try to get counts from summary
    if not passed and not failed and not errors and summary_match:
        # Just use counts from summary for total
        pass

    total = len(passed) + len(failed) + len(errors) + len(skipped)

    return TestRunResult(
        exit_code=exit_code,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        total=total,
        duration=duration,
        raw_output=output,
    )


def get_test_files(project_dir: Path, test_dir: str = "tests") -> list[str]:
    """
    Get list of test files in a directory.

    Args:
        project_dir: Path to the project directory.
        test_dir: Test directory name (default "tests").

    Returns:
        List of test file paths relative to project_dir.
    """
    test_path = project_dir / test_dir
    if not test_path.exists():
        return []

    test_files = []
    for file in test_path.rglob("test_*.py"):
        test_files.append(str(file.relative_to(project_dir)))
    for file in test_path.rglob("*_test.py"):
        test_files.append(str(file.relative_to(project_dir)))

    return sorted(set(test_files))


def discover_tests(
    project_dir: Path,
    test_path: Optional[str] = None,
) -> list[str]:
    """
    Discover all test IDs in a test file or directory.

    Args:
        project_dir: Path to the project directory.
        test_path: Specific test file or directory (optional).

    Returns:
        List of test IDs.
    """
    cmd = ["poetry", "run", "pytest", "--collect-only", "-q"]
    if test_path:
        cmd.append(test_path)

    try:
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )

        test_ids = []
        for line in result.stdout.split("\n"):
            line = line.strip()
            if "::" in line and not line.startswith("<"):
                test_ids.append(line)

        return test_ids
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def format_test_summary(result: TestRunResult) -> str:
    """
    Format a test result summary for display.

    Args:
        result: TestRunResult to format.

    Returns:
        Formatted summary string.
    """
    lines = []
    lines.append(f"Test Results: {result.total} tests in {result.duration:.2f}s")

    if result.passed:
        lines.append(f"  Passed:  {len(result.passed)}")
    if result.failed:
        lines.append(f"  Failed:  {len(result.failed)}")
    if result.errors:
        lines.append(f"  Errors:  {len(result.errors)}")
    if result.skipped:
        lines.append(f"  Skipped: {len(result.skipped)}")

    if result.all_passed:
        lines.append("  Status: ALL TESTS PASSED")
    else:
        lines.append("  Status: SOME TESTS FAILED")
        for test_id in result.failed[:5]:
            lines.append(f"    - {test_id}")
        if len(result.failed) > 5:
            lines.append(f"    ... and {len(result.failed) - 5} more")

    return "\n".join(lines)


def run_test_file(
    project_dir: Path,
    test_file: str,
    timeout: int = 300,
) -> TestRunResult:
    """
    Run all tests in a specific file.

    Convenience wrapper for run_tests.

    Args:
        project_dir: Path to the project directory.
        test_file: Path to test file.
        timeout: Timeout in seconds.

    Returns:
        TestRunResult for the file.
    """
    return run_tests(project_dir, test_path=test_file, timeout=timeout)
