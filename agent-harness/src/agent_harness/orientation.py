"""Orientation generator for agent-harness.

Generates compact orientation summaries for agent prompts.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agent_harness.features import (
    FeaturesFile,
    Feature,
    get_next_feature,
    get_feature_progress,
    get_ready_features,
    get_blocked_features,
)
from agent_harness.progress import (
    ProgressEntry,
    get_last_entry,
    get_recent_decisions,
)
from agent_harness.state import SessionState


@dataclass
class OrientationSummary:
    """Structured orientation summary."""

    session_number: int
    total_sessions: int
    feature_progress: str
    current_feature: Optional[Feature]
    next_feature: Optional[Feature]
    recent_decisions: list[str]
    current_state: str
    last_session_summary: str
    blocked_features_count: int
    ready_features_count: int


def generate_orientation_summary(
    project_dir: Path,
    session_state: SessionState,
    features: FeaturesFile,
    progress_entries: Optional[list[ProgressEntry]] = None,
) -> str:
    """
    Generate a compact orientation summary for agent prompts.

    This summary helps the agent understand:
    - Where we are in the project
    - What was done last session
    - What to do next
    - Recent decisions to maintain consistency

    Args:
        project_dir: Path to the project directory.
        session_state: Current session state.
        features: Features file.
        progress_entries: Optional list of progress entries.

    Returns:
        Formatted orientation summary string (under 1000 tokens).
    """
    lines = []

    # Session info
    lines.append(f"SESSION {session_state.last_session + 1}")
    lines.append("")

    # Feature progress
    passing, total, percentage = get_feature_progress(features)
    lines.append(f"PROGRESS: {passing}/{total} features complete ({percentage:.0f}%)")

    # Current feature info
    if session_state.current_feature is not None:
        from agent_harness.features import get_feature_by_id

        current = get_feature_by_id(features, session_state.current_feature)
        if current:
            lines.append("")
            lines.append(f"CURRENT FEATURE: #{current.id} - {current.description}")
            lines.append(f"Test file: {current.test_file}")
            if current.verification_steps:
                lines.append(f"Verification: {len(current.verification_steps)} steps")

    # Next feature
    next_feature = get_next_feature(features)
    if next_feature and (
        session_state.current_feature is None
        or next_feature.id != session_state.current_feature
    ):
        lines.append("")
        lines.append(f"NEXT FEATURE: #{next_feature.id} - {next_feature.description}")
        lines.append(f"Size: {next_feature.size_estimate}")
        if next_feature.depends_on:
            lines.append(f"Depends on: {next_feature.depends_on}")

    # Blocked and ready features
    blocked = get_blocked_features(features)
    ready = get_ready_features(features)
    if blocked or len(ready) > 1:
        lines.append("")
        lines.append(f"Ready features: {len(ready)}, Blocked: {len(blocked)}")

    # Last session summary
    if progress_entries and len(progress_entries) > 0:
        last_entry = progress_entries[-1]
        lines.append("")
        lines.append("LAST SESSION:")
        if last_entry.what_done:
            for item in last_entry.what_done[:3]:
                lines.append(f"  - {item}")
            if len(last_entry.what_done) > 3:
                lines.append(f"  ... and {len(last_entry.what_done) - 3} more items")

        if last_entry.current_state:
            lines.append(f"State: {last_entry.current_state}")

    # Recent decisions
    if progress_entries:
        decisions = []
        for entry in progress_entries[-3:]:
            decisions.extend(entry.decisions)

        if decisions:
            lines.append("")
            lines.append("RECENT DECISIONS:")
            for decision in decisions[-5:]:
                lines.append(f"  - {decision}")

    # Session status
    if session_state.status != "complete":
        lines.append("")
        lines.append(f"STATUS: {session_state.status}")
        if session_state.termination_reason:
            lines.append(f"Reason: {session_state.termination_reason}")

    # Stuck warning
    if session_state.stuck_count > 0:
        lines.append("")
        lines.append(f"WARNING: Stuck count = {session_state.stuck_count}")

    return "\n".join(lines)


def generate_continuation_details(
    feature: Feature,
    last_entry: Optional[ProgressEntry],
) -> str:
    """
    Generate details for a continuation session.

    Args:
        feature: Feature being continued.
        last_entry: Last progress entry.

    Returns:
        Continuation details string.
    """
    lines = []

    lines.append(f"CONTINUING FEATURE #{feature.id}: {feature.description}")
    lines.append("")

    if last_entry:
        lines.append("PREVIOUS PROGRESS:")
        if last_entry.what_done:
            for item in last_entry.what_done:
                lines.append(f"  [x] {item}")

        if last_entry.current_state:
            lines.append("")
            lines.append(f"LEFT OFF AT: {last_entry.current_state}")

        if last_entry.decisions:
            lines.append("")
            lines.append("DECISIONS MADE:")
            for decision in last_entry.decisions:
                lines.append(f"  - {decision}")

    lines.append("")
    lines.append("REMAINING VERIFICATION STEPS:")
    for i, step in enumerate(feature.verification_steps, 1):
        lines.append(f"  {i}. {step}")

    return "\n".join(lines)


def generate_cleanup_orientation(
    project_dir: Path,
    quality_issues: list[str],
    oversized_files: list[tuple[str, int]],
    lint_errors: int,
) -> str:
    """
    Generate orientation for a cleanup session.

    Args:
        project_dir: Path to the project directory.
        quality_issues: List of quality issues to address.
        oversized_files: List of (file_path, line_count) tuples.
        lint_errors: Number of lint errors.

    Returns:
        Cleanup orientation string.
    """
    lines = []

    lines.append("CLEANUP SESSION")
    lines.append("")
    lines.append("Focus on code quality without adding new features.")
    lines.append("")

    if quality_issues:
        lines.append("QUALITY ISSUES:")
        for issue in quality_issues[:10]:
            lines.append(f"  - {issue}")
        if len(quality_issues) > 10:
            lines.append(f"  ... and {len(quality_issues) - 10} more")
        lines.append("")

    if oversized_files:
        lines.append("OVERSIZED FILES (consider refactoring):")
        for file_path, line_count in oversized_files[:5]:
            lines.append(f"  - {file_path}: {line_count} lines")
        lines.append("")

    if lint_errors > 0:
        lines.append(f"LINT ERRORS: {lint_errors}")
        lines.append("Run lint and fix issues.")
        lines.append("")

    lines.append("GOALS:")
    lines.append("  1. Fix lint errors")
    lines.append("  2. Refactor oversized files")
    lines.append("  3. Improve code organization")
    lines.append("  4. Add missing documentation")
    lines.append("")
    lines.append("Do NOT add new features in this session.")

    return "\n".join(lines)


def generate_init_orientation(
    spec_content: str,
    project_summary: str,
    mode: str,
) -> str:
    """
    Generate orientation for initialization session.

    Args:
        spec_content: Content of the spec file.
        project_summary: Summary of existing project (for adopt mode).
        mode: "new" or "adopt".

    Returns:
        Init orientation string.
    """
    lines = []

    lines.append("INITIALIZATION SESSION")
    lines.append("")
    lines.append(f"Mode: {mode.upper()}")
    lines.append("")

    if mode == "adopt":
        lines.append("EXISTING PROJECT SUMMARY:")
        lines.append(project_summary)
        lines.append("")
        lines.append("Analyze existing code and create features.json based on:")
        lines.append("  1. Existing functionality (mark as passing)")
        lines.append("  2. New features from spec (mark as not passing)")
    else:
        lines.append("NEW PROJECT")
        lines.append("Create features.json based on spec, all marked as not passing.")

    lines.append("")
    lines.append("SPECIFICATION:")
    lines.append("-" * 40)
    # Truncate spec if too long
    if len(spec_content) > 2000:
        lines.append(spec_content[:2000])
        lines.append("... [truncated]")
    else:
        lines.append(spec_content)
    lines.append("-" * 40)

    lines.append("")
    lines.append("REQUIRED OUTPUTS:")
    lines.append("  1. features.json with all features")
    lines.append("  2. init.sh setup script")
    lines.append("  3. reset.sh reset script")
    lines.append("  4. Initial claude-progress.txt entry")

    return "\n".join(lines)


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for text.

    Uses rough heuristic of ~4 characters per token.

    Args:
        text: Text to estimate.

    Returns:
        Estimated token count.
    """
    return len(text) // 4


def ensure_under_token_limit(text: str, max_tokens: int = 1000) -> str:
    """
    Truncate text to stay under token limit.

    Args:
        text: Text to truncate.
        max_tokens: Maximum tokens allowed.

    Returns:
        Truncated text if necessary.
    """
    estimated = estimate_token_count(text)
    if estimated <= max_tokens:
        return text

    # Calculate approximate character limit
    char_limit = max_tokens * 4

    # Find a good break point
    truncated = text[:char_limit]
    last_newline = truncated.rfind("\n")
    if last_newline > char_limit * 0.8:
        truncated = truncated[:last_newline]

    return truncated + "\n... [truncated for token limit]"


def get_structured_orientation(
    project_dir: Path,
    session_state: SessionState,
    features: FeaturesFile,
    progress_path: Optional[Path] = None,
) -> OrientationSummary:
    """
    Get structured orientation data.

    Args:
        project_dir: Path to the project directory.
        session_state: Current session state.
        features: Features file.
        progress_path: Path to progress file.

    Returns:
        OrientationSummary with structured data.
    """
    from agent_harness.features import get_feature_by_id

    passing, total, percentage = get_feature_progress(features)

    # Get current and next features
    current_feature = None
    if session_state.current_feature is not None:
        current_feature = get_feature_by_id(features, session_state.current_feature)

    next_feature = get_next_feature(features)

    # Get progress entries
    progress_entries = []
    recent_decisions = []
    last_session_summary = ""

    if progress_path and progress_path.exists():
        from agent_harness.progress import parse_progress_file

        progress_entries = parse_progress_file(progress_path)

        for entry in progress_entries[-3:]:
            recent_decisions.extend(entry.decisions)

        if progress_entries:
            last = progress_entries[-1]
            last_session_summary = f"Session {last.session}: " + ", ".join(last.what_done[:2])

    return OrientationSummary(
        session_number=session_state.last_session + 1,
        total_sessions=session_state.total_sessions,
        feature_progress=f"{passing}/{total} ({percentage:.0f}%)",
        current_feature=current_feature,
        next_feature=next_feature,
        recent_decisions=recent_decisions[-5:],
        current_state=session_state.status,
        last_session_summary=last_session_summary,
        blocked_features_count=len(get_blocked_features(features)),
        ready_features_count=len(get_ready_features(features)),
    )
