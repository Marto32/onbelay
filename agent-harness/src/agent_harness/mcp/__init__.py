"""MCP (Model Context Protocol) integration for agent-harness.

Provides tools for starting and managing MCP servers to extend
agent capabilities with visual verification and other tools.
"""

from agent_harness.mcp.manager import MCPManager, MCPServerConfig, MCPToolResult
from agent_harness.mcp.puppeteer import PuppeteerMCP

__all__ = [
    "MCPManager",
    "MCPServerConfig",
    "MCPToolResult",
    "PuppeteerMCP",
]
