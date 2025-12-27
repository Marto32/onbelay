"""Schema migrations for agent-harness.

Supports upgrading state files between harness versions.
"""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from agent_harness.exceptions import MigrationError, StateError
from agent_harness.version import __version__
from agent_harness.state import SCHEMA_VERSION


@dataclass
class VersionCheck:
    """Result of version compatibility check."""

    compatible: bool
    current_version: Optional[int]
    target_version: int
    needs_migration: bool
    message: str


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    success: bool
    from_version: int
    to_version: int
    backup_path: Optional[Path]
    message: str
    files_migrated: list[str]


# Migration registry
# Maps (from_version, to_version) -> migration function
MIGRATIONS: dict[tuple[int, int], Callable[[Path], bool]] = {}


def register_migration(from_version: int, to_version: int):
    """
    Decorator to register a migration function.

    Args:
        from_version: Source schema version.
        to_version: Target schema version.
    """
    def decorator(func: Callable[[Path], bool]) -> Callable[[Path], bool]:
        MIGRATIONS[(from_version, to_version)] = func
        return func
    return decorator


def check_version_compatibility(state_dir: Path) -> VersionCheck:
    """
    Check if state files are compatible with current harness version.

    Args:
        state_dir: Path to .harness/ directory.

    Returns:
        VersionCheck result.
    """
    state_file = state_dir / "session_state.json"

    # No state file = fresh install, compatible
    if not state_file.exists():
        return VersionCheck(
            compatible=True,
            current_version=None,
            target_version=SCHEMA_VERSION,
            needs_migration=False,
            message="No existing state files. Fresh installation.",
        )

    # Read current schema version
    try:
        with open(state_file) as f:
            data = json.load(f)
            current_version = data.get("schema_version", 0)
    except (json.JSONDecodeError, IOError) as e:
        return VersionCheck(
            compatible=False,
            current_version=None,
            target_version=SCHEMA_VERSION,
            needs_migration=False,
            message=f"Cannot read state file: {e}",
        )

    # Same version = compatible, no migration needed
    if current_version == SCHEMA_VERSION:
        return VersionCheck(
            compatible=True,
            current_version=current_version,
            target_version=SCHEMA_VERSION,
            needs_migration=False,
            message="State files are up to date.",
        )

    # Newer version = incompatible (downgrade not supported)
    if current_version > SCHEMA_VERSION:
        return VersionCheck(
            compatible=False,
            current_version=current_version,
            target_version=SCHEMA_VERSION,
            needs_migration=False,
            message=f"State files are from a newer harness version (schema {current_version}). "
                    f"Downgrade not supported. Please upgrade harness.",
        )

    # Older version = check if migration path exists
    if has_migration_path(current_version, SCHEMA_VERSION):
        return VersionCheck(
            compatible=True,
            current_version=current_version,
            target_version=SCHEMA_VERSION,
            needs_migration=True,
            message=f"State files need migration from schema {current_version} to {SCHEMA_VERSION}.",
        )
    else:
        return VersionCheck(
            compatible=False,
            current_version=current_version,
            target_version=SCHEMA_VERSION,
            needs_migration=False,
            message=f"No migration path from schema {current_version} to {SCHEMA_VERSION}. "
                    f"Manual intervention may be required.",
        )


def has_migration_path(from_version: int, to_version: int) -> bool:
    """
    Check if a migration path exists between versions.

    Args:
        from_version: Source version.
        to_version: Target version.

    Returns:
        True if a path exists.
    """
    if from_version >= to_version:
        return from_version == to_version

    # Check for direct migration
    if (from_version, to_version) in MIGRATIONS:
        return True

    # Check for step-by-step migrations
    current = from_version
    while current < to_version:
        found_next = False
        for next_version in range(current + 1, to_version + 1):
            if (current, next_version) in MIGRATIONS:
                current = next_version
                found_next = True
                break
        if not found_next:
            return False

    return current == to_version


def get_migration_path(from_version: int, to_version: int) -> list[tuple[int, int]]:
    """
    Get the sequence of migrations needed.

    Args:
        from_version: Source version.
        to_version: Target version.

    Returns:
        List of (from, to) tuples representing migration steps.
    """
    if from_version >= to_version:
        return []

    path = []
    current = from_version

    while current < to_version:
        # Try to find the longest jump first
        for next_version in range(to_version, current, -1):
            if (current, next_version) in MIGRATIONS:
                path.append((current, next_version))
                current = next_version
                break
        else:
            # No migration found
            break

    return path if current == to_version else []


def backup_state(state_dir: Path) -> Path:
    """
    Create a backup of the state directory.

    Args:
        state_dir: Path to .harness/ directory.

    Returns:
        Path to backup directory.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = state_dir.parent / f".harness_backup_{timestamp}"

    shutil.copytree(state_dir, backup_dir)

    return backup_dir


def migrate_state(
    state_dir: Path,
    from_version: int,
    to_version: int,
    create_backup: bool = True,
) -> MigrationResult:
    """
    Run migrations to upgrade state files.

    Args:
        state_dir: Path to .harness/ directory.
        from_version: Current schema version.
        to_version: Target schema version.
        create_backup: Whether to create a backup first.

    Returns:
        MigrationResult.
    """
    # Get migration path
    path = get_migration_path(from_version, to_version)
    if not path:
        return MigrationResult(
            success=False,
            from_version=from_version,
            to_version=to_version,
            backup_path=None,
            message=f"No migration path from {from_version} to {to_version}",
            files_migrated=[],
        )

    # Create backup
    backup_path = None
    if create_backup:
        try:
            backup_path = backup_state(state_dir)
        except Exception as e:
            return MigrationResult(
                success=False,
                from_version=from_version,
                to_version=to_version,
                backup_path=None,
                message=f"Failed to create backup: {e}",
                files_migrated=[],
            )

    # Run migrations
    files_migrated = []
    current = from_version

    try:
        for step_from, step_to in path:
            migration_func = MIGRATIONS[(step_from, step_to)]
            success = migration_func(state_dir)

            if not success:
                raise MigrationError(f"Migration from {step_from} to {step_to} failed")

            current = step_to
            files_migrated.append(f"schema_{step_from}_to_{step_to}")

        return MigrationResult(
            success=True,
            from_version=from_version,
            to_version=to_version,
            backup_path=backup_path,
            message=f"Successfully migrated from schema {from_version} to {to_version}",
            files_migrated=files_migrated,
        )

    except Exception as e:
        # Restore from backup on failure
        if backup_path and backup_path.exists():
            try:
                shutil.rmtree(state_dir)
                shutil.copytree(backup_path, state_dir)
            except Exception:
                pass  # Best effort restoration

        return MigrationResult(
            success=False,
            from_version=from_version,
            to_version=current,
            backup_path=backup_path,
            message=f"Migration failed: {e}. Restored from backup.",
            files_migrated=files_migrated,
        )


def migrate_or_fail(state_dir: Path) -> None:
    """
    Check compatibility and migrate if needed, or raise an error.

    Args:
        state_dir: Path to .harness/ directory.

    Raises:
        MigrationError: If migration is needed but fails.
        StateError: If state is incompatible.
    """
    check = check_version_compatibility(state_dir)

    if not check.compatible:
        raise StateError(check.message)

    if check.needs_migration:
        result = migrate_state(
            state_dir,
            check.current_version or 0,
            check.target_version,
        )

        if not result.success:
            raise MigrationError(result.message)


# === Migration Functions ===
# Add new migrations here as schema evolves


@register_migration(0, 1)
def migrate_0_to_1(state_dir: Path) -> bool:
    """
    Migrate from unversioned (0) to schema version 1.

    This handles the initial schema versioning.
    """
    state_file = state_dir / "session_state.json"

    if not state_file.exists():
        return True  # Nothing to migrate

    try:
        with open(state_file) as f:
            data = json.load(f)

        # Add schema version if missing
        if "schema_version" not in data:
            data["schema_version"] = 1

        # Add harness version if missing
        if "harness_version" not in data:
            data["harness_version"] = __version__

        # Add new fields with defaults
        defaults = {
            "total_sessions": data.get("last_session", 0),
            "features_completed_this_session": [],
            "last_checkpoint_id": None,
            "timeout_count": 0,
        }

        for key, default in defaults.items():
            if key not in data:
                data[key] = default

        # Write back
        with open(state_file, "w") as f:
            json.dump(data, f, indent=2)

        return True

    except Exception:
        return False


def list_available_migrations() -> list[tuple[int, int, str]]:
    """
    List all registered migrations.

    Returns:
        List of (from_version, to_version, description) tuples.
    """
    migrations = []

    for (from_v, to_v), func in MIGRATIONS.items():
        doc = func.__doc__ or "No description"
        # Get first line of docstring
        description = doc.strip().split("\n")[0]
        migrations.append((from_v, to_v, description))

    return sorted(migrations)


def get_current_schema_version(state_dir: Path) -> Optional[int]:
    """
    Get the current schema version from state files.

    Args:
        state_dir: Path to .harness/ directory.

    Returns:
        Schema version or None if no state files.
    """
    state_file = state_dir / "session_state.json"

    if not state_file.exists():
        return None

    try:
        with open(state_file) as f:
            data = json.load(f)
            return data.get("schema_version", 0)
    except (json.JSONDecodeError, IOError):
        return None


def format_migration_status(check: VersionCheck) -> str:
    """
    Format version check result for display.

    Args:
        check: VersionCheck result.

    Returns:
        Formatted string.
    """
    lines = []
    lines.append("Schema Version Status")
    lines.append("-" * 40)

    if check.current_version is None:
        lines.append("Current: None (fresh installation)")
    else:
        lines.append(f"Current: {check.current_version}")

    lines.append(f"Target: {check.target_version}")
    lines.append("")

    if check.compatible:
        if check.needs_migration:
            lines.append("Status: MIGRATION NEEDED")
            lines.append("Run 'harness migrate' to upgrade state files.")
        else:
            lines.append("Status: UP TO DATE")
    else:
        lines.append("Status: INCOMPATIBLE")
        lines.append(check.message)

    return "\n".join(lines)
