"""Puppeteer MCP integration for agent-harness.

Provides visual verification capabilities through browser automation.
"""

import asyncio
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agent_harness.mcp.manager import MCPManager, MCPServerConfig, MCPToolResult


@dataclass
class ScreenshotResult:
    """Result of a screenshot operation."""

    success: bool
    image_data: Optional[bytes] = None
    image_path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class NavigationResult:
    """Result of a navigation operation."""

    success: bool
    url: str = ""
    title: str = ""
    error: Optional[str] = None


class PuppeteerMCP:
    """High-level interface for Puppeteer MCP operations."""

    def __init__(self, manager: MCPManager):
        """
        Initialize Puppeteer MCP interface.

        Args:
            manager: MCPManager with puppeteer server.
        """
        self.manager = manager
        self.server_name = "puppeteer"

    @property
    def is_available(self) -> bool:
        """Check if Puppeteer MCP is available."""
        return self.server_name in self.manager.servers and \
               self.manager.servers[self.server_name].is_running

    async def navigate(self, url: str, wait_for: str = "load") -> NavigationResult:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to.
            wait_for: Wait condition ("load", "domcontentloaded", "networkidle0").

        Returns:
            NavigationResult.
        """
        if not self.is_available:
            return NavigationResult(
                success=False,
                error="Puppeteer MCP is not available",
            )

        result = await self.manager.execute_tool("puppeteer_navigate", {
            "url": url,
            "waitUntil": wait_for,
        })

        if result.success:
            return NavigationResult(
                success=True,
                url=url,
                title=str(result.output) if result.output else "",
            )
        else:
            return NavigationResult(
                success=False,
                url=url,
                error=result.error,
            )

    async def screenshot(
        self,
        save_path: Optional[Path] = None,
        full_page: bool = False,
        selector: Optional[str] = None,
    ) -> ScreenshotResult:
        """
        Take a screenshot.

        Args:
            save_path: Path to save the screenshot.
            full_page: Whether to capture full page.
            selector: CSS selector to capture specific element.

        Returns:
            ScreenshotResult.
        """
        if not self.is_available:
            return ScreenshotResult(
                success=False,
                error="Puppeteer MCP is not available",
            )

        params = {
            "fullPage": full_page,
        }
        if selector:
            params["selector"] = selector

        result = await self.manager.execute_tool("puppeteer_screenshot", params)

        if not result.success:
            return ScreenshotResult(
                success=False,
                error=result.error,
            )

        # Extract image data from result
        image_data = None
        if isinstance(result.output, str):
            # Assume base64 encoded
            try:
                image_data = base64.b64decode(result.output)
            except Exception:
                image_data = result.output.encode()

        # Save to file if path provided
        if save_path and image_data:
            try:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(image_data)
            except Exception as e:
                return ScreenshotResult(
                    success=False,
                    error=f"Failed to save screenshot: {e}",
                )

        return ScreenshotResult(
            success=True,
            image_data=image_data,
            image_path=save_path,
        )

    async def click(self, selector: str) -> MCPToolResult:
        """
        Click an element.

        Args:
            selector: CSS selector of element to click.

        Returns:
            MCPToolResult.
        """
        if not self.is_available:
            return MCPToolResult(
                success=False,
                output=None,
                error="Puppeteer MCP is not available",
            )

        return await self.manager.execute_tool("puppeteer_click", {
            "selector": selector,
        })

    async def fill(self, selector: str, text: str) -> MCPToolResult:
        """
        Fill an input field.

        Args:
            selector: CSS selector of input.
            text: Text to fill.

        Returns:
            MCPToolResult.
        """
        if not self.is_available:
            return MCPToolResult(
                success=False,
                output=None,
                error="Puppeteer MCP is not available",
            )

        return await self.manager.execute_tool("puppeteer_fill", {
            "selector": selector,
            "value": text,
        })

    async def evaluate(self, script: str) -> MCPToolResult:
        """
        Execute JavaScript in the page.

        Args:
            script: JavaScript code to execute.

        Returns:
            MCPToolResult with script result.
        """
        if not self.is_available:
            return MCPToolResult(
                success=False,
                output=None,
                error="Puppeteer MCP is not available",
            )

        return await self.manager.execute_tool("puppeteer_evaluate", {
            "script": script,
        })

    async def get_text(self, selector: str) -> Optional[str]:
        """
        Get text content of an element.

        Args:
            selector: CSS selector.

        Returns:
            Text content or None.
        """
        result = await self.evaluate(
            f'document.querySelector("{selector}")?.textContent'
        )
        if result.success and result.output:
            return str(result.output)
        return None

    async def wait_for_selector(
        self,
        selector: str,
        timeout: int = 30000,
    ) -> MCPToolResult:
        """
        Wait for an element to appear.

        Args:
            selector: CSS selector.
            timeout: Timeout in milliseconds.

        Returns:
            MCPToolResult.
        """
        if not self.is_available:
            return MCPToolResult(
                success=False,
                output=None,
                error="Puppeteer MCP is not available",
            )

        return await self.manager.execute_tool("puppeteer_waitForSelector", {
            "selector": selector,
            "timeout": timeout,
        })

    async def verify_element_exists(self, selector: str) -> bool:
        """
        Check if an element exists on the page.

        Args:
            selector: CSS selector.

        Returns:
            True if element exists.
        """
        result = await self.evaluate(
            f'document.querySelector("{selector}") !== null'
        )
        return result.success and result.output == "true"

    async def verify_text_present(self, text: str) -> bool:
        """
        Check if text is present on the page.

        Args:
            text: Text to search for.

        Returns:
            True if text is found.
        """
        escaped_text = text.replace('"', '\\"')
        result = await self.evaluate(
            f'document.body.innerText.includes("{escaped_text}")'
        )
        return result.success and result.output == "true"

    async def close(self) -> None:
        """Close the browser."""
        if self.is_available:
            await self.manager.execute_tool("puppeteer_close", {})


async def create_puppeteer_mcp(project_dir: Path) -> tuple[MCPManager, PuppeteerMCP]:
    """
    Create and start a Puppeteer MCP instance.

    Args:
        project_dir: Project directory for working directory.

    Returns:
        Tuple of (MCPManager, PuppeteerMCP).
    """
    manager = MCPManager()

    config = MCPServerConfig(
        name="puppeteer",
        command="npx",
        args=["-y", "@anthropic/mcp-puppeteer"],
        cwd=str(project_dir),
        timeout=60,
    )

    await manager.add_server(config)

    puppeteer = PuppeteerMCP(manager)

    return manager, puppeteer


async def visual_verification(
    url: str,
    checks: list[dict],
    screenshots_dir: Optional[Path] = None,
    project_dir: Optional[Path] = None,
) -> dict:
    """
    Perform visual verification of a web page.

    Args:
        url: URL to verify.
        checks: List of verification checks, each with:
            - type: "element_exists", "text_present", "screenshot"
            - selector: CSS selector (for element_exists)
            - text: Text to find (for text_present)
            - name: Name for screenshot (for screenshot)
        screenshots_dir: Directory to save screenshots.
        project_dir: Project directory for MCP server.

    Returns:
        Dictionary with verification results.
    """
    results = {
        "success": True,
        "url": url,
        "checks": [],
        "screenshots": [],
    }

    if project_dir is None:
        project_dir = Path.cwd()

    # Start Puppeteer MCP
    manager, puppeteer = await create_puppeteer_mcp(project_dir)

    try:
        # Wait for server to be ready
        await asyncio.sleep(2)

        if not puppeteer.is_available:
            results["success"] = False
            results["error"] = "Puppeteer MCP failed to start"
            return results

        # Navigate to URL
        nav_result = await puppeteer.navigate(url)
        if not nav_result.success:
            results["success"] = False
            results["error"] = f"Failed to navigate: {nav_result.error}"
            return results

        # Run checks
        for check in checks:
            check_type = check.get("type", "")
            check_result = {"type": check_type, "passed": False}

            if check_type == "element_exists":
                selector = check.get("selector", "")
                check_result["selector"] = selector
                check_result["passed"] = await puppeteer.verify_element_exists(selector)

            elif check_type == "text_present":
                text = check.get("text", "")
                check_result["text"] = text
                check_result["passed"] = await puppeteer.verify_text_present(text)

            elif check_type == "screenshot":
                name = check.get("name", "screenshot")
                if screenshots_dir:
                    save_path = screenshots_dir / f"{name}.png"
                    screenshot = await puppeteer.screenshot(save_path=save_path)
                    check_result["passed"] = screenshot.success
                    if screenshot.success:
                        results["screenshots"].append(str(save_path))
                else:
                    screenshot = await puppeteer.screenshot()
                    check_result["passed"] = screenshot.success

            if not check_result["passed"]:
                results["success"] = False

            results["checks"].append(check_result)

    finally:
        # Cleanup
        await puppeteer.close()
        await manager.stop_servers()

    return results
