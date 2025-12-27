"""Continuation prompt template for agent-harness."""

from typing import Optional

from agent_harness.features import Feature
from agent_harness.progress import ProgressEntry


def build_continuation_prompt(
    orientation: str,
    partial_details: Optional[str] = None,
    feature: Optional[Feature] = None,
    last_entry: Optional[ProgressEntry] = None,
) -> str:
    """
    Build a continuation prompt for resuming partial work.

    Args:
        orientation: Orientation summary.
        partial_details: Details about partial work.
        feature: Feature being continued.
        last_entry: Last progress entry.

    Returns:
        Complete continuation prompt string.
    """
    lines = []

    lines.append("CONTINUATION SESSION")
    lines.append("=" * 40)
    lines.append("")
    lines.append("You are resuming work from a previous session.")
    lines.append("")

    # Add orientation
    lines.append(orientation)
    lines.append("")

    # Add partial work details
    if partial_details:
        lines.append("PREVIOUS PROGRESS:")
        lines.append(partial_details)
        lines.append("")

    # Add last session info
    if last_entry:
        lines.append("LAST SESSION SUMMARY:")
        if last_entry.what_done:
            lines.append("  Completed:")
            for item in last_entry.what_done:
                lines.append(f"    [x] {item}")

        if last_entry.current_state:
            lines.append(f"  State: {last_entry.current_state}")

        if last_entry.decisions:
            lines.append("  Decisions made:")
            for decision in last_entry.decisions:
                lines.append(f"    - {decision}")
        lines.append("")

    # Add feature details
    if feature:
        lines.append("FEATURE TO COMPLETE:")
        lines.append(f"  #{feature.id}: {feature.description}")
        lines.append(f"  Test file: {feature.test_file}")

        if feature.verification_steps:
            lines.append("  Remaining verification steps:")
            for i, step in enumerate(feature.verification_steps, 1):
                lines.append(f"    {i}. {step}")
        lines.append("")

    # Add instructions
    lines.append("INSTRUCTIONS:")
    lines.append("1. Review what was done previously")
    lines.append("2. Continue from where you left off")
    lines.append("3. Complete the remaining work")
    lines.append("4. Verify all tests pass")
    lines.append("5. Update progress before finishing")
    lines.append("")
    lines.append("Continue the work:")

    return "\n".join(lines)


def build_context_limit_continuation(
    feature: Feature,
    progress_so_far: list[str],
) -> str:
    """
    Build a continuation prompt after hitting context limit.

    Args:
        feature: Feature being worked on.
        progress_so_far: List of progress items.

    Returns:
        Continuation prompt string.
    """
    lines = []

    lines.append("CONTEXT LIMIT CONTINUATION")
    lines.append("=" * 40)
    lines.append("")
    lines.append("The previous session ended due to context limit.")
    lines.append("A checkpoint was created. Continue the work.")
    lines.append("")
    lines.append(f"FEATURE: #{feature.id} - {feature.description}")
    lines.append("")

    if progress_so_far:
        lines.append("PROGRESS SO FAR:")
        for item in progress_so_far:
            lines.append(f"  [x] {item}")
        lines.append("")

    lines.append("Continue implementation:")

    return "\n".join(lines)


def build_stuck_recovery_prompt(
    feature: Feature,
    stuck_count: int,
    last_error: Optional[str] = None,
) -> str:
    """
    Build a prompt to help recover from being stuck.

    Args:
        feature: Feature being worked on.
        stuck_count: Number of times stuck.
        last_error: Last error encountered.

    Returns:
        Recovery prompt string.
    """
    lines = []

    lines.append("STUCK RECOVERY SESSION")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Previous attempts on this feature have stalled ({stuck_count} times).")
    lines.append("Let's try a different approach.")
    lines.append("")
    lines.append(f"FEATURE: #{feature.id} - {feature.description}")
    lines.append("")

    if last_error:
        lines.append("LAST ERROR:")
        lines.append(f"  {last_error}")
        lines.append("")

    lines.append("RECOVERY SUGGESTIONS:")
    lines.append("1. Break the feature into smaller pieces")
    lines.append("2. Try a simpler implementation first")
    lines.append("3. Focus on getting ONE test to pass")
    lines.append("4. If still stuck, skip and document the blocker")
    lines.append("")
    lines.append("Try a new approach:")

    return "\n".join(lines)
