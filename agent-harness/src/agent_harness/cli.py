"""CLI entry point for agent-harness."""

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


# --- Init command (placeholder) ---


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
@pass_context
def init(ctx: HarnessContext, spec: Path, mode: str):
    """Initialize harness for a project.

    Runs the initializer agent to set up harness files,
    create features.json, and prepare the project for
    automated coding sessions.
    """
    print_heading("Harness Initialization")
    print_info(f"Project: {ctx.project_dir}")
    print_info(f"Spec file: {spec}")
    print_info(f"Mode: {mode}")
    print_warning("Init command not yet implemented")
    # TODO: Implement in Phase 7.1


# --- Run command (placeholder) ---


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
@pass_context
def run(ctx: HarnessContext, dry_run: bool, feature: Optional[int]):
    """Execute a coding session.

    Runs the harness to complete the next available feature
    (or specified feature). Includes pre-flight checks,
    agent conversation, and verification.
    """
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

        print_warning("Run command not yet implemented")
        # TODO: Implement in Phase 7.2

    except ConfigError as e:
        print_error(str(e))
        sys.exit(1)


# --- Status command (placeholder) ---


@main.command()
@pass_context
def status(ctx: HarnessContext):
    """Show project status.

    Displays current feature progress, session information,
    costs, and next actions.
    """
    try:
        config = ctx.load_config()
        print_heading(f"Project Status: {config.project.name}")

        table = create_status_table()
        table.add_row("Project", config.project.name)
        table.add_row("Session", "Not started")
        table.add_row("Features", "0/0 passing (0%)")
        table.add_row("Current", "Ready for initialization")
        table.add_row("Last session", "N/A")
        table.add_row("Next prompt", "init")
        table.add_row("Costs", "$0.00 total")

        console.print(table)
        print_warning("Status details not yet implemented")
        # TODO: Implement in Phase 7.3

    except ConfigError as e:
        print_error(str(e))
        sys.exit(1)


# --- Health command (placeholder) ---


@main.command()
@pass_context
def health(ctx: HarnessContext):
    """Show project health metrics.

    Runs tests, linting, and checks file sizes to
    calculate a composite health score.
    """
    try:
        config = ctx.load_config()
        print_heading(f"Project Health: {config.project.name}")
        print_warning("Health command not yet implemented")
        # TODO: Implement in Phase 7.4

    except ConfigError as e:
        print_error(str(e))
        sys.exit(1)


# --- Verify command (placeholder) ---


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
@pass_context
def verify(ctx: HarnessContext, feature: Optional[int], verify_all: bool):
    """Verify feature completion.

    Runs the test file for a specific feature (or all features)
    and reports pass/fail status.
    """
    try:
        config = ctx.load_config()
        print_heading("Feature Verification")

        if verify_all:
            print_info("Verifying all features")
        elif feature:
            print_info(f"Verifying feature #{feature}")
        else:
            print_error("Please specify --feature ID or --all")
            sys.exit(1)

        print_warning("Verify command not yet implemented")
        # TODO: Implement in Phase 7.5

    except ConfigError as e:
        print_error(str(e))
        sys.exit(1)


# --- Control commands (placeholders) ---


@main.command()
@pass_context
def pause(ctx: HarnessContext):
    """Pause harness execution.

    Sets the harness state to paused, preventing
    further sessions until resumed.
    """
    print_info("Pausing harness...")
    print_warning("Pause command not yet implemented")
    # TODO: Implement in Phase 7.6


@main.command()
@pass_context
def resume(ctx: HarnessContext):
    """Resume paused harness.

    Clears the paused state, allowing sessions
    to continue.
    """
    print_info("Resuming harness...")
    print_warning("Resume command not yet implemented")
    # TODO: Implement in Phase 7.6


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
    print_info(f"Skipping feature #{feature}")
    if reason:
        print_info(f"Reason: {reason}")
    print_warning("Skip command not yet implemented")
    # TODO: Implement in Phase 7.6


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
    print_info("Handing off to human developer")
    if reason:
        print_info(f"Reason: {reason}")
    print_warning("Handoff command not yet implemented")
    # TODO: Implement in Phase 7.6


@main.command()
@pass_context
def takeback(ctx: HarnessContext):
    """Take back control from human.

    Resumes harness after human intervention,
    updating baseline if needed.
    """
    print_info("Taking back control from human")
    print_warning("Takeback command not yet implemented")
    # TODO: Implement in Phase 7.6


# --- Cleanup command (placeholder) ---


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
    if now:
        print_info("Running cleanup session...")
    else:
        print_info("Scheduling cleanup for next session...")
    print_warning("Cleanup command not yet implemented")
    # TODO: Implement in Phase 7.7


# --- Logs command (placeholder) ---


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
@pass_context
def logs(ctx: HarnessContext, query: Optional[str], session: Optional[str], level: str):
    """Query event logs.

    Displays logged events, filtered by query,
    session, and/or level.
    """
    print_heading("Event Logs")
    if query:
        print_info(f"Filter: {query}")
    if session:
        print_info(f"Session: {session}")
    print_info(f"Level: {level}+")
    print_warning("Logs command not yet implemented")
    # TODO: Implement in Phase 8.3


# --- Migrate command (placeholder) ---


@main.command()
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip backup before migration (dangerous)"
)
@pass_context
def migrate(ctx: HarnessContext, no_backup: bool):
    """Migrate state files to current version.

    Upgrades state files from older harness versions
    to the current schema.
    """
    print_heading("State Migration")
    if no_backup:
        print_warning("Backup disabled - this is dangerous!")
    print_warning("Migrate command not yet implemented")
    # TODO: Implement in Phase 11.2


if __name__ == "__main__":
    main()
