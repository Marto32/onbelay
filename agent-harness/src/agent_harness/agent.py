"""Agent runner for executing Claude API conversations.

Handles:
- Anthropic client initialization
- Message sending with system prompts
- Streaming response handling
- Tool use parsing and execution
- Token usage tracking
"""

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Optional

try:
    import anthropic
    from anthropic import Anthropic
    from anthropic.types import (
        ContentBlock,
        Message,
        MessageParam,
        TextBlock,
        ToolResultBlockParam,
        ToolUseBlock,
    )

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from agent_harness.costs import calculate_cost
from agent_harness.tools.definitions import get_tools_as_api_format


@dataclass
class TokenUsage:
    """Token usage for a single API call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Add two TokenUsage instances."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=(
                self.cache_creation_input_tokens + other.cache_creation_input_tokens
            ),
            cache_read_input_tokens=(
                self.cache_read_input_tokens + other.cache_read_input_tokens
            ),
        )


@dataclass
class ToolCall:
    """A tool call from the model."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class AgentResponse:
    """Response from the agent."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""

    @property
    def has_tool_calls(self) -> bool:
        """Check if response has tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSession:
    """A complete agent session with history and usage tracking."""

    model: str
    system_prompt: str
    session_type: str
    history: list[ConversationTurn] = field(default_factory=list)
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    tool_call_count: int = 0


# Type alias for tool executor function
ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


class AgentRunner:
    """Runs Claude agent conversations with tool use support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ):
        """Initialize the agent runner.

        Args:
            api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
            model: Model to use for conversations.
            max_tokens: Maximum tokens in response.

        Raises:
            ImportError: If anthropic package is not installed.
            ValueError: If no API key is available.
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package is required. Install with: pip install anthropic"
            )

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Set ANTHROPIC_API_KEY or pass api_key parameter."
            )

        self.model = model
        self.max_tokens = max_tokens
        self.client = Anthropic(api_key=self.api_key)

    def send_message(
        self,
        messages: list[MessageParam],
        system_prompt: str,
        tools: Optional[list[dict]] = None,
    ) -> AgentResponse:
        """Send a message to Claude and get a response.

        Args:
            messages: List of message objects in Claude API format.
            system_prompt: System prompt for the conversation.
            tools: Optional list of tool definitions.

        Returns:
            AgentResponse with content, tool calls, and usage.
        """
        # Build request params
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }

        if tools:
            params["tools"] = tools

        # Call API
        response: Message = self.client.messages.create(**params)

        # Parse response
        return self._parse_response(response)

    def send_message_streaming(
        self,
        messages: list[MessageParam],
        system_prompt: str,
        tools: Optional[list[dict]] = None,
        on_text: Optional[Callable[[str], None]] = None,
    ) -> AgentResponse:
        """Send a message with streaming response.

        Args:
            messages: List of message objects in Claude API format.
            system_prompt: System prompt for the conversation.
            tools: Optional list of tool definitions.
            on_text: Optional callback for streaming text chunks.

        Returns:
            AgentResponse with complete content and usage.
        """
        # Build request params
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }

        if tools:
            params["tools"] = tools

        # Stream response
        collected_text = []
        tool_calls = []
        stop_reason = ""
        usage = TokenUsage()

        with self.client.messages.stream(**params) as stream:
            for event in stream:
                # Handle text delta events
                if hasattr(event, "delta") and hasattr(event.delta, "text"):
                    text = event.delta.text
                    collected_text.append(text)
                    if on_text:
                        on_text(text)

            # Get final message for tool calls and usage
            final_message = stream.get_final_message()
            stop_reason = final_message.stop_reason or ""

            # Extract tool calls
            for block in final_message.content:
                if isinstance(block, ToolUseBlock):
                    tool_calls.append(
                        ToolCall(
                            id=block.id,
                            name=block.name,
                            input=block.input,
                        )
                    )

            # Extract usage
            if final_message.usage:
                usage = TokenUsage(
                    input_tokens=final_message.usage.input_tokens,
                    output_tokens=final_message.usage.output_tokens,
                )

        return AgentResponse(
            content="".join(collected_text),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            model=self.model,
        )

    def _parse_response(self, response: Message) -> AgentResponse:
        """Parse Claude API response into AgentResponse.

        Args:
            response: Raw API response.

        Returns:
            Parsed AgentResponse.
        """
        # Extract text content
        text_parts = []
        tool_calls = []

        for block in response.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif isinstance(block, ToolUseBlock):
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    )
                )

        # Extract usage
        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        return AgentResponse(
            content="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "",
            usage=usage,
            model=response.model,
        )

    def run_conversation(
        self,
        initial_message: str,
        system_prompt: str,
        session_type: str = "coding",
        tool_executor: Optional[ToolExecutor] = None,
        max_turns: int = 50,
        on_response: Optional[Callable[[AgentResponse], None]] = None,
    ) -> AgentSession:
        """Run a full conversation with tool use loop.

        Args:
            initial_message: Initial user message.
            system_prompt: System prompt for the conversation.
            session_type: Type of session for tool selection.
            tool_executor: Function to execute tool calls.
            max_turns: Maximum conversation turns.
            on_response: Optional callback for each response.

        Returns:
            AgentSession with complete history and usage.
        """
        # Get tools for session type
        tools = get_tools_as_api_format(session_type)

        # Initialize session
        session = AgentSession(
            model=self.model,
            system_prompt=system_prompt,
            session_type=session_type,
        )

        # Build initial messages
        messages: list[MessageParam] = [
            {"role": "user", "content": initial_message}
        ]

        # Track initial user turn
        session.history.append(
            ConversationTurn(role="user", content=initial_message)
        )

        turns = 0
        while turns < max_turns:
            turns += 1

            # Get response
            response = self.send_message(messages, system_prompt, tools)
            session.total_usage = session.total_usage + response.usage

            if on_response:
                on_response(response)

            # Add assistant turn
            turn = ConversationTurn(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            )
            session.history.append(turn)

            # Check if done
            if response.stop_reason == "end_turn" and not response.has_tool_calls:
                break

            # Handle tool calls
            if response.has_tool_calls:
                # Build assistant message with tool use
                assistant_content: list[Any] = []
                if response.content:
                    assistant_content.append({"type": "text", "text": response.content})

                for tc in response.tool_calls:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                    })

                messages.append({"role": "assistant", "content": assistant_content})

                # Execute tools and collect results
                tool_results: list[ToolResultBlockParam] = []
                for tc in response.tool_calls:
                    session.tool_call_count += 1

                    if tool_executor:
                        try:
                            result = tool_executor(tc.name, tc.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tc.id,
                                "content": str(result),
                            })
                            turn.tool_results[tc.id] = result
                        except Exception as e:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tc.id,
                                "content": f"Error: {str(e)}",
                                "is_error": True,
                            })
                            turn.tool_results[tc.id] = {"error": str(e)}
                    else:
                        # No executor - return stub
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": "Tool executed (no handler)",
                        })

                # Add tool results as user message
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason != "end_turn":
                # Unexpected stop reason
                break

        return session

    def get_cost(self, usage: TokenUsage) -> float:
        """Calculate cost for token usage.

        Args:
            usage: TokenUsage to calculate cost for.

        Returns:
            Cost in USD.
        """
        return calculate_cost(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            model=self.model,
        )


def create_agent_runner(
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> AgentRunner:
    """Create an agent runner with default configuration.

    Args:
        api_key: Optional API key (uses env var if not provided).
        model: Model to use.
        max_tokens: Maximum tokens in response.

    Returns:
        Configured AgentRunner.
    """
    return AgentRunner(api_key=api_key, model=model, max_tokens=max_tokens)


def is_anthropic_available() -> bool:
    """Check if anthropic package is available.

    Returns:
        True if anthropic can be imported.
    """
    return ANTHROPIC_AVAILABLE
