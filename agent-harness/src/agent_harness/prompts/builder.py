"""Prompt builder utilities for agent-harness."""

from typing import Optional

from agent_harness.config import Config
from agent_harness.features import FeaturesFile, get_next_feature
from agent_harness.state import SessionState


# Base system prompt that applies to all session types
BASE_SYSTEM_PROMPT = """You are an expert software engineer working on a structured project.

CORE RULES:
1. Focus on ONE feature per session - never work on multiple features
2. Write comprehensive tests BEFORE implementing features
3. All code must pass tests and linting before completion
4. Document your decisions and reasoning
5. If stuck, explain the problem and ask for help

STRUCTURED OUTPUT:
Use these prefixes to help track your actions:
- [FILE:READ] filename - when reading a file
- [FILE:WRITE] filename - when writing a file
- [CMD:RUN] command - when running a command
- [VERIFY:PASS] - when verification passes
- [VERIFY:FAIL] reason - when verification fails
- [DECISION] description - when making an important decision

VERIFICATION:
Before marking a feature complete:
1. Run the feature's test file
2. Ensure all tests pass
3. Run linting
4. Update features.json to mark the feature as passing
5. Update claude-progress.txt with session summary
"""


def build_system_prompt(
    session_type: str,
    config: Optional[Config] = None,
) -> str:
    """
    Build the system prompt for a session.

    Args:
        session_type: Type of session (coding, continuation, cleanup, init).
        config: Configuration object.

    Returns:
        Complete system prompt string.
    """
    lines = [BASE_SYSTEM_PROMPT]

    # Add session-type specific instructions
    if session_type == "cleanup":
        lines.append("\nCLEANUP SESSION:")
        lines.append("- Focus on code quality, not new features")
        lines.append("- Fix lint errors and warnings")
        lines.append("- Refactor oversized files")
        lines.append("- Do NOT add new functionality")

    elif session_type == "continuation":
        lines.append("\nCONTINUATION SESSION:")
        lines.append("- Continue work from previous session")
        lines.append("- Review what was done before")
        lines.append("- Complete the remaining work")

    elif session_type == "init":
        lines.append("\nINITIALIZATION SESSION:")
        lines.append("- Analyze the project specification")
        lines.append("- Create features.json with all features")
        lines.append("- Create init.sh and reset.sh scripts")
        lines.append("- Set up the project structure")

    # Add config-specific instructions
    if config:
        if config.verification.require_evidence:
            lines.append("\nEVIDENCE REQUIRED:")
            lines.append("- Show test output before marking features complete")

        if config.quality.max_file_lines:
            lines.append(f"\nFILE SIZE LIMIT: {config.quality.max_file_lines} lines per file")

    return "\n".join(lines)


def build_user_prompt(
    orientation: str,
    additional_context: Optional[str] = None,
) -> str:
    """
    Build the user prompt for a session.

    Args:
        orientation: Orientation summary from orientation.py.
        additional_context: Additional context to include.

    Returns:
        User prompt string.
    """
    lines = ["Here is your current context:\n"]
    lines.append(orientation)

    if additional_context:
        lines.append("\nADDITIONAL CONTEXT:")
        lines.append(additional_context)

    lines.append("\nBegin working on the next task.")

    return "\n".join(lines)


def select_prompt_type(
    state: SessionState,
    features: FeaturesFile,
    config: Config,
) -> str:
    """
    Select the appropriate prompt type based on state.

    Args:
        state: Current session state.
        features: Features file.
        config: Configuration.

    Returns:
        Prompt type string: "init", "coding", "continuation", or "cleanup".
    """
    # Check explicit next_prompt setting
    if state.next_prompt == "init":
        return "init"

    if state.next_prompt == "cleanup":
        return "cleanup"

    if state.next_prompt == "continuation":
        return "continuation"

    # Check if all features are complete
    next_feature = get_next_feature(features)
    if next_feature is None:
        # All features done - might need cleanup
        return "cleanup"

    # Check if we should trigger periodic cleanup
    if state.total_sessions > 0:
        if state.total_sessions % config.quality.cleanup_interval == 0:
            return "cleanup"

    # Default to coding
    return "coding"


def get_model_for_prompt_type(prompt_type: str, config: Config) -> str:
    """
    Get the model to use for a prompt type.

    Args:
        prompt_type: Type of prompt.
        config: Configuration.

    Returns:
        Model name string.
    """
    models = config.models

    if prompt_type == "init":
        return models.initializer
    elif prompt_type == "cleanup":
        return models.cleanup
    elif prompt_type == "continuation":
        return models.continuation
    elif prompt_type == "coding":
        return models.coding
    else:
        return models.default
