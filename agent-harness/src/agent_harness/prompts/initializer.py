"""Initializer prompt template for agent-harness."""

from typing import Optional


def build_initializer_prompt(
    spec_content: str,
    project_summary: Optional[str] = None,
    mode: str = "new",
) -> str:
    """
    Build an initializer prompt for project setup.

    Args:
        spec_content: Content of the specification file.
        project_summary: Summary of existing project (for adopt mode).
        mode: "new" or "adopt".

    Returns:
        Complete initializer prompt string.
    """
    lines = []

    lines.append("INITIALIZATION SESSION")
    lines.append("=" * 40)
    lines.append("")

    if mode == "adopt":
        lines.append("MODE: ADOPT (existing project)")
        lines.append("")
        if project_summary:
            lines.append("EXISTING PROJECT SUMMARY:")
            lines.append(project_summary)
            lines.append("")
        lines.append("Create features.json that includes:")
        lines.append("  - Existing functionality (mark as passing)")
        lines.append("  - New features from spec (mark as not passing)")
    else:
        lines.append("MODE: NEW (greenfield project)")
        lines.append("")
        lines.append("Create features.json with all features from spec.")
        lines.append("All features start as not passing.")

    lines.append("")
    lines.append("SPECIFICATION:")
    lines.append("-" * 40)

    # Include spec content (truncated if too long)
    if len(spec_content) > 3000:
        lines.append(spec_content[:3000])
        lines.append("... [truncated]")
    else:
        lines.append(spec_content)

    lines.append("-" * 40)
    lines.append("")

    lines.append("REQUIRED OUTPUTS:")
    lines.append("")
    lines.append("1. features.json with structure:")
    lines.append('   {')
    lines.append('     "project": "<project_name>",')
    lines.append('     "generated_by": "harness-init",')
    lines.append('     "init_mode": "<new|adopt>",')
    lines.append('     "last_updated": "<ISO timestamp>",')
    lines.append('     "features": [')
    lines.append('       {')
    lines.append('         "id": 1,')
    lines.append('         "category": "<category>",')
    lines.append('         "description": "<what this feature does>",')
    lines.append('         "test_file": "tests/test_<name>.py",')
    lines.append('         "verification_steps": ["step1", "step2"],')
    lines.append('         "size_estimate": "<small|medium|large>",')
    lines.append('         "depends_on": [<dependency_ids>],')
    lines.append('         "passes": false,')
    lines.append('         "origin": "<spec|existing>",')
    lines.append('         "verification_type": "<automated|hybrid|manual>"')
    lines.append('       }')
    lines.append('     ]')
    lines.append('   }')
    lines.append("")
    lines.append("2. init.sh - Setup script")
    lines.append("3. reset.sh - Reset script (restore to clean state)")
    lines.append("4. Initial claude-progress.txt entry")
    lines.append("")
    lines.append("FEATURE GUIDELINES:")
    lines.append("- Order features by dependencies (dependencies first)")
    lines.append("- Keep verification_steps to 7 or fewer")
    lines.append("- Use realistic size estimates")
    lines.append("- Group related features in same category")
    lines.append("")
    lines.append("Begin initialization:")

    return "\n".join(lines)


def build_adopt_analysis_prompt(
    project_dir: str,
    detected_files: list[str],
    detected_tests: list[str],
    frameworks: list[str],
) -> str:
    """
    Build a prompt for analyzing an existing project.

    Args:
        project_dir: Project directory path.
        detected_files: List of detected source files.
        detected_tests: List of detected test files.
        frameworks: List of detected frameworks.

    Returns:
        Analysis prompt string.
    """
    lines = []

    lines.append("PROJECT ANALYSIS")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Analyzing existing project at: {project_dir}")
    lines.append("")

    if detected_files:
        lines.append(f"SOURCE FILES ({len(detected_files)}):")
        for f in detected_files[:20]:
            lines.append(f"  - {f}")
        if len(detected_files) > 20:
            lines.append(f"  ... and {len(detected_files) - 20} more")
        lines.append("")

    if detected_tests:
        lines.append(f"TEST FILES ({len(detected_tests)}):")
        for t in detected_tests[:10]:
            lines.append(f"  - {t}")
        if len(detected_tests) > 10:
            lines.append(f"  ... and {len(detected_tests) - 10} more")
        lines.append("")

    if frameworks:
        lines.append("DETECTED FRAMEWORKS:")
        for fw in frameworks:
            lines.append(f"  - {fw}")
        lines.append("")

    lines.append("Analyze this project structure and identify:")
    lines.append("1. Major components and their purpose")
    lines.append("2. Test coverage status")
    lines.append("3. Potential features to extract")

    return "\n".join(lines)


def build_features_validation_prompt(features_json: str) -> str:
    """
    Build a prompt for validating generated features.

    Args:
        features_json: Generated features.json content.

    Returns:
        Validation prompt string.
    """
    lines = []

    lines.append("FEATURES VALIDATION")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Validate the generated features.json:")
    lines.append("")
    lines.append(features_json[:2000])
    if len(features_json) > 2000:
        lines.append("... [truncated]")
    lines.append("")
    lines.append("CHECK:")
    lines.append("1. All required fields present")
    lines.append("2. No circular dependencies")
    lines.append("3. All test files have unique names")
    lines.append("4. Size estimates are reasonable")
    lines.append("5. Verification steps are actionable")

    return "\n".join(lines)
