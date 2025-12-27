"""Coding prompt template for agent-harness."""

from typing import Optional

from agent_harness.features import Feature


def build_coding_prompt(
    orientation: str,
    feature: Optional[Feature] = None,
    recent_decisions: Optional[list[str]] = None,
) -> str:
    """
    Build a coding prompt for implementing a feature.

    Args:
        orientation: Orientation summary.
        feature: Feature to implement (optional).
        recent_decisions: Recent decisions to maintain consistency.

    Returns:
        Complete coding prompt string.
    """
    lines = []

    lines.append("CODING SESSION")
    lines.append("=" * 40)
    lines.append("")

    # Add orientation
    lines.append(orientation)
    lines.append("")

    # Add feature details if provided
    if feature:
        lines.append("CURRENT TASK:")
        lines.append(f"Feature #{feature.id}: {feature.description}")
        lines.append(f"Test file: {feature.test_file}")
        lines.append(f"Size estimate: {feature.size_estimate}")

        if feature.depends_on:
            lines.append(f"Dependencies: {feature.depends_on}")

        if feature.verification_steps:
            lines.append("")
            lines.append("VERIFICATION STEPS:")
            for i, step in enumerate(feature.verification_steps, 1):
                lines.append(f"  {i}. {step}")

    # Add recent decisions for consistency
    if recent_decisions:
        lines.append("")
        lines.append("MAINTAIN CONSISTENCY WITH:")
        for decision in recent_decisions[-3:]:
            lines.append(f"  - {decision}")

    # Add instructions
    lines.append("")
    lines.append("INSTRUCTIONS:")
    lines.append("1. Write tests first (TDD approach)")
    lines.append("2. Implement the feature to make tests pass")
    lines.append("3. Run all tests to verify no regressions")
    lines.append("4. Update features.json when complete")
    lines.append("5. Document your work in claude-progress.txt")
    lines.append("")
    lines.append("Begin implementation:")

    return "\n".join(lines)


def build_feature_intro(feature: Feature) -> str:
    """
    Build a brief feature introduction.

    Args:
        feature: Feature to introduce.

    Returns:
        Feature introduction string.
    """
    lines = []
    lines.append(f"Feature #{feature.id}: {feature.description}")
    lines.append(f"Category: {feature.category}")
    lines.append(f"Test file: {feature.test_file}")

    if feature.note:
        lines.append(f"Note: {feature.note}")

    return "\n".join(lines)


def build_test_first_reminder() -> str:
    """Build a reminder to write tests first."""
    return """
REMINDER: Test-Driven Development
1. Write a failing test for the new functionality
2. Run the test to confirm it fails
3. Write the minimal code to make the test pass
4. Refactor while keeping tests passing
5. Repeat for each piece of functionality
"""
