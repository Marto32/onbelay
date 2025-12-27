"""Pre-flight checks for agent harness.

Verifies the environment is ready before launching an agent session:
- Working directory exists
- Harness files present
- Git state clean
- Init script runs
- Health checks pass
- Baseline tests pass
- Budget available
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent_harness.baseline import TestBaseline, load_baseline
from agent_harness.config import Config, load_config
from agent_harness.costs import check_budget, load_costs
from agent_harness.features import FeaturesFile, load_features
from agent_harness.git_ops import get_changed_files, get_head_ref, get_untracked_files
from agent_harness.state import SessionState, load_session_state
from agent_harness.test_runner import run_tests


@dataclass
class PreflightCheckResult:
    """Result of a single pre-flight check."""

    name: str
    passed: bool
    message: str = ""
    warning: bool = False
    details: Optional[str] = None


@dataclass
class PreflightResult:
    """Result of all pre-flight checks."""

    passed: bool
    checks: list[PreflightCheckResult] = field(default_factory=list)
    abort_reason: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def add_check(self, check: PreflightCheckResult) -> None:
        """Add a check result."""
        self.checks.append(check)
        if not check.passed and not check.warning:
            self.passed = False
            if not self.abort_reason:
                self.abort_reason = f"{check.name}: {check.message}"
        if check.warning:
            self.warnings.append(f"{check.name}: {check.message}")


def check_working_directory(project_dir: Path) -> PreflightCheckResult:
    """Verify the working directory exists and is accessible.

    Args:
        project_dir: Path to project directory.

    Returns:
        PreflightCheckResult.
    """
    if not project_dir.exists():
        return PreflightCheckResult(
            name="working_directory",
            passed=False,
            message=f"Directory does not exist: {project_dir}",
        )

    if not project_dir.is_dir():
        return PreflightCheckResult(
            name="working_directory",
            passed=False,
            message=f"Path is not a directory: {project_dir}",
        )

    return PreflightCheckResult(
        name="working_directory",
        passed=True,
        message="Working directory exists",
    )


def check_harness_files(project_dir: Path) -> PreflightCheckResult:
    """Verify required harness files exist.

    Args:
        project_dir: Path to project directory.

    Returns:
        PreflightCheckResult.
    """
    harness_dir = project_dir / ".harness"
    features_file = project_dir / "features.json"

    missing = []
    if not harness_dir.exists():
        missing.append(".harness/")
    if not features_file.exists():
        missing.append("features.json")

    if missing:
        return PreflightCheckResult(
            name="harness_files",
            passed=False,
            message=f"Missing required files: {', '.join(missing)}",
            details="Run 'harness init' to initialize the project",
        )

    return PreflightCheckResult(
        name="harness_files",
        passed=True,
        message="All harness files present",
    )


def check_git_state(project_dir: Path) -> PreflightCheckResult:
    """Verify git repository state.

    Args:
        project_dir: Path to project directory.

    Returns:
        PreflightCheckResult.
    """
    git_dir = project_dir / ".git"

    if not git_dir.exists():
        return PreflightCheckResult(
            name="git_state",
            passed=False,
            message="Not a git repository",
        )

    # Check for uncommitted changes
    try:
        changes = get_changed_files(project_dir) + get_untracked_files(project_dir)
        if changes:
            return PreflightCheckResult(
                name="git_state",
                passed=True,  # Warning, not failure
                message=f"Uncommitted changes: {len(changes)} files",
                warning=True,
                details="\n".join(changes[:10]),
            )

        return PreflightCheckResult(
            name="git_state",
            passed=True,
            message="Git state clean",
        )
    except Exception as e:
        # Handle invalid git repositories (e.g., .git exists but not a valid repo)
        return PreflightCheckResult(
            name="git_state",
            passed=False,
            message=f"Invalid git repository: {str(e)}",
        )


def run_init_script(
    project_dir: Path,
    try_reset_on_fail: bool = True,
) -> PreflightCheckResult:
    """Run init.sh script, with reset.sh fallback on failure.

    Args:
        project_dir: Path to project directory.
        try_reset_on_fail: Whether to try reset.sh if init.sh fails.

    Returns:
        PreflightCheckResult.
    """
    init_script = project_dir / "init.sh"
    reset_script = project_dir / "reset.sh"

    if not init_script.exists():
        return PreflightCheckResult(
            name="init_script",
            passed=True,  # Not required
            message="No init.sh script found (optional)",
            warning=True,
        )

    # Try running init.sh
    try:
        result = subprocess.run(
            ["bash", str(init_script)],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode == 0:
            return PreflightCheckResult(
                name="init_script",
                passed=True,
                message="init.sh completed successfully",
            )

        # Init failed - try reset if enabled
        if try_reset_on_fail and reset_script.exists():
            reset_result = subprocess.run(
                ["bash", str(reset_script)],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if reset_result.returncode == 0:
                # Try init again after reset
                retry_result = subprocess.run(
                    ["bash", str(init_script)],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if retry_result.returncode == 0:
                    return PreflightCheckResult(
                        name="init_script",
                        passed=True,
                        message="init.sh succeeded after reset.sh",
                    )

        return PreflightCheckResult(
            name="init_script",
            passed=False,
            message=f"init.sh failed with code {result.returncode}",
            details=result.stderr[:500] if result.stderr else result.stdout[:500],
        )

    except subprocess.TimeoutExpired:
        return PreflightCheckResult(
            name="init_script",
            passed=False,
            message="init.sh timed out after 5 minutes",
        )
    except Exception as e:
        return PreflightCheckResult(
            name="init_script",
            passed=False,
            message=f"Failed to run init.sh: {str(e)}",
        )


def check_baseline_tests(
    project_dir: Path,
    baseline: Optional[TestBaseline] = None,
) -> PreflightCheckResult:
    """Run baseline tests and verify no regressions.

    Args:
        project_dir: Path to project directory.
        baseline: Optional baseline to compare against.

    Returns:
        PreflightCheckResult.
    """
    # Run tests
    test_result = run_tests(project_dir)

    if not test_result.success:
        return PreflightCheckResult(
            name="baseline_tests",
            passed=False,
            message=f"Tests failed: {test_result.failed} failed, {test_result.errors} errors",
            details=test_result.output[:1000] if test_result.output else None,
        )

    # Compare to baseline if provided
    if baseline:
        current_passing = set(test_result.test_names or [])
        baseline_passing = set(baseline.passing_tests)

        regressions = baseline_passing - current_passing
        if regressions:
            return PreflightCheckResult(
                name="baseline_tests",
                passed=False,
                message=f"Baseline regressions: {len(regressions)} tests no longer passing",
                details="\n".join(sorted(regressions)[:10]),
            )

    return PreflightCheckResult(
        name="baseline_tests",
        passed=True,
        message=f"All tests pass ({test_result.passed} passed)",
    )


def check_budget_available(
    project_dir: Path,
    config: Config,
) -> PreflightCheckResult:
    """Verify budget is available for a session.

    Args:
        project_dir: Path to project directory.
        config: Configuration object.

    Returns:
        PreflightCheckResult.
    """
    harness_dir = project_dir / ".harness"
    costs_file = harness_dir / "costs.yaml"

    try:
        tracker = load_costs(costs_file) if costs_file.exists() else None
        if tracker is None:
            return PreflightCheckResult(
                name="budget",
                passed=True,
                message="No cost history found (first run)",
            )

        budget_result = check_budget(tracker, config.costs)

        if not budget_result.within_budget:
            return PreflightCheckResult(
                name="budget",
                passed=False,
                message=budget_result.message,
                details=f"Limit: ${budget_result.limit:.2f}, Current: ${budget_result.current:.2f}",
            )

        if budget_result.remaining < config.costs.session_limit:
            return PreflightCheckResult(
                name="budget",
                passed=True,
                message=f"Low budget: ${budget_result.remaining:.2f} remaining",
                warning=True,
            )

        return PreflightCheckResult(
            name="budget",
            passed=True,
            message=f"Budget available: ${budget_result.remaining:.2f} remaining",
        )

    except Exception as e:
        return PreflightCheckResult(
            name="budget",
            passed=True,  # Don't fail on budget check errors
            message=f"Could not check budget: {str(e)}",
            warning=True,
        )


def check_features_file(project_dir: Path) -> PreflightCheckResult:
    """Verify features.json is valid and has work to do.

    Args:
        project_dir: Path to project directory.

    Returns:
        PreflightCheckResult.
    """
    features_file = project_dir / "features.json"

    try:
        features = load_features(features_file)

        total = len(features.features)
        passing = len([f for f in features.features if f.passes])

        if total == 0:
            return PreflightCheckResult(
                name="features_file",
                passed=False,
                message="No features defined in features.json",
            )

        if passing == total:
            return PreflightCheckResult(
                name="features_file",
                passed=True,
                message=f"All {total} features complete!",
                warning=True,
            )

        return PreflightCheckResult(
            name="features_file",
            passed=True,
            message=f"Features: {passing}/{total} complete, {total - passing} remaining",
        )

    except Exception as e:
        return PreflightCheckResult(
            name="features_file",
            passed=False,
            message=f"Invalid features.json: {str(e)}",
        )


def run_preflight_checks(
    project_dir: Path,
    config: Optional[Config] = None,
    skip_tests: bool = False,
    skip_init_script: bool = False,
) -> PreflightResult:
    """Run all pre-flight checks.

    Args:
        project_dir: Path to project directory.
        config: Optional configuration (loaded if not provided).
        skip_tests: Skip baseline test check.
        skip_init_script: Skip init.sh execution.

    Returns:
        PreflightResult with all check results.
    """
    result = PreflightResult(passed=True)

    # Load config if not provided
    if config is None:
        try:
            config = load_config(project_dir / ".harness" / "config.yaml")
        except Exception:
            config = Config()

    # 1. Check working directory
    result.add_check(check_working_directory(project_dir))
    if not result.passed:
        return result

    # 2. Check harness files
    result.add_check(check_harness_files(project_dir))
    if not result.passed:
        return result

    # 3. Check git state
    result.add_check(check_git_state(project_dir))

    # 4. Check features file
    result.add_check(check_features_file(project_dir))
    if not result.passed:
        return result

    # 5. Run init script (if not skipped)
    if not skip_init_script:
        result.add_check(run_init_script(project_dir))
        if not result.passed:
            return result

    # 6. Check baseline tests (if not skipped)
    if not skip_tests:
        baseline = None
        baseline_file = project_dir / ".harness" / "baseline.json"
        if baseline_file.exists():
            try:
                baseline = load_baseline(baseline_file)
            except Exception:
                pass
        result.add_check(check_baseline_tests(project_dir, baseline))
        if not result.passed:
            return result

    # 7. Check budget
    result.add_check(check_budget_available(project_dir, config))

    return result


def format_preflight_result(result: PreflightResult) -> str:
    """Format preflight result for display.

    Args:
        result: PreflightResult to format.

    Returns:
        Formatted string.
    """
    lines = ["Pre-flight Checks", "=" * 40]

    for check in result.checks:
        status = "[PASS]" if check.passed else "[FAIL]"
        if check.warning:
            status = "[WARN]"

        lines.append(f"{status} {check.name}: {check.message}")

        if check.details and not check.passed:
            for detail_line in check.details.split("\n")[:5]:
                lines.append(f"       {detail_line}")

    lines.append("")
    if result.passed:
        lines.append("All checks passed!")
    else:
        lines.append(f"ABORT: {result.abort_reason}")

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines)
