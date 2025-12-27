"""Tests for github_sync module."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from agent_harness.github_sync import (
    GitHubIssue,
    SyncResult,
    check_gh_auth,
    get_repo_info,
    list_issues,
    get_issue,
    create_issue_for_feature,
    close_issue,
    reopen_issue,
    add_comment,
    find_issue_for_feature,
    sync_to_github,
    get_sync_status,
    format_sync_status,
)
from agent_harness.features import Feature, FeaturesFile
from agent_harness.config import GithubConfig


@pytest.fixture
def sample_features():
    """Create sample features file."""
    return FeaturesFile(
        project="test",
        generated_by="test",
        init_mode="new",
        last_updated="2024-01-01",
        features=[
            Feature(id=1, category="core", description="Feature 1", test_file="tests/test_1.py", passes=True),
            Feature(id=2, category="core", description="Feature 2", test_file="tests/test_2.py", passes=False),
            Feature(id=3, category="api", description="Feature 3", test_file="tests/test_3.py", passes=False),
        ],
    )


@pytest.fixture
def sample_github_config():
    """Create sample GitHub config."""
    return GithubConfig(enabled=True, label="harness")


@pytest.fixture
def sample_issues():
    """Create sample GitHub issues."""
    return [
        GitHubIssue(
            number=10,
            title="[Feature #1] Feature 1",
            state="closed",
            labels=["harness"],
        ),
        GitHubIssue(
            number=11,
            title="[Feature #2] Feature 2",
            state="open",
            labels=["harness"],
        ),
    ]


class TestGitHubIssue:
    """Tests for GitHubIssue dataclass."""

    def test_github_issue_creation(self):
        """Test creating a GitHubIssue."""
        issue = GitHubIssue(
            number=123,
            title="Test Issue",
            state="open",
            labels=["bug", "harness"],
            body="Issue body",
            url="https://github.com/test/repo/issues/123",
        )

        assert issue.number == 123
        assert issue.title == "Test Issue"
        assert issue.state == "open"
        assert "bug" in issue.labels
        assert issue.body == "Issue body"
        assert issue.url is not None


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_creation(self):
        """Test creating a SyncResult."""
        result = SyncResult(
            success=True,
            created=[1, 2, 3],
            closed=[4, 5],
            message="Sync complete",
        )

        assert result.success
        assert len(result.created) == 3
        assert len(result.closed) == 2
        assert result.message == "Sync complete"

    def test_sync_result_with_errors(self):
        """Test SyncResult with errors."""
        result = SyncResult(
            success=False,
            errors=["Failed to create issue", "Rate limited"],
            message="Sync failed",
        )

        assert not result.success
        assert len(result.errors) == 2


class TestCheckGhAuth:
    """Tests for check_gh_auth function."""

    @patch("agent_harness.github_sync._run_gh_command")
    def test_check_auth_success(self, mock_run):
        """Test successful auth check."""
        mock_run.return_value = (True, "Logged in", "")

        result = check_gh_auth()

        assert result is True
        mock_run.assert_called_once_with(["auth", "status"])

    @patch("agent_harness.github_sync._run_gh_command")
    def test_check_auth_failure(self, mock_run):
        """Test failed auth check."""
        mock_run.return_value = (False, "", "Not authenticated")

        result = check_gh_auth()

        assert result is False


class TestGetRepoInfo:
    """Tests for get_repo_info function."""

    @patch("agent_harness.github_sync._run_gh_command")
    def test_get_repo_info_success(self, mock_run):
        """Test successful repo info retrieval."""
        mock_run.return_value = (
            True,
            '{"owner": {"login": "testuser"}, "name": "testrepo"}',
            "",
        )

        result = get_repo_info()

        assert result == ("testuser", "testrepo")

    @patch("agent_harness.github_sync._run_gh_command")
    def test_get_repo_info_failure(self, mock_run):
        """Test failed repo info retrieval."""
        mock_run.return_value = (False, "", "Not a repo")

        result = get_repo_info()

        assert result is None


class TestListIssues:
    """Tests for list_issues function."""

    @patch("agent_harness.github_sync._run_gh_command")
    def test_list_issues_success(self, mock_run):
        """Test successful issue listing."""
        mock_run.return_value = (
            True,
            '[{"number": 1, "title": "Issue 1", "state": "open", "labels": [{"name": "harness"}], "body": "Body", "url": "http://example.com"}]',
            "",
        )

        issues = list_issues(label="harness")

        assert len(issues) == 1
        assert issues[0].number == 1
        assert issues[0].title == "Issue 1"
        assert "harness" in issues[0].labels

    @patch("agent_harness.github_sync._run_gh_command")
    def test_list_issues_empty(self, mock_run):
        """Test listing with no issues."""
        mock_run.return_value = (True, "[]", "")

        issues = list_issues()

        assert len(issues) == 0

    @patch("agent_harness.github_sync._run_gh_command")
    def test_list_issues_failure(self, mock_run):
        """Test failed issue listing."""
        mock_run.return_value = (False, "", "Error")

        issues = list_issues()

        assert len(issues) == 0


class TestGetIssue:
    """Tests for get_issue function."""

    @patch("agent_harness.github_sync._run_gh_command")
    def test_get_issue_success(self, mock_run):
        """Test successful issue retrieval."""
        mock_run.return_value = (
            True,
            '{"number": 123, "title": "Test", "state": "open", "labels": [], "body": "", "url": ""}',
            "",
        )

        issue = get_issue(123)

        assert issue is not None
        assert issue.number == 123

    @patch("agent_harness.github_sync._run_gh_command")
    def test_get_issue_not_found(self, mock_run):
        """Test issue not found."""
        mock_run.return_value = (False, "", "Issue not found")

        issue = get_issue(999)

        assert issue is None


class TestFindIssueForFeature:
    """Tests for find_issue_for_feature function."""

    def test_find_existing_issue(self, sample_issues):
        """Test finding an existing issue for a feature."""
        issue = find_issue_for_feature(1, sample_issues)

        assert issue is not None
        assert issue.number == 10

    def test_find_nonexistent_issue(self, sample_issues):
        """Test finding an issue for feature without one."""
        issue = find_issue_for_feature(99, sample_issues)

        assert issue is None


class TestCreateIssueForFeature:
    """Tests for create_issue_for_feature function."""

    @patch("agent_harness.github_sync._run_gh_command")
    def test_create_issue_success(self, mock_run, sample_github_config):
        """Test successful issue creation."""
        mock_run.return_value = (
            True,
            "https://github.com/test/repo/issues/456\n",
            "",
        )

        feature = Feature(
            id=5,
            category="core",
            description="Test feature",
            test_file="tests/test_5.py",
            verification_steps=["Step 1", "Step 2"],
        )

        issue_num = create_issue_for_feature(feature, sample_github_config)

        assert issue_num == 456
        mock_run.assert_called_once()

    @patch("agent_harness.github_sync._run_gh_command")
    def test_create_issue_failure(self, mock_run, sample_github_config):
        """Test failed issue creation."""
        mock_run.return_value = (False, "", "Rate limited")

        feature = Feature(
            id=5,
            category="core",
            description="Test feature",
            test_file="tests/test_5.py",
        )

        issue_num = create_issue_for_feature(feature, sample_github_config)

        assert issue_num is None


class TestCloseIssue:
    """Tests for close_issue function."""

    @patch("agent_harness.github_sync._run_gh_command")
    def test_close_issue_success(self, mock_run):
        """Test successful issue close."""
        mock_run.return_value = (True, "", "")

        result = close_issue(123)

        assert result is True

    @patch("agent_harness.github_sync._run_gh_command")
    def test_close_issue_with_comment(self, mock_run):
        """Test closing with comment."""
        mock_run.return_value = (True, "", "")

        result = close_issue(123, comment="Feature verified")

        assert result is True
        # Should have been called twice - once for comment, once for close
        assert mock_run.call_count == 2


class TestReopenIssue:
    """Tests for reopen_issue function."""

    @patch("agent_harness.github_sync._run_gh_command")
    def test_reopen_issue_success(self, mock_run):
        """Test successful issue reopen."""
        mock_run.return_value = (True, "", "")

        result = reopen_issue(123)

        assert result is True
        mock_run.assert_called_once_with(["issue", "reopen", "123"])


class TestAddComment:
    """Tests for add_comment function."""

    @patch("agent_harness.github_sync._run_gh_command")
    def test_add_comment_success(self, mock_run):
        """Test successful comment addition."""
        mock_run.return_value = (True, "", "")

        result = add_comment(123, "Test comment")

        assert result is True


class TestGetSyncStatus:
    """Tests for get_sync_status function."""

    @patch("agent_harness.github_sync.list_issues")
    def test_sync_status_in_sync(self, mock_list, sample_features, sample_github_config):
        """Test getting sync status when in sync."""
        mock_list.return_value = [
            GitHubIssue(number=10, title="[Feature #1] Feature 1", state="closed", labels=["harness"]),
            GitHubIssue(number=11, title="[Feature #2] Feature 2", state="open", labels=["harness"]),
            GitHubIssue(number=12, title="[Feature #3] Feature 3", state="open", labels=["harness"]),
        ]

        status = get_sync_status(sample_features, sample_github_config)

        assert status["synced"] is True
        assert len(status["features_without_issues"]) == 0

    @patch("agent_harness.github_sync.list_issues")
    def test_sync_status_missing_issues(self, mock_list, sample_features, sample_github_config):
        """Test getting sync status with missing issues."""
        mock_list.return_value = [
            GitHubIssue(number=10, title="[Feature #1] Feature 1", state="closed", labels=["harness"]),
        ]

        status = get_sync_status(sample_features, sample_github_config)

        assert status["synced"] is False
        assert 2 in status["features_without_issues"]
        assert 3 in status["features_without_issues"]

    @patch("agent_harness.github_sync.list_issues")
    def test_sync_status_mismatched_state(self, mock_list, sample_features, sample_github_config):
        """Test getting sync status with mismatched state."""
        mock_list.return_value = [
            GitHubIssue(number=10, title="[Feature #1] Feature 1", state="open", labels=["harness"]),  # Should be closed
            GitHubIssue(number=11, title="[Feature #2] Feature 2", state="open", labels=["harness"]),
            GitHubIssue(number=12, title="[Feature #3] Feature 3", state="open", labels=["harness"]),
        ]

        status = get_sync_status(sample_features, sample_github_config)

        assert status["synced"] is False
        assert len(status["mismatched_state"]) == 1


class TestFormatSyncStatus:
    """Tests for format_sync_status function."""

    def test_format_in_sync(self):
        """Test formatting in-sync status."""
        status = {
            "synced": True,
            "issues_open": 5,
            "issues_closed": 3,
            "features_without_issues": [],
            "issues_without_features": [],
            "mismatched_state": [],
        }

        formatted = format_sync_status(status)

        assert "IN SYNC" in formatted
        assert "5 open" in formatted
        assert "3 closed" in formatted

    def test_format_out_of_sync(self):
        """Test formatting out-of-sync status."""
        status = {
            "synced": False,
            "issues_open": 3,
            "issues_closed": 1,
            "features_without_issues": [4, 5],
            "issues_without_features": [99],
            "mismatched_state": [{"feature_id": 1, "issue_number": 10, "feature_passes": True, "issue_state": "open"}],
        }

        formatted = format_sync_status(status)

        assert "OUT OF SYNC" in formatted
        assert "4" in formatted or "5" in formatted  # Missing features
        assert "99" in formatted  # Orphan issue


class TestSyncToGitHub:
    """Tests for sync_to_github function."""

    @patch("agent_harness.github_sync.check_gh_auth")
    def test_sync_not_authenticated(self, mock_auth, sample_features, sample_github_config):
        """Test sync when not authenticated."""
        mock_auth.return_value = False

        result = sync_to_github(sample_features, sample_github_config)

        assert not result.success
        assert "authenticated" in result.message.lower()

    @patch("agent_harness.github_sync.check_gh_auth")
    @patch("agent_harness.github_sync.list_issues")
    @patch("agent_harness.github_sync.create_issue_for_feature")
    @patch("agent_harness.github_sync.close_issue")
    @patch("time.sleep")
    def test_sync_creates_missing_issues(
        self, mock_sleep, mock_close, mock_create, mock_list, mock_auth,
        sample_features, sample_github_config
    ):
        """Test sync creates issues for features without them."""
        mock_auth.return_value = True
        mock_list.return_value = []  # No existing issues
        mock_create.return_value = 100

        result = sync_to_github(
            sample_features,
            sample_github_config,
            create_missing=True,
            close_completed=False,
        )

        assert result.success
        # Should create issues for features 2 and 3 (not passing)
        assert mock_create.call_count == 2

    @patch("agent_harness.github_sync.check_gh_auth")
    @patch("agent_harness.github_sync.list_issues")
    @patch("agent_harness.github_sync.close_issue")
    @patch("time.sleep")
    def test_sync_closes_completed_issues(
        self, mock_sleep, mock_close, mock_list, mock_auth,
        sample_features, sample_github_config
    ):
        """Test sync closes issues for completed features."""
        mock_auth.return_value = True
        mock_list.return_value = [
            GitHubIssue(number=10, title="[Feature #1] Feature 1", state="open", labels=["harness"]),
        ]
        mock_close.return_value = True

        result = sync_to_github(
            sample_features,
            sample_github_config,
            create_missing=False,
            close_completed=True,
        )

        assert result.success
        # Feature 1 passes and has open issue, should be closed
        mock_close.assert_called_once()
        assert 10 in result.closed
