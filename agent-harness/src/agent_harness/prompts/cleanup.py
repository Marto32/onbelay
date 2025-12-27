"""Cleanup prompt template for agent-harness."""

from typing import Optional


def build_cleanup_prompt(
    quality_issues: Optional[str] = None,
    oversized_files: Optional[list[tuple[str, int]]] = None,
    lint_errors: int = 0,
    lint_warnings: int = 0,
) -> str:
    """
    Build a cleanup prompt for code quality improvements.

    Args:
        quality_issues: Description of quality issues.
        oversized_files: List of (file_path, line_count) for large files.
        lint_errors: Number of lint errors.
        lint_warnings: Number of lint warnings.

    Returns:
        Complete cleanup prompt string.
    """
    lines = []

    lines.append("CLEANUP SESSION")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Focus on code quality improvements.")
    lines.append("DO NOT add new features in this session.")
    lines.append("")

    # Add quality issues
    if quality_issues:
        lines.append("QUALITY ISSUES TO ADDRESS:")
        lines.append(quality_issues)
        lines.append("")

    # Add lint status
    if lint_errors > 0 or lint_warnings > 0:
        lines.append("LINT STATUS:")
        if lint_errors > 0:
            lines.append(f"  Errors: {lint_errors}")
        if lint_warnings > 0:
            lines.append(f"  Warnings: {lint_warnings}")
        lines.append("")

    # Add oversized files
    if oversized_files:
        lines.append("OVERSIZED FILES (consider refactoring):")
        for file_path, line_count in oversized_files[:10]:
            lines.append(f"  - {file_path}: {line_count} lines")
        lines.append("")

    # Add instructions
    lines.append("CLEANUP PRIORITIES:")
    lines.append("1. Fix all lint errors")
    lines.append("2. Reduce lint warnings")
    lines.append("3. Refactor oversized files (split into modules)")
    lines.append("4. Improve code organization")
    lines.append("5. Add missing docstrings")
    lines.append("6. Remove dead code")
    lines.append("")
    lines.append("RULES:")
    lines.append("- Keep all existing tests passing")
    lines.append("- Do NOT add new features")
    lines.append("- Do NOT change public APIs")
    lines.append("- Document any significant refactoring")
    lines.append("")
    lines.append("Begin cleanup:")

    return "\n".join(lines)


def build_lint_fix_prompt(
    lint_output: str,
    auto_fixable: int = 0,
) -> str:
    """
    Build a prompt focused on fixing lint issues.

    Args:
        lint_output: Raw lint output.
        auto_fixable: Number of auto-fixable issues.

    Returns:
        Lint fix prompt string.
    """
    lines = []

    lines.append("LINT FIX SESSION")
    lines.append("=" * 40)
    lines.append("")

    if auto_fixable > 0:
        lines.append(f"NOTE: {auto_fixable} issues can be auto-fixed with 'ruff check --fix'")
        lines.append("")

    lines.append("LINT OUTPUT:")
    lines.append("-" * 40)
    lines.append(lint_output[:2000])  # Limit output size
    if len(lint_output) > 2000:
        lines.append("... [truncated]")
    lines.append("-" * 40)
    lines.append("")

    lines.append("Fix these lint issues while maintaining test coverage.")

    return "\n".join(lines)


def build_refactor_prompt(
    file_path: str,
    line_count: int,
    suggested_splits: Optional[list[str]] = None,
) -> str:
    """
    Build a prompt for refactoring an oversized file.

    Args:
        file_path: Path to the oversized file.
        line_count: Current line count.
        suggested_splits: Suggested module splits.

    Returns:
        Refactor prompt string.
    """
    lines = []

    lines.append("REFACTOR SESSION")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"FILE: {file_path}")
    lines.append(f"SIZE: {line_count} lines (over limit)")
    lines.append("")

    if suggested_splits:
        lines.append("SUGGESTED SPLITS:")
        for split in suggested_splits:
            lines.append(f"  - {split}")
        lines.append("")

    lines.append("REFACTORING APPROACH:")
    lines.append("1. Identify logical groupings of functionality")
    lines.append("2. Extract related functions to new modules")
    lines.append("3. Update imports throughout the codebase")
    lines.append("4. Ensure all tests still pass")
    lines.append("5. Add docstrings to new modules")
    lines.append("")
    lines.append("Begin refactoring:")

    return "\n".join(lines)
