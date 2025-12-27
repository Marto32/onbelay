"""Git operations for agent-harness.

Provides safe git operations for checkpoint management and version control.
"""

from pathlib import Path
from typing import Optional

from git import Repo, InvalidGitRepositoryError, GitCommandError
from git.exc import BadName

from agent_harness.exceptions import GitError


def get_repo(project_dir: Path) -> Repo:
    """
    Get a git Repo object for the project directory.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Git Repo object.

    Raises:
        GitError: If directory is not a git repository.
    """
    try:
        return Repo(project_dir)
    except InvalidGitRepositoryError:
        raise GitError(f"Not a git repository: {project_dir}")


def is_git_repo(project_dir: Path) -> bool:
    """
    Check if a directory is a git repository.

    Args:
        project_dir: Path to check.

    Returns:
        True if directory is a git repository.
    """
    try:
        Repo(project_dir)
        return True
    except InvalidGitRepositoryError:
        return False


def get_current_branch(project_dir: Path) -> str:
    """
    Get the current branch name.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Current branch name.

    Raises:
        GitError: If not in a git repository or detached HEAD.
    """
    repo = get_repo(project_dir)

    if repo.head.is_detached:
        raise GitError("Repository is in detached HEAD state")

    return repo.active_branch.name


def is_working_tree_clean(project_dir: Path) -> bool:
    """
    Check if the working tree is clean (no uncommitted changes).

    Args:
        project_dir: Path to the project directory.

    Returns:
        True if working tree is clean.
    """
    repo = get_repo(project_dir)
    return not repo.is_dirty(untracked_files=True)


def is_detached_head(project_dir: Path) -> bool:
    """
    Check if the repository is in detached HEAD state.

    Args:
        project_dir: Path to the project directory.

    Returns:
        True if HEAD is detached.
    """
    repo = get_repo(project_dir)
    return repo.head.is_detached


def get_head_ref(project_dir: Path) -> str:
    """
    Get the current HEAD reference (commit SHA).

    Args:
        project_dir: Path to the project directory.

    Returns:
        HEAD commit SHA.
    """
    repo = get_repo(project_dir)
    return repo.head.commit.hexsha


def get_head_short_ref(project_dir: Path) -> str:
    """
    Get the short HEAD reference (7 characters).

    Args:
        project_dir: Path to the project directory.

    Returns:
        Short HEAD commit SHA.
    """
    return get_head_ref(project_dir)[:7]


def commits_between(project_dir: Path, from_ref: str, to_ref: str) -> list[str]:
    """
    List commits between two references.

    Args:
        project_dir: Path to the project directory.
        from_ref: Starting reference (exclusive).
        to_ref: Ending reference (inclusive).

    Returns:
        List of commit SHAs between the references.

    Raises:
        GitError: If references are invalid.
    """
    repo = get_repo(project_dir)

    try:
        commits = list(repo.iter_commits(f"{from_ref}..{to_ref}"))
        return [c.hexsha for c in commits]
    except (BadName, GitCommandError) as e:
        raise GitError(f"Invalid git reference: {e}")


def reset_hard(project_dir: Path, ref: str) -> None:
    """
    Perform a hard reset to the specified reference.

    Warning: This will discard all uncommitted changes!

    Args:
        project_dir: Path to the project directory.
        ref: Reference to reset to (commit SHA, branch, tag).

    Raises:
        GitError: If reset fails.
    """
    repo = get_repo(project_dir)

    try:
        repo.head.reset(ref, index=True, working_tree=True)
    except (BadName, GitCommandError) as e:
        raise GitError(f"Failed to reset to {ref}: {e}")


def create_commit(
    project_dir: Path,
    message: str,
    files: Optional[list[str]] = None,
    add_all: bool = False,
) -> str:
    """
    Create a new commit.

    Args:
        project_dir: Path to the project directory.
        message: Commit message.
        files: Specific files to commit (optional).
        add_all: Add all changes (including untracked) if True.

    Returns:
        New commit SHA.

    Raises:
        GitError: If commit fails.
    """
    repo = get_repo(project_dir)

    try:
        if add_all:
            repo.git.add(A=True)
        elif files:
            for file in files:
                repo.index.add([file])

        # Check if there's anything to commit
        if not repo.is_dirty(untracked_files=False) and not repo.untracked_files:
            if not files and not add_all:
                raise GitError("Nothing to commit")

        commit = repo.index.commit(message)
        return commit.hexsha
    except GitCommandError as e:
        raise GitError(f"Failed to create commit: {e}")


def stash_changes(project_dir: Path, message: Optional[str] = None) -> bool:
    """
    Stash uncommitted changes.

    Args:
        project_dir: Path to the project directory.
        message: Optional stash message.

    Returns:
        True if changes were stashed, False if nothing to stash.
    """
    repo = get_repo(project_dir)

    if is_working_tree_clean(project_dir):
        return False

    try:
        if message:
            repo.git.stash("push", "-m", message)
        else:
            repo.git.stash("push")
        return True
    except GitCommandError:
        return False


def pop_stash(project_dir: Path) -> bool:
    """
    Pop the most recent stash.

    Args:
        project_dir: Path to the project directory.

    Returns:
        True if stash was popped, False if no stash exists.
    """
    repo = get_repo(project_dir)

    try:
        repo.git.stash("pop")
        return True
    except GitCommandError:
        return False


def get_changed_files(project_dir: Path, staged: bool = False) -> list[str]:
    """
    Get list of changed files.

    Args:
        project_dir: Path to the project directory.
        staged: If True, return only staged files.

    Returns:
        List of changed file paths.
    """
    repo = get_repo(project_dir)

    if staged:
        # Get staged files
        return [item.a_path for item in repo.index.diff("HEAD")]
    else:
        # Get all changed files (staged + unstaged + untracked)
        changed = set()

        # Staged changes
        for item in repo.index.diff("HEAD"):
            changed.add(item.a_path)

        # Unstaged changes
        for item in repo.index.diff(None):
            changed.add(item.a_path)

        # Untracked files
        changed.update(repo.untracked_files)

        return sorted(list(changed))


def get_untracked_files(project_dir: Path) -> list[str]:
    """
    Get list of untracked files.

    Args:
        project_dir: Path to the project directory.

    Returns:
        List of untracked file paths.
    """
    repo = get_repo(project_dir)
    return repo.untracked_files


def stage_files(project_dir: Path, files: list[str]) -> None:
    """
    Stage specific files for commit.

    Args:
        project_dir: Path to the project directory.
        files: List of file paths to stage.

    Raises:
        GitError: If staging fails.
    """
    repo = get_repo(project_dir)

    try:
        for file in files:
            repo.index.add([file])
    except GitCommandError as e:
        raise GitError(f"Failed to stage files: {e}")


def stage_all(project_dir: Path) -> None:
    """
    Stage all changes including untracked files.

    Args:
        project_dir: Path to the project directory.
    """
    repo = get_repo(project_dir)
    repo.git.add(A=True)


def get_commit_message(project_dir: Path, ref: str = "HEAD") -> str:
    """
    Get the commit message for a reference.

    Args:
        project_dir: Path to the project directory.
        ref: Reference to get message for.

    Returns:
        Commit message.

    Raises:
        GitError: If reference is invalid.
    """
    repo = get_repo(project_dir)

    try:
        commit = repo.commit(ref)
        return commit.message
    except (BadName, GitCommandError) as e:
        raise GitError(f"Invalid reference: {e}")


def get_commit_info(project_dir: Path, ref: str = "HEAD") -> dict:
    """
    Get detailed information about a commit.

    Args:
        project_dir: Path to the project directory.
        ref: Reference to get info for.

    Returns:
        Dictionary with commit information.
    """
    repo = get_repo(project_dir)

    try:
        commit = repo.commit(ref)
        return {
            "sha": commit.hexsha,
            "short_sha": commit.hexsha[:7],
            "message": commit.message.strip(),
            "author": str(commit.author),
            "author_email": commit.author.email,
            "date": commit.committed_datetime.isoformat(),
            "parents": [p.hexsha for p in commit.parents],
        }
    except (BadName, GitCommandError) as e:
        raise GitError(f"Invalid reference: {e}")


def get_recent_commits(project_dir: Path, n: int = 10) -> list[dict]:
    """
    Get recent commits.

    Args:
        project_dir: Path to the project directory.
        n: Number of commits to return.

    Returns:
        List of commit info dictionaries.
    """
    repo = get_repo(project_dir)
    commits = list(repo.iter_commits("HEAD", max_count=n))

    return [
        {
            "sha": c.hexsha,
            "short_sha": c.hexsha[:7],
            "message": c.message.strip().split("\n")[0],  # First line only
            "author": str(c.author),
            "date": c.committed_datetime.isoformat(),
        }
        for c in commits
    ]


def checkout_branch(project_dir: Path, branch: str, create: bool = False) -> None:
    """
    Checkout a branch.

    Args:
        project_dir: Path to the project directory.
        branch: Branch name.
        create: Create the branch if it doesn't exist.

    Raises:
        GitError: If checkout fails.
    """
    repo = get_repo(project_dir)

    try:
        if create:
            repo.git.checkout("-b", branch)
        else:
            repo.git.checkout(branch)
    except GitCommandError as e:
        raise GitError(f"Failed to checkout branch {branch}: {e}")


def branch_exists(project_dir: Path, branch: str) -> bool:
    """
    Check if a branch exists.

    Args:
        project_dir: Path to the project directory.
        branch: Branch name to check.

    Returns:
        True if branch exists.
    """
    repo = get_repo(project_dir)
    return branch in [b.name for b in repo.branches]


def get_file_hash(project_dir: Path, file_path: str) -> Optional[str]:
    """
    Get the git blob hash for a file.

    Args:
        project_dir: Path to the project directory.
        file_path: Relative path to the file.

    Returns:
        Blob hash, or None if file is not tracked.
    """
    repo = get_repo(project_dir)

    try:
        blob = repo.head.commit.tree / file_path
        return blob.hexsha
    except (KeyError, GitCommandError):
        return None


def format_commit_message(
    summary: str,
    body: Optional[str] = None,
    footer: Optional[str] = None,
) -> str:
    """
    Format a commit message with conventional format.

    Args:
        summary: First line summary (50 chars recommended).
        body: Optional detailed description.
        footer: Optional footer (e.g., issue references).

    Returns:
        Formatted commit message.
    """
    lines = [summary]

    if body:
        lines.append("")
        lines.append(body)

    if footer:
        lines.append("")
        lines.append(footer)

    return "\n".join(lines)
