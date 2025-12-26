"""Tests for features schema and operations."""

import json
import pytest
from pathlib import Path

from agent_harness.features import (
    Feature,
    FeaturesFile,
    load_features,
    save_features,
    get_next_feature,
    get_feature_by_id,
    get_features_by_status,
    detect_dependency_cycles,
    validate_features,
    mark_feature_complete,
    get_feature_progress,
    get_blocked_features,
    get_ready_features,
)
from agent_harness.exceptions import StateError


@pytest.fixture
def sample_features_file():
    """Create a sample FeaturesFile for testing."""
    return FeaturesFile(
        project="test-project",
        generated_by="test",
        init_mode="new",
        last_updated="2025-01-01T00:00:00Z",
        features=[
            Feature(
                id=1,
                category="core",
                description="Feature one",
                test_file="tests/test_one.py",
                depends_on=[],
                passes=True,
            ),
            Feature(
                id=2,
                category="core",
                description="Feature two",
                test_file="tests/test_two.py",
                depends_on=[1],
                passes=False,
            ),
            Feature(
                id=3,
                category="api",
                description="Feature three",
                test_file="tests/test_three.py",
                depends_on=[1, 2],
                passes=False,
            ),
            Feature(
                id=4,
                category="api",
                description="Feature four",
                test_file="tests/test_four.py",
                depends_on=[],
                passes=False,
            ),
        ],
    )


class TestFeatureDataclass:
    """Test Feature dataclass."""

    def test_valid_feature(self):
        """Valid feature should be created."""
        f = Feature(
            id=1,
            category="core",
            description="Test feature",
            test_file="tests/test.py",
        )
        assert f.id == 1
        assert f.passes is False
        assert f.size_estimate == "medium"

    def test_feature_missing_test_file(self):
        """Feature without test_file should raise error."""
        with pytest.raises(StateError):
            Feature(
                id=1,
                category="core",
                description="Test",
                test_file="",
            )

    def test_feature_missing_description(self):
        """Feature without description should raise error."""
        with pytest.raises(StateError):
            Feature(
                id=1,
                category="core",
                description="",
                test_file="tests/test.py",
            )

    def test_feature_invalid_size_estimate(self):
        """Feature with invalid size_estimate should raise error."""
        with pytest.raises(StateError):
            Feature(
                id=1,
                category="core",
                description="Test",
                test_file="tests/test.py",
                size_estimate="huge",
            )

    def test_feature_invalid_verification_type(self):
        """Feature with invalid verification_type should raise error."""
        with pytest.raises(StateError):
            Feature(
                id=1,
                category="core",
                description="Test",
                test_file="tests/test.py",
                verification_type="invalid",
            )


class TestLoadSaveFeatures:
    """Test loading and saving features files."""

    def test_load_valid_features(self, temp_project_dir):
        """Loading valid features file should work."""
        features_data = {
            "project": "test-project",
            "generated_by": "test",
            "init_mode": "new",
            "last_updated": "2025-01-01T00:00:00Z",
            "features": [
                {
                    "id": 1,
                    "category": "core",
                    "description": "Test feature",
                    "test_file": "tests/test.py",
                }
            ],
        }
        features_path = temp_project_dir / "features.json"
        features_path.write_text(json.dumps(features_data))

        features_file = load_features(features_path)
        assert features_file.project == "test-project"
        assert len(features_file.features) == 1
        assert features_file.features[0].description == "Test feature"

    def test_load_missing_file(self, temp_project_dir):
        """Loading non-existent file should raise error."""
        with pytest.raises(StateError):
            load_features(temp_project_dir / "missing.json")

    def test_load_invalid_json(self, temp_project_dir):
        """Loading invalid JSON should raise error."""
        features_path = temp_project_dir / "features.json"
        features_path.write_text("not valid json")

        with pytest.raises(StateError):
            load_features(features_path)

    def test_save_and_reload(self, temp_project_dir, sample_features_file):
        """Saved features should be reloadable."""
        features_path = temp_project_dir / "features.json"
        save_features(features_path, sample_features_file)

        loaded = load_features(features_path)
        assert loaded.project == sample_features_file.project
        assert len(loaded.features) == len(sample_features_file.features)


class TestGetNextFeature:
    """Test get_next_feature function."""

    def test_get_next_with_dependencies(self, sample_features_file):
        """Should return feature with satisfied dependencies."""
        # Feature 1 passes, so feature 2 should be next
        next_feature = get_next_feature(sample_features_file)
        assert next_feature.id == 2

    def test_get_next_no_dependencies(self, sample_features_file):
        """Should return feature without dependencies if available."""
        # Mark feature 2 as passing
        sample_features_file.features[1].passes = True
        next_feature = get_next_feature(sample_features_file)
        # Feature 3 depends on 1 and 2 (both pass), feature 4 has no deps
        # Order matters - feature 3 comes first in the list
        assert next_feature.id == 3

    def test_get_next_all_complete(self, sample_features_file):
        """Should return None when all features complete."""
        for f in sample_features_file.features:
            f.passes = True

        next_feature = get_next_feature(sample_features_file)
        assert next_feature is None

    def test_get_next_respects_dependencies(self, sample_features_file):
        """Should not return features with unmet dependencies."""
        # Feature 1 is passing, so feature 2 (depends on 1) becomes available
        # Feature 3 depends on 1 and 2, so it's blocked until 2 passes
        # Feature 4 has no dependencies
        # With feature 1 passing, the order should be: 2 first, then 4
        # (because they both have deps satisfied, but 2 comes first)
        next_feature = get_next_feature(sample_features_file)
        assert next_feature.id == 2

        # Mark feature 1 as not passing - now only feature 4 should be available
        sample_features_file.features[0].passes = False
        next_feature = get_next_feature(sample_features_file)
        # Feature 1 has no deps and doesn't pass - it should be first
        assert next_feature.id == 1


class TestFeatureQueries:
    """Test feature query functions."""

    def test_get_feature_by_id(self, sample_features_file):
        """Should find feature by ID."""
        feature = get_feature_by_id(sample_features_file, 2)
        assert feature.description == "Feature two"

    def test_get_feature_by_id_not_found(self, sample_features_file):
        """Should return None for missing ID."""
        feature = get_feature_by_id(sample_features_file, 999)
        assert feature is None

    def test_get_features_by_status_passing(self, sample_features_file):
        """Should return passing features."""
        passing = get_features_by_status(sample_features_file, passes=True)
        assert len(passing) == 1
        assert passing[0].id == 1

    def test_get_features_by_status_pending(self, sample_features_file):
        """Should return pending features."""
        pending = get_features_by_status(sample_features_file, passes=False)
        assert len(pending) == 3


class TestDependencyCycles:
    """Test dependency cycle detection."""

    def test_no_cycles(self, sample_features_file):
        """Should detect no cycles in valid graph."""
        cycles = detect_dependency_cycles(sample_features_file.features)
        assert len(cycles) == 0

    def test_simple_cycle(self):
        """Should detect simple A -> B -> A cycle."""
        features = [
            Feature(id=1, category="core", description="A", test_file="a.py", depends_on=[2]),
            Feature(id=2, category="core", description="B", test_file="b.py", depends_on=[1]),
        ]
        cycles = detect_dependency_cycles(features)
        assert len(cycles) > 0

    def test_self_cycle(self):
        """Should detect self-dependency."""
        features = [
            Feature(id=1, category="core", description="A", test_file="a.py", depends_on=[1]),
        ]
        cycles = detect_dependency_cycles(features)
        assert len(cycles) > 0

    def test_longer_cycle(self):
        """Should detect longer cycles."""
        features = [
            Feature(id=1, category="core", description="A", test_file="a.py", depends_on=[3]),
            Feature(id=2, category="core", description="B", test_file="b.py", depends_on=[1]),
            Feature(id=3, category="core", description="C", test_file="c.py", depends_on=[2]),
        ]
        cycles = detect_dependency_cycles(features)
        assert len(cycles) > 0


class TestValidateFeatures:
    """Test features validation."""

    def test_valid_features(self, sample_features_file):
        """Valid features should pass validation."""
        result = validate_features(sample_features_file)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_duplicate_ids(self):
        """Should detect duplicate IDs."""
        features_file = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2025-01-01",
            features=[
                Feature(id=1, category="core", description="A", test_file="a.py"),
                Feature(id=1, category="core", description="B", test_file="b.py"),
            ],
        )
        result = validate_features(features_file)
        assert result.valid is False
        assert any("Duplicate" in e for e in result.errors)

    def test_invalid_dependencies(self):
        """Should detect invalid dependencies."""
        features_file = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2025-01-01",
            features=[
                Feature(id=1, category="core", description="A", test_file="a.py", depends_on=[99]),
            ],
        )
        result = validate_features(features_file)
        assert result.valid is False
        assert any("non-existent" in e for e in result.errors)

    def test_excessive_verification_steps(self):
        """Should warn about excessive verification steps."""
        features_file = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2025-01-01",
            features=[
                Feature(
                    id=1,
                    category="core",
                    description="A",
                    test_file="a.py",
                    verification_steps=["step"] * 10,
                ),
            ],
        )
        result = validate_features(features_file, max_verification_steps=7)
        assert result.valid is True
        assert len(result.warnings) > 0


class TestFeatureProgress:
    """Test feature progress functions."""

    def test_mark_feature_complete(self, sample_features_file):
        """Should mark feature as complete."""
        assert sample_features_file.features[1].passes is False
        result = mark_feature_complete(sample_features_file, 2, passes=True)
        assert result is True
        assert sample_features_file.features[1].passes is True

    def test_mark_feature_complete_not_found(self, sample_features_file):
        """Should return False for non-existent feature."""
        result = mark_feature_complete(sample_features_file, 999)
        assert result is False

    def test_get_feature_progress(self, sample_features_file):
        """Should return correct progress stats."""
        passing, total, percentage = get_feature_progress(sample_features_file)
        assert passing == 1
        assert total == 4
        assert percentage == 25.0

    def test_get_blocked_features(self, sample_features_file):
        """Should identify blocked features."""
        blocked = get_blocked_features(sample_features_file)
        # Feature 3 is blocked (depends on 1 and 2, only 1 passes)
        assert len(blocked) == 1
        assert blocked[0].id == 3

    def test_get_ready_features(self, sample_features_file):
        """Should identify ready features."""
        ready = get_ready_features(sample_features_file)
        # Features 2 and 4 are ready (deps met or none)
        assert len(ready) == 2
        ready_ids = {f.id for f in ready}
        assert ready_ids == {2, 4}
