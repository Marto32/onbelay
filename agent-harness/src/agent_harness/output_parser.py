"""Agent output parser for agent-harness.

Parses structured prefixes from agent output to understand actions taken.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedAction:
    """A parsed action from agent output."""

    type: str  # file_read, file_write, cmd_run, verify_pass, etc.
    data: dict
    source: str  # "prefix" or "heuristic" or "tool_use"
    raw_text: Optional[str] = None


# Prefix patterns
PREFIX_PATTERNS = {
    # File operations
    r"\[FILE:READ\]\s*(.+)": ("file_read", lambda m: {"path": m.group(1).strip()}),
    r"\[FILE:WRITE\]\s*(.+)": ("file_write", lambda m: {"path": m.group(1).strip()}),
    r"\[FILE:CREATE\]\s*(.+)": ("file_create", lambda m: {"path": m.group(1).strip()}),
    r"\[FILE:DELETE\]\s*(.+)": ("file_delete", lambda m: {"path": m.group(1).strip()}),

    # Command operations
    r"\[CMD:RUN\]\s*(.+)": ("cmd_run", lambda m: {"command": m.group(1).strip()}),
    r"\[CMD:OUTPUT\]": ("cmd_output", lambda m: {}),

    # Verification
    r"\[VERIFY:PASS\]\s*(.*)": ("verify_pass", lambda m: {"details": m.group(1).strip()}),
    r"\[VERIFY:FAIL\]\s*(.+)": ("verify_fail", lambda m: {"reason": m.group(1).strip()}),
    r"\[VERIFY:SKIP\]\s*(.*)": ("verify_skip", lambda m: {"reason": m.group(1).strip()}),

    # Feature operations
    r"\[FEATURE:START\]\s*(\d+)": ("feature_start", lambda m: {"feature_id": int(m.group(1))}),
    r"\[FEATURE:COMPLETE\]\s*(\d+)": ("feature_complete", lambda m: {"feature_id": int(m.group(1))}),
    r"\[FEATURE:BLOCKED\]\s*(\d+)\s*(.*)": ("feature_blocked", lambda m: {"feature_id": int(m.group(1)), "reason": m.group(2).strip()}),

    # Test operations
    r"\[TEST:RUN\]\s*(.+)": ("test_run", lambda m: {"test_path": m.group(1).strip()}),
    r"\[TEST:PASS\]\s*(.+)": ("test_pass", lambda m: {"test_id": m.group(1).strip()}),
    r"\[TEST:FAIL\]\s*(.+)": ("test_fail", lambda m: {"test_id": m.group(1).strip()}),

    # Session control
    r"\[SESSION:WRAP_UP\]": ("session_wrap_up", lambda m: {}),
    r"\[SESSION:STUCK\]": ("session_stuck", lambda m: {}),

    # Decision
    r"\[DECISION\]\s*(.+)": ("decision", lambda m: {"decision": m.group(1).strip()}),

    # Progress
    r"\[PROGRESS\]\s*(.+)": ("progress", lambda m: {"message": m.group(1).strip()}),
}

# Compiled patterns
COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), action_type, extractor)
    for pattern, (action_type, extractor) in PREFIX_PATTERNS.items()
]


def parse_agent_output(output: str) -> list[ParsedAction]:
    """
    Parse structured prefixes from agent output.

    Args:
        output: Agent output text.

    Returns:
        List of ParsedAction objects.
    """
    actions = []

    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try each prefix pattern
        for pattern, action_type, extractor in COMPILED_PATTERNS:
            match = pattern.match(line)
            if match:
                try:
                    data = extractor(match)
                    actions.append(ParsedAction(
                        type=action_type,
                        data=data,
                        source="prefix",
                        raw_text=line,
                    ))
                except Exception:
                    # If extraction fails, skip this action
                    pass
                break

    return actions


def parse_tool_calls(tool_calls: list[dict]) -> list[ParsedAction]:
    """
    Parse actions from Claude API tool calls.

    Args:
        tool_calls: List of tool call dictionaries from Claude API.

    Returns:
        List of ParsedAction objects.
    """
    actions = []

    for call in tool_calls:
        tool_name = call.get("name", "")
        tool_input = call.get("input", {})

        if tool_name in ("read_file", "str_replace_editor"):
            # File read
            path = tool_input.get("path", tool_input.get("file", ""))
            if path:
                actions.append(ParsedAction(
                    type="file_read",
                    data={"path": path},
                    source="tool_use",
                ))

        elif tool_name in ("write_file", "create_file"):
            # File write
            path = tool_input.get("path", tool_input.get("file", ""))
            if path:
                actions.append(ParsedAction(
                    type="file_write",
                    data={"path": path},
                    source="tool_use",
                ))

        elif tool_name in ("bash", "execute_command", "run_command"):
            # Command run
            command = tool_input.get("command", tool_input.get("cmd", ""))
            if command:
                actions.append(ParsedAction(
                    type="cmd_run",
                    data={"command": command},
                    source="tool_use",
                ))

                # Check if it's a test command
                if "pytest" in command or "test" in command.lower():
                    actions.append(ParsedAction(
                        type="test_run",
                        data={"command": command},
                        source="tool_use",
                    ))

    return actions


def parse_with_heuristics(output: str) -> list[ParsedAction]:
    """
    Use heuristics to detect actions when prefixes are missing.

    Args:
        output: Agent output text.

    Returns:
        List of ParsedAction objects.
    """
    actions = []

    # File path patterns
    file_patterns = [
        (r"(?:read|reading|opened|opening)\s+(?:file\s+)?['\"]?([^\s'\"]+\.\w+)['\"]?", "file_read"),
        (r"(?:writ|creat|sav|updat)(?:e|ing|ed)\s+(?:to\s+)?(?:file\s+)?['\"]?([^\s'\"]+\.\w+)['\"]?", "file_write"),
        (r"(?:created|added|wrote)\s+['\"]?([^\s'\"]+\.\w+)['\"]?", "file_create"),
    ]

    for pattern, action_type in file_patterns:
        for match in re.finditer(pattern, output, re.IGNORECASE):
            path = match.group(1)
            if _looks_like_file_path(path):
                actions.append(ParsedAction(
                    type=action_type,
                    data={"path": path},
                    source="heuristic",
                    raw_text=match.group(0),
                ))

    # Command patterns
    command_patterns = [
        r"(?:running|ran|execute|executing)\s+(?:command\s+)?[`'\"]([^`'\"]+)[`'\"]",
        r"\$\s+([^\n]+)",  # Shell prompt pattern
        r"```(?:bash|shell|sh)\n([^`]+)```",  # Code block commands
    ]

    for pattern in command_patterns:
        for match in re.finditer(pattern, output, re.IGNORECASE | re.DOTALL):
            command = match.group(1).strip()
            if command and len(command) > 2:
                actions.append(ParsedAction(
                    type="cmd_run",
                    data={"command": command},
                    source="heuristic",
                    raw_text=match.group(0)[:100],
                ))

    # Test patterns
    test_patterns = [
        r"test[s]?\s+(?:are\s+)?(?:all\s+)?pass(?:ing|ed)?",
        r"(?:all\s+)?tests?\s+pass(?:ing|ed)?",
        r"pytest\s+.*\s+passed",
    ]

    for pattern in test_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            actions.append(ParsedAction(
                type="test_pass",
                data={},
                source="heuristic",
            ))
            break

    # Verification patterns
    if re.search(r"verification\s+(?:is\s+)?(?:complete|passed|successful)", output, re.IGNORECASE):
        actions.append(ParsedAction(
            type="verify_pass",
            data={},
            source="heuristic",
        ))

    if re.search(r"feature\s+(?:#?\d+\s+)?(?:is\s+)?(?:complete|implemented|done)", output, re.IGNORECASE):
        # Try to extract feature ID
        feature_match = re.search(r"feature\s+#?(\d+)", output, re.IGNORECASE)
        feature_id = int(feature_match.group(1)) if feature_match else None
        actions.append(ParsedAction(
            type="feature_complete",
            data={"feature_id": feature_id},
            source="heuristic",
        ))

    return actions


def _looks_like_file_path(path: str) -> bool:
    """Check if a string looks like a file path."""
    if not path:
        return False

    # Must have an extension
    if "." not in path:
        return False

    # Check for common file extensions
    common_extensions = {
        ".py", ".js", ".ts", ".tsx", ".jsx",
        ".json", ".yaml", ".yml", ".toml",
        ".md", ".txt", ".rst",
        ".html", ".css", ".scss",
        ".sh", ".bash",
    }

    for ext in common_extensions:
        if path.endswith(ext):
            return True

    return False


def parse_all(output: str, tool_calls: Optional[list[dict]] = None) -> list[ParsedAction]:
    """
    Parse actions from output using all available methods.

    Args:
        output: Agent output text.
        tool_calls: Optional list of tool calls from API response.

    Returns:
        Combined list of ParsedAction objects, deduplicated.
    """
    actions = []

    # Parse with prefixes first (most reliable)
    actions.extend(parse_agent_output(output))

    # Parse tool calls if available
    if tool_calls:
        actions.extend(parse_tool_calls(tool_calls))

    # Use heuristics as fallback
    heuristic_actions = parse_with_heuristics(output)

    # Add heuristic actions that don't duplicate prefix/tool actions
    existing_keys = set()
    for action in actions:
        key = (action.type, str(action.data))
        existing_keys.add(key)

    for action in heuristic_actions:
        key = (action.type, str(action.data))
        if key not in existing_keys:
            actions.append(action)
            existing_keys.add(key)

    return actions


def get_file_operations(actions: list[ParsedAction]) -> list[ParsedAction]:
    """
    Filter to file operations only.

    Args:
        actions: List of ParsedAction objects.

    Returns:
        File operations only.
    """
    file_types = {"file_read", "file_write", "file_create", "file_delete"}
    return [a for a in actions if a.type in file_types]


def get_command_operations(actions: list[ParsedAction]) -> list[ParsedAction]:
    """
    Filter to command operations only.

    Args:
        actions: List of ParsedAction objects.

    Returns:
        Command operations only.
    """
    return [a for a in actions if a.type == "cmd_run"]


def get_test_operations(actions: list[ParsedAction]) -> list[ParsedAction]:
    """
    Filter to test operations only.

    Args:
        actions: List of ParsedAction objects.

    Returns:
        Test operations only.
    """
    test_types = {"test_run", "test_pass", "test_fail"}
    return [a for a in actions if a.type in test_types]


def get_verification_operations(actions: list[ParsedAction]) -> list[ParsedAction]:
    """
    Filter to verification operations only.

    Args:
        actions: List of ParsedAction objects.

    Returns:
        Verification operations only.
    """
    verify_types = {"verify_pass", "verify_fail", "verify_skip"}
    return [a for a in actions if a.type in verify_types]


def summarize_actions(actions: list[ParsedAction]) -> dict[str, int]:
    """
    Summarize actions by type.

    Args:
        actions: List of ParsedAction objects.

    Returns:
        Dictionary mapping action types to counts.
    """
    summary: dict[str, int] = {}
    for action in actions:
        summary[action.type] = summary.get(action.type, 0) + 1
    return summary


def format_action(action: ParsedAction) -> str:
    """
    Format an action for display.

    Args:
        action: ParsedAction to format.

    Returns:
        Formatted string.
    """
    source_marker = {
        "prefix": "[P]",
        "tool_use": "[T]",
        "heuristic": "[H]",
    }.get(action.source, "[?]")

    if action.type in ("file_read", "file_write", "file_create"):
        return f"{source_marker} {action.type}: {action.data.get('path', '?')}"
    elif action.type == "cmd_run":
        cmd = action.data.get("command", "?")
        if len(cmd) > 50:
            cmd = cmd[:47] + "..."
        return f"{source_marker} {action.type}: {cmd}"
    elif action.type in ("test_pass", "test_fail"):
        return f"{source_marker} {action.type}: {action.data.get('test_id', '')}"
    elif action.type in ("feature_complete", "feature_start"):
        return f"{source_marker} {action.type}: #{action.data.get('feature_id', '?')}"
    else:
        return f"{source_marker} {action.type}: {str(action.data)[:50]}"
