"""CLI entry point for agent-harness."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click

from agent_harness.version import __version__
from agent_harness.config import load_config
from agent_harness.console import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
    print_heading,
    print_panel,
    create_status_table,
)
from agent_harness.exceptions import ConfigError, HarnessError


# --- Context object for sharing state between commands ---


class HarnessContext:
    """Context object for CLI commands."""

    def __init__(self):
        self.project_dir: Path = Path.cwd()
        self.config = None
        self.verbose: bool = False

    def load_config(self):
        """Load configuration if not already loaded."""
        if self.config is None:
            self.config = load_config(self.project_dir)
        return self.config


pass_context = click.make_pass_decorator(HarnessContext, ensure=True)


# --- Main CLI group ---


@click.group()
@click.option(
    "--project-dir", "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Project directory (defaults to current directory)"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose output"
)
@click.version_option(version=__version__, prog_name="harness")
@pass_context
def main(ctx: HarnessContext, project_dir: Optional[Path], verbose: bool):
    """Universal Agent Harness - Autonomous coding agent orchestration.

    The harness manages AI coding sessions, tracks features, and ensures
    code quality across multiple sessions.
    """
    if project_dir:
        ctx.project_dir = project_dir
    ctx.verbose = verbose


# --- Version command ---


@main.command()
def version():
    """Show version information."""
    print_info(f"Agent Harness v{__version__}")


# --- Init command ---


@main.command()
@click.option(
    "--spec", "-s",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to requirements/specification file"
)
@click.option(
    "--mode", "-m",
    type=click.Choice(["new", "adopt", "auto"]),
    default="auto",
    help="Initialization mode"
)
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    help="Preview without running agent"
)
@pass_context
def init(ctx: HarnessContext, spec: Path, mode: str, dry_run: bool):
    """Initialize harness for a project.

    Runs the initializer agent to set up harness files,
    create features.json, and prepare the project for
    automated coding sessions.
    """
    asyncio.run(_async_init(ctx, spec, mode, dry_run))


async def _async_init(ctx: HarnessContext, spec: Path, mode: str, dry_run: bool):
    """Async implementation of init command."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from agent_harness.init import init_project

    print_heading("Harness Initialization")
    print_info(f"Project: {ctx.project_dir}")
    print_info(f"Spec file: {spec}")
    print_info(f"Mode: {mode}")

    if dry_run:
        print_warning("Dry run mode - agent will not be executed")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing project...", total=None)

            def on_response(response):
                """Update progress on agent response."""
                progress.update(task, description=f"Agent working... ({response.usage.output_tokens} tokens)")

            result = await init_project(
                project_dir=ctx.project_dir,
                spec_file=spec,
                mode=mode,
                dry_run=dry_run,
                on_response=on_response if not dry_run else None,
            )

        if result.success:
            print_success(result.message)
            print_info(f"Mode: {result.mode}")
            print_info(f"Features: {result.features_count}")

            if result.warnings:
                print_warning(f"Warnings ({len(result.warnings)}):")
                for warning in result.warnings:
                    print_warning(f"  - {warning}")

            print_info("")
            print_info("Next steps:")
            print_info("  1. Review features.json")
            print_info("  2. Run 'harness status' to check project state")
            print_info("  3. Run 'harness run' to start coding session")
        else:
            print_error(f"Initialization failed: {result.error}")
            sys.exit(1)

    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# --- Run command ---


@main.command()
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    help="Preview without executing"
)
@click.option(
    "--feature", "-f",
    type=int,
    default=None,
    help="Override feature selection"
)
@click.option(
    "--skip-preflight",
    is_flag=True,
    help="Skip pre-flight checks"
)
@click.option(
    "--skip-tests",
    is_flag=True,
    help="Skip test verification"
)
@click.option(
    "--skip-commit",
    is_flag=True,
    help="Skip git commit on success"
)
@click.option(
    "--max-turns", "-t",
    type=int,
    default=50,
    help="Maximum conversation turns"
)
@pass_context
def run(
    ctx: HarnessContext,
    dry_run: bool,
    feature: Optional[int],
    skip_preflight: bool,
    skip_tests: bool,
    skip_commit: bool,
    max_turns: int,
):
    """Execute a coding session.

    Runs the harness to complete the next available feature
    (or specified feature). Includes pre-flight checks,
    agent conversation, and verification.
    """
    asyncio.run(_async_run(
        ctx, dry_run, feature, skip_preflight, skip_tests, skip_commit, max_turns
    ))


async def _async_run(
    ctx: HarnessContext,
    dry_run: bool,
    feature: Optional[int],
    skip_preflight: bool,
    skip_tests: bool,
    skip_commit: bool,
    max_turns: int,
):
    """Async implementation of run command."""
    import signal
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from agent_harness.session import run_session, SessionConfig
    from agent_harness.preflight import format_preflight_result

    # Handle Ctrl+C gracefully
    interrupted = False

    def signal_handler(sig, frame):
        nonlocal interrupted
        interrupted = True
        print_warning("\nInterrupted - finishing current turn...")

    signal.signal(signal.SIGINT, signal_handler)

    try:
        config = ctx.load_config()
        print_heading("Harness Run")
        print_info(f"Project: {config.project.name}")

        if dry_run:
            print_warning("Dry run mode - no changes will be made")

        if feature:
            print_info(f"Target feature: #{feature}")
        else:
            print_info("Target: Next available feature")

        print_info("")

        # Create status table for live display
        def create_run_table(tokens: int = 0, turns: int = 0, status: str = "Starting..."):
            table = Table(show_header=False, box=None)
            table.add_column("Key", style="dim")
            table.add_column("Value")
            table.add_row("Status", status)
            table.add_row("Tokens", f"{tokens:,}")
            table.add_row("Turns", str(turns))
            return table

        tokens_used = 0
        turns_completed = 0

        def on_response(response):
            """Update display on agent response."""
            nonlocal tokens_used, turns_completed
            tokens_used += response.usage.total_tokens
            turns_completed += 1

        # Run session with live display
        with Live(
            create_run_table(0, 0, "Running pre-flight checks..."),
            console=console,
            refresh_per_second=4,
        ) as live:
            result = await run_session(
                project_dir=ctx.project_dir,
                config=config,
                skip_preflight=skip_preflight,
                skip_tests=skip_tests,
                skip_commit=skip_commit,
                dry_run=dry_run,
                max_turns=max_turns,
                on_response=lambda r: (on_response(r), live.update(
                    create_run_table(tokens_used, turns_completed, "Agent working...")
                )),
            )

            live.update(create_run_table(
                tokens_used,
                turns_completed,
                "Complete" if result.success else "Failed",
            ))

        print_info("")

        # Display preflight result if available
        if result.preflight_result:
            print_info(format_preflight_result(result.preflight_result))
            print_info("")

        # Display result
        if result.success:
            print_success(result.message or "Session completed successfully")

            if result.features_completed:
                print_info(f"Features completed: {result.features_completed}")

            if result.verification_passed:
                print_success("Verification: PASSED")
            elif result.features_completed:
                print_warning("Verification: NOT PASSED")

            # Display stats
            stats_table = Table(show_header=False, box=None)
            stats_table.add_column("Metric", style="dim")
            stats_table.add_column("Value")
            stats_table.add_row("Session ID", str(result.session_id))
            stats_table.add_row("Tokens", f"{result.tokens_used.total_tokens:,}")
            stats_table.add_row("Cost", f"${result.cost_usd:.4f}")
            stats_table.add_row("Duration", f"{result.duration_seconds:.1f}s")
            console.print(stats_table)

        else:
            print_error(f"Session failed: {result.error or 'Unknown error'}")

            if result.rolled_back:
                print_warning("Changes rolled back to checkpoint")

            sys.exit(1)

    except ConfigError as e:
        print_error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print_warning("\nSession interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# --- Status command ---


@main.command()
@pass_context
def status(ctx: HarnessContext):
    """Show project status.

    Displays current feature progress, session information,
    costs, and next actions.
    """
    from rich.table import Table
    from agent_harness.features import load_features, get_feature_progress, get_next_feature
    from agent_harness.state import load_session_state
    from agent_harness.costs import load_costs

    try:
        config = ctx.load_config()
        print_heading(f"Project Status: {config.project.name}")

        harness_dir = ctx.project_dir / ".harness"
        features_path = ctx.project_dir / "features.json"

        # Load state files
        state = load_session_state(harness_dir)
        costs = load_costs(harness_dir / "costs.yaml")

        # Feature progress
        features_table = Table(show_header=False, box=None)
        features_table.add_column("Key", style="dim")
        features_table.add_column("Value")

        if features_path.exists():
            features = load_features(features_path)
            passing, total, pct = get_feature_progress(features)
            next_feature = get_next_feature(features)

            features_table.add_row("Features", f"{passing}/{total} passing ({pct:.0f}%)")
            if next_feature:
                features_table.add_row("Next Feature", f"#{next_feature.id}: {next_feature.description[:50]}")
            else:
                features_table.add_row("Next Feature", "All features complete!")
        else:
            features_table.add_row("Features", "No features.json found")
            features_table.add_row("Next Feature", "Run 'harness init' first")

        console.print(features_table)
        print_info("")

        # Session state
        state_table = Table(show_header=False, box=None)
        state_table.add_column("Key", style="dim")
        state_table.add_column("Value")

        state_table.add_row("Last Session", str(state.last_session))
        state_table.add_row("Status", state.status)
        state_table.add_row("Next Prompt", state.next_prompt)

        if state.current_feature:
            state_table.add_row("Current Feature", f"#{state.current_feature}")

        if state.stuck_count > 0:
            state_table.add_row("Stuck Count", str(state.stuck_count))

        console.print(state_table)
        print_info("")

        # Costs
        costs_table = Table(show_header=False, box=None)
        costs_table.add_column("Key", style="dim")
        costs_table.add_column("Value")

        costs_table.add_row("Total Sessions", str(costs.total_sessions))
        costs_table.add_row("Total Cost", f"${costs.total_cost_usd:.2f}")
        costs_table.add_row("Total Tokens", f"{costs.total_tokens_input + costs.total_tokens_output:,}")

        console.print(costs_table)

    except ConfigError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# --- Health command ---


@main.command()
@click.option(
    "--quick", "-q",
    is_flag=True,
    help="Quick health check (skip tests and lint)"
)
@pass_context
def health(ctx: HarnessContext, quick: bool):
    """Show project health metrics.

    Runs tests, linting, and checks file sizes to
    calculate a composite health score.
    """
    asyncio.run(_async_health(ctx, quick))


async def _async_health(ctx: HarnessContext, quick: bool):
    """Async implementation of health command."""
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from agent_harness.health import (
        calculate_health,
        calculate_quick_health,
        get_health_color,
        get_score_color,
        get_health_recommendations,
    )
    from agent_harness.features import load_features
    from agent_harness.file_sizes import load_file_sizes

    try:
        config = ctx.load_config()
        print_heading(f"Project Health: {config.project.name}")

        harness_dir = ctx.project_dir / ".harness"
        features_path = ctx.project_dir / "features.json"

        if quick:
            # Quick health check
            if features_path.exists():
                features = load_features(features_path)
                file_tracker = load_file_sizes(harness_dir / "file_sizes.json")
                health_result = calculate_quick_health(
                    features,
                    file_tracker,
                    config.quality.max_file_lines,
                )
            else:
                print_error("No features.json found. Run 'harness init' first.")
                sys.exit(1)
        else:
            # Full health check with progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Calculating project health...", total=None)

                features = load_features(features_path) if features_path.exists() else None
                health_result = await calculate_health(
                    ctx.project_dir,
                    config,
                    features,
                    run_full_tests=True,
                    run_full_lint=True,
                )

        # Display overall status
        status_color = get_health_color(health_result.status)
        console.print(f"\nOverall Health: [{status_color}]{health_result.status}[/{status_color}] ({health_result.overall:.0%})\n")

        # Component scores
        scores_table = Table(show_header=True, box=None)
        scores_table.add_column("Component", style="dim")
        scores_table.add_column("Score")
        scores_table.add_column("Details")

        scores_table.add_row(
            "Feature Completion",
            f"[{get_score_color(health_result.feature_completion)}]{health_result.feature_completion:.0%}[/]",
            f"{health_result.features_passing}/{health_result.features_total}"
        )
        scores_table.add_row(
            "Test Pass Rate",
            f"[{get_score_color(health_result.test_pass_rate)}]{health_result.test_pass_rate:.0%}[/]",
            f"{health_result.tests_passing}/{health_result.tests_total}"
        )
        scores_table.add_row(
            "Lint Score",
            f"[{get_score_color(health_result.lint_score)}]{health_result.lint_score:.0%}[/]",
            f"{health_result.lint_errors} errors, {health_result.lint_warnings} warnings"
        )
        scores_table.add_row(
            "File Health",
            f"[{get_score_color(health_result.file_health)}]{health_result.file_health:.0%}[/]",
            f"{health_result.oversized_files} oversized files"
        )

        console.print(scores_table)

        # Recommendations
        recommendations = get_health_recommendations(health_result)
        if recommendations:
            print_info("")
            print_info("Recommendations:")
            for rec in recommendations:
                print_info(f"  - {rec}")

    except ConfigError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# --- Verify command ---


@main.command()
@click.option(
    "--feature", "-f",
    type=int,
    default=None,
    help="Feature ID to verify"
)
@click.option(
    "--all", "-a", "verify_all",
    is_flag=True,
    help="Verify all features"
)
@click.option(
    "--update", "-u",
    is_flag=True,
    help="Update features.json with results"
)
@pass_context
def verify(ctx: HarnessContext, feature: Optional[int], verify_all: bool, update: bool):
    """Verify feature completion.

    Runs the test file for a specific feature (or all features)
    and reports pass/fail status.
    """
    asyncio.run(_async_verify(ctx, feature, verify_all, update))


async def _async_verify(ctx: HarnessContext, feature: Optional[int], verify_all: bool, update: bool):
    """Async implementation of verify command."""
    from rich.table import Table
    from agent_harness.features import load_features, save_features, get_feature_by_id, mark_feature_complete
    from agent_harness.test_runner import run_test_file_async, format_test_summary

    try:
        config = ctx.load_config()
        print_heading("Feature Verification")

        features_path = ctx.project_dir / "features.json"
        if not features_path.exists():
            print_error("No features.json found. Run 'harness init' first.")
            sys.exit(1)

        features = load_features(features_path)

        if not verify_all and not feature:
            print_error("Please specify --feature ID or --all")
            sys.exit(1)

        # Determine which features to verify
        if verify_all:
            to_verify = features.features
        else:
            f = get_feature_by_id(features, feature)
            if not f:
                print_error(f"Feature #{feature} not found")
                sys.exit(1)
            to_verify = [f]

        # Verify each feature
        results_table = Table(show_header=True, box=None)
        results_table.add_column("ID")
        results_table.add_column("Description")
        results_table.add_column("Status")

        any_updated = False

        for f in to_verify:
            print_info(f"Verifying feature #{f.id}: {f.description[:40]}...")

            test_result = await run_test_file_async(ctx.project_dir, f.test_file)
            passed = test_result.all_passed

            status_str = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            results_table.add_row(
                str(f.id),
                f.description[:50],
                status_str,
            )

            # Update if requested and status changed
            if update and passed != f.passes:
                mark_feature_complete(features, f.id, passed)
                any_updated = True

            if not passed and ctx.verbose:
                print_info(format_test_summary(test_result))

        console.print(results_table)

        if any_updated:
            save_features(features_path, features)
            print_success("Updated features.json with verification results")

    except ConfigError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# --- Control commands ---


@main.command()
@click.option(
    "--reason", "-r",
    type=str,
    default=None,
    help="Reason for pausing"
)
@pass_context
def pause(ctx: HarnessContext, reason: Optional[str]):
    """Pause harness execution.

    Sets the harness state to paused, preventing
    further sessions until resumed.
    """
    from agent_harness.state import load_session_state, save_session_state, set_paused

    try:
        harness_dir = ctx.project_dir / ".harness"
        state = load_session_state(harness_dir)

        state = set_paused(state, reason)
        save_session_state(harness_dir, state)

        print_success("Harness paused")
        if reason:
            print_info(f"Reason: {reason}")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        sys.exit(1)


@main.command()
@pass_context
def resume(ctx: HarnessContext):
    """Resume paused harness.

    Clears the paused state, allowing sessions
    to continue.
    """
    from agent_harness.state import load_session_state, save_session_state, clear_paused, is_paused

    try:
        harness_dir = ctx.project_dir / ".harness"
        state = load_session_state(harness_dir)

        if not is_paused(state):
            print_warning("Harness is not paused")
            return

        state = clear_paused(state)
        save_session_state(harness_dir, state)

        print_success("Harness resumed")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        sys.exit(1)


@main.command()
@click.option(
    "--feature", "-f",
    type=int,
    required=True,
    help="Feature ID to skip"
)
@click.option(
    "--reason", "-r",
    type=str,
    default=None,
    help="Reason for skipping"
)
@pass_context
def skip(ctx: HarnessContext, feature: int, reason: Optional[str]):
    """Skip a feature.

    Marks a feature as skipped, removing it from
    the queue without implementing it.
    """
    from agent_harness.features import load_features, save_features, get_feature_by_id

    try:
        features_path = ctx.project_dir / "features.json"
        if not features_path.exists():
            print_error("No features.json found")
            sys.exit(1)

        features = load_features(features_path)
        f = get_feature_by_id(features, feature)

        if not f:
            print_error(f"Feature #{feature} not found")
            sys.exit(1)

        # Mark as passes with a skip note
        f.passes = True
        f.note = f"SKIPPED: {reason}" if reason else "SKIPPED"

        save_features(features_path, features)

        print_success(f"Skipped feature #{feature}")
        if reason:
            print_info(f"Reason: {reason}")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        sys.exit(1)


@main.command()
@click.option(
    "--reason", "-r",
    type=str,
    default=None,
    help="Reason for handoff"
)
@pass_context
def handoff(ctx: HarnessContext, reason: Optional[str]):
    """Hand off to human developer.

    Pauses the harness and records that human
    intervention is needed.
    """
    from agent_harness.state import load_session_state, save_session_state, set_paused

    try:
        harness_dir = ctx.project_dir / ".harness"
        state = load_session_state(harness_dir)

        handoff_reason = f"Handoff to human: {reason}" if reason else "Handoff to human"
        state = set_paused(state, handoff_reason)
        save_session_state(harness_dir, state)

        print_success("Handed off to human developer")
        print_info("Run 'harness takeback' when done with manual work")
        if reason:
            print_info(f"Reason: {reason}")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        sys.exit(1)


@main.command()
@pass_context
def takeback(ctx: HarnessContext):
    """Take back control from human.

    Resumes harness after human intervention,
    updating baseline if needed.
    """
    asyncio.run(_async_takeback(ctx))


async def _async_takeback(ctx: HarnessContext):
    """Async implementation of takeback command."""
    from agent_harness.state import load_session_state, save_session_state, clear_paused, is_paused
    from agent_harness.baseline import create_baseline_from_test_results, save_baseline
    from agent_harness.test_runner import run_tests_async

    try:
        harness_dir = ctx.project_dir / ".harness"
        state = load_session_state(harness_dir)

        if not is_paused(state):
            print_warning("Harness is not paused")
            return

        # Update test baseline
        print_info("Updating test baseline...")
        test_result = await run_tests_async(ctx.project_dir)
        if test_result.total > 0:
            baseline = create_baseline_from_test_results(test_result)
            save_baseline(harness_dir / "baseline.json", baseline)
            print_info(f"Baseline updated: {len(test_result.passed)} passing tests")

        state = clear_paused(state)
        save_session_state(harness_dir, state)

        print_success("Control returned to harness")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        sys.exit(1)


# --- Cleanup command ---


@main.command()
@click.option(
    "--now", "-n",
    is_flag=True,
    help="Run cleanup session immediately"
)
@pass_context
def cleanup(ctx: HarnessContext, now: bool):
    """Trigger cleanup session.

    Schedules (or immediately runs) a cleanup session
    to address code quality issues.
    """
    from agent_harness.state import load_session_state, save_session_state

    try:
        harness_dir = ctx.project_dir / ".harness"
        state = load_session_state(harness_dir)

        # Set next prompt to cleanup
        state.next_prompt = "cleanup"
        save_session_state(harness_dir, state)

        if now:
            print_info("Running cleanup session...")
            # Invoke run command
            ctx.invoke(run)
        else:
            print_success("Cleanup scheduled for next session")
            print_info("Run 'harness run' to start the cleanup session")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        sys.exit(1)


# --- Logs command ---


@main.command()
@click.option(
    "--query", "-q",
    type=str,
    default=None,
    help="Filter string"
)
@click.option(
    "--session", "-s",
    type=str,
    default=None,
    help="Session ID or 'last'"
)
@click.option(
    "--level", "-l",
    type=click.Choice(["critical", "important", "routine", "debug"]),
    default="important",
    help="Minimum log level"
)
@click.option(
    "--limit", "-n",
    type=int,
    default=50,
    help="Maximum events to show"
)
@pass_context
def logs(ctx: HarnessContext, query: Optional[str], session: Optional[str], level: str, limit: int):
    """Query event logs.

    Displays logged events, filtered by query,
    session, and/or level.
    """
    from agent_harness.logging import (
        LogLevel,
        query_logs,
        get_last_session_id,
        format_log_event,
    )

    try:
        logs_dir = ctx.project_dir / ".harness" / "logs"

        if not logs_dir.exists():
            print_warning("No logs found. Run a session first.")
            return

        # Parse session filter
        session_id = None
        if session:
            if session.lower() == "last":
                session_id = get_last_session_id(logs_dir)
                if session_id is None:
                    print_warning("No sessions found in logs")
                    return
            else:
                try:
                    session_id = int(session)
                except ValueError:
                    print_error("Session must be an integer or 'last'")
                    sys.exit(1)

        # Query logs
        min_level = LogLevel(level)
        events = query_logs(
            logs_dir,
            "events",
            query=query,
            session_id=session_id,
            min_level=min_level,
            limit=limit,
        )

        if not events:
            print_warning("No matching events found")
            return

        print_heading("Event Logs")
        if session_id:
            print_info(f"Session: {session_id}")
        if query:
            print_info(f"Filter: {query}")
        print_info(f"Level: {level}+")
        print_info(f"Showing: {len(events)} events")
        print_info("")

        for event in events:
            console.print(format_log_event(event))

    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# --- Migrate command ---


@main.command()
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip backup before migration (dangerous)"
)
@click.option(
    "--status",
    is_flag=True,
    help="Show migration status only"
)
@pass_context
def migrate(ctx: HarnessContext, no_backup: bool, status: bool):
    """Migrate state files to current version.

    Upgrades state files from older harness versions
    to the current schema.
    """
    from agent_harness.migrations import (
        check_version_compatibility,
        migrate_state,
        format_migration_status,
        list_available_migrations,
    )
    from agent_harness.state import SCHEMA_VERSION

    try:
        harness_dir = ctx.project_dir / ".harness"

        if not harness_dir.exists():
            print_warning("No .harness directory found. Run 'harness init' first.")
            return

        # Check compatibility
        check = check_version_compatibility(harness_dir)

        if status:
            console.print(format_migration_status(check))
            return

        if not check.needs_migration:
            if check.compatible:
                print_success("State files are up to date")
            else:
                print_error(check.message)
            return

        # Confirm migration
        if no_backup:
            print_warning("Backup disabled - this is dangerous!")
            if not click.confirm("Are you sure you want to proceed?"):
                return

        print_info(f"Migrating from schema {check.current_version} to {check.target_version}...")

        result = migrate_state(
            harness_dir,
            check.current_version or 0,
            check.target_version,
            create_backup=not no_backup,
        )

        if result.success:
            print_success(result.message)
            if result.backup_path:
                print_info(f"Backup created at: {result.backup_path}")
        else:
            print_error(result.message)
            sys.exit(1)

    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# --- Scan command (for adopt mode) ---


@main.command()
@pass_context
def scan(ctx: HarnessContext):
    """Scan project structure.

    Analyzes the project to detect source files, tests,
    frameworks, and other configuration for adopt mode.
    """
    from agent_harness.scanner import scan_project, format_project_summary, get_adoption_recommendations

    try:
        print_heading("Project Scan")

        summary = scan_project(ctx.project_dir)

        console.print(format_project_summary(summary))
        print_info("")

        recommendations = get_adoption_recommendations(summary)
        print_info("Recommendations:")
        for rec in recommendations:
            print_info(f"  - {rec}")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# --- Sync command (GitHub) ---


@main.command()
@click.option(
    "--create", "-c",
    is_flag=True,
    help="Create issues for features without them"
)
@click.option(
    "--close", "-x",
    is_flag=True,
    help="Close issues for passing features"
)
@click.option(
    "--status", "-s",
    is_flag=True,
    help="Show sync status only"
)
@pass_context
def sync(ctx: HarnessContext, create: bool, close: bool, status: bool):
    """Sync features with GitHub Issues.

    Creates issues for pending features and closes
    issues for completed features.
    """
    from agent_harness.github_sync import (
        sync_to_github,
        get_sync_status,
        format_sync_status,
        check_gh_auth,
    )
    from agent_harness.features import load_features

    try:
        config = ctx.load_config()

        if not config.github.enabled:
            print_warning("GitHub integration is not enabled in config")
            return

        # Check authentication
        if not check_gh_auth():
            print_error("GitHub CLI not authenticated. Run 'gh auth login' first.")
            sys.exit(1)

        features_path = ctx.project_dir / "features.json"
        if not features_path.exists():
            print_error("No features.json found")
            sys.exit(1)

        features = load_features(features_path)

        if status:
            # Show status only
            sync_status = get_sync_status(features, config.github)
            console.print(format_sync_status(sync_status))
            return

        # Default behavior if neither flag specified
        if not create and not close:
            create = True
            close = True

        print_info("Syncing with GitHub...")

        result = sync_to_github(
            features,
            config.github,
            create_missing=create,
            close_completed=close,
        )

        if result.success:
            print_success(result.message)
            if result.created:
                print_info(f"Created issues: {result.created}")
            if result.closed:
                print_info(f"Closed issues: {result.closed}")
        else:
            print_error(result.message)
            for error in result.errors:
                print_error(f"  - {error}")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
