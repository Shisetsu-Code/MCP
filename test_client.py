from __future__ import annotations

import asyncio

from mcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8765/mcp") as client:
        tools = await client.list_tools()
        print("TOOLS")
        for tool in tools:
            print("-", tool.name)

        result = await client.call_tool(
            "browser_start",
            {
                "cdp_url": "http://127.0.0.1:9222",
                "launch_if_unavailable": True,
                "headless": False,
            },
        )
        print("\nSTART")
        print(result.structured_content)

        status = await client.call_tool("browser_status", {})
        print("\nSTATUS")
        print(status.structured_content)


if __name__ == "__main__":
    asyncio.run(main())
