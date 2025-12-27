"""Integration tests for verification system.

Tests the complete verification flow including feature completion checking,
regression detection, and rollback on verification failure.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent_harness.verification import (
    verify_feature_completion,
    check_for_regressions,
    validate_features_diff,
    verify_single_feature_rule,
    quick_verify_feature,
    verify_all_features,
)
from agent_harness.features import load_features, save_features, FeaturesFile, Feature
from agent_harness.baseline import TestBaseline, TestResults
from agent_harness.config import VerificationConfig
from agent_harness.test_runner import TestRunResult


@pytest.mark.integration
class TestFeatureVerification:
    """Test feature completion verification."""

    @pytest.mark.asyncio
    async def test_successful_feature_verification(
        self,
        integration_project,
        mock_test_runner,
    ):
        """Test successful feature verification flow.

        Verifies:
        - Feature tests run
        - Tests pass
        - Verification result is positive
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")
        feature = features.features[0]

        baseline = TestBaseline(
            session=1,
            timestamp="2025-01-01T00:00:00Z",
            passing_tests=[],
            total_passing=0,
            total_tests=0,
            pre_existing_failures=[],
        )

        config = VerificationConfig(regression_check=False)

        result = await verify_feature_completion(
            project_dir,
            feature,
            baseline,
            config,
        )

        # Verify tests were run
        mock_test_runner.assert_called()

        # Verify verification passed
        assert result.passed is True
        assert result.feature_test_passed is True
        assert result.new_tests_passing > 0

    @pytest.mark.asyncio
    async def test_feature_verification_with_test_failures(
        self,
        integration_project,
    ):
        """Test verification when feature tests fail.

        Verifies:
        - Failed tests detected
        - Verification fails
        - Failure details included
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")
        feature = features.features[0]

        baseline = TestBaseline(
            session=1,
            timestamp="2025-01-01T00:00:00Z",
            passing_tests=[],
            total_passing=0,
            total_tests=0,
            pre_existing_failures=[],
        )

        config = VerificationConfig(regression_check=False)

        with patch("agent_harness.verification.run_tests_async") as mock_run:
            # Mock failing tests
            mock_run.return_value = TestRunResult(
                exit_code=1,
                passed=[],
                failed=["tests/test_calculator.py::test_add"],
                errors=["tests/test_calculator.py::test_subtract"],
                skipped=[],
                total=2,
                duration=0.5,
                raw_output="test failures",
                results=[],
            )

            result = await verify_feature_completion(
                project_dir,
                feature,
                baseline,
                config,
            )

            # Verify verification failed
            assert result.passed is False
            assert result.feature_test_passed is False
            assert "Feature tests failed" in result.details

    @pytest.mark.asyncio
    async def test_feature_verification_with_lint_errors(
        self,
        integration_project,
        mock_test_runner,
    ):
        """Test verification with lint errors.

        Verifies:
        - Lint command runs
        - Errors detected
        - Details included in result
        """
        from agent_harness.lint import LintResult

        project_dir = integration_project
        features = load_features(project_dir / "features.json")
        feature = features.features[0]

        baseline = TestBaseline(
            session=1,
            timestamp="2025-01-01T00:00:00Z",
            passing_tests=[],
            total_passing=0,
            total_tests=0,
            pre_existing_failures=[],
        )

        config = VerificationConfig(regression_check=False)

        with patch("agent_harness.verification.run_lint") as mock_lint:
            mock_lint.return_value = LintResult(
                exit_code=1,
                errors=5,
                warnings=10,
                raw_output="Lint errors found",
            )

            result = await verify_feature_completion(
                project_dir,
                feature,
                baseline,
                config,
                lint_command="ruff check .",
            )

            # Verify lint ran
            mock_lint.assert_called_once()

            # Verify lint errors in result
            assert result.lint_errors == 5
            assert result.lint_warnings == 10
            assert "Lint errors: 5" in result.details


@pytest.mark.integration
class TestRegressionDetection:
    """Test regression detection during verification."""

    @pytest.mark.asyncio
    async def test_no_regressions_detected(
        self,
        integration_project,
        mock_test_runner,
    ):
        """Test when no regressions occur.

        Verifies:
        - Baseline tests still pass
        - No regressions reported
        - Verification succeeds
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")
        feature = features.features[0]

        # Create baseline with passing tests
        baseline = TestBaseline(
            session=1,
            timestamp="2025-01-01T00:00:00Z",
            passing_tests=["tests/test_baseline.py::test_one", "tests/test_baseline.py::test_two"],
            total_passing=2,
            total_tests=2,
            pre_existing_failures=[],
        )

        config = VerificationConfig(regression_check=True)

        # Mock test runner to return passing tests
        with patch("agent_harness.verification.run_tests_async") as mock_run:
            mock_run.return_value = TestRunResult(
                exit_code=0,
                passed=[
                    "tests/test_baseline.py::test_one",
                    "tests/test_baseline.py::test_two",
                    "tests/test_calculator.py::test_add",
                ],
                failed=[],
                errors=[],
                skipped=[],
                total=3,
                duration=1.0,
                raw_output="test output",
                results=[],
            )

            result = await verify_feature_completion(
                project_dir,
                feature,
                baseline,
                config,
            )

            # No regressions
            assert result.regression_tests == []
            assert result.passed is True

    @pytest.mark.asyncio
    async def test_regressions_detected_and_reported(
        self,
        integration_project,
        mock_test_runner,
    ):
        """Test regression detection when tests that passed now fail.

        Verifies:
        - Regressions identified
        - Verification fails
        - Regressed tests listed
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")
        feature = features.features[0]

        # Create baseline with passing tests
        baseline = TestBaseline(
            session=1,
            timestamp="2025-01-01T00:00:00Z",
            passing_tests=["tests/test_baseline.py::test_one", "tests/test_baseline.py::test_two"],
            total_passing=2,
            total_tests=2,
            pre_existing_failures=[],
        )

        config = VerificationConfig(regression_check=True)

        with patch("agent_harness.verification.run_tests_async") as mock_run:
            # First call: feature tests
            # Second call: full suite with regressions
            mock_run.side_effect = [
                # Feature test result
                TestRunResult(
                exit_code=0,
                    passed=["tests/test_calculator.py::test_add"],
                    failed=[],
                    errors=[],
                    skipped=[],
                    total=1,
                    duration=0.5,
                raw_output="test output",
                results=[],
                ),
                # Full suite with regression
                TestRunResult(
                exit_code=1,
                    passed=["tests/test_baseline.py::test_one"],
                    failed=["tests/test_baseline.py::test_two"],  # Regressed!
                    errors=[],
                    skipped=[],
                    total=2,
                    duration=1.0,
                raw_output="test output",
                results=[],
                ),
            ]

            result = await verify_feature_completion(
                project_dir,
                feature,
                baseline,
                config,
            )

            # Regression detected
            assert len(result.regression_tests) > 0
            assert result.passed is False
            assert "Regressions detected" in result.details

    @pytest.mark.asyncio
    async def test_check_for_regressions_function(
        self,
        integration_project,
    ):
        """Test standalone regression checking function.

        Verifies:
        - Function runs full test suite
        - Compares against baseline
        - Returns regressed test list
        """
        project_dir = integration_project

        baseline = TestBaseline(
            session=1,
            timestamp="2025-01-01T00:00:00Z",
            passing_tests=["test_a", "test_b", "test_c"],
            total_passing=3,
            total_tests=3,
            pre_existing_failures=[],
        )

        with patch("agent_harness.verification.run_tests_async") as mock_run:
            mock_run.return_value = TestRunResult(
                exit_code=1,
                passed=["test_a", "test_c"],
                failed=["test_b"],  # Regressed
                errors=[],
                skipped=[],
                total=3,
                duration=1.0,
                raw_output="test output",
                results=[],
            )

            regressions = await check_for_regressions(project_dir, baseline)

            assert "test_b" in regressions
            assert len(regressions) == 1


@pytest.mark.integration
class TestFeaturesDiffValidation:
    """Test validation of features.json changes."""

    def test_single_feature_marked_passing_valid(
        self,
        integration_project,
    ):
        """Test that marking one feature as passing is valid.

        Verifies:
        - Single feature change allowed
        - Validation passes
        - Changed feature ID reported
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")

        # Create old state
        old_features = FeaturesFile(
            project=features.project,
            generated_by=features.generated_by,
            init_mode=features.init_mode,
            last_updated=features.last_updated,
            features=[
                Feature(
                    id=f.id,
                    category=f.category,
                    description=f.description,
                    test_file=f.test_file,
                    verification_steps=f.verification_steps,
                    passes=False,  # All false initially
                )
                for f in features.features
            ],
        )

        # Mark one feature as passing in new state
        new_features = load_features(project_dir / "features.json")
        new_features.features[0].passes = True

        result = validate_features_diff(old_features, new_features, max_features_per_session=1)

        assert result.valid is True
        assert result.features_changed == 1
        assert 1 in result.features_marked_passing

    def test_multiple_features_marked_passing_invalid(
        self,
        integration_project,
    ):
        """Test that marking multiple features as passing is invalid.

        Verifies:
        - Multiple changes rejected
        - Validation fails
        - Error message indicates limit exceeded
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")

        # Old state: all false
        old_features = FeaturesFile(
            project=features.project,
            generated_by=features.generated_by,
            init_mode=features.init_mode,
            last_updated=features.last_updated,
            features=[
                Feature(
                    id=f.id,
                    category=f.category,
                    description=f.description,
                    test_file=f.test_file,
                    verification_steps=f.verification_steps,
                    passes=False,
                )
                for f in features.features
            ],
        )

        # Mark multiple as passing
        new_features = load_features(project_dir / "features.json")
        new_features.features[0].passes = True
        new_features.features[1].passes = True

        result = validate_features_diff(old_features, new_features, max_features_per_session=1)

        assert result.valid is False
        assert result.features_changed == 2
        assert len(result.errors) > 0
        assert "Too many features" in result.errors[0]

    def test_verify_single_feature_rule(
        self,
        integration_project,
    ):
        """Test the single feature rule verification helper.

        Verifies:
        - Helper enforces one feature limit
        - Returns boolean result
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")

        # Old state
        old_features = FeaturesFile(
            project=features.project,
            generated_by=features.generated_by,
            init_mode=features.init_mode,
            last_updated=features.last_updated,
            features=[
                Feature(
                    id=f.id,
                    category=f.category,
                    description=f.description,
                    test_file=f.test_file,
                    verification_steps=f.verification_steps,
                    passes=False,
                )
                for f in features.features
            ],
        )

        # One feature passing - should be valid
        new_features_valid = load_features(project_dir / "features.json")
        new_features_valid.features[0].passes = True

        assert verify_single_feature_rule(old_features, new_features_valid) is True

        # Two features passing - should be invalid
        new_features_invalid = load_features(project_dir / "features.json")
        new_features_invalid.features[0].passes = True
        new_features_invalid.features[1].passes = True

        assert verify_single_feature_rule(old_features, new_features_invalid) is False


@pytest.mark.integration
class TestQuickVerification:
    """Test quick verification helpers."""

    @pytest.mark.asyncio
    async def test_quick_verify_feature_success(
        self,
        integration_project,
        mock_test_runner,
    ):
        """Test quick feature verification when tests pass.

        Verifies:
        - Quick verification runs tests
        - Returns pass/message tuple
        - Message indicates success
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")

        passed, message = await quick_verify_feature(project_dir, 1, features)

        assert passed is True
        assert "passed" in message.lower()

    @pytest.mark.asyncio
    async def test_quick_verify_feature_failure(
        self,
        integration_project,
    ):
        """Test quick verification when tests fail.

        Verifies:
        - Failure detected
        - Returns False
        - Message contains failure info
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")

        with patch("agent_harness.verification.run_tests_async") as mock_run:
            mock_run.return_value = TestRunResult(
                exit_code=1,
                passed=[],
                failed=["tests/test_calculator.py::test_add"],
                errors=["tests/test_calculator.py::test_subtract"],
                skipped=[],
                total=2,
                duration=0.5,
                raw_output="test output",
                results=[],
            )

            passed, message = await quick_verify_feature(project_dir, 1, features)

            assert passed is False
            assert "failed" in message.lower()

    @pytest.mark.asyncio
    async def test_quick_verify_nonexistent_feature(
        self,
        integration_project,
    ):
        """Test quick verification with nonexistent feature ID.

        Verifies:
        - Nonexistent feature handled
        - Returns failure
        - Message indicates not found
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")

        passed, message = await quick_verify_feature(project_dir, 999, features)

        assert passed is False
        assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_verify_all_features(
        self,
        integration_project,
        mock_test_runner,
    ):
        """Test verifying all features at once.

        Verifies:
        - All features checked
        - Results dictionary returned
        - Each feature has pass/message
        """
        project_dir = integration_project
        features = load_features(project_dir / "features.json")

        results = await verify_all_features(project_dir, features)

        # Should have results for each feature
        assert len(results) == len(features.features)

        # Each result should be a tuple
        for feature_id, (passed, message) in results.items():
            assert isinstance(passed, bool)
            assert isinstance(message, str)
            assert feature_id in [f.id for f in features.features]


@pytest.mark.integration
class TestVerificationWithRollback:
    """Test verification triggering rollback on failure."""

    @pytest.mark.asyncio
    async def test_verification_failure_in_session_triggers_rollback(
        self,
        integration_project,
        mock_agent_runner,
        mock_preflight_checks,
    ):
        """Test that verification failure during session can trigger rollback.

        This is tested at the session level, but we verify the flow here.

        Verifies:
        - Failed verification detected
        - Session marked as partial
        - Features not marked as passing
        """
        from agent_harness.session import SessionOrchestrator, SessionConfig
        from agent_harness.checkpoint import Checkpoint

        project_dir = integration_project

        with patch("agent_harness.session.create_checkpoint") as mock_create, \
             patch("agent_harness.verification.run_tests_async") as mock_run:

            mock_create.return_value = Checkpoint(
                id="cp_test",
                timestamp="2025-01-01T00:00:00Z",
                session=1,
                git_ref="abc123",
                features_json_hash="hash1",
                progress_file_hash="hash2",
                session_state_hash="hash3",
                reason="Session start",
                files_backed_up=["features.json"],
            )

            # Mock tests failing for verification
            mock_run.return_value = TestRunResult(
                exit_code=1,
                passed=[],
                failed=["tests/test_calculator.py::test_add"],
                errors=[],
                skipped=[],
                total=1,
                duration=0.5,
                raw_output="test output",
                results=[],
            )

            orchestrator = SessionOrchestrator(project_dir)
            config = SessionConfig(
                project_dir=project_dir,
                skip_commit=True,
            )

            result = await orchestrator.run_session(config)

            # Verification should fail
            assert result.verification_passed is False

            # Features should not be marked complete
            assert result.features_completed == []

            # Session should still succeed (completed without verification)
            assert result.success is True
