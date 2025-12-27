"""Tests for health module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from agent_harness.health import (
    ProjectHealth,
    calculate_health,
    calculate_quick_health,
    get_health_color,
    get_score_color,
    format_health_report,
    get_health_recommendations,
    WEIGHTS,
)
from agent_harness.features import Feature, FeaturesFile
from agent_harness.file_sizes import FileSizeTracker, FileInfo
from agent_harness.config import Config


@pytest.fixture
def sample_features():
    """Create sample features file."""
    return FeaturesFile(
        project="test",
        generated_by="test",
        init_mode="new",
        last_updated="2024-01-01",
        features=[
            Feature(id=1, category="core", description="Feature 1", test_file="tests/test_1.py", passes=True),
            Feature(id=2, category="core", description="Feature 2", test_file="tests/test_2.py", passes=True),
            Feature(id=3, category="api", description="Feature 3", test_file="tests/test_3.py", passes=False),
            Feature(id=4, category="api", description="Feature 4", test_file="tests/test_4.py", passes=False),
        ],
    )


@pytest.fixture
def sample_file_tracker():
    """Create sample file size tracker."""
    tracker = FileSizeTracker(session=1)
    tracker.files = {
        "module1.py": FileInfo(lines=100, session_added=1),
        "module2.py": FileInfo(lines=200, session_added=1),
        "module3.py": FileInfo(lines=600, session_added=1),  # Oversized
    }
    return tracker


class TestProjectHealth:
    """Tests for ProjectHealth dataclass."""

    def test_project_health_creation(self):
        """Test creating a ProjectHealth object."""
        health = ProjectHealth(
            feature_completion=0.75,
            test_pass_rate=0.90,
            lint_score=0.85,
            file_health=0.95,
            overall=0.86,
            status="GOOD",
        )

        assert health.feature_completion == 0.75
        assert health.test_pass_rate == 0.90
        assert health.lint_score == 0.85
        assert health.file_health == 0.95
        assert health.overall == 0.86
        assert health.status == "GOOD"

    def test_project_health_with_raw_metrics(self):
        """Test ProjectHealth with raw metrics."""
        health = ProjectHealth(
            feature_completion=0.50,
            test_pass_rate=0.80,
            lint_score=0.90,
            file_health=1.0,
            overall=0.75,
            status="FAIR",
            features_passing=5,
            features_total=10,
            tests_passing=80,
            tests_total=100,
            lint_errors=5,
            lint_warnings=10,
            oversized_files=0,
            total_files=20,
        )

        assert health.features_passing == 5
        assert health.features_total == 10
        assert health.tests_passing == 80
        assert health.tests_total == 100


class TestCalculateQuickHealth:
    """Tests for calculate_quick_health function."""

    def test_quick_health_with_features(self, sample_features, sample_file_tracker):
        """Test quick health calculation with features and file tracker."""
        health = calculate_quick_health(
            sample_features,
            sample_file_tracker,
            max_file_lines=500,
        )

        assert health.feature_completion == 0.5  # 2/4 passing
        assert health.features_passing == 2
        assert health.features_total == 4
        assert health.file_health < 1.0  # Has oversized files
        assert health.oversized_files == 1

    def test_quick_health_without_file_tracker(self, sample_features):
        """Test quick health without file tracker."""
        health = calculate_quick_health(sample_features, None)

        assert health.feature_completion == 0.5
        assert health.file_health == 1.0  # Default when no tracker

    def test_quick_health_status_good(self):
        """Test GOOD status when completion is high."""
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[
                Feature(id=1, category="core", description="F1", test_file="t1.py", passes=True),
                Feature(id=2, category="core", description="F2", test_file="t2.py", passes=True),
                Feature(id=3, category="core", description="F3", test_file="t3.py", passes=True),
                Feature(id=4, category="core", description="F4", test_file="t4.py", passes=True),
            ],
        )

        health = calculate_quick_health(features, None)
        assert health.status == "GOOD"
        assert health.overall >= 0.8

    def test_quick_health_status_poor(self):
        """Test POOR status when completion is low."""
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[
                Feature(id=1, category="core", description="F1", test_file="t1.py", passes=False),
                Feature(id=2, category="core", description="F2", test_file="t2.py", passes=False),
                Feature(id=3, category="core", description="F3", test_file="t3.py", passes=False),
                Feature(id=4, category="core", description="F4", test_file="t4.py", passes=False),
            ],
        )

        health = calculate_quick_health(features, None)
        assert health.status == "POOR"
        assert health.overall < 0.5


class TestGetColors:
    """Tests for color helper functions."""

    def test_health_color_good(self):
        """Test green color for GOOD status."""
        assert get_health_color("GOOD") == "green"

    def test_health_color_fair(self):
        """Test yellow color for FAIR status."""
        assert get_health_color("FAIR") == "yellow"

    def test_health_color_poor(self):
        """Test red color for POOR status."""
        assert get_health_color("POOR") == "red"

    def test_health_color_unknown(self):
        """Test default color for unknown status."""
        assert get_health_color("UNKNOWN") == "white"

    def test_score_color_high(self):
        """Test green color for high scores."""
        assert get_score_color(0.9) == "green"
        assert get_score_color(0.8) == "green"

    def test_score_color_medium(self):
        """Test yellow color for medium scores."""
        assert get_score_color(0.7) == "yellow"
        assert get_score_color(0.5) == "yellow"

    def test_score_color_low(self):
        """Test red color for low scores."""
        assert get_score_color(0.4) == "red"
        assert get_score_color(0.0) == "red"


class TestFormatHealthReport:
    """Tests for format_health_report function."""

    def test_format_health_report(self):
        """Test formatting a health report."""
        health = ProjectHealth(
            feature_completion=0.75,
            test_pass_rate=0.90,
            lint_score=0.85,
            file_health=0.95,
            overall=0.86,
            status="GOOD",
            features_passing=6,
            features_total=8,
            tests_passing=90,
            tests_total=100,
            lint_errors=5,
            lint_warnings=10,
            oversized_files=1,
            total_files=20,
        )

        report = format_health_report(health)

        assert "GOOD" in report
        assert "86%" in report
        assert "75%" in report  # Feature completion
        assert "90%" in report  # Test pass rate
        assert "6/8" in report  # Features

    def test_format_health_report_with_oversized_files(self):
        """Test report includes oversized files."""
        health = ProjectHealth(
            feature_completion=0.50,
            test_pass_rate=0.80,
            lint_score=0.90,
            file_health=0.70,
            overall=0.70,
            status="FAIR",
            oversized_files=3,
            oversized_file_list=["big1.py", "big2.py", "big3.py"],
        )

        report = format_health_report(health)

        assert "Oversized Files" in report
        assert "big1.py" in report


class TestGetHealthRecommendations:
    """Tests for get_health_recommendations function."""

    def test_recommendations_for_low_feature_completion(self):
        """Test recommendations when feature completion is low."""
        health = ProjectHealth(
            feature_completion=0.30,
            test_pass_rate=1.0,
            lint_score=1.0,
            file_health=1.0,
            overall=0.60,
            status="FAIR",
            features_passing=3,
            features_total=10,
        )

        recs = get_health_recommendations(health)

        assert any("features" in r.lower() for r in recs)

    def test_recommendations_for_failing_tests(self):
        """Test recommendations when tests are failing."""
        health = ProjectHealth(
            feature_completion=1.0,
            test_pass_rate=0.70,
            lint_score=1.0,
            file_health=1.0,
            overall=0.80,
            status="GOOD",
            tests_passing=70,
            tests_total=100,
        )

        recs = get_health_recommendations(health)

        assert any("test" in r.lower() for r in recs)

    def test_recommendations_for_lint_errors(self):
        """Test recommendations when there are lint errors."""
        health = ProjectHealth(
            feature_completion=1.0,
            test_pass_rate=1.0,
            lint_score=0.80,
            file_health=1.0,
            overall=0.90,
            status="GOOD",
            lint_errors=10,
            lint_warnings=5,
        )

        recs = get_health_recommendations(health)

        assert any("lint" in r.lower() for r in recs)

    def test_recommendations_for_oversized_files(self):
        """Test recommendations when there are oversized files."""
        health = ProjectHealth(
            feature_completion=1.0,
            test_pass_rate=1.0,
            lint_score=1.0,
            file_health=0.80,
            overall=0.90,
            status="GOOD",
            oversized_files=5,
        )

        recs = get_health_recommendations(health)

        assert any("oversized" in r.lower() for r in recs)

    def test_no_recommendations_when_healthy(self):
        """Test positive message when everything is healthy."""
        health = ProjectHealth(
            feature_completion=1.0,
            test_pass_rate=1.0,
            lint_score=1.0,
            file_health=1.0,
            overall=1.0,
            status="GOOD",
            lint_errors=0,
            lint_warnings=0,
            oversized_files=0,
        )

        recs = get_health_recommendations(health)

        assert len(recs) == 1
        assert "good" in recs[0].lower()


class TestWeights:
    """Tests for health score weights."""

    def test_weights_sum_to_one(self):
        """Test that weights sum to 1.0."""
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_weights_positive(self):
        """Test that all weights are positive."""
        for weight in WEIGHTS.values():
            assert weight > 0

    def test_required_weights_exist(self):
        """Test that required weight keys exist."""
        assert "feature_completion" in WEIGHTS
        assert "test_pass_rate" in WEIGHTS
        assert "lint_score" in WEIGHTS
        assert "file_health" in WEIGHTS
