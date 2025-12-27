"""Tests for git_ops.py - Git operations."""

import pytest
from pathlib import Path

from agent_harness.git_ops import (
    get_repo,
    is_git_repo,
    get_current_branch,
    is_working_tree_clean,
    is_detached_head,
    get_head_ref,
    get_head_short_ref,
    commits_between,
    reset_hard,
    create_commit,
    stash_changes,
    pop_stash,
    get_changed_files,
    get_untracked_files,
    stage_files,
    stage_all,
    get_commit_message,
    get_commit_info,
    get_recent_commits,
    checkout_branch,
    branch_exists,
    format_commit_message,
)
from agent_harness.exceptions import GitError

from git import Repo


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository."""
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create initial commit
    test_file = tmp_path / "initial.txt"
    test_file.write_text("initial content")
    repo.index.add(["initial.txt"])
    repo.index.commit("Initial commit")

    return tmp_path


class TestGetRepo:
    """Tests for get_repo function."""

    def test_get_repo_valid(self, git_repo):
        """Test getting a valid repo."""
        repo = get_repo(git_repo)
        assert repo is not None

    def test_get_repo_invalid(self, tmp_path):
        """Test getting repo from non-git directory raises error."""
        with pytest.raises(GitError, match="Not a git repository"):
            get_repo(tmp_path)


class TestIsGitRepo:
    """Tests for is_git_repo function."""

    def test_is_git_repo_true(self, git_repo):
        """Test detecting a git repo."""
        assert is_git_repo(git_repo) is True

    def test_is_git_repo_false(self, tmp_path):
        """Test detecting non-git directory."""
        assert is_git_repo(tmp_path) is False


class TestGetCurrentBranch:
    """Tests for get_current_branch function."""

    def test_get_current_branch(self, git_repo):
        """Test getting current branch name."""
        # Default branch is usually 'master' or 'main'
        branch = get_current_branch(git_repo)
        assert branch in ["master", "main"]


class TestIsWorkingTreeClean:
    """Tests for is_working_tree_clean function."""

    def test_clean_tree(self, git_repo):
        """Test detecting clean working tree."""
        assert is_working_tree_clean(git_repo) is True

    def test_dirty_tree_modified(self, git_repo):
        """Test detecting dirty tree with modified file."""
        (git_repo / "initial.txt").write_text("modified")
        assert is_working_tree_clean(git_repo) is False

    def test_dirty_tree_untracked(self, git_repo):
        """Test detecting dirty tree with untracked file."""
        (git_repo / "untracked.txt").write_text("new file")
        assert is_working_tree_clean(git_repo) is False


class TestIsDetachedHead:
    """Tests for is_detached_head function."""

    def test_not_detached(self, git_repo):
        """Test detecting non-detached HEAD."""
        assert is_detached_head(git_repo) is False

    def test_detached_head(self, git_repo):
        """Test detecting detached HEAD."""
        repo = Repo(git_repo)
        head_sha = repo.head.commit.hexsha
        repo.head.reference = repo.commit(head_sha)

        assert is_detached_head(git_repo) is True


class TestGetHeadRef:
    """Tests for get_head_ref function."""

    def test_get_head_ref(self, git_repo):
        """Test getting HEAD reference."""
        ref = get_head_ref(git_repo)
        assert len(ref) == 40  # Full SHA

    def test_get_head_short_ref(self, git_repo):
        """Test getting short HEAD reference."""
        ref = get_head_short_ref(git_repo)
        assert len(ref) == 7


class TestCommitsBetween:
    """Tests for commits_between function."""

    def test_commits_between(self, git_repo):
        """Test listing commits between refs."""
        repo = Repo(git_repo)
        initial_sha = repo.head.commit.hexsha

        # Create more commits
        (git_repo / "file1.txt").write_text("content")
        repo.index.add(["file1.txt"])
        repo.index.commit("Second commit")

        (git_repo / "file2.txt").write_text("content")
        repo.index.add(["file2.txt"])
        repo.index.commit("Third commit")

        commits = commits_between(git_repo, initial_sha, "HEAD")
        assert len(commits) == 2

    def test_commits_between_invalid_ref(self, git_repo):
        """Test commits_between with invalid ref raises error."""
        with pytest.raises(GitError, match="Invalid git reference"):
            commits_between(git_repo, "invalid", "HEAD")


class TestResetHard:
    """Tests for reset_hard function."""

    def test_reset_hard(self, git_repo):
        """Test hard reset."""
        repo = Repo(git_repo)
        initial_sha = repo.head.commit.hexsha

        # Make changes and commit
        (git_repo / "new.txt").write_text("content")
        repo.index.add(["new.txt"])
        repo.index.commit("New commit")

        # Reset back
        reset_hard(git_repo, initial_sha)

        assert get_head_ref(git_repo) == initial_sha
        assert not (git_repo / "new.txt").exists()

    def test_reset_hard_invalid_ref(self, git_repo):
        """Test reset with invalid ref raises error."""
        with pytest.raises(GitError, match="Failed to reset"):
            reset_hard(git_repo, "invalid_ref")


class TestCreateCommit:
    """Tests for create_commit function."""

    def test_create_commit_add_all(self, git_repo):
        """Test creating commit with add_all."""
        (git_repo / "new.txt").write_text("content")

        sha = create_commit(git_repo, "Test commit", add_all=True)

        assert len(sha) == 40
        assert "Test commit" in get_commit_message(git_repo)

    def test_create_commit_specific_files(self, git_repo):
        """Test creating commit with specific files."""
        (git_repo / "staged.txt").write_text("staged")
        (git_repo / "unstaged.txt").write_text("unstaged")

        repo = Repo(git_repo)
        repo.index.add(["staged.txt"])

        sha = create_commit(git_repo, "Staged only", files=["staged.txt"])

        assert len(sha) == 40
        # unstaged.txt should still be untracked
        assert "unstaged.txt" in get_untracked_files(git_repo)


class TestStash:
    """Tests for stash functions."""

    def test_stash_and_pop(self, git_repo):
        """Test stashing and popping changes."""
        (git_repo / "initial.txt").write_text("modified")

        result = stash_changes(git_repo, "Test stash")
        assert result is True
        assert is_working_tree_clean(git_repo) is True

        result = pop_stash(git_repo)
        assert result is True
        assert is_working_tree_clean(git_repo) is False

    def test_stash_nothing_to_stash(self, git_repo):
        """Test stashing when nothing to stash."""
        result = stash_changes(git_repo)
        assert result is False


class TestGetChangedFiles:
    """Tests for get_changed_files function."""

    def test_get_changed_files(self, git_repo):
        """Test getting changed files."""
        (git_repo / "initial.txt").write_text("modified")
        (git_repo / "new.txt").write_text("new")

        changed = get_changed_files(git_repo)

        assert "initial.txt" in changed
        assert "new.txt" in changed

    def test_get_staged_files(self, git_repo):
        """Test getting only staged files."""
        repo = Repo(git_repo)
        (git_repo / "staged.txt").write_text("staged")
        (git_repo / "unstaged.txt").write_text("unstaged")
        repo.index.add(["staged.txt"])

        staged = get_changed_files(git_repo, staged=True)

        assert "staged.txt" in staged
        assert "unstaged.txt" not in staged


class TestGetUntrackedFiles:
    """Tests for get_untracked_files function."""

    def test_get_untracked_files(self, git_repo):
        """Test getting untracked files."""
        (git_repo / "untracked1.txt").write_text("content")
        (git_repo / "untracked2.txt").write_text("content")

        untracked = get_untracked_files(git_repo)

        assert "untracked1.txt" in untracked
        assert "untracked2.txt" in untracked


class TestStageFiles:
    """Tests for staging functions."""

    def test_stage_files(self, git_repo):
        """Test staging specific files."""
        (git_repo / "file.txt").write_text("content")

        stage_files(git_repo, ["file.txt"])

        staged = get_changed_files(git_repo, staged=True)
        assert "file.txt" in staged

    def test_stage_all(self, git_repo):
        """Test staging all files."""
        (git_repo / "file1.txt").write_text("content")
        (git_repo / "file2.txt").write_text("content")

        stage_all(git_repo)

        staged = get_changed_files(git_repo, staged=True)
        assert "file1.txt" in staged
        assert "file2.txt" in staged


class TestGetCommitInfo:
    """Tests for commit info functions."""

    def test_get_commit_message(self, git_repo):
        """Test getting commit message."""
        message = get_commit_message(git_repo)
        assert "Initial commit" in message

    def test_get_commit_info(self, git_repo):
        """Test getting commit info."""
        info = get_commit_info(git_repo)

        assert len(info["sha"]) == 40
        assert len(info["short_sha"]) == 7
        assert "Initial commit" in info["message"]
        assert info["author"] == "Test User"

    def test_get_recent_commits(self, git_repo):
        """Test getting recent commits."""
        repo = Repo(git_repo)

        # Add more commits
        for i in range(3):
            (git_repo / f"file{i}.txt").write_text("content")
            repo.index.add([f"file{i}.txt"])
            repo.index.commit(f"Commit {i}")

        commits = get_recent_commits(git_repo, n=2)

        assert len(commits) == 2
        assert "Commit 2" in commits[0]["message"]


class TestBranches:
    """Tests for branch functions."""

    def test_checkout_new_branch(self, git_repo):
        """Test checking out a new branch."""
        checkout_branch(git_repo, "feature", create=True)
        assert get_current_branch(git_repo) == "feature"

    def test_branch_exists(self, git_repo):
        """Test checking if branch exists."""
        main_branch = get_current_branch(git_repo)
        assert branch_exists(git_repo, main_branch) is True
        assert branch_exists(git_repo, "nonexistent") is False


class TestFormatCommitMessage:
    """Tests for commit message formatting."""

    def test_format_simple_message(self):
        """Test formatting simple message."""
        message = format_commit_message("Add feature")
        assert message == "Add feature"

    def test_format_message_with_body(self):
        """Test formatting message with body."""
        message = format_commit_message(
            "Add feature",
            body="This adds a new feature that does something.",
        )
        assert "Add feature" in message
        assert "\n\n" in message
        assert "This adds a new feature" in message

    def test_format_message_with_footer(self):
        """Test formatting message with footer."""
        message = format_commit_message(
            "Fix bug",
            footer="Fixes #123",
        )
        assert "Fix bug" in message
        assert "Fixes #123" in message
