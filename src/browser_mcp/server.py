from __future__ import annotations

import os
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.utilities.types import Image

from .browser import BrowserController


mcp = MCPServer("Shisetsu Browser MCP")
browser = BrowserController()


@mcp.tool()
async def browser_start(
    cdp_url: str = "http://127.0.0.1:9222",
    launch_if_unavailable: bool = True,
    headless: bool = False,
) -> dict[str, Any]:
    """Attach to an existing Chromium CDP endpoint, or launch a persistent browser."""
    return await browser.start(
        cdp_url=cdp_url,
        launch_if_unavailable=launch_if_unavailable,
        headless=headless,
    )


@mcp.tool()
async def browser_status() -> dict[str, Any]:
    """Return browser connection, active page, tab count and capture status."""
    return await browser.status()


@mcp.tool()
async def browser_open(url: str, wait_until: str = "domcontentloaded") -> dict[str, Any]:
    """Open an allowed URL in the active browser tab."""
    return await browser.open(url, wait_until=wait_until)


@mcp.tool()
async def browser_tabs() -> list[dict[str, Any]]:
    """List open tabs with indexes."""
    return await browser.tabs()


@mcp.tool()
async def browser_select_tab(index: int) -> dict[str, Any]:
    """Select an open browser tab by index."""
    return await browser.select_tab(index)


@mcp.tool()
async def browser_click(x: float, y: float) -> dict[str, Any]:
    """Click an exact viewport coordinate in the active page."""
    return await browser.click(x, y)


@mcp.tool()
async def browser_click_text(text: str, exact: bool = False) -> dict[str, Any]:
    """Click the first visible text match."""
    return await browser.click_text(text, exact=exact)


@mcp.tool()
async def browser_type(text: str) -> dict[str, Any]:
    """Type text using the keyboard into the currently focused control."""
    return await browser.type_text(text)


@mcp.tool()
async def browser_press(key: str) -> dict[str, Any]:
    """Press a Playwright keyboard key such as Enter, Escape or Control+L."""
    return await browser.press(key)


@mcp.tool()
async def browser_wait(milliseconds: int) -> dict[str, Any]:
    """Wait up to 60 seconds while keeping the browser/session alive."""
    return await browser.wait(milliseconds)


@mcp.tool()
async def browser_screenshot() -> Image:
    """Return a live PNG screenshot of the active browser viewport."""
    return Image(data=await browser.screenshot(), format="png")


@mcp.tool()
async def network_clear() -> dict[str, Any]:
    """Clear captured browser request/response events."""
    return await browser.network_clear()


@mcp.tool()
async def network_events(
    contains: str | None = None,
    kind: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return recent captured network requests/responses, optionally filtered by URL and kind."""
    return await browser.network_events(contains=contains, kind=kind, limit=limit)


@mcp.tool()
async def browser_eval(expression: str) -> Any:
    """Evaluate JavaScript in the active page. Disabled unless MCP_ENABLE_EVAL=1."""
    return await browser.evaluate(expression)


def main() -> None:
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8765"))
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        stateless_http=False,
        json_response=True,
    )


if __name__ == "__main__":
    main()
