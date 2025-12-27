"""Progress file parsing and updating for agent-harness.

Handles reading and writing claude-progress.txt, the human-readable
log of what the agent has done across sessions.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class ProgressEntry:
    """A single session entry in the progress file."""

    session: int
    date: str
    feature_id: Optional[int] = None
    feature_description: Optional[str] = None
    what_done: list[str] = field(default_factory=list)
    verification: str = ""
    decisions: list[str] = field(default_factory=list)
    current_state: str = ""
    next_feature: Optional[str] = None
    commits: list[str] = field(default_factory=list)
    status: str = "complete"  # "complete", "partial", "failed"
    notes: list[str] = field(default_factory=list)


# Regex patterns for parsing
SESSION_HEADER_PATTERN = re.compile(
    r"^##\s*Session\s*(\d+)\s*[-–]\s*(.+)$",
    re.MULTILINE
)

SECTION_PATTERN = re.compile(
    r"^\*\*([A-Z][A-Za-z\s]+):\*\*\s*(.*)$",
    re.MULTILINE
)

FEATURE_PATTERN = re.compile(
    r"(?:Feature\s*)?#?(\d+)(?:\s*[-:]\s*(.+))?",
    re.IGNORECASE
)

LIST_ITEM_PATTERN = re.compile(r"^\s*[-*]\s*(.+)$", re.MULTILINE)


def parse_progress_file(path: Path) -> list[ProgressEntry]:
    """
    Parse a progress file into a list of entries.

    Args:
        path: Path to claude-progress.txt file.

    Returns:
        List of ProgressEntry objects, oldest first.
    """
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    return parse_progress_content(content)


def parse_progress_content(content: str) -> list[ProgressEntry]:
    """
    Parse progress file content into entries.

    Args:
        content: Raw text content of progress file.

    Returns:
        List of ProgressEntry objects, oldest first.
    """
    entries = []

    # Find all session headers
    headers = list(SESSION_HEADER_PATTERN.finditer(content))

    if not headers:
        return entries

    # Parse each session section
    for i, header_match in enumerate(headers):
        session_num = int(header_match.group(1))
        date_str = header_match.group(2).strip()

        # Get section content (from this header to next header or end)
        start = header_match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        section_content = content[start:end]

        entry = _parse_session_section(session_num, date_str, section_content)
        entries.append(entry)

    return entries


def _parse_session_section(session: int, date: str, content: str) -> ProgressEntry:
    """Parse a single session section."""
    entry = ProgressEntry(session=session, date=date)

    # Find all labeled sections
    sections = {}
    current_section = None
    current_content = []

    for line in content.split("\n"):
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content)
            current_section = section_match.group(1).strip().lower()
            current_content = [section_match.group(2)]
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content)

    # Map sections to entry fields
    if "feature" in sections:
        feature_text = sections["feature"]
        match = FEATURE_PATTERN.search(feature_text)
        if match:
            entry.feature_id = int(match.group(1))
            entry.feature_description = match.group(2) or ""

    if "what was done" in sections or "done" in sections:
        done_text = sections.get("what was done", sections.get("done", ""))
        entry.what_done = _extract_list_items(done_text)

    if "verification" in sections:
        entry.verification = sections["verification"].strip()

    if "decisions" in sections:
        entry.decisions = _extract_list_items(sections["decisions"])

    if "current state" in sections or "state" in sections:
        entry.current_state = sections.get("current state", sections.get("state", "")).strip()

    if "next" in sections or "next feature" in sections:
        entry.next_feature = sections.get("next", sections.get("next feature", "")).strip()

    if "commits" in sections:
        entry.commits = _extract_list_items(sections["commits"])

    if "status" in sections:
        status_text = sections["status"].strip().lower()
        if "partial" in status_text:
            entry.status = "partial"
        elif "failed" in status_text or "error" in status_text:
            entry.status = "failed"
        else:
            entry.status = "complete"

    if "notes" in sections:
        entry.notes = _extract_list_items(sections["notes"])

    return entry


def _extract_list_items(text: str) -> list[str]:
    """Extract list items from text."""
    items = []
    for match in LIST_ITEM_PATTERN.finditer(text):
        item = match.group(1).strip()
        if item:
            items.append(item)

    # If no list items found, treat each non-empty line as an item
    if not items:
        for line in text.split("\n"):
            line = line.strip()
            if line and not line.startswith("**"):
                items.append(line)

    return items


def get_last_entry(path: Path) -> Optional[ProgressEntry]:
    """
    Get the most recent entry from the progress file.

    Args:
        path: Path to claude-progress.txt file.

    Returns:
        Most recent ProgressEntry, or None if file is empty.
    """
    entries = parse_progress_file(path)
    return entries[-1] if entries else None


def get_recent_decisions(path: Path, n: int = 3) -> list[str]:
    """
    Get recent decisions from the progress file.

    Args:
        path: Path to claude-progress.txt file.
        n: Number of recent sessions to check.

    Returns:
        List of decision strings from recent sessions.
    """
    entries = parse_progress_file(path)

    if not entries:
        return []

    decisions = []
    for entry in entries[-n:]:
        decisions.extend(entry.decisions)

    return decisions


def append_entry(path: Path, entry: ProgressEntry) -> None:
    """
    Append a new entry to the progress file.

    Args:
        path: Path to claude-progress.txt file.
        entry: ProgressEntry to append.
    """
    # Format the entry
    formatted = format_entry(entry)

    # Ensure file exists with header
    if not path.exists():
        header = _create_file_header()
        path.write_text(header + "\n\n", encoding="utf-8")

    # Append entry
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + formatted + "\n")


def format_entry(entry: ProgressEntry) -> str:
    """
    Format a progress entry for writing to file.

    Args:
        entry: ProgressEntry to format.

    Returns:
        Formatted string.
    """
    lines = []

    # Session header
    lines.append(f"## Session {entry.session} - {entry.date}")
    lines.append("")

    # Feature
    if entry.feature_id is not None:
        feature_text = f"#{entry.feature_id}"
        if entry.feature_description:
            feature_text += f" - {entry.feature_description}"
        lines.append(f"**Feature:** {feature_text}")

    # What was done
    if entry.what_done:
        lines.append("**What Was Done:**")
        for item in entry.what_done:
            lines.append(f"- {item}")
        lines.append("")

    # Verification
    if entry.verification:
        lines.append(f"**Verification:** {entry.verification}")

    # Decisions
    if entry.decisions:
        lines.append("**Decisions:**")
        for decision in entry.decisions:
            lines.append(f"- {decision}")
        lines.append("")

    # Current state
    if entry.current_state:
        lines.append(f"**Current State:** {entry.current_state}")

    # Next feature
    if entry.next_feature:
        lines.append(f"**Next:** {entry.next_feature}")

    # Commits
    if entry.commits:
        lines.append("**Commits:**")
        for commit in entry.commits:
            lines.append(f"- {commit}")
        lines.append("")

    # Status
    lines.append(f"**Status:** {entry.status}")

    # Notes
    if entry.notes:
        lines.append("**Notes:**")
        for note in entry.notes:
            lines.append(f"- {note}")

    # Separator
    lines.append("")
    lines.append("---")

    return "\n".join(lines)


def _create_file_header() -> str:
    """Create the header for a new progress file."""
    return """# Claude Progress Log

This file tracks the progress of Claude coding sessions. Each session
documents what was done, decisions made, and current state.

---"""


def create_entry_for_session(
    session: int,
    feature_id: Optional[int] = None,
    feature_description: Optional[str] = None,
    status: str = "complete",
) -> ProgressEntry:
    """
    Create a new progress entry for a session.

    Args:
        session: Session number.
        feature_id: Feature being worked on (optional).
        feature_description: Description of the feature (optional).
        status: Session status.

    Returns:
        New ProgressEntry object.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return ProgressEntry(
        session=session,
        date=date_str,
        feature_id=feature_id,
        feature_description=feature_description,
        status=status,
    )


def get_session_count(path: Path) -> int:
    """
    Get the number of sessions recorded in the progress file.

    Args:
        path: Path to claude-progress.txt file.

    Returns:
        Number of sessions.
    """
    entries = parse_progress_file(path)
    return len(entries)


def get_feature_history(path: Path, feature_id: int) -> list[ProgressEntry]:
    """
    Get all entries related to a specific feature.

    Args:
        path: Path to claude-progress.txt file.
        feature_id: Feature ID to filter by.

    Returns:
        List of entries for the feature.
    """
    entries = parse_progress_file(path)
    return [e for e in entries if e.feature_id == feature_id]


def summarize_recent_activity(path: Path, n: int = 5) -> str:
    """
    Get a summary of recent activity from the progress file.

    Args:
        path: Path to claude-progress.txt file.
        n: Number of recent sessions to summarize.

    Returns:
        Summary string.
    """
    entries = parse_progress_file(path)

    if not entries:
        return "No previous sessions recorded."

    recent = entries[-n:]

    lines = [f"Recent activity ({len(recent)} sessions):"]
    for entry in recent:
        feature_info = f"Feature #{entry.feature_id}" if entry.feature_id else "No feature"
        status_info = f"[{entry.status}]"
        done_summary = f"{len(entry.what_done)} items" if entry.what_done else "no items"
        lines.append(f"  Session {entry.session} ({entry.date}): {feature_info} - {done_summary} {status_info}")

    return "\n".join(lines)
