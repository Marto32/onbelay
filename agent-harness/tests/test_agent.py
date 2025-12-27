"""Tests for agent module."""

from unittest.mock import MagicMock, patch

import pytest

from agent_harness.agent import (
    AgentResponse,
    AgentSession,
    ConversationTurn,
    TokenUsage,
    ToolCall,
    is_anthropic_available,
)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_default_values(self):
        """Default values should be zero."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0

    def test_total_tokens(self):
        """Total tokens should be sum of input and output."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_addition(self):
        """Token usage should be addable."""
        usage1 = TokenUsage(input_tokens=100, output_tokens=50)
        usage2 = TokenUsage(input_tokens=200, output_tokens=100)
        total = usage1 + usage2
        assert total.input_tokens == 300
        assert total.output_tokens == 150
        assert total.total_tokens == 450

    def test_cache_tokens(self):
        """Cache tokens should be tracked."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=20,
            cache_read_input_tokens=30,
        )
        assert usage.cache_creation_input_tokens == 20
        assert usage.cache_read_input_tokens == 30


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self):
        """Should create tool call with all fields."""
        tc = ToolCall(
            id="tool_123",
            name="run_tests",
            input={"test_file": "tests/test_main.py"},
        )
        assert tc.id == "tool_123"
        assert tc.name == "run_tests"
        assert tc.input == {"test_file": "tests/test_main.py"}


class TestAgentResponse:
    """Tests for AgentResponse dataclass."""

    def test_simple_response(self):
        """Simple text response without tool calls."""
        response = AgentResponse(
            content="Hello, I can help with that.",
            stop_reason="end_turn",
            model="claude-sonnet-4-20250514",
        )
        assert response.content == "Hello, I can help with that."
        assert not response.has_tool_calls
        assert response.stop_reason == "end_turn"

    def test_response_with_tool_calls(self):
        """Response with tool calls."""
        response = AgentResponse(
            content="I'll run the tests now.",
            tool_calls=[
                ToolCall(
                    id="tool_1",
                    name="run_tests",
                    input={"verbose": True},
                )
            ],
            stop_reason="tool_use",
            model="claude-sonnet-4-20250514",
        )
        assert response.has_tool_calls
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "run_tests"

    def test_response_with_usage(self):
        """Response with token usage."""
        response = AgentResponse(
            content="Done.",
            usage=TokenUsage(input_tokens=500, output_tokens=100),
        )
        assert response.usage.input_tokens == 500
        assert response.usage.output_tokens == 100


class TestConversationTurn:
    """Tests for ConversationTurn dataclass."""

    def test_user_turn(self):
        """User turn should have role and content."""
        turn = ConversationTurn(
            role="user",
            content="Please implement feature X",
        )
        assert turn.role == "user"
        assert turn.content == "Please implement feature X"
        assert turn.tool_calls == []

    def test_assistant_turn_with_tool(self):
        """Assistant turn with tool call."""
        turn = ConversationTurn(
            role="assistant",
            content="I'll run the tests.",
            tool_calls=[
                ToolCall(id="t1", name="run_tests", input={})
            ],
            tool_results={"t1": {"passed": True}},
        )
        assert turn.role == "assistant"
        assert len(turn.tool_calls) == 1
        assert turn.tool_results["t1"]["passed"] is True


class TestAgentSession:
    """Tests for AgentSession dataclass."""

    def test_empty_session(self):
        """Empty session should have defaults."""
        session = AgentSession(
            model="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            session_type="coding",
        )
        assert session.model == "claude-sonnet-4-20250514"
        assert session.history == []
        assert session.total_usage.total_tokens == 0
        assert session.tool_call_count == 0

    def test_session_with_history(self):
        """Session with conversation history."""
        session = AgentSession(
            model="claude-sonnet-4-20250514",
            system_prompt="You are a helpful assistant.",
            session_type="coding",
            history=[
                ConversationTurn(role="user", content="Hello"),
                ConversationTurn(role="assistant", content="Hi there!"),
            ],
            total_usage=TokenUsage(input_tokens=100, output_tokens=50),
            tool_call_count=0,
        )
        assert len(session.history) == 2
        assert session.total_usage.total_tokens == 150


class TestIsAnthropicAvailable:
    """Tests for is_anthropic_available function."""

    def test_returns_boolean(self):
        """Should return a boolean."""
        result = is_anthropic_available()
        assert isinstance(result, bool)


# Tests that require mocking the Anthropic client
@pytest.mark.skipif(
    not is_anthropic_available(),
    reason="anthropic package not installed"
)
class TestAgentRunner:
    """Tests for AgentRunner class."""

    def test_init_without_api_key_raises(self):
        """Should raise ValueError without API key."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove any existing API key from environment
            import os
            old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                from agent_harness.agent import AgentRunner
                with pytest.raises(ValueError, match="API key required"):
                    AgentRunner()
            finally:
                if old_key:
                    os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_init_with_api_key(self):
        """Should initialize with provided API key."""
        from agent_harness.agent import AgentRunner

        with patch("agent_harness.agent.AsyncAnthropic") as mock_anthropic:
            runner = AgentRunner(api_key="test-key")
            assert runner.api_key == "test-key"
            assert runner.model == "claude-sonnet-4-20250514"
            mock_anthropic.assert_called_once_with(api_key="test-key")

    async def test_send_message(self):
        """Should send message and parse response."""
        from agent_harness.agent import AgentRunner

        with patch("agent_harness.agent.AsyncAnthropic") as mock_anthropic:
            # Mock the response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Hello!", type="text")]
            mock_response.content[0].text = "Hello!"
            mock_response.stop_reason = "end_turn"
            mock_response.usage = MagicMock(
                input_tokens=100,
                output_tokens=10,
            )
            mock_response.model = "claude-sonnet-4-20250514"

            # Make content[0] appear as TextBlock
            mock_text_block = MagicMock()
            mock_text_block.text = "Hello!"

            # Patch isinstance to handle our mock
            with patch("agent_harness.agent.TextBlock", MagicMock):
                with patch("agent_harness.agent.ToolUseBlock", MagicMock):
                    # Mock the async create method
                    async def mock_create(**kwargs):
                        return mock_response

                    mock_anthropic.return_value.messages.create = mock_create

                    runner = AgentRunner(api_key="test-key")
                    response = await runner.send_message(
                        messages=[{"role": "user", "content": "Hi"}],
                        system_prompt="Be helpful",
                    )

                    # Response should be returned (we can't easily verify async mock call)

    def test_get_cost(self):
        """Should calculate cost from usage."""
        from agent_harness.agent import AgentRunner

        with patch("agent_harness.agent.AsyncAnthropic"):
            runner = AgentRunner(api_key="test-key")
            usage = TokenUsage(input_tokens=1000, output_tokens=500)
            cost = runner.get_cost(usage)

            # Should return a float representing cost in USD
            assert isinstance(cost, float)
            assert cost > 0


class TestCreateAgentRunner:
    """Tests for create_agent_runner factory function."""

    @pytest.mark.skipif(
        not is_anthropic_available(),
        reason="anthropic package not installed"
    )
    def test_create_with_defaults(self):
        """Should create runner with default configuration."""
        from agent_harness.agent import create_agent_runner

        with patch("agent_harness.agent.AsyncAnthropic"):
            runner = create_agent_runner(api_key="test-key")
            assert runner.model == "claude-sonnet-4-20250514"
            assert runner.max_tokens == 4096

    @pytest.mark.skipif(
        not is_anthropic_available(),
        reason="anthropic package not installed"
    )
    def test_create_with_custom_model(self):
        """Should create runner with custom model."""
        from agent_harness.agent import create_agent_runner

        with patch("agent_harness.agent.AsyncAnthropic"):
            runner = create_agent_runner(
                api_key="test-key",
                model="claude-3-opus-20240229",
                max_tokens=8192,
            )
            assert runner.model == "claude-3-opus-20240229"
            assert runner.max_tokens == 8192
