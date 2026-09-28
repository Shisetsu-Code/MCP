from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from .browser import BrowserController


COMMAND_FILE = Path(os.getenv("MCP_COMMAND_FILE", "commands/current.json"))
RESULT_FILE = Path(os.getenv("MCP_RESULT_FILE", "commands/result.json"))
POLL_MS = int(os.getenv("MCP_COMMAND_POLL_MS", "400"))


class CommandAgent:
    def __init__(self) -> None:
        self.browser = BrowserController()
        self.last_id: str | None = None

    async def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        action = command.get("action")
        args = command.get("args") or {}

        if action == "browser_start":
            return await self.browser.start(**args)
        if action == "browser_status":
            return await self.browser.status()
        if action == "browser_open":
            return await self.browser.open(**args)
        if action == "browser_click":
            return await self.browser.click(**args)
        if action == "browser_click_text":
            return await self.browser.click_text(**args)
        if action == "browser_type":
            return await self.browser.type_text(**args)
        if action == "browser_press":
            return await self.browser.press(**args)
        if action == "browser_wait":
            return await self.browser.wait(**args)
        if action == "browser_tabs":
            return {"tabs": await self.browser.tabs()}
        if action == "browser_select_tab":
            return await self.browser.select_tab(**args)
        if action == "network_clear":
            return await self.browser.network_clear()
        if action == "network_events":
            return {"events": await self.browser.network_events(**args)}
        if action == "browser_screenshot":
            path = Path(args.get("path", "commands/latest.png"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(await self.browser.screenshot())
            return {"path": str(path.resolve())}

        raise ValueError(f"Unsupported action: {action!r}")

    async def run_forever(self) -> None:
        COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)

        print(f"Watching {COMMAND_FILE.resolve()} every {POLL_MS} ms")

        while True:
            try:
                if COMMAND_FILE.exists():
                    raw = COMMAND_FILE.read_text(encoding="utf-8").strip()
                    if raw:
                        command = json.loads(raw)
                        command_id = str(command.get("id", ""))
                        if command_id and command_id != self.last_id:
                            self.last_id = command_id
                            started = time.time()
                            try:
                                result = await self.execute(command)
                                payload = {
                                    "id": command_id,
                                    "ok": True,
                                    "action": command.get("action"),
                                    "result": result,
                                    "started_at": started,
                                    "finished_at": time.time(),
                                }
                            except Exception as exc:
                                payload = {
                                    "id": command_id,
                                    "ok": False,
                                    "action": command.get("action"),
                                    "error": f"{type(exc).__name__}: {exc}",
                                    "started_at": started,
                                    "finished_at": time.time(),
                                }

                            RESULT_FILE.write_text(
                                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8",
                            )
                            print(json.dumps(payload, ensure_ascii=False))
            except Exception as exc:
                print(f"agent loop error: {type(exc).__name__}: {exc}")

            await asyncio.sleep(POLL_MS / 1000)


def main() -> None:
    asyncio.run(CommandAgent().run_forever())


if __name__ == "__main__":
    main()
