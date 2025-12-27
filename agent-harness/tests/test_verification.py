"""Tests for verification.py - Verification engine."""

import pytest
from pathlib import Path

from agent_harness.verification import (
    VerificationResult,
    ValidationResult,
    verify_feature_completion,
    check_for_regressions,
    validate_features_diff,
    verify_single_feature_rule,
    run_verification_steps,
    format_verification_report,
    quick_verify_feature,
)
from agent_harness.baseline import TestBaseline
from agent_harness.config import VerificationConfig
from agent_harness.features import Feature, FeaturesFile


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_create_passed_result(self):
        """Test creating a passed verification result."""
        result = VerificationResult(
            passed=True,
            feature_test_passed=True,
            new_tests_passing=5,
        )
        assert result.passed is True
        assert result.regression_tests == []

    def test_create_failed_result(self):
        """Test creating a failed verification result."""
        result = VerificationResult(
            passed=False,
            feature_test_passed=False,
            regression_tests=["test1", "test2"],
            lint_errors=3,
        )
        assert result.passed is False
        assert len(result.regression_tests) == 2


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Test valid validation result."""
        result = ValidationResult(
            valid=True,
            features_changed=1,
            features_marked_passing=[42],
        )
        assert result.valid is True
        assert result.features_changed == 1

    def test_invalid_result(self):
        """Test invalid validation result."""
        result = ValidationResult(
            valid=False,
            features_changed=3,
            errors=["Too many features changed"],
        )
        assert result.valid is False


class TestValidateFeaturesDiff:
    """Tests for validate_features_diff function."""

    def test_validate_no_changes(self):
        """Test validation with no feature changes."""
        old = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py"),
                Feature(id=2, category="test", description="F2", test_file="t2.py"),
            ],
        )
        new = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py"),
                Feature(id=2, category="test", description="F2", test_file="t2.py"),
            ],
        )

        result = validate_features_diff(old, new)

        assert result.valid is True
        assert result.features_changed == 0

    def test_validate_one_feature_passing(self):
        """Test validation with one feature marked passing."""
        old = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py", passes=False),
                Feature(id=2, category="test", description="F2", test_file="t2.py", passes=False),
            ],
        )
        new = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py", passes=True),
                Feature(id=2, category="test", description="F2", test_file="t2.py", passes=False),
            ],
        )

        result = validate_features_diff(old, new)

        assert result.valid is True
        assert result.features_changed == 1
        assert 1 in result.features_marked_passing

    def test_validate_too_many_features(self):
        """Test validation with too many features changed."""
        old = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py", passes=False),
                Feature(id=2, category="test", description="F2", test_file="t2.py", passes=False),
                Feature(id=3, category="test", description="F3", test_file="t3.py", passes=False),
            ],
        )
        new = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py", passes=True),
                Feature(id=2, category="test", description="F2", test_file="t2.py", passes=True),
                Feature(id=3, category="test", description="F3", test_file="t3.py", passes=False),
            ],
        )

        result = validate_features_diff(old, new, max_features_per_session=1)

        assert result.valid is False
        assert result.features_changed == 2
        assert "Too many features" in result.errors[0]


class TestVerifySingleFeatureRule:
    """Tests for verify_single_feature_rule function."""

    def test_single_feature_rule_passed(self):
        """Test single feature rule when passed."""
        old = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py", passes=False),
            ],
        )
        new = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py", passes=True),
            ],
        )

        assert verify_single_feature_rule(old, new) is True

    def test_single_feature_rule_failed(self):
        """Test single feature rule when failed."""
        old = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py", passes=False),
                Feature(id=2, category="test", description="F2", test_file="t2.py", passes=False),
            ],
        )
        new = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="",
            features=[
                Feature(id=1, category="test", description="F1", test_file="t1.py", passes=True),
                Feature(id=2, category="test", description="F2", test_file="t2.py", passes=True),
            ],
        )

        assert verify_single_feature_rule(old, new) is False


class TestRunVerificationSteps:
    """Tests for run_verification_steps function."""

    def test_automated_steps(self):
        """Test running automated verification steps."""
        feature = Feature(
            id=1,
            category="test",
            description="Test",
            test_file="test.py",
            verification_steps=["Step 1", "Step 2"],
            verification_type="automated",
        )

        results = run_verification_steps(Path("."), feature)

        assert len(results) == 2
        assert all(passed for _, passed, _ in results)

    def test_manual_steps(self):
        """Test running manual verification steps."""
        feature = Feature(
            id=1,
            category="test",
            description="Test",
            test_file="test.py",
            verification_steps=["Check UI", "Review logs"],
            verification_type="manual",
        )

        results = run_verification_steps(Path("."), feature)

        assert len(results) == 2
        assert all(not passed for _, passed, _ in results)  # Manual needs confirmation


class TestFormatVerificationReport:
    """Tests for format_verification_report function."""

    def test_format_passed_report(self):
        """Test formatting passed verification report."""
        result = VerificationResult(
            passed=True,
            feature_test_passed=True,
            new_tests_passing=5,
        )
        feature = Feature(
            id=42,
            category="test",
            description="Test feature",
            test_file="test.py",
        )

        report = format_verification_report(result, feature)

        assert "Feature #42" in report
        assert "PASSED" in report
        assert "5" in report

    def test_format_failed_report(self):
        """Test formatting failed verification report."""
        result = VerificationResult(
            passed=False,
            feature_test_passed=False,
            regression_tests=["test1", "test2"],
            lint_errors=3,
            details="Tests failed",
        )
        feature = Feature(
            id=1,
            category="test",
            description="Feature",
            test_file="test.py",
        )

        report = format_verification_report(result, feature)

        assert "FAILED" in report
        assert "Regressions" in report
        assert "test1" in report
        assert "Lint" in report
