"""Health calculation for agent-harness.

Calculates a composite project health score based on:
- Feature completion rate
- Test pass rate
- Lint score
- File size health
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent_harness.config import Config
from agent_harness.features import FeaturesFile, get_feature_progress
from agent_harness.file_sizes import (
    FileSizeTracker,
    get_oversized_files,
    get_file_count,
    load_file_sizes,
    scan_file_sizes,
    update_tracker_from_scan,
)
from agent_harness.lint import LintResult, run_lint
from agent_harness.test_runner import TestRunResult


@dataclass
class ProjectHealth:
    """Project health metrics."""

    feature_completion: float  # 0.0 - 1.0
    test_pass_rate: float  # 0.0 - 1.0
    lint_score: float  # 0.0 - 1.0 (1.0 = no issues)
    file_health: float  # 0.0 - 1.0 (1.0 = no oversized files)
    overall: float  # 0.0 - 1.0 weighted average
    status: str  # "GOOD", "FAIR", "POOR"

    # Raw metrics
    features_passing: int = 0
    features_total: int = 0
    tests_passing: int = 0
    tests_total: int = 0
    lint_errors: int = 0
    lint_warnings: int = 0
    oversized_files: int = 0
    total_files: int = 0

    # Details
    test_result: Optional[TestRunResult] = None
    lint_result: Optional[LintResult] = None
    oversized_file_list: list[str] = field(default_factory=list)


# Weight configuration for overall score
WEIGHTS = {
    "feature_completion": 0.30,
    "test_pass_rate": 0.35,
    "lint_score": 0.20,
    "file_health": 0.15,
}


async def calculate_health(
    project_dir: Path,
    config: Config,
    features: Optional[FeaturesFile] = None,
    run_full_tests: bool = True,
    run_full_lint: bool = True,
) -> ProjectHealth:
    """
    Calculate comprehensive project health (async).

    Args:
        project_dir: Path to the project directory.
        config: Project configuration.
        features: Optional pre-loaded FeaturesFile.
        run_full_tests: Whether to run full test suite.
        run_full_lint: Whether to run full lint check.

    Returns:
        ProjectHealth object with all metrics.
    """
    from agent_harness.test_runner import run_tests_async

    # Calculate feature completion
    feature_completion = 0.0
    features_passing = 0
    features_total = 0

    if features and features.features:
        features_passing, features_total, feature_pct = get_feature_progress(features)
        feature_completion = features_passing / features_total if features_total > 0 else 0.0

    # Calculate test pass rate
    test_pass_rate = 0.0
    tests_passing = 0
    tests_total = 0
    test_result = None

    if run_full_tests:
        test_result = await run_tests_async(project_dir, timeout=config.testing.timeout)
        tests_passing = len(test_result.passed)
        tests_total = test_result.total
        test_pass_rate = tests_passing / tests_total if tests_total > 0 else 1.0

    # Calculate lint score
    lint_score = 1.0
    lint_errors = 0
    lint_warnings = 0
    lint_result = None

    if run_full_lint:
        lint_result = run_lint(project_dir, config.testing.lint_command)
        lint_errors = lint_result.errors
        lint_warnings = lint_result.warnings

        # Score decreases with issues (errors count more than warnings)
        issue_penalty = (lint_errors * 2 + lint_warnings * 0.5) / 100
        lint_score = max(0.0, 1.0 - issue_penalty)

    # Calculate file health
    file_health = 1.0
    oversized_files = 0
    total_files = 0
    oversized_file_list = []

    harness_dir = project_dir / ".harness"
    file_sizes_path = harness_dir / "file_sizes.json"
    src_dir = project_dir / config.project.source_dir

    if src_dir.exists():
        # Load or create tracker
        tracker = load_file_sizes(file_sizes_path)
        tracker = update_tracker_from_scan(tracker, src_dir, tracker.session)

        total_files = get_file_count(tracker)
        oversized_file_list = get_oversized_files(tracker, config.quality.max_file_lines)
        oversized_files = len(oversized_file_list)

        # Score based on percentage of oversized files
        if total_files > 0:
            oversized_pct = oversized_files / total_files
            file_health = max(0.0, 1.0 - (oversized_pct * 2))  # 50% oversized = 0.0

    # Calculate overall weighted score
    overall = (
        feature_completion * WEIGHTS["feature_completion"] +
        test_pass_rate * WEIGHTS["test_pass_rate"] +
        lint_score * WEIGHTS["lint_score"] +
        file_health * WEIGHTS["file_health"]
    )

    # Determine status
    if overall >= 0.8:
        status = "GOOD"
    elif overall >= 0.5:
        status = "FAIR"
    else:
        status = "POOR"

    return ProjectHealth(
        feature_completion=feature_completion,
        test_pass_rate=test_pass_rate,
        lint_score=lint_score,
        file_health=file_health,
        overall=overall,
        status=status,
        features_passing=features_passing,
        features_total=features_total,
        tests_passing=tests_passing,
        tests_total=tests_total,
        lint_errors=lint_errors,
        lint_warnings=lint_warnings,
        oversized_files=oversized_files,
        total_files=total_files,
        test_result=test_result,
        lint_result=lint_result,
        oversized_file_list=oversized_file_list,
    )


def calculate_quick_health(
    features: FeaturesFile,
    file_tracker: Optional[FileSizeTracker] = None,
    max_file_lines: int = 500,
) -> ProjectHealth:
    """
    Calculate a quick health score without running tests/lint.

    Useful for status displays where full health check is too slow.

    Args:
        features: FeaturesFile object.
        file_tracker: Optional pre-loaded FileSizeTracker.
        max_file_lines: Max lines threshold.

    Returns:
        ProjectHealth with feature and file metrics only.
    """
    # Calculate feature completion
    features_passing, features_total, _ = get_feature_progress(features)
    feature_completion = features_passing / features_total if features_total > 0 else 0.0

    # Calculate file health if tracker provided
    file_health = 1.0
    oversized_files = 0
    total_files = 0
    oversized_file_list = []

    if file_tracker:
        total_files = get_file_count(file_tracker)
        oversized_file_list = get_oversized_files(file_tracker, max_file_lines)
        oversized_files = len(oversized_file_list)

        if total_files > 0:
            oversized_pct = oversized_files / total_files
            file_health = max(0.0, 1.0 - (oversized_pct * 2))

    # Simplified overall score (only using feature and file health)
    overall = (feature_completion * 0.7 + file_health * 0.3)

    if overall >= 0.8:
        status = "GOOD"
    elif overall >= 0.5:
        status = "FAIR"
    else:
        status = "POOR"

    return ProjectHealth(
        feature_completion=feature_completion,
        test_pass_rate=1.0,  # Unknown
        lint_score=1.0,  # Unknown
        file_health=file_health,
        overall=overall,
        status=status,
        features_passing=features_passing,
        features_total=features_total,
        tests_passing=0,
        tests_total=0,
        lint_errors=0,
        lint_warnings=0,
        oversized_files=oversized_files,
        total_files=total_files,
        oversized_file_list=oversized_file_list,
    )


def get_health_color(status: str) -> str:
    """
    Get the color to use for a health status.

    Args:
        status: Health status string.

    Returns:
        Color name for Rich.
    """
    colors = {
        "GOOD": "green",
        "FAIR": "yellow",
        "POOR": "red",
    }
    return colors.get(status, "white")


def get_score_color(score: float) -> str:
    """
    Get the color to use for a numeric score.

    Args:
        score: Score between 0.0 and 1.0.

    Returns:
        Color name for Rich.
    """
    if score >= 0.8:
        return "green"
    elif score >= 0.5:
        return "yellow"
    else:
        return "red"


def format_health_report(health: ProjectHealth) -> str:
    """
    Format a health report for plain text display.

    Args:
        health: ProjectHealth object.

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append(f"Project Health: {health.status} ({health.overall:.0%})")
    lines.append("-" * 40)
    lines.append("")
    lines.append("Component Scores:")
    lines.append(f"  Feature Completion: {health.feature_completion:.0%} ({health.features_passing}/{health.features_total})")
    lines.append(f"  Test Pass Rate:     {health.test_pass_rate:.0%} ({health.tests_passing}/{health.tests_total})")
    lines.append(f"  Lint Score:         {health.lint_score:.0%} ({health.lint_errors} errors, {health.lint_warnings} warnings)")
    lines.append(f"  File Health:        {health.file_health:.0%} ({health.oversized_files} oversized files)")
    lines.append("")
    lines.append(f"Overall Score: {health.overall:.0%}")

    if health.oversized_file_list:
        lines.append("")
        lines.append("Oversized Files:")
        for path in health.oversized_file_list[:5]:
            lines.append(f"  - {path}")
        if len(health.oversized_file_list) > 5:
            lines.append(f"  ... and {len(health.oversized_file_list) - 5} more")

    return "\n".join(lines)


def get_health_recommendations(health: ProjectHealth) -> list[str]:
    """
    Get recommendations for improving health.

    Args:
        health: ProjectHealth object.

    Returns:
        List of recommendation strings.
    """
    recommendations = []

    if health.feature_completion < 0.5:
        remaining = health.features_total - health.features_passing
        recommendations.append(f"Complete more features ({remaining} remaining)")

    if health.test_pass_rate < 1.0 and health.tests_total > 0:
        failing = health.tests_total - health.tests_passing
        recommendations.append(f"Fix failing tests ({failing} failing)")

    if health.lint_errors > 0:
        recommendations.append(f"Fix lint errors ({health.lint_errors} errors)")

    if health.lint_warnings > 10:
        recommendations.append(f"Address lint warnings ({health.lint_warnings} warnings)")

    if health.oversized_files > 0:
        recommendations.append(f"Refactor oversized files ({health.oversized_files} files)")

    if not recommendations:
        recommendations.append("Project health is good! Keep up the good work.")

    return recommendations
