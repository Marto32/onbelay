"""Tests for orientation.py - Orientation generator."""

import pytest
from pathlib import Path

from agent_harness.orientation import (
    OrientationSummary,
    generate_orientation_summary,
    generate_continuation_details,
    generate_cleanup_orientation,
    generate_init_orientation,
    estimate_token_count,
    ensure_under_token_limit,
    get_structured_orientation,
)
from agent_harness.features import Feature, FeaturesFile
from agent_harness.progress import ProgressEntry
from agent_harness.state import SessionState


@pytest.fixture
def sample_features():
    """Create sample features file."""
    return FeaturesFile(
        project="test-project",
        generated_by="test",
        init_mode="new",
        last_updated="2024-01-01",
        features=[
            Feature(
                id=1,
                category="core",
                description="First feature",
                test_file="tests/test_first.py",
                passes=True,
            ),
            Feature(
                id=2,
                category="core",
                description="Second feature",
                test_file="tests/test_second.py",
                passes=False,
                depends_on=[1],
            ),
            Feature(
                id=3,
                category="extra",
                description="Third feature",
                test_file="tests/test_third.py",
                passes=False,
                depends_on=[2],
            ),
        ],
    )


@pytest.fixture
def sample_state():
    """Create sample session state."""
    return SessionState(
        last_session=5,
        total_sessions=5,
        status="complete",
        current_feature=None,
    )


@pytest.fixture
def sample_progress_entries():
    """Create sample progress entries."""
    return [
        ProgressEntry(
            session=4,
            date="2024-01-04",
            feature_id=1,
            what_done=["Implemented feature 1", "Added tests"],
            decisions=["Used approach A", "Avoided B"],
            status="complete",
        ),
        ProgressEntry(
            session=5,
            date="2024-01-05",
            feature_id=1,
            what_done=["Fixed edge case"],
            decisions=["Refactored for clarity"],
            current_state="Feature 1 complete",
            status="complete",
        ),
    ]


class TestGenerateOrientationSummary:
    """Tests for generate_orientation_summary function."""

    def test_generate_basic_summary(self, sample_features, sample_state, tmp_path):
        """Test generating basic orientation summary."""
        summary = generate_orientation_summary(
            tmp_path,
            sample_state,
            sample_features,
        )

        assert "SESSION 6" in summary  # Next session
        assert "1/3" in summary  # Progress
        assert "33" in summary  # Percentage

    def test_generate_summary_with_progress(
        self, sample_features, sample_state, sample_progress_entries, tmp_path
    ):
        """Test generating summary with progress entries."""
        summary = generate_orientation_summary(
            tmp_path,
            sample_state,
            sample_features,
            progress_entries=sample_progress_entries,
        )

        assert "LAST SESSION" in summary
        assert "RECENT DECISIONS" in summary
        assert "approach A" in summary

    def test_generate_summary_with_current_feature(self, sample_features, tmp_path):
        """Test summary when working on a feature."""
        state = SessionState(
            last_session=5,
            current_feature=2,
            status="partial",
        )

        summary = generate_orientation_summary(
            tmp_path,
            state,
            sample_features,
        )

        assert "CURRENT FEATURE" in summary
        assert "#2" in summary
        assert "Second feature" in summary

    def test_generate_summary_stuck_warning(self, sample_features, tmp_path):
        """Test summary with stuck warning."""
        state = SessionState(
            last_session=5,
            stuck_count=2,
        )

        summary = generate_orientation_summary(
            tmp_path,
            state,
            sample_features,
        )

        assert "WARNING" in summary
        assert "Stuck count" in summary


class TestGenerateContinuationDetails:
    """Tests for generate_continuation_details function."""

    def test_continuation_with_last_entry(self):
        """Test continuation details with last entry."""
        feature = Feature(
            id=2,
            category="test",
            description="Test feature",
            test_file="test.py",
            verification_steps=["Step 1", "Step 2", "Step 3"],
        )
        last_entry = ProgressEntry(
            session=5,
            date="2024-01-05",
            what_done=["Started implementation", "Added basic tests"],
            current_state="Halfway done",
            decisions=["Using library X"],
        )

        details = generate_continuation_details(feature, last_entry)

        assert "CONTINUING FEATURE #2" in details
        assert "PREVIOUS PROGRESS" in details
        assert "Started implementation" in details
        assert "Halfway done" in details
        assert "REMAINING VERIFICATION STEPS" in details

    def test_continuation_without_last_entry(self):
        """Test continuation details without last entry."""
        feature = Feature(
            id=1,
            category="test",
            description="Feature",
            test_file="test.py",
            verification_steps=["Step 1"],
        )

        details = generate_continuation_details(feature, None)

        assert "CONTINUING FEATURE #1" in details
        assert "REMAINING VERIFICATION STEPS" in details


class TestGenerateCleanupOrientation:
    """Tests for generate_cleanup_orientation function."""

    def test_cleanup_with_issues(self, tmp_path):
        """Test cleanup orientation with issues."""
        orientation = generate_cleanup_orientation(
            tmp_path,
            quality_issues=["Missing docstring", "Complex function"],
            oversized_files=[("src/big.py", 600), ("src/huge.py", 800)],
            lint_errors=5,
        )

        assert "CLEANUP SESSION" in orientation
        assert "QUALITY ISSUES" in orientation
        assert "Missing docstring" in orientation
        assert "OVERSIZED FILES" in orientation
        assert "600 lines" in orientation
        assert "LINT ERRORS: 5" in orientation
        assert "Do NOT add new features" in orientation

    def test_cleanup_minimal(self, tmp_path):
        """Test cleanup orientation with minimal issues."""
        orientation = generate_cleanup_orientation(
            tmp_path,
            quality_issues=[],
            oversized_files=[],
            lint_errors=0,
        )

        assert "CLEANUP SESSION" in orientation
        assert "GOALS" in orientation


class TestGenerateInitOrientation:
    """Tests for generate_init_orientation function."""

    def test_init_new_mode(self):
        """Test init orientation for new project."""
        orientation = generate_init_orientation(
            spec_content="Build a todo app",
            project_summary="",
            mode="new",
        )

        assert "INITIALIZATION SESSION" in orientation
        assert "Mode: NEW" in orientation
        assert "NEW PROJECT" in orientation
        assert "Build a todo app" in orientation
        assert "REQUIRED OUTPUTS" in orientation

    def test_init_adopt_mode(self):
        """Test init orientation for adopt mode."""
        orientation = generate_init_orientation(
            spec_content="Add new features",
            project_summary="Existing Flask app with 10 endpoints",
            mode="adopt",
        )

        assert "Mode: ADOPT" in orientation
        assert "EXISTING PROJECT SUMMARY" in orientation
        assert "Flask app" in orientation
        assert "mark as passing" in orientation

    def test_init_truncates_long_spec(self):
        """Test that long spec is truncated."""
        long_spec = "x" * 5000

        orientation = generate_init_orientation(
            spec_content=long_spec,
            project_summary="",
            mode="new",
        )

        assert "[truncated]" in orientation


class TestEstimateTokenCount:
    """Tests for estimate_token_count function."""

    def test_estimate_short_text(self):
        """Test estimating tokens for short text."""
        text = "Hello world"
        estimate = estimate_token_count(text)
        # ~4 chars per token, 11 chars = ~2-3 tokens
        assert 2 <= estimate <= 5

    def test_estimate_longer_text(self):
        """Test estimating tokens for longer text."""
        text = "a" * 400
        estimate = estimate_token_count(text)
        # 400 chars / 4 = 100 tokens
        assert estimate == 100


class TestEnsureUnderTokenLimit:
    """Tests for ensure_under_token_limit function."""

    def test_short_text_unchanged(self):
        """Test that short text is unchanged."""
        text = "Short text"
        result = ensure_under_token_limit(text, max_tokens=100)
        assert result == text
        assert "[truncated]" not in result

    def test_long_text_truncated(self):
        """Test that long text is truncated."""
        text = "a" * 5000
        result = ensure_under_token_limit(text, max_tokens=100)
        assert len(result) < 5000
        assert "truncated" in result  # Could be "[truncated]" or "[truncated for token limit]"


class TestGetStructuredOrientation:
    """Tests for get_structured_orientation function."""

    def test_get_structured_data(self, sample_features, sample_state, tmp_path):
        """Test getting structured orientation data."""
        result = get_structured_orientation(
            tmp_path,
            sample_state,
            sample_features,
        )

        assert isinstance(result, OrientationSummary)
        assert result.session_number == 6
        assert "1/3" in result.feature_progress
        assert result.ready_features_count == 1  # Feature 2 is ready
        assert result.blocked_features_count == 1  # Feature 3 is blocked
