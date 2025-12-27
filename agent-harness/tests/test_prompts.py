"""Tests for prompt templates module."""

import pytest

from agent_harness.config import Config
from agent_harness.features import Feature, FeaturesFile
from agent_harness.progress import ProgressEntry
from agent_harness.prompts.builder import (
    BASE_SYSTEM_PROMPT,
    build_system_prompt,
    build_user_prompt,
    get_model_for_prompt_type,
    select_prompt_type,
)
from agent_harness.prompts.cleanup import (
    build_cleanup_prompt,
    build_lint_fix_prompt,
    build_refactor_prompt,
)
from agent_harness.prompts.coding import (
    build_coding_prompt,
    build_feature_intro,
    build_test_first_reminder,
)
from agent_harness.prompts.continuation import (
    build_context_limit_continuation,
    build_continuation_prompt,
    build_stuck_recovery_prompt,
)
from agent_harness.prompts.initializer import (
    build_adopt_analysis_prompt,
    build_features_validation_prompt,
    build_initializer_prompt,
)
from agent_harness.state import SessionState


class TestBuildSystemPrompt:
    """Tests for build_system_prompt."""

    def test_base_prompt_always_included(self):
        """Base prompt should be included in all system prompts."""
        prompt = build_system_prompt("coding")
        assert "expert software engineer" in prompt
        assert "CORE RULES" in prompt

    def test_cleanup_session_instructions(self):
        """Cleanup session should have specific instructions."""
        prompt = build_system_prompt("cleanup")
        assert "CLEANUP SESSION" in prompt
        assert "code quality" in prompt
        assert "NOT add new functionality" in prompt

    def test_continuation_session_instructions(self):
        """Continuation session should have specific instructions."""
        prompt = build_system_prompt("continuation")
        assert "CONTINUATION SESSION" in prompt
        assert "previous session" in prompt

    def test_init_session_instructions(self):
        """Init session should have specific instructions."""
        prompt = build_system_prompt("init")
        assert "INITIALIZATION SESSION" in prompt
        assert "features.json" in prompt

    def test_config_evidence_required(self):
        """Config with require_evidence should add evidence instructions."""
        config = Config()
        config.verification.require_evidence = True
        prompt = build_system_prompt("coding", config)
        assert "EVIDENCE REQUIRED" in prompt

    def test_config_file_size_limit(self):
        """Config with max_file_lines should add limit info."""
        config = Config()
        config.quality.max_file_lines = 500
        prompt = build_system_prompt("coding", config)
        assert "FILE SIZE LIMIT" in prompt
        assert "500" in prompt


class TestBuildUserPrompt:
    """Tests for build_user_prompt."""

    def test_orientation_included(self):
        """Orientation should be included in user prompt."""
        orientation = "Project: test-project\nFeatures: 5 total"
        prompt = build_user_prompt(orientation)
        assert "test-project" in prompt
        assert "5 total" in prompt

    def test_additional_context_included(self):
        """Additional context should be included when provided."""
        prompt = build_user_prompt("orientation", "Extra info here")
        assert "ADDITIONAL CONTEXT" in prompt
        assert "Extra info here" in prompt

    def test_ends_with_begin_working(self):
        """Prompt should end with instruction to begin working."""
        prompt = build_user_prompt("orientation")
        assert "Begin working" in prompt


class TestSelectPromptType:
    """Tests for select_prompt_type."""

    def test_explicit_init_prompt(self):
        """Explicit init next_prompt should return init."""
        state = SessionState(next_prompt="init", status="init")
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[],
        )
        config = Config()
        assert select_prompt_type(state, features, config) == "init"

    def test_explicit_cleanup_prompt(self):
        """Explicit cleanup next_prompt should return cleanup."""
        state = SessionState(next_prompt="cleanup")
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[],
        )
        config = Config()
        assert select_prompt_type(state, features, config) == "cleanup"

    def test_explicit_continuation_prompt(self):
        """Explicit continuation next_prompt should return continuation."""
        state = SessionState(next_prompt="continuation")
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[],
        )
        config = Config()
        assert select_prompt_type(state, features, config) == "continuation"

    def test_all_features_complete_triggers_cleanup(self):
        """When all features are complete, should return cleanup."""
        state = SessionState()
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[
                Feature(
                    id=1,
                    category="test",
                    description="Done",
                    test_file="tests/test_done.py",
                    passes=True,
                )
            ],
        )
        config = Config()
        assert select_prompt_type(state, features, config) == "cleanup"

    def test_periodic_cleanup_interval(self):
        """Should trigger cleanup at cleanup interval."""
        state = SessionState(total_sessions=5)
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[
                Feature(
                    id=1,
                    category="test",
                    description="Not done",
                    test_file="tests/test_notdone.py",
                    passes=False,
                )
            ],
        )
        config = Config()
        config.quality.cleanup_interval = 5
        assert select_prompt_type(state, features, config) == "cleanup"

    def test_default_is_coding(self):
        """Default prompt type should be coding."""
        state = SessionState(total_sessions=1)
        features = FeaturesFile(
            project="test",
            generated_by="test",
            init_mode="new",
            last_updated="2024-01-01",
            features=[
                Feature(
                    id=1,
                    category="test",
                    description="Not done",
                    test_file="tests/test_notdone.py",
                    passes=False,
                )
            ],
        )
        config = Config()
        assert select_prompt_type(state, features, config) == "coding"


class TestGetModelForPromptType:
    """Tests for get_model_for_prompt_type."""

    def test_init_model(self):
        """Init prompt type should use initializer model."""
        config = Config()
        config.models.initializer = "claude-3-opus"
        assert get_model_for_prompt_type("init", config) == "claude-3-opus"

    def test_cleanup_model(self):
        """Cleanup prompt type should use cleanup model."""
        config = Config()
        config.models.cleanup = "claude-3-haiku"
        assert get_model_for_prompt_type("cleanup", config) == "claude-3-haiku"

    def test_unknown_uses_default(self):
        """Unknown prompt type should use default model."""
        config = Config()
        config.models.default = "claude-3-sonnet"
        assert get_model_for_prompt_type("unknown", config) == "claude-3-sonnet"


class TestBuildCodingPrompt:
    """Tests for build_coding_prompt."""

    def test_includes_orientation(self):
        """Coding prompt should include orientation."""
        prompt = build_coding_prompt("Project status: good")
        assert "Project status: good" in prompt
        assert "CODING SESSION" in prompt

    def test_includes_feature_details(self):
        """Should include feature details when provided."""
        feature = Feature(
            id=1,
            category="auth",
            description="Add login",
            test_file="tests/test_login.py",
            size_estimate="medium",
            verification_steps=["Test login form", "Test validation"],
        )
        prompt = build_coding_prompt("orientation", feature=feature)
        assert "Feature #1" in prompt
        assert "Add login" in prompt
        assert "test_login.py" in prompt
        assert "VERIFICATION STEPS" in prompt
        assert "Test login form" in prompt

    def test_includes_dependencies(self):
        """Should include dependencies when present."""
        feature = Feature(
            id=2,
            category="test",
            description="Test",
            test_file="tests/test_dep.py",
            depends_on=[1],
        )
        prompt = build_coding_prompt("orientation", feature=feature)
        assert "Dependencies" in prompt
        assert "[1]" in prompt

    def test_includes_recent_decisions(self):
        """Should include recent decisions for consistency."""
        decisions = ["Use pytest", "Follow TDD", "Use dataclasses"]
        prompt = build_coding_prompt("orientation", recent_decisions=decisions)
        assert "MAINTAIN CONSISTENCY" in prompt
        assert "Use pytest" in prompt

    def test_instructions_included(self):
        """Should include TDD instructions."""
        prompt = build_coding_prompt("orientation")
        assert "tests first" in prompt.lower() or "Write tests" in prompt


class TestBuildFeatureIntro:
    """Tests for build_feature_intro."""

    def test_basic_feature_intro(self):
        """Should include basic feature info."""
        feature = Feature(
            id=5,
            description="User registration",
            category="auth",
            test_file="tests/test_auth.py",
        )
        intro = build_feature_intro(feature)
        assert "Feature #5" in intro
        assert "User registration" in intro
        assert "auth" in intro
        assert "test_auth.py" in intro

    def test_includes_note_when_present(self):
        """Should include note when present."""
        feature = Feature(
            id=1,
            category="test",
            description="Test",
            test_file="tests/test_note.py",
            note="This is complex",
        )
        intro = build_feature_intro(feature)
        assert "Note:" in intro
        assert "This is complex" in intro


class TestBuildTestFirstReminder:
    """Tests for build_test_first_reminder."""

    def test_tdd_steps_included(self):
        """Should include TDD steps."""
        reminder = build_test_first_reminder()
        assert "failing test" in reminder.lower()
        assert "minimal code" in reminder.lower()
        assert "Refactor" in reminder


class TestBuildContinuationPrompt:
    """Tests for build_continuation_prompt."""

    def test_basic_continuation(self):
        """Basic continuation prompt structure."""
        prompt = build_continuation_prompt("Project orientation here")
        assert "CONTINUATION SESSION" in prompt
        assert "resuming work" in prompt
        assert "Project orientation here" in prompt

    def test_includes_partial_details(self):
        """Should include partial work details."""
        prompt = build_continuation_prompt(
            "orientation",
            partial_details="Implemented 3 of 5 functions",
        )
        assert "PREVIOUS PROGRESS" in prompt
        assert "3 of 5 functions" in prompt

    def test_includes_last_entry(self):
        """Should include last progress entry."""
        last_entry = ProgressEntry(
            session=1,
            date="2024-01-01",
            what_done=["Created models", "Added tests"],
            current_state="In progress",
            decisions=["Use SQLite"],
        )
        prompt = build_continuation_prompt("orientation", last_entry=last_entry)
        assert "LAST SESSION" in prompt
        assert "Created models" in prompt
        assert "Use SQLite" in prompt

    def test_includes_feature_to_complete(self):
        """Should include feature being completed."""
        feature = Feature(
            id=3,
            category="api",
            description="API endpoints",
            test_file="tests/test_api.py",
            verification_steps=["Test GET", "Test POST"],
        )
        prompt = build_continuation_prompt("orientation", feature=feature)
        assert "FEATURE TO COMPLETE" in prompt
        assert "#3" in prompt
        assert "API endpoints" in prompt
        assert "Test GET" in prompt


class TestBuildContextLimitContinuation:
    """Tests for build_context_limit_continuation."""

    def test_context_limit_message(self):
        """Should indicate context limit was reached."""
        feature = Feature(
            id=1,
            category="test",
            description="Big feature",
            test_file="tests/test_big.py",
        )
        prompt = build_context_limit_continuation(feature, ["Step 1 done"])
        assert "CONTEXT LIMIT" in prompt
        assert "checkpoint" in prompt.lower()

    def test_includes_progress_so_far(self):
        """Should include progress made before limit."""
        feature = Feature(
            id=2,
            category="test",
            description="Test",
            test_file="tests/test_progress.py",
        )
        progress = ["Created files", "Added imports", "Wrote function"]
        prompt = build_context_limit_continuation(feature, progress)
        assert "PROGRESS SO FAR" in prompt
        assert "Created files" in prompt
        assert "Wrote function" in prompt


class TestBuildStuckRecoveryPrompt:
    """Tests for build_stuck_recovery_prompt."""

    def test_stuck_count_shown(self):
        """Should show how many times stuck."""
        feature = Feature(
            id=1,
            category="test",
            description="Hard feature",
            test_file="tests/test_hard.py",
        )
        prompt = build_stuck_recovery_prompt(feature, stuck_count=3)
        assert "3 times" in prompt
        assert "different approach" in prompt

    def test_includes_last_error(self):
        """Should include last error when provided."""
        feature = Feature(
            id=1,
            category="test",
            description="Test",
            test_file="tests/test_error.py",
        )
        prompt = build_stuck_recovery_prompt(
            feature,
            stuck_count=2,
            last_error="ImportError: module not found",
        )
        assert "LAST ERROR" in prompt
        assert "ImportError" in prompt

    def test_recovery_suggestions(self):
        """Should include recovery suggestions."""
        feature = Feature(
            id=1,
            category="test",
            description="Test",
            test_file="tests/test_recovery.py",
        )
        prompt = build_stuck_recovery_prompt(feature, stuck_count=1)
        assert "RECOVERY SUGGESTIONS" in prompt
        assert "smaller pieces" in prompt


class TestBuildCleanupPrompt:
    """Tests for build_cleanup_prompt."""

    def test_basic_cleanup_prompt(self):
        """Basic cleanup prompt structure."""
        prompt = build_cleanup_prompt()
        assert "CLEANUP SESSION" in prompt
        assert "code quality" in prompt
        assert "DO NOT add new features" in prompt

    def test_includes_quality_issues(self):
        """Should include quality issues when provided."""
        prompt = build_cleanup_prompt(quality_issues="Duplicate code in utils.py")
        assert "QUALITY ISSUES" in prompt
        assert "Duplicate code" in prompt

    def test_includes_lint_status(self):
        """Should include lint status when provided."""
        prompt = build_cleanup_prompt(lint_errors=5, lint_warnings=12)
        assert "LINT STATUS" in prompt
        assert "Errors: 5" in prompt
        assert "Warnings: 12" in prompt

    def test_includes_oversized_files(self):
        """Should include oversized files when provided."""
        oversized = [("src/big_file.py", 800), ("src/huge.py", 1200)]
        prompt = build_cleanup_prompt(oversized_files=oversized)
        assert "OVERSIZED FILES" in prompt
        assert "big_file.py" in prompt
        assert "800 lines" in prompt

    def test_cleanup_priorities(self):
        """Should include cleanup priorities."""
        prompt = build_cleanup_prompt()
        assert "CLEANUP PRIORITIES" in prompt
        assert "lint errors" in prompt.lower()


class TestBuildLintFixPrompt:
    """Tests for build_lint_fix_prompt."""

    def test_lint_output_included(self):
        """Should include lint output."""
        lint_output = "E501: line too long\nW503: line break before operator"
        prompt = build_lint_fix_prompt(lint_output)
        assert "LINT FIX SESSION" in prompt
        assert "E501" in prompt
        assert "W503" in prompt

    def test_auto_fixable_note(self):
        """Should note auto-fixable issues."""
        prompt = build_lint_fix_prompt("errors", auto_fixable=10)
        assert "10 issues can be auto-fixed" in prompt
        assert "ruff check --fix" in prompt

    def test_truncates_long_output(self):
        """Should truncate very long lint output."""
        long_output = "x" * 3000
        prompt = build_lint_fix_prompt(long_output)
        assert "truncated" in prompt.lower()


class TestBuildRefactorPrompt:
    """Tests for build_refactor_prompt."""

    def test_file_info_included(self):
        """Should include file info."""
        prompt = build_refactor_prompt("src/monolith.py", 1500)
        assert "REFACTOR SESSION" in prompt
        assert "src/monolith.py" in prompt
        assert "1500 lines" in prompt

    def test_suggested_splits_included(self):
        """Should include suggested splits."""
        splits = ["models.py", "views.py", "utils.py"]
        prompt = build_refactor_prompt("src/app.py", 1000, suggested_splits=splits)
        assert "SUGGESTED SPLITS" in prompt
        assert "models.py" in prompt
        assert "views.py" in prompt

    def test_refactoring_approach(self):
        """Should include refactoring approach."""
        prompt = build_refactor_prompt("file.py", 500)
        assert "REFACTORING APPROACH" in prompt
        assert "logical groupings" in prompt


class TestBuildInitializerPrompt:
    """Tests for build_initializer_prompt."""

    def test_new_mode(self):
        """New mode should have all features not passing."""
        spec = "Build a CLI tool with commands: init, run, status"
        prompt = build_initializer_prompt(spec, mode="new")
        assert "MODE: NEW" in prompt
        assert "greenfield" in prompt
        assert "not passing" in prompt

    def test_adopt_mode(self):
        """Adopt mode should include existing project info."""
        spec = "Add new features"
        summary = "Existing Python project with 10 modules"
        prompt = build_initializer_prompt(spec, project_summary=summary, mode="adopt")
        assert "MODE: ADOPT" in prompt
        assert "EXISTING PROJECT SUMMARY" in prompt
        assert "10 modules" in prompt

    def test_spec_content_included(self):
        """Spec content should be included."""
        spec = "Feature 1: User auth\nFeature 2: Dashboard"
        prompt = build_initializer_prompt(spec)
        assert "SPECIFICATION" in prompt
        assert "User auth" in prompt
        assert "Dashboard" in prompt

    def test_long_spec_truncated(self):
        """Very long specs should be truncated."""
        spec = "x" * 5000
        prompt = build_initializer_prompt(spec)
        assert "truncated" in prompt.lower()

    def test_required_outputs_documented(self):
        """Should document required outputs."""
        prompt = build_initializer_prompt("spec")
        assert "REQUIRED OUTPUTS" in prompt
        assert "features.json" in prompt
        assert "init.sh" in prompt
        assert "reset.sh" in prompt

    def test_feature_guidelines(self):
        """Should include feature guidelines."""
        prompt = build_initializer_prompt("spec")
        assert "FEATURE GUIDELINES" in prompt
        assert "dependencies" in prompt.lower()


class TestBuildAdoptAnalysisPrompt:
    """Tests for build_adopt_analysis_prompt."""

    def test_project_dir_shown(self):
        """Should show project directory."""
        prompt = build_adopt_analysis_prompt(
            "/path/to/project",
            detected_files=[],
            detected_tests=[],
            frameworks=[],
        )
        assert "PROJECT ANALYSIS" in prompt
        assert "/path/to/project" in prompt

    def test_source_files_listed(self):
        """Should list detected source files."""
        files = ["src/main.py", "src/utils.py", "src/models.py"]
        prompt = build_adopt_analysis_prompt("/proj", files, [], [])
        assert "SOURCE FILES (3)" in prompt
        assert "main.py" in prompt
        assert "utils.py" in prompt

    def test_test_files_listed(self):
        """Should list detected test files."""
        tests = ["tests/test_main.py", "tests/test_utils.py"]
        prompt = build_adopt_analysis_prompt("/proj", [], tests, [])
        assert "TEST FILES (2)" in prompt
        assert "test_main.py" in prompt

    def test_frameworks_listed(self):
        """Should list detected frameworks."""
        frameworks = ["pytest", "flask", "sqlalchemy"]
        prompt = build_adopt_analysis_prompt("/proj", [], [], frameworks)
        assert "DETECTED FRAMEWORKS" in prompt
        assert "pytest" in prompt
        assert "flask" in prompt

    def test_analysis_instructions(self):
        """Should include analysis instructions."""
        prompt = build_adopt_analysis_prompt("/proj", [], [], [])
        assert "Analyze this project" in prompt
        assert "components" in prompt


class TestBuildFeaturesValidationPrompt:
    """Tests for build_features_validation_prompt."""

    def test_features_json_included(self):
        """Should include features.json content."""
        features_json = '{"project": "test", "features": []}'
        prompt = build_features_validation_prompt(features_json)
        assert "FEATURES VALIDATION" in prompt
        assert '"project"' in prompt

    def test_validation_checks(self):
        """Should list validation checks."""
        prompt = build_features_validation_prompt("{}")
        assert "CHECK" in prompt
        assert "required fields" in prompt
        assert "circular dependencies" in prompt
        assert "unique names" in prompt

    def test_long_json_truncated(self):
        """Very long JSON should be truncated."""
        long_json = '{"data": "' + "x" * 3000 + '"}'
        prompt = build_features_validation_prompt(long_json)
        assert "truncated" in prompt.lower()
