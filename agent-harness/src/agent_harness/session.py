"""Session orchestration for agent harness.

Orchestrates a complete session lifecycle:
1. Pre-flight checks
2. Prompt selection and generation
3. Checkpoint creation
4. Agent conversation
5. Progress monitoring
6. Context management
7. Verification
8. State updates
9. Commit on success
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from agent_harness.agent import AgentRunner, AgentSession, TokenUsage
from agent_harness.checkpoint import create_checkpoint, rollback_to_checkpoint
from agent_harness.config import Config, load_config
from agent_harness.context_manager import ContextManager, ContextWarning
from agent_harness.costs import add_usage, load_costs, save_costs, start_session as start_cost_session, end_session as end_cost_session
from agent_harness.features import (
    FeaturesFile,
    get_next_feature,
    load_features,
    save_features,
)
from agent_harness.git_ops import create_commit
from agent_harness.orientation import generate_orientation_summary
from agent_harness.preflight import PreflightResult, run_preflight_checks
from agent_harness.progress import append_entry, ProgressEntry
from agent_harness.progress_monitor import ProgressMonitor, ProgressSnapshot
from agent_harness.prompts.builder import (
    build_system_prompt,
    build_user_prompt,
    get_model_for_prompt_type,
    select_prompt_type,
)
from agent_harness.state import (
    SessionState,
    end_session,
    load_session_state,
    save_session_state,
    start_new_session,
)
from agent_harness.tools.executor import ToolExecutor, create_default_handlers
from agent_harness.verification import verify_feature_completion


@dataclass
class SessionResult:
    """Result of a session run."""

    success: bool
    session_id: int
    features_completed: list[int] = field(default_factory=list)
    tokens_used: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    message: str = ""
    error: Optional[str] = None
    preflight_result: Optional[PreflightResult] = None
    verification_passed: bool = False
    rolled_back: bool = False


@dataclass
class SessionConfig:
    """Configuration for a session run."""

    project_dir: Path
    skip_preflight: bool = False
    skip_tests: bool = False
    skip_commit: bool = False
    dry_run: bool = False
    max_turns: int = 50
    on_response: Optional[Callable] = None
    on_progress: Optional[Callable] = None


class SessionOrchestrator:
    """Orchestrates a complete agent session."""

    def __init__(
        self,
        project_dir: Path,
        config: Optional[Config] = None,
    ):
        """Initialize the orchestrator.

        Args:
            project_dir: Path to project directory.
            config: Optional configuration (loaded if not provided).
        """
        self.project_dir = project_dir
        self.harness_dir = project_dir / ".harness"

        # Load or use provided config
        if config is None:
            try:
                self.config = load_config(self.harness_dir / "config.yaml")
            except Exception:
                self.config = Config()
        else:
            self.config = config

        # Initialize components
        self.context_manager: Optional[ContextManager] = None
        self.progress_monitor: Optional[ProgressMonitor] = None
        self.tool_executor: Optional[ToolExecutor] = None
        self.agent_runner: Optional[AgentRunner] = None

        # Session tracking
        self.current_checkpoint_id: Optional[str] = None
        self.files_modified: int = 0
        self.tests_run: int = 0
        self.tool_calls: int = 0

    def run_session(self, session_config: SessionConfig) -> SessionResult:
        """Run a complete session.

        Args:
            session_config: Session configuration.

        Returns:
            SessionResult with outcome.
        """
        start_time = datetime.now(timezone.utc)

        # Load state
        state = load_session_state(self.harness_dir)
        features = load_features(self.project_dir / "features.json")

        # Initialize result
        result = SessionResult(
            success=False,
            session_id=state.last_session + 1,
        )

        try:
            # 1. Pre-flight checks
            if not session_config.skip_preflight:
                preflight = run_preflight_checks(
                    self.project_dir,
                    self.config,
                    skip_tests=session_config.skip_tests,
                )
                result.preflight_result = preflight

                if not preflight.passed:
                    result.error = f"Pre-flight failed: {preflight.abort_reason}"
                    return result

            # 2. Select prompt type and get next feature
            prompt_type = select_prompt_type(state, features, self.config)
            next_feature = get_next_feature(features)

            if next_feature is None and prompt_type == "coding":
                result.success = True
                result.message = "All features complete!"
                return result

            # 3. Start session in state
            state = start_new_session(
                state,
                feature_id=next_feature.id if next_feature else None,
            )
            save_session_state(self.harness_dir, state)

            # 4. Create checkpoint
            if not session_config.dry_run:
                checkpoint = create_checkpoint(
                    self.project_dir,
                    session=result.session_id,
                    reason=f"Session {result.session_id} start",
                )
                self.current_checkpoint_id = checkpoint.checkpoint_id
                state.last_checkpoint_id = checkpoint.checkpoint_id

            # 5. Generate prompts
            orientation = generate_orientation_summary(
                self.project_dir,
                state,
                features,
            )
            system_prompt = build_system_prompt(prompt_type, self.config)
            user_prompt = build_user_prompt(orientation)

            # 6. Check for dry run before initializing agent (avoids API key requirement)
            if session_config.dry_run:
                result.success = True
                result.message = "Dry run - no agent execution"
                return result

            # 7. Initialize agent (only if not dry run)
            model = get_model_for_prompt_type(prompt_type, self.config)
            self.agent_runner = AgentRunner(model=model, max_tokens=4096)

            # 8. Initialize monitors
            self.context_manager = ContextManager(model=model)
            self.progress_monitor = ProgressMonitor(
                check_interval_tokens=self.config.progress.check_interval_tokens,
            )

            # 9. Initialize tool executor
            self.tool_executor = ToolExecutor(self.project_dir)
            handlers = create_default_handlers(self.project_dir)
            for name, handler in handlers.items():
                self.tool_executor.register_handler(name, handler)

            agent_session = self._run_agent_loop(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prompt_type=prompt_type,
                max_turns=session_config.max_turns,
                on_response=session_config.on_response,
            )

            result.tokens_used = agent_session.total_usage

            # 10. Verify completion
            if next_feature:
                verification = verify_feature_completion(
                    self.project_dir,
                    features,
                    next_feature.id,
                )
                result.verification_passed = verification.passed

                if verification.passed:
                    result.features_completed.append(next_feature.id)

            # 11. End session in state
            session_status = "complete" if result.verification_passed else "partial"
            state = end_session(
                state,
                status=session_status,
                features_completed=result.features_completed,
            )
            save_session_state(self.harness_dir, state)

            # 12. Save features
            save_features(self.project_dir / "features.json", features)

            # 13. Update costs
            costs_file = self.harness_dir / "costs.yaml"
            if costs_file.exists():
                cost_tracker = load_costs(costs_file)
            else:
                from agent_harness.costs import CostTracker
                cost_tracker = CostTracker()

            start_cost_session(
                cost_tracker,
                session_id=result.session_id,
                model=model,
                feature_id=next_feature.id if next_feature else None,
            )
            add_usage(
                cost_tracker,
                input_tokens=result.tokens_used.input_tokens,
                output_tokens=result.tokens_used.output_tokens,
            )
            end_cost_session(cost_tracker)
            save_costs(costs_file, cost_tracker)
            result.cost_usd = self.agent_runner.get_cost(result.tokens_used)

            # 14. Append progress entry
            self._append_progress_entry(result, state, next_feature)

            # 15. Commit if passed and not skipped
            if (
                result.verification_passed
                and result.features_completed
                and not session_config.skip_commit
            ):
                self._commit_changes(result)

            result.success = True
            result.message = self._build_success_message(result)

        except Exception as e:
            result.error = str(e)

            # Rollback on error if we have a checkpoint
            if self.current_checkpoint_id:
                rollback_result = rollback_to_checkpoint(
                    self.project_dir,
                    self.current_checkpoint_id,
                )
                result.rolled_back = rollback_result.success

        finally:
            end_time = datetime.now(timezone.utc)
            result.duration_seconds = (end_time - start_time).total_seconds()

        return result

    def _run_agent_loop(
        self,
        system_prompt: str,
        user_prompt: str,
        prompt_type: str,
        max_turns: int,
        on_response: Optional[Callable] = None,
    ) -> AgentSession:
        """Run the agent conversation loop.

        Args:
            system_prompt: System prompt.
            user_prompt: Initial user prompt.
            prompt_type: Type of session.
            max_turns: Maximum turns.
            on_response: Response callback.

        Returns:
            AgentSession with results.
        """

        def tool_executor_fn(name: str, inputs: dict) -> dict:
            """Execute a tool call."""
            self.tool_calls += 1
            result = self.tool_executor.execute(name, inputs)
            return result.to_dict()

        def response_callback(response):
            """Handle response and check monitors."""
            # Update context manager
            if self.context_manager:
                self.context_manager.update_usage(
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )

                # Check for context warnings
                warning = self.context_manager.check_and_warn()
                if warning and warning.force_action:
                    # Inject warning into conversation
                    pass  # Would need to modify agent loop

            # Check progress monitor
            if self.progress_monitor:
                snapshot = ProgressSnapshot(
                    tokens_used=self.context_manager.tokens_used if self.context_manager else 0,
                    files_modified=self.files_modified,
                    tests_run=self.tests_run,
                    tool_calls=self.tool_calls,
                )
                self.progress_monitor.snapshots.append(snapshot)

            # Call user callback
            if on_response:
                on_response(response)

        return self.agent_runner.run_conversation(
            initial_message=user_prompt,
            system_prompt=system_prompt,
            session_type=prompt_type,
            tool_executor=tool_executor_fn,
            max_turns=max_turns,
            on_response=response_callback,
        )

    def _append_progress_entry(
        self,
        result: SessionResult,
        state: SessionState,
        feature: Optional[Any],
    ) -> None:
        """Append a progress entry for the session."""
        entry = ProgressEntry(
            session=result.session_id,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            feature_id=feature.id if feature else None,
            feature_description=feature.description if feature else None,
            what_done=[],  # Would be populated from agent conversation
            current_state=state.status,
            status="complete" if result.verification_passed else "partial",
        )

        progress_file = self.project_dir / "claude-progress.txt"
        append_entry(progress_file, entry)

    def _commit_changes(self, result: SessionResult) -> None:
        """Commit changes after successful verification."""
        message = f"Session {result.session_id}: Complete feature(s) {result.features_completed}"
        create_commit(self.project_dir, message)

    def _build_success_message(self, result: SessionResult) -> str:
        """Build success message for result."""
        parts = []

        if result.features_completed:
            parts.append(f"Completed features: {result.features_completed}")

        parts.append(f"Tokens used: {result.tokens_used.total_tokens:,}")
        parts.append(f"Cost: ${result.cost_usd:.4f}")
        parts.append(f"Duration: {result.duration_seconds:.1f}s")

        if result.verification_passed:
            parts.append("Verification: PASSED")
        else:
            parts.append("Verification: NOT RUN or FAILED")

        return " | ".join(parts)


def run_session(
    project_dir: Path,
    config: Optional[Config] = None,
    skip_preflight: bool = False,
    skip_tests: bool = False,
    skip_commit: bool = False,
    dry_run: bool = False,
    max_turns: int = 50,
    on_response: Optional[Callable] = None,
) -> SessionResult:
    """Run a session with default configuration.

    Args:
        project_dir: Path to project directory.
        config: Optional configuration.
        skip_preflight: Skip pre-flight checks.
        skip_tests: Skip test checks.
        skip_commit: Skip committing changes.
        dry_run: Simulate without running agent.
        max_turns: Maximum conversation turns.
        on_response: Response callback.

    Returns:
        SessionResult with outcome.
    """
    orchestrator = SessionOrchestrator(project_dir, config)

    session_config = SessionConfig(
        project_dir=project_dir,
        skip_preflight=skip_preflight,
        skip_tests=skip_tests,
        skip_commit=skip_commit,
        dry_run=dry_run,
        max_turns=max_turns,
        on_response=on_response,
    )

    return orchestrator.run_session(session_config)
