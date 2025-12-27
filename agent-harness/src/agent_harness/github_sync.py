"""GitHub integration for agent-harness.

Syncs features to GitHub Issues.
"""

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent_harness.config import GithubConfig
from agent_harness.features import Feature, FeaturesFile


@dataclass
class GitHubIssue:
    """A GitHub issue."""

    number: int
    title: str
    state: str  # "open" or "closed"
    labels: list[str] = field(default_factory=list)
    body: Optional[str] = None
    url: Optional[str] = None


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    created: list[int] = field(default_factory=list)  # Issue numbers created
    closed: list[int] = field(default_factory=list)  # Issue numbers closed
    errors: list[str] = field(default_factory=list)
    rate_limited: bool = False
    message: str = ""


def _run_gh_command(args: list[str], timeout: int = 30) -> tuple[bool, str, str]:
    """
    Run a gh CLI command.

    Args:
        args: Command arguments.
        timeout: Timeout in seconds.

    Returns:
        Tuple of (success, stdout, stderr).
    """
    cmd = ["gh"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except FileNotFoundError:
        return False, "", "gh CLI not found. Install from https://cli.github.com/"


def check_gh_auth() -> bool:
    """
    Check if gh CLI is authenticated.

    Returns:
        True if authenticated.
    """
    success, _, _ = _run_gh_command(["auth", "status"])
    return success


def get_repo_info() -> Optional[tuple[str, str]]:
    """
    Get the current repo owner and name.

    Returns:
        Tuple of (owner, repo) or None if not in a repo.
    """
    success, stdout, _ = _run_gh_command(["repo", "view", "--json", "owner,name"])
    if not success:
        return None

    try:
        data = json.loads(stdout)
        return data.get("owner", {}).get("login"), data.get("name")
    except json.JSONDecodeError:
        return None


def list_issues(
    label: Optional[str] = None,
    state: str = "all",
    limit: int = 100,
) -> list[GitHubIssue]:
    """
    List issues in the repository.

    Args:
        label: Filter by label.
        state: Issue state ("open", "closed", "all").
        limit: Maximum issues to return.

    Returns:
        List of GitHubIssue objects.
    """
    args = ["issue", "list", "--json", "number,title,state,labels,body,url", "--limit", str(limit)]

    if label:
        args.extend(["--label", label])

    if state != "all":
        args.extend(["--state", state])

    success, stdout, _ = _run_gh_command(args)
    if not success:
        return []

    try:
        data = json.loads(stdout)
        issues = []
        for item in data:
            labels = [l.get("name", "") for l in item.get("labels", [])]
            issues.append(GitHubIssue(
                number=item.get("number", 0),
                title=item.get("title", ""),
                state=item.get("state", "").lower(),
                labels=labels,
                body=item.get("body"),
                url=item.get("url"),
            ))
        return issues
    except json.JSONDecodeError:
        return []


def get_issue(issue_number: int) -> Optional[GitHubIssue]:
    """
    Get a specific issue.

    Args:
        issue_number: Issue number.

    Returns:
        GitHubIssue object or None.
    """
    args = ["issue", "view", str(issue_number), "--json", "number,title,state,labels,body,url"]
    success, stdout, _ = _run_gh_command(args)

    if not success:
        return None

    try:
        item = json.loads(stdout)
        labels = [l.get("name", "") for l in item.get("labels", [])]
        return GitHubIssue(
            number=item.get("number", 0),
            title=item.get("title", ""),
            state=item.get("state", "").lower(),
            labels=labels,
            body=item.get("body"),
            url=item.get("url"),
        )
    except json.JSONDecodeError:
        return None


def create_issue_for_feature(
    feature: Feature,
    config: GithubConfig,
) -> Optional[int]:
    """
    Create a GitHub issue for a feature.

    Args:
        feature: Feature to create issue for.
        config: GitHub configuration.

    Returns:
        Issue number or None if failed.
    """
    title = f"[Feature #{feature.id}] {feature.description}"

    # Build body
    body_parts = [
        f"## Feature #{feature.id}",
        "",
        f"**Category:** {feature.category}",
        f"**Size:** {feature.size_estimate}",
        f"**Test File:** `{feature.test_file}`",
        "",
    ]

    if feature.depends_on:
        deps = ", ".join(f"#{d}" for d in feature.depends_on)
        body_parts.append(f"**Dependencies:** {deps}")
        body_parts.append("")

    if feature.verification_steps:
        body_parts.append("## Verification Steps")
        for i, step in enumerate(feature.verification_steps, 1):
            body_parts.append(f"{i}. {step}")
        body_parts.append("")

    if feature.note:
        body_parts.append(f"**Note:** {feature.note}")
        body_parts.append("")

    body_parts.append("---")
    body_parts.append("*Created by agent-harness*")

    body = "\n".join(body_parts)

    # Build command
    args = ["issue", "create", "--title", title, "--body", body]

    # Add labels
    labels = [config.label]
    if feature.size_estimate:
        labels.append(f"size:{feature.size_estimate}")
    if feature.category:
        labels.append(f"category:{feature.category}")

    for label in labels:
        args.extend(["--label", label])

    success, stdout, stderr = _run_gh_command(args)

    if not success:
        # Check for rate limiting
        if "rate limit" in stderr.lower():
            return None
        return None

    # Parse issue number from output
    # gh outputs URL like "https://github.com/owner/repo/issues/123"
    try:
        if "/" in stdout:
            parts = stdout.strip().split("/")
            return int(parts[-1])
    except (ValueError, IndexError):
        pass

    return None


def close_issue(
    issue_number: int,
    comment: Optional[str] = None,
) -> bool:
    """
    Close a GitHub issue.

    Args:
        issue_number: Issue number to close.
        comment: Optional comment to add.

    Returns:
        True if successful.
    """
    # Add comment if provided
    if comment:
        _run_gh_command(["issue", "comment", str(issue_number), "--body", comment])

    # Close the issue
    success, _, _ = _run_gh_command(["issue", "close", str(issue_number)])
    return success


def reopen_issue(issue_number: int) -> bool:
    """
    Reopen a GitHub issue.

    Args:
        issue_number: Issue number to reopen.

    Returns:
        True if successful.
    """
    success, _, _ = _run_gh_command(["issue", "reopen", str(issue_number)])
    return success


def add_comment(issue_number: int, comment: str) -> bool:
    """
    Add a comment to an issue.

    Args:
        issue_number: Issue number.
        comment: Comment text.

    Returns:
        True if successful.
    """
    success, _, _ = _run_gh_command(["issue", "comment", str(issue_number), "--body", comment])
    return success


def find_issue_for_feature(
    feature_id: int,
    issues: list[GitHubIssue],
) -> Optional[GitHubIssue]:
    """
    Find an existing issue for a feature.

    Args:
        feature_id: Feature ID to find.
        issues: List of issues to search.

    Returns:
        Matching issue or None.
    """
    pattern = f"[Feature #{feature_id}]"
    for issue in issues:
        if pattern in issue.title:
            return issue
    return None


def sync_to_github(
    features: FeaturesFile,
    config: GithubConfig,
    create_missing: bool = True,
    close_completed: bool = True,
    rate_limit_delay: float = 1.0,
) -> SyncResult:
    """
    Sync features to GitHub issues.

    Args:
        features: FeaturesFile to sync.
        config: GitHub configuration.
        create_missing: Create issues for features without them.
        close_completed: Close issues for passing features.
        rate_limit_delay: Delay between API calls to avoid rate limiting.

    Returns:
        SyncResult with details.
    """
    result = SyncResult(success=True)

    # Check authentication
    if not check_gh_auth():
        result.success = False
        result.message = "GitHub CLI not authenticated. Run 'gh auth login' first."
        return result

    # Get existing issues with our label
    existing_issues = list_issues(label=config.label, state="all")

    for feature in features.features:
        # Find existing issue
        existing = find_issue_for_feature(feature.id, existing_issues)

        if feature.passes:
            # Feature is complete
            if existing and existing.state == "open" and close_completed:
                # Close the issue
                comment = f"Feature #{feature.id} verified as passing. Closing automatically."
                if close_issue(existing.number, comment):
                    result.closed.append(existing.number)
                else:
                    result.errors.append(f"Failed to close issue #{existing.number}")

                time.sleep(rate_limit_delay)

        else:
            # Feature is pending
            if not existing and create_missing:
                # Create new issue
                issue_num = create_issue_for_feature(feature, config)
                if issue_num:
                    result.created.append(issue_num)
                else:
                    result.errors.append(f"Failed to create issue for feature #{feature.id}")

                time.sleep(rate_limit_delay)

            elif existing and existing.state == "closed":
                # Reopen if it was closed
                if reopen_issue(existing.number):
                    add_comment(
                        existing.number,
                        f"Feature #{feature.id} is no longer passing. Reopening issue.",
                    )
                else:
                    result.errors.append(f"Failed to reopen issue #{existing.number}")

                time.sleep(rate_limit_delay)

    if result.errors:
        result.success = False
        result.message = f"Sync completed with {len(result.errors)} errors"
    else:
        result.message = f"Sync complete. Created: {len(result.created)}, Closed: {len(result.closed)}"

    return result


def get_sync_status(
    features: FeaturesFile,
    config: GithubConfig,
) -> dict:
    """
    Get the current sync status between features and GitHub issues.

    Args:
        features: FeaturesFile to check.
        config: GitHub configuration.

    Returns:
        Dictionary with sync status.
    """
    status = {
        "synced": True,
        "issues_open": 0,
        "issues_closed": 0,
        "features_without_issues": [],
        "issues_without_features": [],
        "mismatched_state": [],
    }

    # Get existing issues
    existing_issues = list_issues(label=config.label, state="all")

    # Build maps
    feature_ids = {f.id for f in features.features}
    issue_feature_map = {}

    for issue in existing_issues:
        # Extract feature ID from title
        if "[Feature #" in issue.title:
            try:
                start = issue.title.index("[Feature #") + 10
                end = issue.title.index("]", start)
                feature_id = int(issue.title[start:end])
                issue_feature_map[feature_id] = issue
            except (ValueError, IndexError):
                pass

    # Check each feature
    for feature in features.features:
        issue = issue_feature_map.get(feature.id)

        if not issue:
            status["features_without_issues"].append(feature.id)
            status["synced"] = False
        else:
            if issue.state == "open":
                status["issues_open"] += 1
            else:
                status["issues_closed"] += 1

            # Check state match
            if feature.passes and issue.state == "open":
                status["mismatched_state"].append({
                    "feature_id": feature.id,
                    "issue_number": issue.number,
                    "feature_passes": True,
                    "issue_state": "open",
                })
                status["synced"] = False
            elif not feature.passes and issue.state == "closed":
                status["mismatched_state"].append({
                    "feature_id": feature.id,
                    "issue_number": issue.number,
                    "feature_passes": False,
                    "issue_state": "closed",
                })
                status["synced"] = False

    # Find orphan issues
    for feature_id, issue in issue_feature_map.items():
        if feature_id not in feature_ids:
            status["issues_without_features"].append(issue.number)

    return status


def format_sync_status(status: dict) -> str:
    """
    Format sync status for display.

    Args:
        status: Status dictionary from get_sync_status.

    Returns:
        Formatted string.
    """
    lines = []

    if status["synced"]:
        lines.append("GitHub Sync: IN SYNC")
    else:
        lines.append("GitHub Sync: OUT OF SYNC")

    lines.append(f"  Issues: {status['issues_open']} open, {status['issues_closed']} closed")

    if status["features_without_issues"]:
        lines.append(f"  Features missing issues: {status['features_without_issues']}")

    if status["issues_without_features"]:
        lines.append(f"  Orphan issues: {status['issues_without_features']}")

    if status["mismatched_state"]:
        lines.append("  State mismatches:")
        for mismatch in status["mismatched_state"]:
            lines.append(
                f"    Feature #{mismatch['feature_id']}: passes={mismatch['feature_passes']}, "
                f"issue #{mismatch['issue_number']} is {mismatch['issue_state']}"
            )

    return "\n".join(lines)
