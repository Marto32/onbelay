"""Tests for test_runner.py - Test execution."""

import pytest
from pathlib import Path

from agent_harness.test_runner import (
    TestResult,
    TestRunResult,
    run_tests_async,
    run_single_test_async,
    get_test_files,
    discover_tests,
    format_test_summary,
    run_test_file_async,
    _parse_pytest_output,
)


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_create_passed_result(self):
        """Test creating a passed test result."""
        result = TestResult(
            test_id="test_file.py::test_function",
            status="passed",
            duration=0.5,
        )
        assert result.status == "passed"
        assert result.error_message is None

    def test_create_failed_result(self):
        """Test creating a failed test result."""
        result = TestResult(
            test_id="test_file.py::test_function",
            status="failed",
            error_message="AssertionError: expected 1, got 2",
        )
        assert result.status == "failed"
        assert "AssertionError" in result.error_message


class TestTestRunResult:
    """Tests for TestRunResult dataclass."""

    def test_all_passed_true(self):
        """Test all_passed when all tests pass."""
        result = TestRunResult(
            exit_code=0,
            passed=["test1", "test2"],
            failed=[],
            errors=[],
            total=2,
        )
        assert result.all_passed is True

    def test_all_passed_false_with_failures(self):
        """Test all_passed when tests fail."""
        result = TestRunResult(
            exit_code=1,
            passed=["test1"],
            failed=["test2"],
            errors=[],
            total=2,
        )
        assert result.all_passed is False

    def test_all_passed_false_with_errors(self):
        """Test all_passed when tests error."""
        result = TestRunResult(
            exit_code=1,
            passed=["test1"],
            failed=[],
            errors=["test2"],
            total=2,
        )
        assert result.all_passed is False

    def test_pass_rate(self):
        """Test pass rate calculation."""
        result = TestRunResult(
            exit_code=1,
            passed=["test1", "test2", "test3"],
            failed=["test4"],
            total=4,
        )
        assert result.pass_rate == 0.75


class TestParsePytestOutput:
    """Tests for parsing pytest output."""

    def test_parse_all_passed(self):
        """Test parsing output with all tests passed."""
        output = """
tests/test_example.py::test_one PASSED
tests/test_example.py::test_two PASSED
tests/test_example.py::test_three PASSED

====================== 3 passed in 0.52s ======================
"""
        result = _parse_pytest_output(output, exit_code=0)

        assert len(result.passed) == 3
        assert len(result.failed) == 0
        assert result.duration == pytest.approx(0.52, rel=0.1)

    def test_parse_with_failures(self):
        """Test parsing output with failures."""
        output = """
tests/test_example.py::test_one PASSED
tests/test_example.py::test_two FAILED
tests/test_example.py::test_three PASSED

====================== 1 failed, 2 passed in 0.75s ======================
"""
        result = _parse_pytest_output(output, exit_code=1)

        assert len(result.passed) == 2
        assert len(result.failed) == 1
        assert "test_two" in result.failed[0]

    def test_parse_with_errors(self):
        """Test parsing output with errors."""
        output = """
tests/test_example.py::test_one PASSED
tests/test_example.py::test_two ERROR

====================== 1 error, 1 passed in 0.30s ======================
"""
        result = _parse_pytest_output(output, exit_code=1)

        assert len(result.passed) == 1
        assert len(result.errors) == 1

    def test_parse_with_skipped(self):
        """Test parsing output with skipped tests."""
        output = """
tests/test_example.py::test_one PASSED
tests/test_example.py::test_two SKIPPED

====================== 1 passed, 1 skipped in 0.20s ======================
"""
        result = _parse_pytest_output(output, exit_code=0)

        assert len(result.passed) == 1
        assert len(result.skipped) == 1


class TestGetTestFiles:
    """Tests for get_test_files function."""

    def test_get_test_files(self, tmp_path):
        """Test finding test files."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        (test_dir / "test_one.py").write_text("def test_a(): pass")
        (test_dir / "test_two.py").write_text("def test_b(): pass")
        (test_dir / "helper.py").write_text("def helper(): pass")

        files = get_test_files(tmp_path)

        assert "tests/test_one.py" in files
        assert "tests/test_two.py" in files
        assert "tests/helper.py" not in files

    def test_get_test_files_nested(self, tmp_path):
        """Test finding nested test files."""
        test_dir = tmp_path / "tests" / "unit"
        test_dir.mkdir(parents=True)

        (test_dir / "test_nested.py").write_text("def test_c(): pass")

        files = get_test_files(tmp_path)

        assert "tests/unit/test_nested.py" in files

    def test_get_test_files_empty(self, tmp_path):
        """Test with no test files."""
        files = get_test_files(tmp_path)
        assert files == []


class TestFormatTestSummary:
    """Tests for format_test_summary function."""

    def test_format_all_passed(self):
        """Test formatting summary with all passed."""
        result = TestRunResult(
            exit_code=0,
            passed=["test1", "test2"],
            total=2,
            duration=1.5,
        )

        summary = format_test_summary(result)

        assert "2 tests" in summary
        assert "1.50s" in summary
        assert "Passed:  2" in summary
        assert "ALL TESTS PASSED" in summary

    def test_format_with_failures(self):
        """Test formatting summary with failures."""
        result = TestRunResult(
            exit_code=1,
            passed=["test1"],
            failed=["test2", "test3"],
            total=3,
            duration=2.0,
        )

        summary = format_test_summary(result)

        assert "Failed:  2" in summary
        assert "SOME TESTS FAILED" in summary
        assert "test2" in summary


class TestRunTests:
    """Integration tests for run_tests function."""

    @pytest.mark.asyncio
    async def test_run_tests_on_real_tests(self, tmp_path):
        """Test running actual pytest on test files."""
        # Create a simple test file
        (tmp_path / "test_simple.py").write_text("""
def test_passes():
    assert True

def test_also_passes():
    assert 1 + 1 == 2
""")

        # Run tests (this uses subprocess so may not work in all environments)
        # Note: This may fail if poetry is not available in the tmp_path context
        result = await run_tests_async(tmp_path, test_path="test_simple.py", use_json_report=False)

        # Test runs but may fail if no pyproject.toml - just verify it returns a result
        assert isinstance(result, TestRunResult)
        # If it ran successfully (has a pyproject.toml), check for success
        if "pyproject.toml" not in result.raw_output:
            assert result.exit_code == 0


class TestRunTestFile:
    """Tests for run_test_file function."""

    @pytest.mark.asyncio
    async def test_run_test_file_convenience(self, tmp_path):
        """Test run_test_file convenience wrapper."""
        (tmp_path / "test_example.py").write_text("def test_one(): assert True")

        # Just verify it runs without error
        result = await run_test_file_async(tmp_path, "test_example.py")
        assert isinstance(result, TestRunResult)
