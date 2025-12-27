"""Tests for migrations module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from agent_harness.migrations import (
    VersionCheck,
    MigrationResult,
    check_version_compatibility,
    has_migration_path,
    get_migration_path,
    backup_state,
    migrate_state,
    migrate_or_fail,
    register_migration,
    MIGRATIONS,
    list_available_migrations,
    get_current_schema_version,
    format_migration_status,
)
from agent_harness.state import SCHEMA_VERSION
from agent_harness.exceptions import MigrationError, StateError


@pytest.fixture
def temp_harness_dir(tmp_path):
    """Create a temporary .harness directory."""
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()
    return harness_dir


@pytest.fixture
def state_file(temp_harness_dir):
    """Create a state file."""
    state_file = temp_harness_dir / "session_state.json"
    return state_file


class TestVersionCheck:
    """Tests for VersionCheck dataclass."""

    def test_version_check_creation(self):
        """Test creating a VersionCheck."""
        check = VersionCheck(
            compatible=True,
            current_version=1,
            target_version=2,
            needs_migration=True,
            message="Migration needed",
        )

        assert check.compatible
        assert check.current_version == 1
        assert check.target_version == 2
        assert check.needs_migration
        assert check.message == "Migration needed"


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_migration_result_success(self):
        """Test successful MigrationResult."""
        result = MigrationResult(
            success=True,
            from_version=0,
            to_version=1,
            backup_path=Path("/backup"),
            message="Migration complete",
            files_migrated=["session_state.json"],
        )

        assert result.success
        assert result.from_version == 0
        assert result.to_version == 1

    def test_migration_result_failure(self):
        """Test failed MigrationResult."""
        result = MigrationResult(
            success=False,
            from_version=0,
            to_version=1,
            backup_path=None,
            message="Migration failed",
            files_migrated=[],
        )

        assert not result.success


class TestCheckVersionCompatibility:
    """Tests for check_version_compatibility function."""

    def test_no_state_file(self, temp_harness_dir):
        """Test compatibility when no state file exists."""
        check = check_version_compatibility(temp_harness_dir)

        assert check.compatible
        assert check.current_version is None
        assert check.needs_migration is False
        assert "Fresh" in check.message

    def test_same_version(self, temp_harness_dir, state_file):
        """Test compatibility when versions match."""
        state_file.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "status": "complete",
        }))

        check = check_version_compatibility(temp_harness_dir)

        assert check.compatible
        assert check.current_version == SCHEMA_VERSION
        assert check.needs_migration is False
        assert "up to date" in check.message.lower()

    def test_older_version(self, temp_harness_dir, state_file):
        """Test compatibility with older version."""
        state_file.write_text(json.dumps({
            "schema_version": 0,
            "status": "complete",
        }))

        check = check_version_compatibility(temp_harness_dir)

        assert check.compatible
        assert check.current_version == 0
        assert check.needs_migration is True

    def test_newer_version(self, temp_harness_dir, state_file):
        """Test incompatibility with newer version."""
        state_file.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION + 10,
            "status": "complete",
        }))

        check = check_version_compatibility(temp_harness_dir)

        assert not check.compatible
        assert "newer" in check.message.lower()

    def test_invalid_json(self, temp_harness_dir, state_file):
        """Test with invalid JSON."""
        state_file.write_text("not valid json")

        check = check_version_compatibility(temp_harness_dir)

        assert not check.compatible
        assert "Cannot read" in check.message


class TestHasMigrationPath:
    """Tests for has_migration_path function."""

    def test_same_version(self):
        """Test path exists for same version."""
        assert has_migration_path(1, 1)

    def test_direct_migration(self):
        """Test direct migration path exists."""
        # Migration 0->1 is registered
        assert has_migration_path(0, 1)

    def test_no_path_downgrade(self):
        """Test no path for downgrade."""
        assert not has_migration_path(2, 1)


class TestGetMigrationPath:
    """Tests for get_migration_path function."""

    def test_same_version_empty_path(self):
        """Test empty path for same version."""
        path = get_migration_path(1, 1)
        assert path == []

    def test_direct_path(self):
        """Test direct migration path."""
        path = get_migration_path(0, 1)
        assert (0, 1) in path

    def test_no_path_downgrade(self):
        """Test no path for downgrade."""
        path = get_migration_path(2, 1)
        assert path == []


class TestBackupState:
    """Tests for backup_state function."""

    def test_backup_creates_directory(self, temp_harness_dir, state_file):
        """Test backup creates a new directory."""
        state_file.write_text(json.dumps({"test": "data"}))

        backup_path = backup_state(temp_harness_dir)

        assert backup_path.exists()
        assert backup_path.is_dir()
        assert "backup" in backup_path.name

    def test_backup_copies_files(self, temp_harness_dir, state_file):
        """Test backup copies all files."""
        state_file.write_text(json.dumps({"test": "data"}))
        (temp_harness_dir / "other.json").write_text('{"other": 1}')

        backup_path = backup_state(temp_harness_dir)

        assert (backup_path / "session_state.json").exists()
        assert (backup_path / "other.json").exists()


class TestMigrateState:
    """Tests for migrate_state function."""

    def test_migrate_from_0_to_1(self, temp_harness_dir, state_file):
        """Test migration from version 0 to 1."""
        state_file.write_text(json.dumps({
            "status": "complete",
            "last_session": 5,
        }))

        result = migrate_state(temp_harness_dir, 0, 1)

        assert result.success
        assert result.from_version == 0
        assert result.to_version == 1

        # Verify state was updated
        new_state = json.loads(state_file.read_text())
        assert new_state.get("schema_version") == 1

    def test_migrate_creates_backup(self, temp_harness_dir, state_file):
        """Test migration creates backup."""
        state_file.write_text(json.dumps({"status": "complete"}))

        result = migrate_state(temp_harness_dir, 0, 1, create_backup=True)

        assert result.success
        assert result.backup_path is not None
        assert result.backup_path.exists()

    def test_migrate_no_backup(self, temp_harness_dir, state_file):
        """Test migration without backup."""
        state_file.write_text(json.dumps({"status": "complete"}))

        result = migrate_state(temp_harness_dir, 0, 1, create_backup=False)

        assert result.success
        assert result.backup_path is None

    def test_migrate_no_path(self, temp_harness_dir):
        """Test migration with no available path."""
        result = migrate_state(temp_harness_dir, 5, 10)

        assert not result.success
        assert "No migration path" in result.message


class TestMigrateOrFail:
    """Tests for migrate_or_fail function."""

    def test_no_migration_needed(self, temp_harness_dir, state_file):
        """Test when no migration is needed."""
        state_file.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "status": "complete",
        }))

        # Should not raise
        migrate_or_fail(temp_harness_dir)

    def test_migration_succeeds(self, temp_harness_dir, state_file):
        """Test successful migration."""
        # Use a state without schema_version (truly version 0)
        state_file.write_text(json.dumps({
            "status": "complete",
            "last_session": 3,
        }))

        # Should not raise
        migrate_or_fail(temp_harness_dir)

        new_state = json.loads(state_file.read_text())
        # After migration, schema_version should be added
        assert "schema_version" in new_state

    def test_incompatible_raises(self, temp_harness_dir, state_file):
        """Test incompatible version raises StateError."""
        state_file.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION + 10,
            "status": "complete",
        }))

        with pytest.raises(StateError):
            migrate_or_fail(temp_harness_dir)


class TestMigration0To1:
    """Tests for the 0->1 migration."""

    def test_adds_schema_version(self, temp_harness_dir, state_file):
        """Test migration adds schema_version."""
        state_file.write_text(json.dumps({
            "status": "complete",
            "last_session": 3,
        }))

        migrate_state(temp_harness_dir, 0, 1)

        new_state = json.loads(state_file.read_text())
        assert new_state["schema_version"] == 1

    def test_adds_harness_version(self, temp_harness_dir, state_file):
        """Test migration adds harness_version."""
        state_file.write_text(json.dumps({
            "status": "complete",
        }))

        migrate_state(temp_harness_dir, 0, 1)

        new_state = json.loads(state_file.read_text())
        assert "harness_version" in new_state

    def test_adds_new_fields(self, temp_harness_dir, state_file):
        """Test migration adds new fields."""
        state_file.write_text(json.dumps({
            "status": "complete",
            "last_session": 5,
        }))

        migrate_state(temp_harness_dir, 0, 1)

        new_state = json.loads(state_file.read_text())
        assert "total_sessions" in new_state
        assert "features_completed_this_session" in new_state
        assert "last_checkpoint_id" in new_state
        assert "timeout_count" in new_state

    def test_preserves_existing_data(self, temp_harness_dir, state_file):
        """Test migration preserves existing data."""
        state_file.write_text(json.dumps({
            "status": "partial",
            "last_session": 10,
            "current_feature": 5,
        }))

        migrate_state(temp_harness_dir, 0, 1)

        new_state = json.loads(state_file.read_text())
        assert new_state["status"] == "partial"
        assert new_state["last_session"] == 10
        assert new_state["current_feature"] == 5


class TestListAvailableMigrations:
    """Tests for list_available_migrations function."""

    def test_list_migrations(self):
        """Test listing available migrations."""
        migrations = list_available_migrations()

        assert len(migrations) > 0
        assert any(m[0] == 0 and m[1] == 1 for m in migrations)

    def test_migrations_have_descriptions(self):
        """Test migrations have descriptions."""
        migrations = list_available_migrations()

        for from_v, to_v, desc in migrations:
            assert desc is not None
            assert len(desc) > 0


class TestGetCurrentSchemaVersion:
    """Tests for get_current_schema_version function."""

    def test_no_state_file(self, temp_harness_dir):
        """Test with no state file."""
        version = get_current_schema_version(temp_harness_dir)
        assert version is None

    def test_with_schema_version(self, temp_harness_dir, state_file):
        """Test with schema version in state."""
        state_file.write_text(json.dumps({"schema_version": 5}))

        version = get_current_schema_version(temp_harness_dir)
        assert version == 5

    def test_with_no_schema_version(self, temp_harness_dir, state_file):
        """Test with missing schema version (old format)."""
        state_file.write_text(json.dumps({"status": "complete"}))

        version = get_current_schema_version(temp_harness_dir)
        assert version == 0


class TestFormatMigrationStatus:
    """Tests for format_migration_status function."""

    def test_format_up_to_date(self):
        """Test formatting up-to-date status."""
        check = VersionCheck(
            compatible=True,
            current_version=SCHEMA_VERSION,
            target_version=SCHEMA_VERSION,
            needs_migration=False,
            message="Up to date",
        )

        formatted = format_migration_status(check)

        assert "UP TO DATE" in formatted
        assert str(SCHEMA_VERSION) in formatted

    def test_format_needs_migration(self):
        """Test formatting migration-needed status."""
        check = VersionCheck(
            compatible=True,
            current_version=0,
            target_version=1,
            needs_migration=True,
            message="Migration needed",
        )

        formatted = format_migration_status(check)

        assert "MIGRATION NEEDED" in formatted
        assert "0" in formatted
        assert "1" in formatted

    def test_format_incompatible(self):
        """Test formatting incompatible status."""
        check = VersionCheck(
            compatible=False,
            current_version=10,
            target_version=1,
            needs_migration=False,
            message="Version too new",
        )

        formatted = format_migration_status(check)

        assert "INCOMPATIBLE" in formatted
