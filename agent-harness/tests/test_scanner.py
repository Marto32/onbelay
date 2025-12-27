"""Tests for scanner module."""

import pytest
from pathlib import Path

from agent_harness.scanner import (
    ProjectSummary,
    scan_project,
    format_project_summary,
    get_adoption_recommendations,
    _detect_package_manager,
    _detect_python_version,
    _find_source_dir,
    _find_test_dir,
    _count_python_files,
    _count_tests,
    _detect_docker,
    _detect_ci,
    _detect_frameworks,
)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory."""
    project = tmp_path / "test_project"
    project.mkdir()
    return project


@pytest.fixture
def python_project(temp_project):
    """Create a Python project structure."""
    # Source directory
    src = temp_project / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
    (src / "utils.py").write_text("def helper():\n    pass")

    # Tests directory
    tests = temp_project / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "test_main.py").write_text("""
import pytest

def test_one():
    assert True

def test_two():
    assert True

async def test_async():
    assert True
""")

    # Config files
    (temp_project / "pyproject.toml").write_text("""
[tool.poetry]
name = "test-project"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.10"
fastapi = "^0.100.0"
""")

    # Docker
    (temp_project / "Dockerfile").write_text("FROM python:3.10")

    # CI
    github_dir = temp_project / ".github" / "workflows"
    github_dir.mkdir(parents=True)
    (github_dir / "ci.yml").write_text("name: CI\non: push")

    return temp_project


class TestProjectSummary:
    """Tests for ProjectSummary dataclass."""

    def test_project_summary_defaults(self):
        """Test default values for ProjectSummary."""
        summary = ProjectSummary()

        assert not summary.has_source
        assert summary.source_files == 0
        assert summary.package_manager == "none"
        assert not summary.has_docker
        assert summary.source_dir == "src"
        assert summary.test_dir == "tests"

    def test_project_summary_with_values(self):
        """Test ProjectSummary with values."""
        summary = ProjectSummary(
            has_source=True,
            source_files=10,
            source_lines=500,
            has_tests=True,
            test_files=5,
            test_count=25,
            package_manager="poetry",
            python_version="^3.10",
            has_docker=True,
            has_ci=True,
            ci_type="github",
            frameworks=["fastapi", "pytest"],
        )

        assert summary.has_source
        assert summary.source_files == 10
        assert "fastapi" in summary.frameworks


class TestScanProject:
    """Tests for scan_project function."""

    def test_scan_empty_project(self, temp_project):
        """Test scanning an empty project."""
        summary = scan_project(temp_project)

        assert not summary.has_source
        assert not summary.has_tests
        assert summary.package_manager == "none"

    def test_scan_python_project(self, python_project):
        """Test scanning a Python project."""
        summary = scan_project(python_project)

        assert summary.has_source
        assert summary.source_files >= 2
        assert summary.has_tests
        assert summary.test_files >= 1
        assert summary.test_count >= 3
        assert summary.package_manager == "poetry"
        assert summary.has_docker
        assert summary.has_ci
        assert summary.ci_type == "github"
        assert "fastapi" in summary.frameworks


class TestDetectPackageManager:
    """Tests for _detect_package_manager function."""

    def test_detect_poetry(self, temp_project):
        """Test detecting Poetry."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("[tool.poetry]\nname = 'test'")

        assert _detect_package_manager(temp_project) == "poetry"

    def test_detect_pip_pyproject(self, temp_project):
        """Test detecting pip with PEP 621 pyproject.toml."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")

        assert _detect_package_manager(temp_project) == "pip"

    def test_detect_pipenv(self, temp_project):
        """Test detecting Pipenv."""
        (temp_project / "Pipfile").write_text("")

        assert _detect_package_manager(temp_project) == "pipenv"

    def test_detect_requirements(self, temp_project):
        """Test detecting requirements.txt."""
        (temp_project / "requirements.txt").write_text("flask==2.0.0")

        assert _detect_package_manager(temp_project) == "pip"

    def test_detect_setup_py(self, temp_project):
        """Test detecting setup.py."""
        (temp_project / "setup.py").write_text("from setuptools import setup")

        assert _detect_package_manager(temp_project) == "pip"

    def test_detect_none(self, temp_project):
        """Test no package manager."""
        assert _detect_package_manager(temp_project) == "none"


class TestDetectPythonVersion:
    """Tests for _detect_python_version function."""

    def test_detect_from_poetry(self, temp_project):
        """Test detecting from Poetry pyproject.toml."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.10"')

        version = _detect_python_version(temp_project)

        assert version == "^3.10"

    def test_detect_from_pep621(self, temp_project):
        """Test detecting from PEP 621 pyproject.toml."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text('[project]\nrequires-python = ">=3.9"')

        version = _detect_python_version(temp_project)

        assert version == ">=3.9"

    def test_detect_from_python_version_file(self, temp_project):
        """Test detecting from .python-version file."""
        (temp_project / ".python-version").write_text("3.11.0")

        version = _detect_python_version(temp_project)

        assert version == "3.11.0"

    def test_detect_none(self, temp_project):
        """Test no Python version found."""
        version = _detect_python_version(temp_project)

        assert version is None


class TestFindSourceDir:
    """Tests for _find_source_dir function."""

    def test_find_src(self, temp_project):
        """Test finding src directory."""
        src = temp_project / "src"
        src.mkdir()
        (src / "main.py").write_text("")

        assert _find_source_dir(temp_project) == "src"

    def test_find_lib(self, temp_project):
        """Test finding lib directory."""
        lib = temp_project / "lib"
        lib.mkdir()
        (lib / "main.py").write_text("")

        assert _find_source_dir(temp_project) == "lib"

    def test_find_package_dir(self, temp_project):
        """Test finding package directory with __init__.py."""
        pkg = temp_project / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        assert _find_source_dir(temp_project) == "mypackage"

    def test_default_to_src(self, temp_project):
        """Test defaulting to src."""
        assert _find_source_dir(temp_project) == "src"


class TestFindTestDir:
    """Tests for _find_test_dir function."""

    def test_find_tests(self, temp_project):
        """Test finding tests directory."""
        (temp_project / "tests").mkdir()

        assert _find_test_dir(temp_project) == "tests"

    def test_find_test(self, temp_project):
        """Test finding test directory."""
        (temp_project / "test").mkdir()

        assert _find_test_dir(temp_project) == "test"

    def test_default_to_tests(self, temp_project):
        """Test defaulting to tests."""
        assert _find_test_dir(temp_project) == "tests"


class TestCountPythonFiles:
    """Tests for _count_python_files function."""

    def test_count_files(self, temp_project):
        """Test counting Python files."""
        src = temp_project / "src"
        src.mkdir()
        (src / "a.py").write_text("# line 1\n# line 2")
        (src / "b.py").write_text("# single line")

        file_count, line_count = _count_python_files(src)

        assert file_count == 2
        assert line_count >= 3

    def test_count_nested_files(self, temp_project):
        """Test counting nested Python files."""
        src = temp_project / "src"
        sub = src / "sub"
        sub.mkdir(parents=True)
        (src / "a.py").write_text("")
        (sub / "b.py").write_text("")

        file_count, _ = _count_python_files(src)

        assert file_count == 2

    def test_count_excludes_pycache(self, temp_project):
        """Test that __pycache__ is excluded."""
        src = temp_project / "src"
        pycache = src / "__pycache__"
        pycache.mkdir(parents=True)
        (src / "a.py").write_text("")
        (pycache / "a.cpython-310.pyc").write_text("")

        file_count, _ = _count_python_files(src)

        assert file_count == 1

    def test_count_empty_directory(self, temp_project):
        """Test counting in empty directory."""
        src = temp_project / "src"
        src.mkdir()

        file_count, line_count = _count_python_files(src)

        assert file_count == 0
        assert line_count == 0


class TestCountTests:
    """Tests for _count_tests function."""

    def test_count_tests(self, temp_project):
        """Test counting test functions."""
        tests = temp_project / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text("""
def test_one():
    pass

def test_two():
    pass
""")

        count = _count_tests(tests)

        assert count == 2

    def test_count_async_tests(self, temp_project):
        """Test counting async test functions."""
        tests = temp_project / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text("""
async def test_async():
    pass

def test_sync():
    pass
""")

        count = _count_tests(tests)

        assert count == 2


class TestDetectDocker:
    """Tests for _detect_docker function."""

    def test_detect_dockerfile(self, temp_project):
        """Test detecting Dockerfile."""
        (temp_project / "Dockerfile").write_text("")

        assert _detect_docker(temp_project) is True

    def test_detect_docker_compose(self, temp_project):
        """Test detecting docker-compose.yml."""
        (temp_project / "docker-compose.yml").write_text("")

        assert _detect_docker(temp_project) is True

    def test_detect_dockerignore(self, temp_project):
        """Test detecting .dockerignore."""
        (temp_project / ".dockerignore").write_text("")

        assert _detect_docker(temp_project) is True

    def test_no_docker(self, temp_project):
        """Test no Docker files."""
        assert _detect_docker(temp_project) is False


class TestDetectCI:
    """Tests for _detect_ci function."""

    def test_detect_github_actions(self, temp_project):
        """Test detecting GitHub Actions."""
        workflows = temp_project / ".github" / "workflows"
        workflows.mkdir(parents=True)

        has_ci, ci_type = _detect_ci(temp_project)

        assert has_ci is True
        assert ci_type == "github"

    def test_detect_gitlab_ci(self, temp_project):
        """Test detecting GitLab CI."""
        (temp_project / ".gitlab-ci.yml").write_text("")

        has_ci, ci_type = _detect_ci(temp_project)

        assert has_ci is True
        assert ci_type == "gitlab"

    def test_detect_travis(self, temp_project):
        """Test detecting Travis CI."""
        (temp_project / ".travis.yml").write_text("")

        has_ci, ci_type = _detect_ci(temp_project)

        assert has_ci is True
        assert ci_type == "travis"

    def test_no_ci(self, temp_project):
        """Test no CI configuration."""
        has_ci, ci_type = _detect_ci(temp_project)

        assert has_ci is False
        assert ci_type is None


class TestDetectFrameworks:
    """Tests for _detect_frameworks function."""

    def test_detect_fastapi(self, temp_project):
        """Test detecting FastAPI."""
        src = temp_project / "src"
        src.mkdir()
        (src / "main.py").write_text("from fastapi import FastAPI")

        frameworks = _detect_frameworks(temp_project, "src")

        assert "fastapi" in frameworks

    def test_detect_flask(self, temp_project):
        """Test detecting Flask."""
        src = temp_project / "src"
        src.mkdir()
        (src / "app.py").write_text("from flask import Flask\napp = Flask(__name__)")

        frameworks = _detect_frameworks(temp_project, "src")

        assert "flask" in frameworks

    def test_detect_multiple(self, temp_project):
        """Test detecting multiple frameworks."""
        src = temp_project / "src"
        src.mkdir()
        (src / "app.py").write_text("""
from fastapi import FastAPI
from pydantic import BaseModel
import pytest
""")

        frameworks = _detect_frameworks(temp_project, "src")

        assert "fastapi" in frameworks
        assert "pydantic" in frameworks
        assert "pytest" in frameworks


class TestFormatProjectSummary:
    """Tests for format_project_summary function."""

    def test_format_empty_project(self):
        """Test formatting empty project summary."""
        summary = ProjectSummary()

        formatted = format_project_summary(summary)

        assert "No source code found" in formatted
        assert "No tests found" in formatted

    def test_format_full_project(self):
        """Test formatting full project summary."""
        summary = ProjectSummary(
            has_source=True,
            source_files=10,
            source_lines=500,
            has_tests=True,
            test_files=5,
            test_count=25,
            package_manager="poetry",
            python_version="^3.10",
            has_docker=True,
            has_ci=True,
            ci_type="github",
            frameworks=["fastapi", "pytest"],
            source_dir="src",
            test_dir="tests",
        )

        formatted = format_project_summary(summary)

        assert "src/" in formatted
        assert "10" in formatted  # source files
        assert "500" in formatted  # lines
        assert "25" in formatted  # test count
        assert "poetry" in formatted
        assert "Docker: Yes" in formatted
        assert "github" in formatted
        assert "fastapi" in formatted


class TestGetAdoptionRecommendations:
    """Tests for get_adoption_recommendations function."""

    def test_recommendations_for_minimal_project(self):
        """Test recommendations for minimal project."""
        summary = ProjectSummary(
            has_source=False,
            has_tests=False,
            package_manager="none",
        )

        recs = get_adoption_recommendations(summary)

        assert any("source" in r.lower() for r in recs)
        assert any("test" in r.lower() for r in recs)
        assert any("package manager" in r.lower() for r in recs)

    def test_recommendations_for_missing_docker(self):
        """Test recommendation for missing Docker."""
        summary = ProjectSummary(
            has_source=True,
            has_tests=True,
            package_manager="poetry",
            has_docker=False,
        )

        recs = get_adoption_recommendations(summary)

        assert any("docker" in r.lower() for r in recs)

    def test_recommendations_for_missing_ci(self):
        """Test recommendation for missing CI."""
        summary = ProjectSummary(
            has_source=True,
            has_tests=True,
            package_manager="poetry",
            has_docker=True,
            has_ci=False,
        )

        recs = get_adoption_recommendations(summary)

        assert any("ci" in r.lower() for r in recs)

    def test_no_recommendations_for_complete_project(self):
        """Test positive message for complete project."""
        summary = ProjectSummary(
            has_source=True,
            source_files=10,
            has_tests=True,
            test_count=20,
            package_manager="poetry",
            has_docker=True,
            has_ci=True,
            frameworks=["pytest"],
        )

        recs = get_adoption_recommendations(summary)

        assert len(recs) == 1
        assert "well-structured" in recs[0].lower()
