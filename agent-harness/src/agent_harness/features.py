"""Features schema and operations for agent-harness."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent_harness.exceptions import StateError


@dataclass
class Feature:
    """A single feature in the features file."""

    id: int
    category: str
    description: str
    test_file: str
    verification_steps: list[str] = field(default_factory=list)
    size_estimate: str = "medium"  # "small", "medium", "large"
    depends_on: list[int] = field(default_factory=list)
    passes: bool = False
    origin: str = "spec"  # "spec", "existing"
    verification_type: str = "automated"  # "automated", "hybrid", "manual"
    note: Optional[str] = None

    def __post_init__(self):
        """Validate feature fields."""
        if not self.test_file:
            raise StateError(f"Feature {self.id} missing required test_file")
        if not self.description:
            raise StateError(f"Feature {self.id} missing required description")
        if self.size_estimate not in ("small", "medium", "large"):
            raise StateError(
                f"Feature {self.id} has invalid size_estimate: {self.size_estimate}"
            )
        if self.verification_type not in ("automated", "hybrid", "manual"):
            raise StateError(
                f"Feature {self.id} has invalid verification_type: {self.verification_type}"
            )


@dataclass
class FeaturesFile:
    """Complete features file structure."""

    project: str
    generated_by: str
    init_mode: str  # "new" or "adopt"
    last_updated: str
    features: list[Feature] = field(default_factory=list)

    def __post_init__(self):
        """Validate features file."""
        if not self.project:
            raise StateError("Features file missing required 'project' field")
        if not self.generated_by:
            raise StateError("Features file missing required 'generated_by' field")


@dataclass
class ValidationResult:
    """Result of validating features."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _dict_to_feature(data: dict) -> Feature:
    """Convert a dictionary to a Feature dataclass."""
    return Feature(
        id=data["id"],
        category=data.get("category", "uncategorized"),
        description=data["description"],
        test_file=data["test_file"],
        verification_steps=data.get("verification_steps", []),
        size_estimate=data.get("size_estimate", "medium"),
        depends_on=data.get("depends_on", []),
        passes=data.get("passes", False),
        origin=data.get("origin", "spec"),
        verification_type=data.get("verification_type", "automated"),
        note=data.get("note"),
    )


def _feature_to_dict(feature: Feature) -> dict:
    """Convert a Feature dataclass to a dictionary."""
    return asdict(feature)


def load_features(path: Path) -> FeaturesFile:
    """
    Load features from a features.json file.

    Args:
        path: Path to features.json file.

    Returns:
        FeaturesFile object.

    Raises:
        StateError: If file is missing or invalid.
    """
    if not path.exists():
        raise StateError(f"Features file not found: {path}")

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise StateError(f"Invalid JSON in features file: {e}")

    # Parse features
    features = []
    for feature_data in data.get("features", []):
        try:
            features.append(_dict_to_feature(feature_data))
        except KeyError as e:
            raise StateError(f"Feature missing required field: {e}")

    return FeaturesFile(
        project=data.get("project", "unknown"),
        generated_by=data.get("generated_by", "unknown"),
        init_mode=data.get("init_mode", "new"),
        last_updated=data.get("last_updated", datetime.now(timezone.utc).isoformat()),
        features=features,
    )


def save_features(path: Path, features_file: FeaturesFile) -> None:
    """
    Save features to a features.json file.

    Args:
        path: Path to features.json file.
        features_file: FeaturesFile object to save.
    """
    # Update timestamp
    features_file.last_updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    data = {
        "project": features_file.project,
        "generated_by": features_file.generated_by,
        "init_mode": features_file.init_mode,
        "last_updated": features_file.last_updated,
        "features": [_feature_to_dict(f) for f in features_file.features],
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_next_feature(features_file: FeaturesFile) -> Optional[Feature]:
    """
    Get the next feature to work on.

    Returns the first non-passing feature whose dependencies are all satisfied.

    Args:
        features_file: FeaturesFile object.

    Returns:
        Next Feature to work on, or None if all features are complete.
    """
    passing_ids = {f.id for f in features_file.features if f.passes}

    for feature in features_file.features:
        if feature.passes:
            continue
        # Check if all dependencies are satisfied
        if all(dep_id in passing_ids for dep_id in feature.depends_on):
            return feature

    return None


def get_feature_by_id(features_file: FeaturesFile, feature_id: int) -> Optional[Feature]:
    """
    Get a feature by its ID.

    Args:
        features_file: FeaturesFile object.
        feature_id: ID of the feature to find.

    Returns:
        Feature with matching ID, or None if not found.
    """
    for feature in features_file.features:
        if feature.id == feature_id:
            return feature
    return None


def get_features_by_status(
    features_file: FeaturesFile, passes: bool
) -> list[Feature]:
    """
    Get features by their pass/fail status.

    Args:
        features_file: FeaturesFile object.
        passes: True for passing features, False for pending.

    Returns:
        List of features matching the status.
    """
    return [f for f in features_file.features if f.passes == passes]


def get_features_by_category(
    features_file: FeaturesFile, category: str
) -> list[Feature]:
    """
    Get features by category.

    Args:
        features_file: FeaturesFile object.
        category: Category to filter by.

    Returns:
        List of features in the category.
    """
    return [f for f in features_file.features if f.category == category]


def detect_dependency_cycles(features: list[Feature]) -> list[list[int]]:
    """
    Detect dependency cycles in features.

    Uses depth-first search to find cycles.

    Args:
        features: List of Feature objects.

    Returns:
        List of cycles, where each cycle is a list of feature IDs.
    """
    # Build adjacency list
    adj = {f.id: f.depends_on for f in features}
    all_ids = set(adj.keys())

    # Track visited state
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {fid: WHITE for fid in all_ids}
    parent = {fid: None for fid in all_ids}
    cycles = []

    def dfs(node: int, path: list[int]) -> None:
        color[node] = GRAY

        for neighbor in adj.get(node, []):
            if neighbor not in all_ids:
                continue  # Skip invalid dependencies

            if color[neighbor] == GRAY:
                # Found a cycle - extract it
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
            elif color[neighbor] == WHITE:
                dfs(neighbor, path + [neighbor])

        color[node] = BLACK

    for fid in all_ids:
        if color[fid] == WHITE:
            dfs(fid, [fid])

    return cycles


def validate_features(
    features_file: FeaturesFile, max_verification_steps: int = 7
) -> ValidationResult:
    """
    Validate features file structure and content.

    Args:
        features_file: FeaturesFile object to validate.
        max_verification_steps: Max allowed verification steps before warning.

    Returns:
        ValidationResult with errors and warnings.
    """
    errors = []
    warnings = []

    # Check for duplicate IDs
    ids = [f.id for f in features_file.features]
    duplicates = [fid for fid in ids if ids.count(fid) > 1]
    if duplicates:
        errors.append(f"Duplicate feature IDs: {set(duplicates)}")

    # Check for dependency cycles
    cycles = detect_dependency_cycles(features_file.features)
    if cycles:
        for cycle in cycles:
            errors.append(f"Dependency cycle detected: {' -> '.join(map(str, cycle))}")

    # Check for invalid dependencies
    valid_ids = set(ids)
    for feature in features_file.features:
        invalid_deps = [d for d in feature.depends_on if d not in valid_ids]
        if invalid_deps:
            errors.append(
                f"Feature {feature.id} depends on non-existent features: {invalid_deps}"
            )

    # Check for missing test files (warning)
    for feature in features_file.features:
        if not feature.test_file:
            errors.append(f"Feature {feature.id} missing test_file")

    # Check for excessive verification steps (warning)
    for feature in features_file.features:
        if len(feature.verification_steps) > max_verification_steps:
            warnings.append(
                f"Feature {feature.id} has {len(feature.verification_steps)} verification steps "
                f"(max recommended: {max_verification_steps})"
            )

    # Check for self-dependencies (error)
    for feature in features_file.features:
        if feature.id in feature.depends_on:
            errors.append(f"Feature {feature.id} depends on itself")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def mark_feature_complete(
    features_file: FeaturesFile, feature_id: int, passes: bool = True
) -> bool:
    """
    Mark a feature as complete or incomplete.

    Args:
        features_file: FeaturesFile object.
        feature_id: ID of the feature to update.
        passes: True to mark as passing, False for pending.

    Returns:
        True if feature was found and updated, False otherwise.
    """
    feature = get_feature_by_id(features_file, feature_id)
    if feature:
        feature.passes = passes
        return True
    return False


def get_feature_progress(features_file: FeaturesFile) -> tuple[int, int, float]:
    """
    Get feature progress statistics.

    Returns:
        Tuple of (passing_count, total_count, percentage).
    """
    total = len(features_file.features)
    passing = len([f for f in features_file.features if f.passes])
    percentage = (passing / total * 100) if total > 0 else 0.0
    return passing, total, percentage


def get_blocked_features(features_file: FeaturesFile) -> list[Feature]:
    """
    Get features that are blocked by unmet dependencies.

    Returns:
        List of features with unmet dependencies.
    """
    passing_ids = {f.id for f in features_file.features if f.passes}
    blocked = []

    for feature in features_file.features:
        if feature.passes:
            continue
        if feature.depends_on and not all(d in passing_ids for d in feature.depends_on):
            blocked.append(feature)

    return blocked


def get_ready_features(features_file: FeaturesFile) -> list[Feature]:
    """
    Get features that are ready to be worked on (not passing, dependencies met).

    Returns:
        List of features ready for implementation.
    """
    passing_ids = {f.id for f in features_file.features if f.passes}
    ready = []

    for feature in features_file.features:
        if feature.passes:
            continue
        if all(d in passing_ids for d in feature.depends_on):
            ready.append(feature)

    return ready
