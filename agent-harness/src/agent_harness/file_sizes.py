"""File size tracking for agent-harness.

Tracks source file sizes to monitor code quality and detect files
that are growing too large.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_harness.exceptions import StateError


@dataclass
class FileInfo:
    """Information about a single file."""

    lines: int
    session_added: int
    last_updated_session: Optional[int] = None
    last_lines: Optional[int] = None  # Previous line count for delta tracking


@dataclass
class FileSizeTracker:
    """Tracks file sizes across sessions."""

    session: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    files: dict[str, FileInfo] = field(default_factory=dict)

    def get_file(self, path: str) -> Optional[FileInfo]:
        """Get file info by path."""
        return self.files.get(path)

    def add_file(self, path: str, lines: int, session: Optional[int] = None) -> None:
        """Add or update a file."""
        session = session or self.session
        if path in self.files:
            existing = self.files[path]
            existing.last_lines = existing.lines
            existing.lines = lines
            existing.last_updated_session = session
        else:
            self.files[path] = FileInfo(
                lines=lines,
                session_added=session,
            )

    def remove_file(self, path: str) -> bool:
        """Remove a file from tracking."""
        if path in self.files:
            del self.files[path]
            return True
        return False


def _file_info_to_dict(info: FileInfo) -> dict:
    """Convert FileInfo to dictionary."""
    result = {
        "lines": info.lines,
        "session_added": info.session_added,
    }
    if info.last_updated_session is not None:
        result["last_updated_session"] = info.last_updated_session
    if info.last_lines is not None:
        result["last_lines"] = info.last_lines
    return result


def _dict_to_file_info(data: dict) -> FileInfo:
    """Convert dictionary to FileInfo."""
    return FileInfo(
        lines=data.get("lines", 0),
        session_added=data.get("session_added", 0),
        last_updated_session=data.get("last_updated_session"),
        last_lines=data.get("last_lines"),
    )


def _tracker_to_dict(tracker: FileSizeTracker) -> dict:
    """Convert FileSizeTracker to dictionary."""
    return {
        "session": tracker.session,
        "timestamp": tracker.timestamp,
        "files": {path: _file_info_to_dict(info) for path, info in tracker.files.items()},
    }


def _dict_to_tracker(data: dict) -> FileSizeTracker:
    """Convert dictionary to FileSizeTracker."""
    files = {}
    for path, info_data in data.get("files", {}).items():
        files[path] = _dict_to_file_info(info_data)

    return FileSizeTracker(
        session=data.get("session", 0),
        timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
        files=files,
    )


def load_file_sizes(path: Path) -> FileSizeTracker:
    """
    Load file size tracker from file.

    Args:
        path: Path to file_sizes.json file.

    Returns:
        FileSizeTracker object.

    Raises:
        StateError: If file is invalid.
    """
    if not path.exists():
        return FileSizeTracker(session=0)

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise StateError(f"Invalid JSON in file sizes file: {e}")

    return _dict_to_tracker(data)


def save_file_sizes(path: Path, tracker: FileSizeTracker) -> None:
    """
    Save file size tracker to file.

    Args:
        path: Path to file_sizes.json file.
        tracker: FileSizeTracker object to save.
    """
    # Update timestamp
    tracker.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(_tracker_to_dict(tracker), f, indent=2)


def count_lines(file_path: Path) -> int:
    """
    Count lines in a file.

    Args:
        file_path: Path to the file.

    Returns:
        Number of lines in the file.
    """
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except (OSError, IOError):
        return 0


def scan_file_sizes(
    src_dir: Path,
    extensions: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> dict[str, int]:
    """
    Scan a directory and count lines in all matching files.

    Args:
        src_dir: Source directory to scan.
        extensions: File extensions to include (default: [".py"]).
        exclude_patterns: Path patterns to exclude (default: ["__pycache__", ".git"]).

    Returns:
        Dictionary mapping relative file paths to line counts.
    """
    if extensions is None:
        extensions = [".py"]

    if exclude_patterns is None:
        exclude_patterns = ["__pycache__", ".git", ".pytest_cache", "__pycache__", "node_modules"]

    results = {}

    if not src_dir.exists():
        return results

    for file_path in src_dir.rglob("*"):
        # Skip directories
        if file_path.is_dir():
            continue

        # Skip excluded patterns
        path_str = str(file_path)
        if any(pattern in path_str for pattern in exclude_patterns):
            continue

        # Check extension
        if file_path.suffix not in extensions:
            continue

        # Count lines
        rel_path = str(file_path.relative_to(src_dir))
        results[rel_path] = count_lines(file_path)

    return results


def update_tracker_from_scan(
    tracker: FileSizeTracker,
    src_dir: Path,
    session: int,
    extensions: Optional[list[str]] = None,
) -> FileSizeTracker:
    """
    Update tracker with current file sizes from a scan.

    Args:
        tracker: FileSizeTracker to update.
        src_dir: Source directory to scan.
        session: Current session number.
        extensions: File extensions to include.

    Returns:
        Updated FileSizeTracker.
    """
    tracker.session = session
    current_sizes = scan_file_sizes(src_dir, extensions)

    # Track which files still exist
    existing_paths = set()

    # Update existing and add new files
    for path, lines in current_sizes.items():
        existing_paths.add(path)
        tracker.add_file(path, lines, session)

    # Remove files that no longer exist
    removed = [p for p in tracker.files if p not in existing_paths]
    for path in removed:
        tracker.remove_file(path)

    return tracker


def get_oversized_files(tracker: FileSizeTracker, max_lines: int = 500) -> list[str]:
    """
    Get files that exceed the line count threshold.

    Args:
        tracker: FileSizeTracker object.
        max_lines: Maximum allowed lines per file.

    Returns:
        List of file paths that exceed the threshold.
    """
    oversized = []
    for path, info in tracker.files.items():
        if info.lines > max_lines:
            oversized.append(path)
    return sorted(oversized)


def get_growth_report(tracker: FileSizeTracker) -> dict[str, dict]:
    """
    Get a report of file growth since last update.

    Args:
        tracker: FileSizeTracker object.

    Returns:
        Dictionary mapping paths to growth info.
    """
    report = {}
    for path, info in tracker.files.items():
        if info.last_lines is not None and info.lines != info.last_lines:
            delta = info.lines - info.last_lines
            report[path] = {
                "current": info.lines,
                "previous": info.last_lines,
                "delta": delta,
                "percent_change": (delta / info.last_lines * 100) if info.last_lines > 0 else 0,
            }
    return report


def get_largest_files(tracker: FileSizeTracker, n: int = 10) -> list[tuple[str, int]]:
    """
    Get the n largest files by line count.

    Args:
        tracker: FileSizeTracker object.
        n: Number of files to return.

    Returns:
        List of (path, lines) tuples, sorted by size descending.
    """
    sorted_files = sorted(
        tracker.files.items(),
        key=lambda x: x[1].lines,
        reverse=True,
    )
    return [(path, info.lines) for path, info in sorted_files[:n]]


def get_new_files(tracker: FileSizeTracker, session: int) -> list[str]:
    """
    Get files that were added in a specific session.

    Args:
        tracker: FileSizeTracker object.
        session: Session number to check.

    Returns:
        List of file paths added in that session.
    """
    return [
        path for path, info in tracker.files.items()
        if info.session_added == session
    ]


def get_total_lines(tracker: FileSizeTracker) -> int:
    """
    Get total lines across all tracked files.

    Args:
        tracker: FileSizeTracker object.

    Returns:
        Total line count.
    """
    return sum(info.lines for info in tracker.files.values())


def get_file_count(tracker: FileSizeTracker) -> int:
    """
    Get the number of tracked files.

    Args:
        tracker: FileSizeTracker object.

    Returns:
        Number of files.
    """
    return len(tracker.files)


def generate_size_report(tracker: FileSizeTracker, max_lines: int = 500) -> str:
    """
    Generate a human-readable size report.

    Args:
        tracker: FileSizeTracker object.
        max_lines: Threshold for oversized files.

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append(f"File Size Report (Session {tracker.session})")
    lines.append("-" * 40)
    lines.append(f"Total files: {get_file_count(tracker)}")
    lines.append(f"Total lines: {get_total_lines(tracker)}")
    lines.append("")

    oversized = get_oversized_files(tracker, max_lines)
    if oversized:
        lines.append(f"Oversized files (>{max_lines} lines):")
        for path in oversized:
            info = tracker.files[path]
            lines.append(f"  {path}: {info.lines} lines")
    else:
        lines.append(f"No files exceed {max_lines} lines.")

    lines.append("")
    lines.append("Largest files:")
    for path, line_count in get_largest_files(tracker, 5):
        lines.append(f"  {path}: {line_count} lines")

    return "\n".join(lines)
