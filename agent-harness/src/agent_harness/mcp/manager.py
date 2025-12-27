"""MCP Server Manager for agent-harness.

Manages the lifecycle of MCP servers and provides tool integration.
"""

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    timeout: int = 30


@dataclass
class MCPToolResult:
    """Result of an MCP tool execution."""

    success: bool
    output: Any
    error: Optional[str] = None


@dataclass
class MCPTool:
    """An MCP tool definition."""

    name: str
    description: str
    input_schema: dict
    server_name: str


class MCPServerProcess:
    """Represents a running MCP server process."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.stdin_lock = asyncio.Lock()
        self._request_id = 0

    async def start(self) -> bool:
        """Start the MCP server process."""
        try:
            env = dict(self.config.env) if self.config.env else None

            self.process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.config.cwd,
                env=env,
                text=True,
            )

            # Wait briefly to check if process started
            await asyncio.sleep(0.1)

            if self.process.poll() is not None:
                return False

            return True

        except Exception:
            return False

    async def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except Exception:
                pass
            finally:
                self.process = None

    @property
    def is_running(self) -> bool:
        """Check if the process is running."""
        return self.process is not None and self.process.poll() is None

    async def send_request(self, method: str, params: Optional[dict] = None) -> dict:
        """
        Send a JSON-RPC request to the MCP server.

        Args:
            method: RPC method name.
            params: Method parameters.

        Returns:
            Response dictionary.
        """
        if not self.is_running:
            raise RuntimeError("MCP server is not running")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        async with self.stdin_lock:
            # Write request
            request_str = json.dumps(request) + "\n"
            self.process.stdin.write(request_str)
            self.process.stdin.flush()

            # Read response
            # Note: This is a simplified implementation
            # Real MCP uses proper message framing
            response_line = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self.process.stdout.readline
                ),
                timeout=self.config.timeout,
            )

            if not response_line:
                raise RuntimeError("No response from MCP server")

            return json.loads(response_line)


class MCPManager:
    """Manages multiple MCP servers and their tools."""

    def __init__(self):
        self.servers: dict[str, MCPServerProcess] = {}
        self.tools: dict[str, MCPTool] = {}
        self._initialized = False

    async def add_server(self, config: MCPServerConfig) -> bool:
        """
        Add and start an MCP server.

        Args:
            config: Server configuration.

        Returns:
            True if server started successfully.
        """
        server = MCPServerProcess(config)
        success = await server.start()

        if success:
            self.servers[config.name] = server
            # Discover tools from the server
            await self._discover_tools(config.name)

        return success

    async def remove_server(self, name: str) -> None:
        """
        Stop and remove an MCP server.

        Args:
            name: Server name.
        """
        if name in self.servers:
            await self.servers[name].stop()
            del self.servers[name]

            # Remove tools from this server
            self.tools = {
                k: v for k, v in self.tools.items()
                if v.server_name != name
            }

    async def start_servers(self, configs: list[MCPServerConfig]) -> dict[str, bool]:
        """
        Start multiple MCP servers.

        Args:
            configs: List of server configurations.

        Returns:
            Dictionary mapping server names to success status.
        """
        results = {}
        for config in configs:
            results[config.name] = await self.add_server(config)
        return results

    async def stop_servers(self) -> None:
        """Stop all MCP servers."""
        for name in list(self.servers.keys()):
            await self.remove_server(name)

    async def _discover_tools(self, server_name: str) -> None:
        """Discover available tools from an MCP server."""
        server = self.servers.get(server_name)
        if not server or not server.is_running:
            return

        try:
            response = await server.send_request("tools/list")

            if "result" in response and "tools" in response["result"]:
                for tool_def in response["result"]["tools"]:
                    tool = MCPTool(
                        name=tool_def.get("name", ""),
                        description=tool_def.get("description", ""),
                        input_schema=tool_def.get("inputSchema", {}),
                        server_name=server_name,
                    )
                    self.tools[tool.name] = tool

        except Exception:
            pass  # Tool discovery is best-effort

    def get_tools(self) -> list[dict]:
        """
        Get all available MCP tools in Claude API format.

        Returns:
            List of tool definitions.
        """
        tool_defs = []
        for tool in self.tools.values():
            tool_defs.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            })
        return tool_defs

    def get_tool_names(self) -> list[str]:
        """Get names of all available tools."""
        return list(self.tools.keys())

    async def execute_tool(self, tool_name: str, params: dict) -> MCPToolResult:
        """
        Execute an MCP tool.

        Args:
            tool_name: Name of the tool to execute.
            params: Tool parameters.

        Returns:
            MCPToolResult with execution result.
        """
        tool = self.tools.get(tool_name)
        if not tool:
            return MCPToolResult(
                success=False,
                output=None,
                error=f"Unknown tool: {tool_name}",
            )

        server = self.servers.get(tool.server_name)
        if not server or not server.is_running:
            return MCPToolResult(
                success=False,
                output=None,
                error=f"Server '{tool.server_name}' is not running",
            )

        try:
            response = await server.send_request("tools/call", {
                "name": tool_name,
                "arguments": params,
            })

            if "error" in response:
                return MCPToolResult(
                    success=False,
                    output=None,
                    error=response["error"].get("message", str(response["error"])),
                )

            result = response.get("result", {})
            content = result.get("content", [])

            # Extract text content
            output_parts = []
            for item in content:
                if item.get("type") == "text":
                    output_parts.append(item.get("text", ""))
                elif item.get("type") == "image":
                    output_parts.append(f"[Image: {item.get('mimeType', 'image/*')}]")

            return MCPToolResult(
                success=True,
                output="\n".join(output_parts) if output_parts else result,
            )

        except asyncio.TimeoutError:
            return MCPToolResult(
                success=False,
                output=None,
                error="Tool execution timed out",
            )
        except Exception as e:
            return MCPToolResult(
                success=False,
                output=None,
                error=str(e),
            )

    def get_server_status(self) -> dict[str, bool]:
        """Get running status of all servers."""
        return {name: server.is_running for name, server in self.servers.items()}

    async def health_check(self) -> dict[str, bool]:
        """
        Perform health check on all servers.

        Returns:
            Dictionary mapping server names to health status.
        """
        results = {}
        for name, server in self.servers.items():
            if not server.is_running:
                results[name] = False
                continue

            try:
                # Send a ping request
                response = await server.send_request("ping")
                results[name] = "error" not in response
            except Exception:
                results[name] = False

        return results


def create_default_mcp_configs(project_dir: Path) -> list[MCPServerConfig]:
    """
    Create default MCP server configurations.

    Args:
        project_dir: Path to the project directory.

    Returns:
        List of default MCPServerConfig objects.
    """
    configs = []

    # Puppeteer MCP for visual verification
    configs.append(MCPServerConfig(
        name="puppeteer",
        command="npx",
        args=["-y", "@anthropic/mcp-puppeteer"],
        cwd=str(project_dir),
        timeout=60,
    ))

    return configs
