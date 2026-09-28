from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .browser import BrowserController


COMMAND_FILE = Path(os.getenv("MCP_COMMAND_FILE", "commands/current.json"))
RESULT_FILE = Path(os.getenv("MCP_RESULT_FILE", "commands/result.json"))
POLL_MS = int(os.getenv("MCP_COMMAND_POLL_MS", "1200"))
GIT_SYNC = os.getenv("MCP_GIT_SYNC", "1") == "1"


class CommandAgent:
    def __init__(self) -> None:
        self.browser = BrowserController()
        self.last_id: str | None = None

    def _git(self, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            text=True,
            capture_output=True,
            check=check,
        )

    def sync_from_remote(self) -> None:
        if not GIT_SYNC:
            return
        proc = self._git("pull", "--rebase", "--autostash", "origin", "main")
        if proc.returncode != 0:
            print("git pull:", proc.stderr.strip() or proc.stdout.strip())

    def publish_result(self, command_id: str) -> None:
        if not GIT_SYNC:
            return

        self._git("add", str(RESULT_FILE))
        latest = Path("commands/latest.png")
        if latest.exists():
            self._git("add", str(latest))
        latest_b64 = Path("commands/latest.b64")
        if latest_b64.exists():
            self._git("add", str(latest_b64))
        diff = self._git("diff", "--cached", "--quiet")
        if diff.returncode == 0:
            return

        self._git(
            "-c",
            "user.name=browser-command-agent",
            "-c",
            "user.email=browser-command-agent@localhost",
            "commit",
            "-m",
            f"result: {command_id}",
        )

        for attempt in range(3):
            pushed = self._git("push", "origin", "main")
            if pushed.returncode == 0:
                return
            print("git push:", pushed.stderr.strip() or pushed.stdout.strip())
            self._git("pull", "--rebase", "--autostash", "origin", "main")
            time.sleep(0.4 * (attempt + 1))

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
            png = await self.browser.screenshot()
            path.write_bytes(png)
            b64_path = Path("commands/latest.b64")
            b64_path.write_text(base64.b64encode(png).decode("ascii"), encoding="ascii")
            return {"path": str(path.resolve()), "base64_path": str(b64_path.resolve())}

        raise ValueError(f"Unsupported action: {action!r}")

    async def run_forever(self) -> None:
        COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)

        print(f"Watching {COMMAND_FILE.resolve()} every {POLL_MS} ms")
        print(f"Git sync: {'enabled' if GIT_SYNC else 'disabled'}")

        while True:
            try:
                self.sync_from_remote()

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
                            self.publish_result(command_id)
            except Exception as exc:
                print(f"agent loop error: {type(exc).__name__}: {exc}")

            await asyncio.sleep(POLL_MS / 1000)


def main() -> None:
    asyncio.run(CommandAgent().run_forever())


if __name__ == "__main__":
    main()
