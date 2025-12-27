"""Verification engine for agent-harness.

Independently verifies agent claims about feature completion.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent_harness.baseline import TestBaseline, find_regressions
from agent_harness.config import VerificationConfig
from agent_harness.exceptions import VerificationError
from agent_harness.features import Feature, FeaturesFile, get_feature_by_id
from agent_harness.lint import run_lint, LintResult
from agent_harness.test_runner import run_tests, TestRunResult


@dataclass
class VerificationResult:
    """Result of verification check."""

    passed: bool
    feature_test_passed: bool = False
    regression_tests: list[str] = field(default_factory=list)
    lint_errors: int = 0
    lint_warnings: int = 0
    new_tests_passing: int = 0
    details: str = ""
    test_result: Optional[TestRunResult] = None
    lint_result: Optional[LintResult] = None


@dataclass
class ValidationResult:
    """Result of features diff validation."""

    valid: bool
    features_changed: int = 0
    features_marked_passing: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def verify_feature_completion(
    project_dir: Path,
    feature: Feature,
    baseline: TestBaseline,
    config: VerificationConfig,
    lint_command: Optional[str] = None,
) -> VerificationResult:
    """
    Verify that a feature is actually complete.

    Args:
        project_dir: Path to the project directory.
        feature: Feature claimed to be complete.
        baseline: Test baseline for regression detection.
        config: Verification configuration.
        lint_command: Optional lint command to run.

    Returns:
        VerificationResult with details.
    """
    details = []
    passed = True

    # Run feature-specific tests
    test_result = run_tests(
        project_dir,
        test_path=feature.test_file,
        timeout=300,
    )

    feature_test_passed = test_result.all_passed
    if not feature_test_passed:
        passed = False
        details.append(f"Feature tests failed: {len(test_result.failed)} failures")
        for test_id in test_result.failed[:5]:
            details.append(f"  - {test_id}")
    else:
        details.append(f"Feature tests passed: {len(test_result.passed)} tests")

    # Check for regressions if enabled
    regression_tests = []
    if config.regression_check:
        # Run full test suite to check for regressions
        full_result = run_tests(project_dir, timeout=300)

        # Import TestResults from baseline for comparison
        from agent_harness.baseline import TestResults

        current_results = TestResults(
            passed=full_result.passed,
            failed=full_result.failed,
            errors=full_result.errors,
            skipped=full_result.skipped,
        )

        regression_tests = find_regressions(baseline, current_results)

        if regression_tests:
            passed = False
            details.append(f"Regressions detected: {len(regression_tests)} tests")
            for test_id in regression_tests[:5]:
                details.append(f"  - {test_id}")

    # Run lint check if command provided
    lint_result = None
    lint_errors = 0
    lint_warnings = 0

    if lint_command:
        lint_result = run_lint(project_dir, lint_command)
        lint_errors = lint_result.errors
        lint_warnings = lint_result.warnings

        if lint_errors > 0:
            details.append(f"Lint errors: {lint_errors}")

    return VerificationResult(
        passed=passed,
        feature_test_passed=feature_test_passed,
        regression_tests=regression_tests,
        lint_errors=lint_errors,
        lint_warnings=lint_warnings,
        new_tests_passing=len(test_result.passed),
        details="\n".join(details),
        test_result=test_result,
        lint_result=lint_result,
    )


def check_for_regressions(
    project_dir: Path,
    baseline: TestBaseline,
) -> list[str]:
    """
    Check for test regressions against baseline.

    Args:
        project_dir: Path to the project directory.
        baseline: Test baseline to check against.

    Returns:
        List of regressed test IDs.
    """
    # Run full test suite
    result = run_tests(project_dir, timeout=300)

    from agent_harness.baseline import TestResults

    current_results = TestResults(
        passed=result.passed,
        failed=result.failed,
        errors=result.errors,
        skipped=result.skipped,
    )

    return find_regressions(baseline, current_results)


def validate_features_diff(
    old_features: FeaturesFile,
    new_features: FeaturesFile,
    max_features_per_session: int = 1,
) -> ValidationResult:
    """
    Validate that only allowed number of features changed.

    Args:
        old_features: Previous features file state.
        new_features: New features file state.
        max_features_per_session: Maximum features that can be marked passing.

    Returns:
        ValidationResult with details.
    """
    errors = []
    features_marked_passing = []

    # Build map of old feature states
    old_states = {f.id: f.passes for f in old_features.features}

    # Find features newly marked as passing
    for feature in new_features.features:
        old_state = old_states.get(feature.id, False)
        if feature.passes and not old_state:
            features_marked_passing.append(feature.id)

    features_changed = len(features_marked_passing)

    # Check if too many features changed
    if features_changed > max_features_per_session:
        errors.append(
            f"Too many features marked passing: {features_changed} > {max_features_per_session}"
        )

    return ValidationResult(
        valid=len(errors) == 0,
        features_changed=features_changed,
        features_marked_passing=features_marked_passing,
        errors=errors,
    )


def verify_single_feature_rule(
    old_features: FeaturesFile,
    new_features: FeaturesFile,
) -> bool:
    """
    Quick check that at most 1 feature was marked passing.

    Args:
        old_features: Previous features file state.
        new_features: New features file state.

    Returns:
        True if at most 1 feature changed, False otherwise.
    """
    result = validate_features_diff(old_features, new_features, max_features_per_session=1)
    return result.valid


def run_verification_steps(
    project_dir: Path,
    feature: Feature,
) -> list[tuple[str, bool, str]]:
    """
    Run the verification steps defined for a feature.

    Args:
        project_dir: Path to the project directory.
        feature: Feature with verification steps.

    Returns:
        List of (step_description, passed, details) tuples.
    """
    results = []

    for step in feature.verification_steps:
        # For automated verification, we just run the test file
        # Manual steps would need human confirmation
        if feature.verification_type == "automated":
            # The verification step is informational, actual verification is the test
            results.append((step, True, "Automated - see test results"))
        elif feature.verification_type == "manual":
            # Manual steps need human confirmation
            results.append((step, False, "Manual verification required"))
        else:  # hybrid
            # Some automated, some manual
            results.append((step, False, "Hybrid - needs confirmation"))

    return results


def format_verification_report(result: VerificationResult, feature: Feature) -> str:
    """
    Format a verification result as a readable report.

    Args:
        result: VerificationResult to format.
        feature: Feature that was verified.

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append(f"Verification Report for Feature #{feature.id}")
    lines.append(f"Description: {feature.description}")
    lines.append("-" * 50)

    if result.passed:
        lines.append("STATUS: PASSED")
    else:
        lines.append("STATUS: FAILED")

    lines.append("")
    lines.append("Test Results:")
    lines.append(f"  Feature Tests: {'PASSED' if result.feature_test_passed else 'FAILED'}")
    lines.append(f"  Tests Passing: {result.new_tests_passing}")

    if result.regression_tests:
        lines.append("")
        lines.append("Regressions Detected:")
        for test_id in result.regression_tests:
            lines.append(f"  - {test_id}")

    if result.lint_errors > 0 or result.lint_warnings > 0:
        lines.append("")
        lines.append("Lint Results:")
        lines.append(f"  Errors: {result.lint_errors}")
        lines.append(f"  Warnings: {result.lint_warnings}")

    if result.details:
        lines.append("")
        lines.append("Details:")
        lines.append(result.details)

    return "\n".join(lines)


def quick_verify_feature(
    project_dir: Path,
    feature_id: int,
    features_file: FeaturesFile,
) -> tuple[bool, str]:
    """
    Quick verification of a feature's test file.

    Args:
        project_dir: Path to the project directory.
        feature_id: Feature ID to verify.
        features_file: FeaturesFile containing the feature.

    Returns:
        Tuple of (passed, message).
    """
    feature = get_feature_by_id(features_file, feature_id)
    if feature is None:
        return False, f"Feature {feature_id} not found"

    result = run_tests(project_dir, test_path=feature.test_file)

    if result.all_passed:
        return True, f"All {len(result.passed)} tests passed"
    else:
        return False, f"Tests failed: {len(result.failed)} failures, {len(result.errors)} errors"


def verify_all_features(
    project_dir: Path,
    features_file: FeaturesFile,
) -> dict[int, tuple[bool, str]]:
    """
    Verify all features in a features file.

    Args:
        project_dir: Path to the project directory.
        features_file: FeaturesFile to verify.

    Returns:
        Dictionary mapping feature ID to (passed, message).
    """
    results = {}

    for feature in features_file.features:
        passed, message = quick_verify_feature(project_dir, feature.id, features_file)
        results[feature.id] = (passed, message)

    return results
