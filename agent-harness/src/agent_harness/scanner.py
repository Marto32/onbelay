"""Project scanner for agent-harness.

Scans existing projects for adopt mode to detect structure,
frameworks, and existing tests.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectSummary:
    """Summary of a scanned project."""

    # Basic info
    has_source: bool = False
    source_files: int = 0
    source_lines: int = 0

    has_tests: bool = False
    test_files: int = 0
    test_count: int = 0

    # Package management
    package_manager: str = "none"  # "poetry", "pip", "pipenv", "none"
    python_version: Optional[str] = None

    # Configuration
    has_docker: bool = False
    has_ci: bool = False
    ci_type: Optional[str] = None  # "github", "gitlab", "jenkins", etc.

    # Frameworks detected
    frameworks: list[str] = field(default_factory=list)

    # Directories
    source_dir: str = "src"
    test_dir: str = "tests"

    # Additional info
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)


# Framework detection patterns
FRAMEWORK_PATTERNS = {
    "fastapi": [
        r"from\s+fastapi\s+import",
        r"import\s+fastapi",
        r"FastAPI\(\)",
    ],
    "flask": [
        r"from\s+flask\s+import",
        r"import\s+flask",
        r"Flask\(__name__\)",
    ],
    "django": [
        r"from\s+django",
        r"import\s+django",
        r"DJANGO_SETTINGS_MODULE",
    ],
    "pytest": [
        r"import\s+pytest",
        r"from\s+pytest\s+import",
        r"@pytest\.",
    ],
    "sqlalchemy": [
        r"from\s+sqlalchemy\s+import",
        r"import\s+sqlalchemy",
    ],
    "pydantic": [
        r"from\s+pydantic\s+import",
        r"import\s+pydantic",
        r"BaseModel",
    ],
    "click": [
        r"import\s+click",
        r"from\s+click\s+import",
        r"@click\.",
    ],
    "typer": [
        r"import\s+typer",
        r"from\s+typer\s+import",
    ],
    "rich": [
        r"from\s+rich\s+import",
        r"import\s+rich",
    ],
    "requests": [
        r"import\s+requests",
        r"from\s+requests\s+import",
    ],
    "httpx": [
        r"import\s+httpx",
        r"from\s+httpx\s+import",
    ],
    "aiohttp": [
        r"import\s+aiohttp",
        r"from\s+aiohttp\s+import",
    ],
    "celery": [
        r"from\s+celery\s+import",
        r"import\s+celery",
    ],
    "redis": [
        r"import\s+redis",
        r"from\s+redis\s+import",
    ],
    "mongodb": [
        r"import\s+pymongo",
        r"from\s+pymongo\s+import",
        r"import\s+motor",
    ],
    "postgresql": [
        r"import\s+psycopg",
        r"import\s+asyncpg",
    ],
}


def scan_project(project_dir: Path) -> ProjectSummary:
    """
    Scan a project directory and return a summary.

    Args:
        project_dir: Path to the project directory.

    Returns:
        ProjectSummary object.
    """
    summary = ProjectSummary()

    # Detect package manager
    summary.package_manager = _detect_package_manager(project_dir)

    # Detect Python version
    summary.python_version = _detect_python_version(project_dir)

    # Find source directory
    summary.source_dir = _find_source_dir(project_dir)
    src_path = project_dir / summary.source_dir

    # Scan source files
    if src_path.exists():
        summary.has_source = True
        summary.source_files, summary.source_lines = _count_python_files(src_path)

    # Find test directory
    summary.test_dir = _find_test_dir(project_dir)
    test_path = project_dir / summary.test_dir

    # Scan test files
    if test_path.exists():
        summary.has_tests = True
        summary.test_files, _ = _count_python_files(test_path)
        summary.test_count = _count_tests(test_path)

    # Detect Docker
    summary.has_docker = _detect_docker(project_dir)

    # Detect CI
    summary.has_ci, summary.ci_type = _detect_ci(project_dir)

    # Detect frameworks
    summary.frameworks = _detect_frameworks(project_dir, summary.source_dir)

    # Find entry points
    summary.entry_points = _find_entry_points(project_dir)

    # List config files
    summary.config_files = _find_config_files(project_dir)

    return summary


def _detect_package_manager(project_dir: Path) -> str:
    """Detect which package manager is used."""
    if (project_dir / "pyproject.toml").exists():
        # Check if it's poetry or other
        pyproject = (project_dir / "pyproject.toml").read_text()
        if "[tool.poetry]" in pyproject:
            return "poetry"
        elif "[project]" in pyproject:
            return "pip"  # PEP 621 style

    if (project_dir / "Pipfile").exists():
        return "pipenv"

    if (project_dir / "requirements.txt").exists():
        return "pip"

    if (project_dir / "setup.py").exists():
        return "pip"

    return "none"


def _detect_python_version(project_dir: Path) -> Optional[str]:
    """Detect Python version requirement."""
    # Check pyproject.toml
    pyproject_path = project_dir / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text()
        # Poetry format
        match = re.search(r'python\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
        # PEP 621 format
        match = re.search(r'requires-python\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)

    # Check .python-version
    python_version_path = project_dir / ".python-version"
    if python_version_path.exists():
        return python_version_path.read_text().strip()

    return None


def _find_source_dir(project_dir: Path) -> str:
    """Find the source directory."""
    # Common patterns
    candidates = ["src", "lib", "app"]

    for candidate in candidates:
        path = project_dir / candidate
        if path.exists() and path.is_dir():
            # Check if it has Python files
            if list(path.rglob("*.py")):
                return candidate

    # Check for package directory (same name as project)
    for item in project_dir.iterdir():
        if item.is_dir() and not item.name.startswith(".") and not item.name.startswith("_"):
            if (item / "__init__.py").exists():
                return item.name

    # Default to src even if it doesn't exist
    return "src"


def _find_test_dir(project_dir: Path) -> str:
    """Find the test directory."""
    candidates = ["tests", "test", "spec", "specs"]

    for candidate in candidates:
        path = project_dir / candidate
        if path.exists() and path.is_dir():
            return candidate

    return "tests"


def _count_python_files(directory: Path) -> tuple[int, int]:
    """Count Python files and total lines."""
    file_count = 0
    line_count = 0

    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        file_count += 1
        try:
            line_count += len(py_file.read_text().splitlines())
        except Exception:
            pass

    return file_count, line_count


def _count_tests(test_dir: Path) -> int:
    """Count the number of test functions."""
    test_count = 0
    test_pattern = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)", re.MULTILINE)

    for py_file in test_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            content = py_file.read_text()
            matches = test_pattern.findall(content)
            test_count += len(matches)
        except Exception:
            pass

    return test_count


def _detect_docker(project_dir: Path) -> bool:
    """Detect if Docker is used."""
    docker_files = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"]
    return any((project_dir / f).exists() for f in docker_files)


def _detect_ci(project_dir: Path) -> tuple[bool, Optional[str]]:
    """Detect CI configuration."""
    ci_patterns = {
        "github": [".github/workflows"],
        "gitlab": [".gitlab-ci.yml"],
        "travis": [".travis.yml"],
        "jenkins": ["Jenkinsfile"],
        "circleci": [".circleci/config.yml"],
        "azure": ["azure-pipelines.yml"],
    }

    for ci_type, paths in ci_patterns.items():
        for path in paths:
            if (project_dir / path).exists():
                return True, ci_type

    return False, None


def _detect_frameworks(project_dir: Path, source_dir: str) -> list[str]:
    """Detect frameworks used in the project."""
    detected = set()
    src_path = project_dir / source_dir

    if not src_path.exists():
        return []

    # Read all Python files and check for framework patterns
    for py_file in src_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text()
        except Exception:
            continue

        for framework, patterns in FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    detected.add(framework)
                    break

    return sorted(detected)


def _find_entry_points(project_dir: Path) -> list[str]:
    """Find potential entry points."""
    entry_points = []

    # Check pyproject.toml for scripts
    pyproject_path = project_dir / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text()
        # Find [tool.poetry.scripts] or [project.scripts]
        if "[tool.poetry.scripts]" in content or "[project.scripts]" in content:
            # Simple extraction of script names
            script_pattern = re.compile(r'(\w+)\s*=\s*"')
            matches = script_pattern.findall(content)
            entry_points.extend(matches[:5])  # Limit to 5

    # Check for common entry point files
    common_entry_points = ["main.py", "app.py", "cli.py", "__main__.py"]
    for ep in common_entry_points:
        if (project_dir / ep).exists():
            entry_points.append(ep)

        # Also check in source dir
        for src_dir in ["src", "lib", "app"]:
            src_path = project_dir / src_dir
            if (src_path / ep).exists():
                entry_points.append(f"{src_dir}/{ep}")

    return list(set(entry_points))


def _find_config_files(project_dir: Path) -> list[str]:
    """Find configuration files."""
    config_patterns = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "requirements*.txt",
        ".env",
        ".env.example",
        "config.yaml",
        "config.yml",
        "config.json",
        ".harness.yaml",
    ]

    found = []
    for pattern in config_patterns:
        if "*" in pattern:
            found.extend([str(f.name) for f in project_dir.glob(pattern)])
        elif (project_dir / pattern).exists():
            found.append(pattern)

    return sorted(set(found))


def format_project_summary(summary: ProjectSummary) -> str:
    """
    Format a project summary for display.

    Args:
        summary: ProjectSummary object.

    Returns:
        Formatted string.
    """
    lines = []
    lines.append("Project Scan Results")
    lines.append("=" * 40)
    lines.append("")

    # Source
    lines.append("Source Code:")
    if summary.has_source:
        lines.append(f"  Directory: {summary.source_dir}/")
        lines.append(f"  Files: {summary.source_files}")
        lines.append(f"  Lines: {summary.source_lines:,}")
    else:
        lines.append("  No source code found")
    lines.append("")

    # Tests
    lines.append("Tests:")
    if summary.has_tests:
        lines.append(f"  Directory: {summary.test_dir}/")
        lines.append(f"  Test files: {summary.test_files}")
        lines.append(f"  Test functions: {summary.test_count}")
    else:
        lines.append("  No tests found")
    lines.append("")

    # Package management
    lines.append("Package Management:")
    lines.append(f"  Manager: {summary.package_manager}")
    if summary.python_version:
        lines.append(f"  Python: {summary.python_version}")
    lines.append("")

    # Frameworks
    if summary.frameworks:
        lines.append("Frameworks Detected:")
        for framework in summary.frameworks:
            lines.append(f"  - {framework}")
        lines.append("")

    # Infrastructure
    lines.append("Infrastructure:")
    lines.append(f"  Docker: {'Yes' if summary.has_docker else 'No'}")
    if summary.has_ci:
        lines.append(f"  CI: Yes ({summary.ci_type})")
    else:
        lines.append("  CI: No")
    lines.append("")

    # Entry points
    if summary.entry_points:
        lines.append("Entry Points:")
        for ep in summary.entry_points[:5]:
            lines.append(f"  - {ep}")
        lines.append("")

    # Config files
    if summary.config_files:
        lines.append("Config Files:")
        for cf in summary.config_files[:10]:
            lines.append(f"  - {cf}")

    return "\n".join(lines)


def get_adoption_recommendations(summary: ProjectSummary) -> list[str]:
    """
    Get recommendations for adopting this project.

    Args:
        summary: ProjectSummary object.

    Returns:
        List of recommendation strings.
    """
    recommendations = []

    if not summary.has_source:
        recommendations.append("Create a source directory (e.g., src/) for your code")

    if not summary.has_tests:
        recommendations.append("Add a tests/ directory with test files")
    elif summary.test_count < 5:
        recommendations.append(f"Add more tests (currently only {summary.test_count})")

    if summary.package_manager == "none":
        recommendations.append("Set up a package manager (Poetry recommended)")

    if not summary.has_docker:
        recommendations.append("Consider adding Docker for reproducible environments")

    if not summary.has_ci:
        recommendations.append("Set up CI/CD (GitHub Actions recommended)")

    if "pytest" not in summary.frameworks and summary.has_tests:
        recommendations.append("Consider using pytest for testing")

    if not recommendations:
        recommendations.append("Project is well-structured for adoption!")

    return recommendations
