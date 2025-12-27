"""Tests for file_sizes.py - File size tracking."""

import json
import pytest
from pathlib import Path

from agent_harness.file_sizes import (
    FileInfo,
    FileSizeTracker,
    load_file_sizes,
    save_file_sizes,
    count_lines,
    scan_file_sizes,
    update_tracker_from_scan,
    get_oversized_files,
    get_growth_report,
    get_largest_files,
    get_new_files,
    get_total_lines,
    get_file_count,
    generate_size_report,
)
from agent_harness.exceptions import StateError


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_create_file_info(self):
        """Test creating file info."""
        info = FileInfo(lines=100, session_added=1)
        assert info.lines == 100
        assert info.session_added == 1
        assert info.last_updated_session is None
        assert info.last_lines is None


class TestFileSizeTracker:
    """Tests for FileSizeTracker dataclass."""

    def test_create_empty_tracker(self):
        """Test creating empty tracker."""
        tracker = FileSizeTracker(session=0)
        assert tracker.session == 0
        assert tracker.files == {}

    def test_add_file(self):
        """Test adding a file to tracker."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("test.py", 100)

        assert "test.py" in tracker.files
        assert tracker.files["test.py"].lines == 100
        assert tracker.files["test.py"].session_added == 1

    def test_update_file(self):
        """Test updating an existing file."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("test.py", 100)

        # Update in session 2
        tracker.session = 2
        tracker.add_file("test.py", 150, session=2)

        info = tracker.files["test.py"]
        assert info.lines == 150
        assert info.last_lines == 100
        assert info.last_updated_session == 2
        assert info.session_added == 1  # Original session preserved

    def test_remove_file(self):
        """Test removing a file from tracker."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("test.py", 100)

        result = tracker.remove_file("test.py")

        assert result is True
        assert "test.py" not in tracker.files

    def test_remove_nonexistent_file(self):
        """Test removing a nonexistent file."""
        tracker = FileSizeTracker(session=1)
        result = tracker.remove_file("missing.py")
        assert result is False

    def test_get_file(self):
        """Test getting file info."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("test.py", 100)

        info = tracker.get_file("test.py")
        assert info is not None
        assert info.lines == 100

    def test_get_missing_file(self):
        """Test getting missing file returns None."""
        tracker = FileSizeTracker(session=1)
        assert tracker.get_file("missing.py") is None


class TestLoadSaveFileSizes:
    """Tests for load/save functions."""

    def test_save_and_load(self, tmp_path):
        """Test saving and loading file sizes."""
        sizes_path = tmp_path / "file_sizes.json"
        tracker = FileSizeTracker(session=5)
        tracker.add_file("src/main.py", 200)
        tracker.add_file("src/utils.py", 150)

        save_file_sizes(sizes_path, tracker)
        loaded = load_file_sizes(sizes_path)

        assert loaded.session == 5
        assert len(loaded.files) == 2
        assert loaded.files["src/main.py"].lines == 200

    def test_load_missing_file(self, tmp_path):
        """Test loading missing file returns empty tracker."""
        loaded = load_file_sizes(tmp_path / "missing.json")
        assert loaded.session == 0
        assert loaded.files == {}

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises error."""
        invalid_path = tmp_path / "invalid.json"
        invalid_path.write_text("not json")

        with pytest.raises(StateError, match="Invalid JSON"):
            load_file_sizes(invalid_path)


class TestCountLines:
    """Tests for line counting."""

    def test_count_lines(self, tmp_path):
        """Test counting lines in a file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\n")

        count = count_lines(test_file)
        assert count == 3

    def test_count_lines_empty_file(self, tmp_path):
        """Test counting lines in empty file."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("")

        count = count_lines(test_file)
        assert count == 0

    def test_count_lines_missing_file(self, tmp_path):
        """Test counting lines in missing file returns 0."""
        count = count_lines(tmp_path / "missing.py")
        assert count == 0


class TestScanFileSizes:
    """Tests for scanning file sizes."""

    def test_scan_file_sizes(self, tmp_path):
        """Test scanning a directory."""
        # Create test files
        (tmp_path / "main.py").write_text("line1\nline2\n")
        (tmp_path / "utils.py").write_text("line1\nline2\nline3\n")
        (tmp_path / "readme.md").write_text("# Readme\n")

        sizes = scan_file_sizes(tmp_path, extensions=[".py"])

        assert len(sizes) == 2
        assert sizes["main.py"] == 2
        assert sizes["utils.py"] == 3

    def test_scan_nested_directory(self, tmp_path):
        """Test scanning nested directories."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("a\nb\nc\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("a\nb\n")

        sizes = scan_file_sizes(tmp_path, extensions=[".py"])

        assert "src/main.py" in sizes
        assert "tests/test_main.py" in sizes

    def test_scan_excludes_patterns(self, tmp_path):
        """Test that excluded patterns are skipped."""
        (tmp_path / "main.py").write_text("code\n")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "main.cpython-311.pyc").write_text("cache\n")

        sizes = scan_file_sizes(tmp_path, extensions=[".py", ".pyc"])

        assert "main.py" in sizes
        assert "__pycache__/main.cpython-311.pyc" not in sizes

    def test_scan_missing_directory(self, tmp_path):
        """Test scanning missing directory returns empty."""
        sizes = scan_file_sizes(tmp_path / "missing")
        assert sizes == {}


class TestUpdateTrackerFromScan:
    """Tests for updating tracker from scan."""

    def test_update_tracker(self, tmp_path):
        """Test updating tracker from directory scan."""
        (tmp_path / "main.py").write_text("line1\nline2\n")

        tracker = FileSizeTracker(session=0)
        updated = update_tracker_from_scan(tracker, tmp_path, session=1)

        assert updated.session == 1
        assert "main.py" in updated.files
        assert updated.files["main.py"].lines == 2

    def test_update_removes_deleted_files(self, tmp_path):
        """Test that deleted files are removed from tracker."""
        (tmp_path / "main.py").write_text("line1\n")

        tracker = FileSizeTracker(session=1)
        tracker.add_file("main.py", 1)
        tracker.add_file("deleted.py", 100)  # This file doesn't exist

        updated = update_tracker_from_scan(tracker, tmp_path, session=2)

        assert "main.py" in updated.files
        assert "deleted.py" not in updated.files


class TestOversizedFiles:
    """Tests for oversized file detection."""

    def test_get_oversized_files(self):
        """Test finding oversized files."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("small.py", 100)
        tracker.add_file("medium.py", 400)
        tracker.add_file("large.py", 600)
        tracker.add_file("huge.py", 1000)

        oversized = get_oversized_files(tracker, max_lines=500)

        assert "large.py" in oversized
        assert "huge.py" in oversized
        assert "small.py" not in oversized
        assert "medium.py" not in oversized

    def test_get_oversized_files_custom_threshold(self):
        """Test oversized detection with custom threshold."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("file.py", 150)

        assert get_oversized_files(tracker, max_lines=100) == ["file.py"]
        assert get_oversized_files(tracker, max_lines=200) == []


class TestGrowthReport:
    """Tests for growth reporting."""

    def test_get_growth_report(self):
        """Test getting growth report."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("growing.py", 100)

        # Simulate update
        tracker.session = 2
        tracker.add_file("growing.py", 150, session=2)  # Grew by 50 lines

        report = get_growth_report(tracker)

        assert "growing.py" in report
        assert report["growing.py"]["current"] == 150
        assert report["growing.py"]["previous"] == 100
        assert report["growing.py"]["delta"] == 50
        assert report["growing.py"]["percent_change"] == 50.0

    def test_get_growth_report_no_changes(self):
        """Test growth report with no changes."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("stable.py", 100)

        report = get_growth_report(tracker)

        assert report == {}  # No changes to report


class TestLargestFiles:
    """Tests for finding largest files."""

    def test_get_largest_files(self):
        """Test getting largest files."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("small.py", 10)
        tracker.add_file("medium.py", 100)
        tracker.add_file("large.py", 500)
        tracker.add_file("huge.py", 1000)

        largest = get_largest_files(tracker, n=2)

        assert len(largest) == 2
        assert largest[0] == ("huge.py", 1000)
        assert largest[1] == ("large.py", 500)


class TestNewFiles:
    """Tests for finding new files."""

    def test_get_new_files(self):
        """Test finding files added in a session."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("old.py", 100, session=1)
        tracker.add_file("new1.py", 50, session=3)
        tracker.add_file("new2.py", 75, session=3)

        new_in_3 = get_new_files(tracker, session=3)

        assert "new1.py" in new_in_3
        assert "new2.py" in new_in_3
        assert "old.py" not in new_in_3


class TestTotalLines:
    """Tests for total line counting."""

    def test_get_total_lines(self):
        """Test getting total lines."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("a.py", 100)
        tracker.add_file("b.py", 200)
        tracker.add_file("c.py", 300)

        total = get_total_lines(tracker)
        assert total == 600


class TestFileCount:
    """Tests for file counting."""

    def test_get_file_count(self):
        """Test getting file count."""
        tracker = FileSizeTracker(session=1)
        tracker.add_file("a.py", 100)
        tracker.add_file("b.py", 200)

        count = get_file_count(tracker)
        assert count == 2


class TestSizeReport:
    """Tests for size report generation."""

    def test_generate_size_report(self):
        """Test generating a size report."""
        tracker = FileSizeTracker(session=5)
        tracker.add_file("small.py", 100)
        tracker.add_file("large.py", 600)

        report = generate_size_report(tracker, max_lines=500)

        assert "Session 5" in report
        assert "Total files: 2" in report
        assert "Total lines: 700" in report
        assert "large.py" in report
        assert "600 lines" in report
