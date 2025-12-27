"""Test baseline tracking for agent-harness.

Tracks which tests were passing before each session to detect regressions.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_harness.exceptions import StateError


@dataclass
class TestBaseline:
    """Test baseline for a session.

    Stores the state of tests at the start of a session so we can detect
    regressions introduced during the session.
    """

    session: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    passing_tests: list[str] = field(default_factory=list)
    total_passing: int = 0
    total_tests: int = 0
    pre_existing_failures: list[str] = field(default_factory=list)  # For adopt mode

    def __post_init__(self):
        """Update counts based on lists."""
        if self.total_passing == 0 and self.passing_tests:
            self.total_passing = len(self.passing_tests)


@dataclass
class TestResults:
    """Results from a test run.

    Used as input to create a baseline from pytest output.
    """

    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of tests."""
        return len(self.passed) + len(self.failed) + len(self.errors) + len(self.skipped)

    @property
    def all_passing(self) -> bool:
        """Check if all tests passed."""
        return len(self.failed) == 0 and len(self.errors) == 0


def _baseline_to_dict(baseline: TestBaseline) -> dict:
    """Convert TestBaseline to dictionary for serialization."""
    return {
        "session": baseline.session,
        "timestamp": baseline.timestamp,
        "passing_tests": baseline.passing_tests,
        "total_passing": baseline.total_passing,
        "total_tests": baseline.total_tests,
        "pre_existing_failures": baseline.pre_existing_failures,
    }


def _dict_to_baseline(data: dict) -> TestBaseline:
    """Convert dictionary to TestBaseline."""
    return TestBaseline(
        session=data.get("session", 0),
        timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
        passing_tests=data.get("passing_tests", []),
        total_passing=data.get("total_passing", 0),
        total_tests=data.get("total_tests", 0),
        pre_existing_failures=data.get("pre_existing_failures", []),
    )


def load_baseline(path: Path) -> TestBaseline:
    """
    Load test baseline from file.

    Args:
        path: Path to test_baseline.json file.

    Returns:
        TestBaseline object.

    Raises:
        StateError: If file is invalid.
    """
    if not path.exists():
        raise StateError(f"Baseline file not found: {path}")

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise StateError(f"Invalid JSON in baseline file: {e}")

    return _dict_to_baseline(data)


def save_baseline(path: Path, baseline: TestBaseline) -> None:
    """
    Save test baseline to file.

    Args:
        path: Path to test_baseline.json file.
        baseline: TestBaseline object to save.
    """
    # Update timestamp
    baseline.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(_baseline_to_dict(baseline), f, indent=2)


def create_baseline_from_test_results(
    session: int,
    results: TestResults,
    pre_existing_failures: Optional[list[str]] = None,
) -> TestBaseline:
    """
    Create a baseline from test results.

    Args:
        session: Current session number.
        results: Test results from pytest run.
        pre_existing_failures: Known failures from adopt mode (optional).

    Returns:
        TestBaseline object.
    """
    return TestBaseline(
        session=session,
        passing_tests=results.passed.copy(),
        total_passing=len(results.passed),
        total_tests=results.total,
        pre_existing_failures=pre_existing_failures or [],
    )


def get_baseline_or_create(
    path: Path,
    session: int,
    results: Optional[TestResults] = None,
) -> TestBaseline:
    """
    Get existing baseline or create a new one.

    Args:
        path: Path to test_baseline.json file.
        session: Current session number.
        results: Test results to use if creating new baseline.

    Returns:
        TestBaseline object.
    """
    if path.exists():
        return load_baseline(path)

    if results:
        baseline = create_baseline_from_test_results(session, results)
        save_baseline(path, baseline)
        return baseline

    # Return empty baseline
    return TestBaseline(session=session)


def find_regressions(
    baseline: TestBaseline,
    current_results: TestResults,
) -> list[str]:
    """
    Find tests that were passing in baseline but now failing.

    Args:
        baseline: Previous test baseline.
        current_results: Current test results.

    Returns:
        List of test IDs that regressed.
    """
    baseline_passing = set(baseline.passing_tests)
    current_failing = set(current_results.failed + current_results.errors)

    # Regressions are tests that were passing and are now failing
    # Exclude pre-existing failures from being counted as regressions
    pre_existing = set(baseline.pre_existing_failures)
    regressions = baseline_passing & current_failing - pre_existing

    return sorted(list(regressions))


def find_new_passes(
    baseline: TestBaseline,
    current_results: TestResults,
) -> list[str]:
    """
    Find tests that were failing in baseline but now passing.

    Args:
        baseline: Previous test baseline.
        current_results: Current test results.

    Returns:
        List of test IDs that are now passing.
    """
    baseline_passing = set(baseline.passing_tests)
    current_passing = set(current_results.passed)

    # New passes are tests that are now passing but weren't before
    new_passes = current_passing - baseline_passing

    return sorted(list(new_passes))


def update_baseline_for_adopt_mode(
    baseline: TestBaseline,
    current_results: TestResults,
) -> TestBaseline:
    """
    Update baseline for adopt mode, recording pre-existing failures.

    In adopt mode, we record any failing tests as "pre-existing" so they
    won't be counted as regressions.

    Args:
        baseline: Current baseline.
        current_results: Test results from initial run.

    Returns:
        Updated TestBaseline.
    """
    # All failing tests at adoption time are pre-existing
    baseline.pre_existing_failures = current_results.failed + current_results.errors
    baseline.passing_tests = current_results.passed.copy()
    baseline.total_passing = len(current_results.passed)
    baseline.total_tests = current_results.total

    return baseline


def parse_test_id(test_id: str) -> tuple[str, str]:
    """
    Parse a test identifier into file and test name.

    Test IDs are in the format "file::test_name" or "file::class::method".

    Args:
        test_id: Test identifier string.

    Returns:
        Tuple of (file_path, test_name).
    """
    if "::" not in test_id:
        return test_id, ""

    parts = test_id.split("::", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def format_test_id(file_path: str, test_name: str) -> str:
    """
    Format a test identifier from file and test name.

    Args:
        file_path: Path to test file.
        test_name: Name of the test.

    Returns:
        Formatted test ID string.
    """
    return f"{file_path}::{test_name}"
