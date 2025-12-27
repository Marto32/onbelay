"""Checkpoint system for agent-harness.

Creates and restores checkpoints for rollback capability.
"""

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import uuid

from agent_harness.exceptions import GitError, StateError
from agent_harness.git_ops import get_head_ref, reset_hard, is_git_repo, is_working_tree_clean


@dataclass
class Checkpoint:
    """A checkpoint for rollback."""

    id: str
    timestamp: str
    session: int
    git_ref: str
    features_json_hash: str
    progress_file_hash: str
    session_state_hash: str
    reason: str
    files_backed_up: list[str] = field(default_factory=list)


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    checkpoint_id: str
    git_restored: bool
    files_restored: list[str]
    errors: list[str] = field(default_factory=list)
    message: str = ""


def _compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    if not path.exists():
        return ""

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _checkpoint_to_dict(checkpoint: Checkpoint) -> dict:
    """Convert Checkpoint to dictionary."""
    return {
        "id": checkpoint.id,
        "timestamp": checkpoint.timestamp,
        "session": checkpoint.session,
        "git_ref": checkpoint.git_ref,
        "features_json_hash": checkpoint.features_json_hash,
        "progress_file_hash": checkpoint.progress_file_hash,
        "session_state_hash": checkpoint.session_state_hash,
        "reason": checkpoint.reason,
        "files_backed_up": checkpoint.files_backed_up,
    }


def _dict_to_checkpoint(data: dict) -> Checkpoint:
    """Convert dictionary to Checkpoint."""
    return Checkpoint(
        id=data["id"],
        timestamp=data["timestamp"],
        session=data["session"],
        git_ref=data["git_ref"],
        features_json_hash=data.get("features_json_hash", ""),
        progress_file_hash=data.get("progress_file_hash", ""),
        session_state_hash=data.get("session_state_hash", ""),
        reason=data.get("reason", ""),
        files_backed_up=data.get("files_backed_up", []),
    )


def _get_checkpoint_dir(project_dir: Path) -> Path:
    """Get the checkpoint directory."""
    return project_dir / ".harness" / "checkpoints"


def _get_checkpoint_path(project_dir: Path, checkpoint_id: str) -> Path:
    """Get path for a specific checkpoint."""
    return _get_checkpoint_dir(project_dir) / checkpoint_id


def create_checkpoint(
    project_dir: Path,
    session: int,
    reason: str,
    features_path: Optional[Path] = None,
    progress_path: Optional[Path] = None,
    state_dir: Optional[Path] = None,
) -> Checkpoint:
    """
    Create a checkpoint before risky operations.

    Args:
        project_dir: Path to the project directory.
        session: Current session number.
        reason: Reason for creating checkpoint.
        features_path: Path to features.json (optional).
        progress_path: Path to claude-progress.txt (optional).
        state_dir: Path to .harness directory (optional).

    Returns:
        Created Checkpoint object.

    Raises:
        GitError: If git operations fail.
        StateError: If checkpoint creation fails.
    """
    # Generate checkpoint ID
    checkpoint_id = f"checkpoint-{session}-{uuid.uuid4().hex[:8]}"

    # Determine paths
    if features_path is None:
        features_path = project_dir / "features.json"
    if progress_path is None:
        progress_path = project_dir / "claude-progress.txt"
    if state_dir is None:
        state_dir = project_dir / ".harness"

    # Get git ref
    git_ref = ""
    if is_git_repo(project_dir):
        git_ref = get_head_ref(project_dir)

    # Compute file hashes
    features_hash = _compute_file_hash(features_path)
    progress_hash = _compute_file_hash(progress_path)
    state_hash = _compute_file_hash(state_dir / "session_state.json")

    # Create checkpoint directory
    checkpoint_path = _get_checkpoint_path(project_dir, checkpoint_id)
    checkpoint_path.mkdir(parents=True, exist_ok=True)

    # Backup files
    files_backed_up = []

    if features_path.exists():
        shutil.copy2(features_path, checkpoint_path / "features.json")
        files_backed_up.append("features.json")

    if progress_path.exists():
        shutil.copy2(progress_path, checkpoint_path / "claude-progress.txt")
        files_backed_up.append("claude-progress.txt")

    state_file = state_dir / "session_state.json"
    if state_file.exists():
        shutil.copy2(state_file, checkpoint_path / "session_state.json")
        files_backed_up.append("session_state.json")

    # Create checkpoint object
    checkpoint = Checkpoint(
        id=checkpoint_id,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        session=session,
        git_ref=git_ref,
        features_json_hash=features_hash,
        progress_file_hash=progress_hash,
        session_state_hash=state_hash,
        reason=reason,
        files_backed_up=files_backed_up,
    )

    # Save checkpoint metadata
    metadata_path = checkpoint_path / "checkpoint.json"
    with open(metadata_path, "w") as f:
        json.dump(_checkpoint_to_dict(checkpoint), f, indent=2)

    return checkpoint


def rollback_to_checkpoint(
    project_dir: Path,
    checkpoint_id: str,
    features_path: Optional[Path] = None,
    progress_path: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    restore_git: bool = True,
) -> RollbackResult:
    """
    Rollback to a checkpoint.

    Args:
        project_dir: Path to the project directory.
        checkpoint_id: ID of checkpoint to rollback to.
        features_path: Path to features.json (optional).
        progress_path: Path to claude-progress.txt (optional).
        state_dir: Path to .harness directory (optional).
        restore_git: Whether to restore git state (default True).

    Returns:
        RollbackResult with details of the operation.

    Raises:
        StateError: If checkpoint not found.
    """
    # Load checkpoint
    checkpoint = get_checkpoint(project_dir, checkpoint_id)
    if checkpoint is None:
        raise StateError(f"Checkpoint not found: {checkpoint_id}")

    # Determine paths
    if features_path is None:
        features_path = project_dir / "features.json"
    if progress_path is None:
        progress_path = project_dir / "claude-progress.txt"
    if state_dir is None:
        state_dir = project_dir / ".harness"

    checkpoint_path = _get_checkpoint_path(project_dir, checkpoint_id)
    errors = []
    files_restored = []
    git_restored = False

    # Restore git state
    if restore_git and checkpoint.git_ref and is_git_repo(project_dir):
        try:
            reset_hard(project_dir, checkpoint.git_ref)
            git_restored = True
        except GitError as e:
            errors.append(f"Failed to restore git state: {e}")

    # Restore files
    for filename in checkpoint.files_backed_up:
        backup_file = checkpoint_path / filename
        if backup_file.exists():
            if filename == "features.json":
                shutil.copy2(backup_file, features_path)
            elif filename == "claude-progress.txt":
                shutil.copy2(backup_file, progress_path)
            elif filename == "session_state.json":
                shutil.copy2(backup_file, state_dir / "session_state.json")
            files_restored.append(filename)

    # Verify restoration
    success = len(errors) == 0

    if success:
        # Verify file hashes match
        if checkpoint.features_json_hash and features_path.exists():
            current_hash = _compute_file_hash(features_path)
            if current_hash != checkpoint.features_json_hash:
                errors.append("features.json hash mismatch after restoration")
                success = False

    return RollbackResult(
        success=success,
        checkpoint_id=checkpoint_id,
        git_restored=git_restored,
        files_restored=files_restored,
        errors=errors,
        message="Rollback successful" if success else "Rollback completed with errors",
    )


def get_checkpoint(project_dir: Path, checkpoint_id: str) -> Optional[Checkpoint]:
    """
    Get a checkpoint by ID.

    Args:
        project_dir: Path to the project directory.
        checkpoint_id: ID of the checkpoint.

    Returns:
        Checkpoint object, or None if not found.
    """
    checkpoint_path = _get_checkpoint_path(project_dir, checkpoint_id)
    metadata_path = checkpoint_path / "checkpoint.json"

    if not metadata_path.exists():
        return None

    with open(metadata_path) as f:
        data = json.load(f)

    return _dict_to_checkpoint(data)


def list_checkpoints(project_dir: Path) -> list[Checkpoint]:
    """
    List all checkpoints for a project.

    Args:
        project_dir: Path to the project directory.

    Returns:
        List of Checkpoint objects, newest first.
    """
    checkpoint_dir = _get_checkpoint_dir(project_dir)

    if not checkpoint_dir.exists():
        return []

    checkpoints = []
    for item in checkpoint_dir.iterdir():
        if item.is_dir():
            metadata_path = item / "checkpoint.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    data = json.load(f)
                checkpoints.append(_dict_to_checkpoint(data))

    # Sort by timestamp, newest first
    checkpoints.sort(key=lambda c: c.timestamp, reverse=True)
    return checkpoints


def list_checkpoints_for_session(project_dir: Path, session: int) -> list[Checkpoint]:
    """
    List checkpoints for a specific session.

    Args:
        project_dir: Path to the project directory.
        session: Session number.

    Returns:
        List of Checkpoint objects for the session.
    """
    all_checkpoints = list_checkpoints(project_dir)
    return [c for c in all_checkpoints if c.session == session]


def cleanup_old_checkpoints(
    project_dir: Path,
    max_age_days: int = 7,
    keep_per_session: int = 1,
) -> int:
    """
    Clean up old checkpoints.

    Args:
        project_dir: Path to the project directory.
        max_age_days: Maximum age in days to keep.
        keep_per_session: Number of checkpoints to keep per session.

    Returns:
        Number of checkpoints deleted.
    """
    checkpoints = list_checkpoints(project_dir)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    deleted = 0

    # Group by session
    by_session: dict[int, list[Checkpoint]] = {}
    for cp in checkpoints:
        if cp.session not in by_session:
            by_session[cp.session] = []
        by_session[cp.session].append(cp)

    for session, session_checkpoints in by_session.items():
        # Keep the most recent ones per session
        to_keep = set()
        for cp in session_checkpoints[:keep_per_session]:
            to_keep.add(cp.id)

        for cp in session_checkpoints:
            if cp.id in to_keep:
                continue

            # Parse timestamp
            try:
                cp_time = datetime.fromisoformat(cp.timestamp.replace("Z", "+00:00"))
                if cp_time < cutoff:
                    delete_checkpoint(project_dir, cp.id)
                    deleted += 1
            except ValueError:
                continue

    return deleted


def delete_checkpoint(project_dir: Path, checkpoint_id: str) -> bool:
    """
    Delete a checkpoint.

    Args:
        project_dir: Path to the project directory.
        checkpoint_id: ID of the checkpoint to delete.

    Returns:
        True if deleted, False if not found.
    """
    checkpoint_path = _get_checkpoint_path(project_dir, checkpoint_id)

    if not checkpoint_path.exists():
        return False

    shutil.rmtree(checkpoint_path)
    return True


def verify_checkpoint(project_dir: Path, checkpoint_id: str) -> dict:
    """
    Verify a checkpoint's integrity.

    Args:
        project_dir: Path to the project directory.
        checkpoint_id: ID of the checkpoint.

    Returns:
        Dictionary with verification results.
    """
    checkpoint = get_checkpoint(project_dir, checkpoint_id)
    if checkpoint is None:
        return {"valid": False, "error": "Checkpoint not found"}

    checkpoint_path = _get_checkpoint_path(project_dir, checkpoint_id)
    results = {"valid": True, "files": {}, "errors": []}

    for filename in checkpoint.files_backed_up:
        backup_file = checkpoint_path / filename
        if backup_file.exists():
            results["files"][filename] = {
                "exists": True,
                "size": backup_file.stat().st_size,
            }
        else:
            results["files"][filename] = {"exists": False}
            results["errors"].append(f"Missing backup file: {filename}")
            results["valid"] = False

    return results


def get_latest_checkpoint(project_dir: Path) -> Optional[Checkpoint]:
    """
    Get the most recent checkpoint.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Most recent Checkpoint, or None if no checkpoints exist.
    """
    checkpoints = list_checkpoints(project_dir)
    return checkpoints[0] if checkpoints else None


def get_checkpoint_count(project_dir: Path) -> int:
    """
    Get the number of checkpoints.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Number of checkpoints.
    """
    return len(list_checkpoints(project_dir))
