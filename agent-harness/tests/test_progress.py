"""Tests for progress.py - Progress file parser."""

import pytest
from pathlib import Path

from agent_harness.progress import (
    ProgressEntry,
    parse_progress_file,
    parse_progress_content,
    get_last_entry,
    get_recent_decisions,
    append_entry,
    format_entry,
    create_entry_for_session,
    get_session_count,
    get_feature_history,
    summarize_recent_activity,
)


class TestProgressEntry:
    """Tests for ProgressEntry dataclass."""

    def test_create_entry(self):
        """Test creating a progress entry."""
        entry = ProgressEntry(session=1, date="2024-01-01")
        assert entry.session == 1
        assert entry.date == "2024-01-01"
        assert entry.what_done == []
        assert entry.decisions == []

    def test_entry_with_data(self):
        """Test entry with full data."""
        entry = ProgressEntry(
            session=5,
            date="2024-01-05",
            feature_id=42,
            feature_description="Test feature",
            what_done=["Did thing 1", "Did thing 2"],
            verification="All tests pass",
            decisions=["Used approach A", "Avoided approach B"],
            status="complete",
        )
        assert entry.feature_id == 42
        assert len(entry.what_done) == 2
        assert len(entry.decisions) == 2


class TestParseProgressContent:
    """Tests for parsing progress file content."""

    def test_parse_empty_content(self):
        """Test parsing empty content."""
        entries = parse_progress_content("")
        assert entries == []

    def test_parse_single_session(self):
        """Test parsing a single session entry."""
        content = """
## Session 1 - 2024-01-01 10:00 UTC

**Feature:** #42 - Test feature

**What Was Done:**
- Did thing 1
- Did thing 2

**Status:** complete

---
"""
        entries = parse_progress_content(content)
        assert len(entries) == 1
        assert entries[0].session == 1
        assert entries[0].feature_id == 42
        assert "Did thing 1" in entries[0].what_done

    def test_parse_multiple_sessions(self):
        """Test parsing multiple session entries."""
        content = """
## Session 1 - 2024-01-01

**Feature:** #1 - First feature
**Status:** complete

---

## Session 2 - 2024-01-02

**Feature:** #2 - Second feature
**Status:** partial

---

## Session 3 - 2024-01-03

**Feature:** #3 - Third feature
**Status:** complete

---
"""
        entries = parse_progress_content(content)
        assert len(entries) == 3
        assert entries[0].session == 1
        assert entries[1].session == 2
        assert entries[2].session == 3
        assert entries[1].status == "partial"

    def test_parse_decisions_section(self):
        """Test parsing decisions section."""
        content = """
## Session 1 - 2024-01-01

**Decisions:**
- Decision 1
- Decision 2
- Decision 3

**Status:** complete

---
"""
        entries = parse_progress_content(content)
        assert len(entries[0].decisions) == 3
        assert "Decision 1" in entries[0].decisions

    def test_parse_verification_section(self):
        """Test parsing verification section."""
        content = """
## Session 1 - 2024-01-01

**Verification:** All 42 tests pass

**Status:** complete

---
"""
        entries = parse_progress_content(content)
        assert "42 tests pass" in entries[0].verification

    def test_parse_commits_section(self):
        """Test parsing commits section."""
        content = """
## Session 1 - 2024-01-01

**Commits:**
- abc123: Initial commit
- def456: Add feature

**Status:** complete

---
"""
        entries = parse_progress_content(content)
        assert len(entries[0].commits) == 2

    def test_parse_status_detection(self):
        """Test status detection from text."""
        complete_content = """
## Session 1 - 2024-01-01
**Status:** complete
"""
        partial_content = """
## Session 1 - 2024-01-01
**Status:** partial work in progress
"""
        failed_content = """
## Session 1 - 2024-01-01
**Status:** failed with errors
"""

        assert parse_progress_content(complete_content)[0].status == "complete"
        assert parse_progress_content(partial_content)[0].status == "partial"
        assert parse_progress_content(failed_content)[0].status == "failed"


class TestParseProgressFile:
    """Tests for parsing progress files from disk."""

    def test_parse_missing_file(self, tmp_path):
        """Test parsing missing file returns empty list."""
        entries = parse_progress_file(tmp_path / "missing.txt")
        assert entries == []

    def test_parse_file(self, tmp_path):
        """Test parsing file from disk."""
        progress_file = tmp_path / "progress.txt"
        progress_file.write_text("""
## Session 1 - 2024-01-01

**Feature:** #1 - Test

**Status:** complete

---
""")

        entries = parse_progress_file(progress_file)
        assert len(entries) == 1


class TestGetLastEntry:
    """Tests for get_last_entry function."""

    def test_get_last_entry(self, tmp_path):
        """Test getting the last entry."""
        progress_file = tmp_path / "progress.txt"
        progress_file.write_text("""
## Session 1 - 2024-01-01
**Status:** complete
---
## Session 2 - 2024-01-02
**Status:** complete
---
## Session 3 - 2024-01-03
**Status:** partial
---
""")

        last = get_last_entry(progress_file)
        assert last is not None
        assert last.session == 3
        assert last.status == "partial"

    def test_get_last_entry_empty_file(self, tmp_path):
        """Test getting last entry from empty file."""
        last = get_last_entry(tmp_path / "missing.txt")
        assert last is None


class TestGetRecentDecisions:
    """Tests for get_recent_decisions function."""

    def test_get_recent_decisions(self, tmp_path):
        """Test getting recent decisions."""
        progress_file = tmp_path / "progress.txt"
        progress_file.write_text("""
## Session 1 - 2024-01-01
**Decisions:**
- Decision A
---
## Session 2 - 2024-01-02
**Decisions:**
- Decision B
- Decision C
---
## Session 3 - 2024-01-03
**Decisions:**
- Decision D
---
""")

        decisions = get_recent_decisions(progress_file, n=2)
        assert "Decision B" in decisions
        assert "Decision C" in decisions
        assert "Decision D" in decisions
        assert "Decision A" not in decisions  # Too old

    def test_get_recent_decisions_empty(self, tmp_path):
        """Test getting decisions from empty file."""
        decisions = get_recent_decisions(tmp_path / "missing.txt", n=3)
        assert decisions == []


class TestFormatEntry:
    """Tests for formatting progress entries."""

    def test_format_basic_entry(self):
        """Test formatting a basic entry."""
        entry = ProgressEntry(
            session=5,
            date="2024-01-05 10:00 UTC",
            status="complete",
        )

        formatted = format_entry(entry)

        assert "## Session 5 - 2024-01-05 10:00 UTC" in formatted
        assert "**Status:** complete" in formatted

    def test_format_entry_with_feature(self):
        """Test formatting entry with feature."""
        entry = ProgressEntry(
            session=1,
            date="2024-01-01",
            feature_id=42,
            feature_description="Test feature",
            status="complete",
        )

        formatted = format_entry(entry)

        assert "#42 - Test feature" in formatted

    def test_format_entry_with_all_fields(self):
        """Test formatting entry with all fields."""
        entry = ProgressEntry(
            session=10,
            date="2024-01-10",
            feature_id=99,
            feature_description="Complex feature",
            what_done=["Did thing 1", "Did thing 2"],
            verification="All tests pass",
            decisions=["Used approach A"],
            current_state="Feature complete",
            next_feature="Feature #100",
            commits=["abc123"],
            status="complete",
            notes=["Note 1"],
        )

        formatted = format_entry(entry)

        assert "## Session 10" in formatted
        assert "#99" in formatted
        assert "- Did thing 1" in formatted
        assert "- Did thing 2" in formatted
        assert "All tests pass" in formatted
        assert "- Used approach A" in formatted
        assert "Feature complete" in formatted
        assert "Feature #100" in formatted
        assert "- abc123" in formatted
        assert "**Status:** complete" in formatted


class TestAppendEntry:
    """Tests for appending entries to progress file."""

    def test_append_to_new_file(self, tmp_path):
        """Test appending to a new file."""
        progress_file = tmp_path / "progress.txt"
        entry = ProgressEntry(
            session=1,
            date="2024-01-01",
            status="complete",
        )

        append_entry(progress_file, entry)

        assert progress_file.exists()
        content = progress_file.read_text()
        assert "## Session 1" in content
        assert "Claude Progress Log" in content  # Header should be added

    def test_append_to_existing_file(self, tmp_path):
        """Test appending to existing file."""
        progress_file = tmp_path / "progress.txt"
        progress_file.write_text("""# Claude Progress Log

## Session 1 - 2024-01-01
**Status:** complete
---
""")

        entry = ProgressEntry(
            session=2,
            date="2024-01-02",
            status="complete",
        )

        append_entry(progress_file, entry)

        content = progress_file.read_text()
        assert "## Session 1" in content
        assert "## Session 2" in content


class TestCreateEntry:
    """Tests for creating new entries."""

    def test_create_entry_for_session(self):
        """Test creating entry for a new session."""
        entry = create_entry_for_session(
            session=5,
            feature_id=42,
            feature_description="Test feature",
        )

        assert entry.session == 5
        assert entry.feature_id == 42
        assert entry.feature_description == "Test feature"
        assert entry.status == "complete"
        assert "UTC" in entry.date


class TestSessionCount:
    """Tests for session counting."""

    def test_get_session_count(self, tmp_path):
        """Test counting sessions."""
        progress_file = tmp_path / "progress.txt"
        progress_file.write_text("""
## Session 1 - 2024-01-01
---
## Session 2 - 2024-01-02
---
## Session 3 - 2024-01-03
---
""")

        count = get_session_count(progress_file)
        assert count == 3

    def test_get_session_count_empty(self, tmp_path):
        """Test counting sessions in empty file."""
        count = get_session_count(tmp_path / "missing.txt")
        assert count == 0


class TestFeatureHistory:
    """Tests for feature history."""

    def test_get_feature_history(self, tmp_path):
        """Test getting history for a feature."""
        progress_file = tmp_path / "progress.txt"
        progress_file.write_text("""
## Session 1 - 2024-01-01
**Feature:** #42 - Feature A
---
## Session 2 - 2024-01-02
**Feature:** #99 - Feature B
---
## Session 3 - 2024-01-03
**Feature:** #42 - Feature A (continued)
---
""")

        history = get_feature_history(progress_file, 42)
        assert len(history) == 2
        assert all(e.feature_id == 42 for e in history)


class TestSummarizeActivity:
    """Tests for activity summarization."""

    def test_summarize_recent_activity(self, tmp_path):
        """Test summarizing recent activity."""
        progress_file = tmp_path / "progress.txt"
        progress_file.write_text("""
## Session 1 - 2024-01-01
**Feature:** #1 - Feature 1
**What Was Done:**
- Item 1
- Item 2
**Status:** complete
---
## Session 2 - 2024-01-02
**Feature:** #2 - Feature 2
**Status:** partial
---
""")

        summary = summarize_recent_activity(progress_file, n=5)

        assert "Session 1" in summary
        assert "Session 2" in summary
        assert "Feature #1" in summary
        assert "2 items" in summary
        assert "[partial]" in summary

    def test_summarize_empty_file(self, tmp_path):
        """Test summarizing empty file."""
        summary = summarize_recent_activity(tmp_path / "missing.txt")
        assert "No previous sessions" in summary
