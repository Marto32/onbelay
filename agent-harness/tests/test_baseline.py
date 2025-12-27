"""Tests for baseline.py - Test baseline tracking."""

import json
import pytest
from pathlib import Path

from agent_harness.baseline import (
    TestBaseline,
    TestResults,
    load_baseline,
    save_baseline,
    create_baseline_from_test_results,
    get_baseline_or_create,
    find_regressions,
    find_new_passes,
    update_baseline_for_adopt_mode,
    parse_test_id,
    format_test_id,
)
from agent_harness.exceptions import StateError


class TestTestBaseline:
    """Tests for TestBaseline dataclass."""

    def test_create_baseline(self):
        """Test creating a basic baseline."""
        baseline = TestBaseline(session=1)
        assert baseline.session == 1
        assert baseline.passing_tests == []
        assert baseline.total_passing == 0
        assert baseline.total_tests == 0

    def test_baseline_with_tests(self):
        """Test creating baseline with test data."""
        baseline = TestBaseline(
            session=5,
            passing_tests=["test_a.py::test_one", "test_b.py::test_two"],
            total_tests=3,
        )
        assert baseline.session == 5
        assert len(baseline.passing_tests) == 2
        assert baseline.total_passing == 2  # Auto-calculated from list

    def test_baseline_post_init_updates_count(self):
        """Test that post_init updates total_passing from list."""
        baseline = TestBaseline(
            session=1,
            passing_tests=["a", "b", "c"],
        )
        assert baseline.total_passing == 3


class TestTestResults:
    """Tests for TestResults dataclass."""

    def test_empty_results(self):
        """Test empty test results."""
        results = TestResults()
        assert results.total == 0
        assert results.all_passing is True

    def test_results_with_tests(self):
        """Test results with various test states."""
        results = TestResults(
            passed=["test1", "test2"],
            failed=["test3"],
            errors=["test4"],
            skipped=["test5"],
        )
        assert results.total == 5
        assert results.all_passing is False

    def test_all_passing(self):
        """Test all_passing property."""
        results = TestResults(passed=["test1", "test2"])
        assert results.all_passing is True

        results_with_failures = TestResults(passed=["test1"], failed=["test2"])
        assert results_with_failures.all_passing is False


class TestLoadSaveBaseline:
    """Tests for load/save baseline functions."""

    def test_save_and_load_baseline(self, tmp_path):
        """Test saving and loading a baseline."""
        baseline_path = tmp_path / "test_baseline.json"
        baseline = TestBaseline(
            session=3,
            passing_tests=["test_a.py::test_one", "test_b.py::test_two"],
            total_tests=5,
            pre_existing_failures=["test_c.py::test_three"],
        )

        save_baseline(baseline_path, baseline)
        loaded = load_baseline(baseline_path)

        assert loaded.session == 3
        assert loaded.passing_tests == baseline.passing_tests
        assert loaded.pre_existing_failures == baseline.pre_existing_failures

    def test_load_missing_file_raises_error(self, tmp_path):
        """Test loading from missing file raises StateError."""
        with pytest.raises(StateError, match="not found"):
            load_baseline(tmp_path / "missing.json")

    def test_load_invalid_json_raises_error(self, tmp_path):
        """Test loading invalid JSON raises StateError."""
        invalid_path = tmp_path / "invalid.json"
        invalid_path.write_text("not json")

        with pytest.raises(StateError, match="Invalid JSON"):
            load_baseline(invalid_path)

    def test_save_creates_parent_directory(self, tmp_path):
        """Test that save creates parent directories."""
        baseline_path = tmp_path / "nested" / "dir" / "baseline.json"
        baseline = TestBaseline(session=1)

        save_baseline(baseline_path, baseline)
        assert baseline_path.exists()


class TestCreateBaseline:
    """Tests for creating baselines from test results."""

    def test_create_baseline_from_results(self):
        """Test creating baseline from test results."""
        results = TestResults(
            passed=["test1", "test2", "test3"],
            failed=["test4"],
            skipped=["test5"],
        )

        baseline = create_baseline_from_test_results(session=10, results=results)

        assert baseline.session == 10
        assert baseline.passing_tests == ["test1", "test2", "test3"]
        assert baseline.total_passing == 3
        assert baseline.total_tests == 5
        assert baseline.pre_existing_failures == []

    def test_create_baseline_with_pre_existing_failures(self):
        """Test creating baseline with pre-existing failures."""
        results = TestResults(passed=["test1"])

        baseline = create_baseline_from_test_results(
            session=1,
            results=results,
            pre_existing_failures=["old_failure1", "old_failure2"],
        )

        assert baseline.pre_existing_failures == ["old_failure1", "old_failure2"]


class TestGetBaselineOrCreate:
    """Tests for get_baseline_or_create function."""

    def test_get_existing_baseline(self, tmp_path):
        """Test getting an existing baseline."""
        baseline_path = tmp_path / "baseline.json"
        existing = TestBaseline(session=5, passing_tests=["existing_test"])
        save_baseline(baseline_path, existing)

        result = get_baseline_or_create(baseline_path, session=10)

        assert result.session == 5
        assert result.passing_tests == ["existing_test"]

    def test_create_new_baseline_with_results(self, tmp_path):
        """Test creating new baseline when none exists."""
        baseline_path = tmp_path / "baseline.json"
        results = TestResults(passed=["new_test"])

        result = get_baseline_or_create(baseline_path, session=1, results=results)

        assert result.session == 1
        assert result.passing_tests == ["new_test"]
        assert baseline_path.exists()

    def test_return_empty_baseline_without_results(self, tmp_path):
        """Test returning empty baseline when no results provided."""
        baseline_path = tmp_path / "baseline.json"

        result = get_baseline_or_create(baseline_path, session=1)

        assert result.session == 1
        assert result.passing_tests == []


class TestRegressionDetection:
    """Tests for regression detection functions."""

    def test_find_regressions(self):
        """Test finding test regressions."""
        baseline = TestBaseline(
            session=1,
            passing_tests=["test1", "test2", "test3"],
        )

        current = TestResults(
            passed=["test1"],
            failed=["test2"],  # Regression!
            errors=["test3"],  # Regression!
        )

        regressions = find_regressions(baseline, current)

        assert "test2" in regressions
        assert "test3" in regressions
        assert "test1" not in regressions

    def test_find_regressions_excludes_pre_existing(self):
        """Test that pre-existing failures aren't counted as regressions."""
        baseline = TestBaseline(
            session=1,
            passing_tests=["test1", "test2"],
            pre_existing_failures=["test2"],  # Was pre-existing failure
        )

        current = TestResults(
            passed=["test1"],
            failed=["test2"],  # Not a regression, was pre-existing
        )

        regressions = find_regressions(baseline, current)

        assert "test2" not in regressions
        assert len(regressions) == 0

    def test_find_new_passes(self):
        """Test finding newly passing tests."""
        baseline = TestBaseline(
            session=1,
            passing_tests=["test1"],
        )

        current = TestResults(
            passed=["test1", "test2", "test3"],  # test2 and test3 are new
        )

        new_passes = find_new_passes(baseline, current)

        assert "test2" in new_passes
        assert "test3" in new_passes
        assert "test1" not in new_passes


class TestAdoptMode:
    """Tests for adopt mode functionality."""

    def test_update_baseline_for_adopt_mode(self):
        """Test updating baseline for adopt mode."""
        baseline = TestBaseline(session=1)
        results = TestResults(
            passed=["test1", "test2"],
            failed=["fail1"],
            errors=["error1"],
        )

        updated = update_baseline_for_adopt_mode(baseline, results)

        assert updated.passing_tests == ["test1", "test2"]
        assert updated.total_passing == 2
        assert updated.total_tests == 4
        assert "fail1" in updated.pre_existing_failures
        assert "error1" in updated.pre_existing_failures


class TestTestIdParsing:
    """Tests for test ID parsing utilities."""

    def test_parse_simple_test_id(self):
        """Test parsing simple test ID."""
        file_path, test_name = parse_test_id("test_file.py::test_function")

        assert file_path == "test_file.py"
        assert test_name == "test_function"

    def test_parse_class_test_id(self):
        """Test parsing class-based test ID."""
        file_path, test_name = parse_test_id("test_file.py::TestClass::test_method")

        assert file_path == "test_file.py"
        assert test_name == "TestClass::test_method"

    def test_parse_file_only(self):
        """Test parsing file-only ID."""
        file_path, test_name = parse_test_id("test_file.py")

        assert file_path == "test_file.py"
        assert test_name == ""

    def test_format_test_id(self):
        """Test formatting test ID."""
        test_id = format_test_id("test_file.py", "test_function")

        assert test_id == "test_file.py::test_function"
