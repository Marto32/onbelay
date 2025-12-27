"""Tests for MCP module."""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from agent_harness.mcp.manager import (
    MCPManager,
    MCPServerConfig,
    MCPToolResult,
    MCPTool,
    MCPServerProcess,
    create_default_mcp_configs,
)
from agent_harness.mcp.puppeteer import (
    PuppeteerMCP,
    ScreenshotResult,
    NavigationResult,
)


class TestMCPServerConfig:
    """Tests for MCPServerConfig dataclass."""

    def test_config_creation(self):
        """Test creating a server config."""
        config = MCPServerConfig(
            name="test",
            command="npx",
            args=["-y", "test-server"],
            env={"KEY": "value"},
            cwd="/tmp",
            timeout=60,
        )

        assert config.name == "test"
        assert config.command == "npx"
        assert len(config.args) == 2
        assert config.env["KEY"] == "value"
        assert config.timeout == 60

    def test_config_defaults(self):
        """Test default values."""
        config = MCPServerConfig(
            name="test",
            command="test",
        )

        assert config.args == []
        assert config.env == {}
        assert config.cwd is None
        assert config.timeout == 30


class TestMCPToolResult:
    """Tests for MCPToolResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = MCPToolResult(
            success=True,
            output={"data": "value"},
        )

        assert result.success
        assert result.output == {"data": "value"}
        assert result.error is None

    def test_error_result(self):
        """Test error result."""
        result = MCPToolResult(
            success=False,
            output=None,
            error="Connection failed",
        )

        assert not result.success
        assert result.error == "Connection failed"


class TestMCPTool:
    """Tests for MCPTool dataclass."""

    def test_tool_creation(self):
        """Test creating a tool definition."""
        tool = MCPTool(
            name="screenshot",
            description="Take a screenshot",
            input_schema={"type": "object", "properties": {}},
            server_name="puppeteer",
        )

        assert tool.name == "screenshot"
        assert tool.description == "Take a screenshot"
        assert tool.server_name == "puppeteer"


class TestMCPManager:
    """Tests for MCPManager class."""

    @pytest.fixture
    def manager(self):
        """Create a manager instance."""
        return MCPManager()

    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert manager.servers == {}
        assert manager.tools == {}
        assert manager._initialized is False

    def test_get_tools_empty(self, manager):
        """Test getting tools when none are registered."""
        tools = manager.get_tools()
        assert tools == []

    def test_get_tool_names_empty(self, manager):
        """Test getting tool names when none are registered."""
        names = manager.get_tool_names()
        assert names == []

    def test_get_server_status_empty(self, manager):
        """Test getting server status when none are running."""
        status = manager.get_server_status()
        assert status == {}

    @pytest.mark.asyncio
    async def test_stop_servers_empty(self, manager):
        """Test stopping servers when none are running."""
        await manager.stop_servers()
        assert manager.servers == {}

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, manager):
        """Test executing unknown tool."""
        result = await manager.execute_tool("unknown_tool", {})

        assert not result.success
        assert "Unknown tool" in result.error


class TestMCPServerProcess:
    """Tests for MCPServerProcess class."""

    @pytest.fixture
    def server_config(self):
        """Create a server config."""
        return MCPServerConfig(
            name="test",
            command="echo",
            args=["hello"],
        )

    @pytest.fixture
    def server(self, server_config):
        """Create a server process instance."""
        return MCPServerProcess(server_config)

    def test_server_not_running_initially(self, server):
        """Test server is not running initially."""
        assert not server.is_running

    @pytest.mark.asyncio
    async def test_stop_not_running(self, server):
        """Test stopping a server that isn't running."""
        await server.stop()
        assert not server.is_running


class TestCreateDefaultConfigs:
    """Tests for create_default_mcp_configs function."""

    def test_creates_puppeteer_config(self, tmp_path):
        """Test creating default configs includes Puppeteer."""
        configs = create_default_mcp_configs(tmp_path)

        assert len(configs) >= 1
        puppeteer_config = next((c for c in configs if c.name == "puppeteer"), None)
        assert puppeteer_config is not None
        assert puppeteer_config.command == "npx"
        assert "@anthropic/mcp-puppeteer" in puppeteer_config.args


class TestScreenshotResult:
    """Tests for ScreenshotResult dataclass."""

    def test_success_result(self, tmp_path):
        """Test successful screenshot result."""
        result = ScreenshotResult(
            success=True,
            image_data=b"PNG data",
            image_path=tmp_path / "screenshot.png",
        )

        assert result.success
        assert result.image_data == b"PNG data"
        assert result.image_path is not None

    def test_error_result(self):
        """Test error screenshot result."""
        result = ScreenshotResult(
            success=False,
            error="Failed to capture",
        )

        assert not result.success
        assert result.error == "Failed to capture"


class TestNavigationResult:
    """Tests for NavigationResult dataclass."""

    def test_success_result(self):
        """Test successful navigation result."""
        result = NavigationResult(
            success=True,
            url="https://example.com",
            title="Example",
        )

        assert result.success
        assert result.url == "https://example.com"
        assert result.title == "Example"

    def test_error_result(self):
        """Test error navigation result."""
        result = NavigationResult(
            success=False,
            error="Connection refused",
        )

        assert not result.success
        assert result.error == "Connection refused"


class TestPuppeteerMCP:
    """Tests for PuppeteerMCP class."""

    @pytest.fixture
    def mock_manager(self):
        """Create a mock manager."""
        manager = Mock(spec=MCPManager)
        manager.servers = {}
        return manager

    @pytest.fixture
    def puppeteer(self, mock_manager):
        """Create a PuppeteerMCP instance."""
        return PuppeteerMCP(mock_manager)

    def test_is_available_no_server(self, puppeteer):
        """Test availability when no server."""
        assert not puppeteer.is_available

    def test_is_available_with_server(self, mock_manager):
        """Test availability with running server."""
        mock_server = Mock()
        mock_server.is_running = True
        mock_manager.servers = {"puppeteer": mock_server}

        puppeteer = PuppeteerMCP(mock_manager)

        assert puppeteer.is_available

    @pytest.mark.asyncio
    async def test_navigate_unavailable(self, puppeteer):
        """Test navigate when not available."""
        result = await puppeteer.navigate("https://example.com")

        assert not result.success
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_screenshot_unavailable(self, puppeteer):
        """Test screenshot when not available."""
        result = await puppeteer.screenshot()

        assert not result.success
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_click_unavailable(self, puppeteer):
        """Test click when not available."""
        result = await puppeteer.click("button")

        assert not result.success
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fill_unavailable(self, puppeteer):
        """Test fill when not available."""
        result = await puppeteer.fill("input", "text")

        assert not result.success
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_evaluate_unavailable(self, puppeteer):
        """Test evaluate when not available."""
        result = await puppeteer.evaluate("document.title")

        assert not result.success
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_wait_for_selector_unavailable(self, puppeteer):
        """Test wait_for_selector when not available."""
        result = await puppeteer.wait_for_selector(".element")

        assert not result.success
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_verify_element_exists_unavailable(self, puppeteer):
        """Test verify_element_exists when not available."""
        result = await puppeteer.verify_element_exists(".element")

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_text_present_unavailable(self, puppeteer):
        """Test verify_text_present when not available."""
        result = await puppeteer.verify_text_present("Hello")

        assert result is False

    @pytest.mark.asyncio
    async def test_close_unavailable(self, puppeteer):
        """Test close when not available."""
        # Should not raise
        await puppeteer.close()


class TestPuppeteerMCPWithMockServer:
    """Tests for PuppeteerMCP with a mock server."""

    @pytest.fixture
    def mock_manager(self):
        """Create a mock manager with mock server."""
        manager = Mock(spec=MCPManager)
        mock_server = Mock()
        mock_server.is_running = True
        manager.servers = {"puppeteer": mock_server}
        return manager

    @pytest.fixture
    def puppeteer(self, mock_manager):
        """Create a PuppeteerMCP instance."""
        return PuppeteerMCP(mock_manager)

    @pytest.mark.asyncio
    async def test_navigate_success(self, puppeteer, mock_manager):
        """Test successful navigation."""
        mock_manager.execute_tool = AsyncMock(return_value=MCPToolResult(
            success=True,
            output="Example Page",
        ))

        result = await puppeteer.navigate("https://example.com")

        assert result.success
        assert result.url == "https://example.com"

    @pytest.mark.asyncio
    async def test_navigate_failure(self, puppeteer, mock_manager):
        """Test failed navigation."""
        mock_manager.execute_tool = AsyncMock(return_value=MCPToolResult(
            success=False,
            output=None,
            error="Connection refused",
        ))

        result = await puppeteer.navigate("https://example.com")

        assert not result.success
        assert result.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_screenshot_success(self, puppeteer, mock_manager, tmp_path):
        """Test successful screenshot."""
        mock_manager.execute_tool = AsyncMock(return_value=MCPToolResult(
            success=True,
            output="iVBORw0KGgo=",  # Base64 encoded PNG header
        ))

        save_path = tmp_path / "test.png"
        result = await puppeteer.screenshot(save_path=save_path)

        assert result.success
        assert save_path.exists() or result.image_data is not None

    @pytest.mark.asyncio
    async def test_click_success(self, puppeteer, mock_manager):
        """Test successful click."""
        mock_manager.execute_tool = AsyncMock(return_value=MCPToolResult(
            success=True,
            output="Clicked",
        ))

        result = await puppeteer.click("button.submit")

        assert result.success

    @pytest.mark.asyncio
    async def test_fill_success(self, puppeteer, mock_manager):
        """Test successful fill."""
        mock_manager.execute_tool = AsyncMock(return_value=MCPToolResult(
            success=True,
            output="Filled",
        ))

        result = await puppeteer.fill("input#email", "test@example.com")

        assert result.success

    @pytest.mark.asyncio
    async def test_get_text_success(self, puppeteer, mock_manager):
        """Test getting text content."""
        mock_manager.execute_tool = AsyncMock(return_value=MCPToolResult(
            success=True,
            output="Hello World",
        ))

        text = await puppeteer.get_text(".title")

        assert text == "Hello World"

    @pytest.mark.asyncio
    async def test_get_text_failure(self, puppeteer, mock_manager):
        """Test getting text when element not found."""
        mock_manager.execute_tool = AsyncMock(return_value=MCPToolResult(
            success=False,
            output=None,
            error="Element not found",
        ))

        text = await puppeteer.get_text(".nonexistent")

        assert text is None
