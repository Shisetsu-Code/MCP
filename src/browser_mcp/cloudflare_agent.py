from __future__ import annotations

import asyncio
import json
import os
import struct
import time
from urllib.parse import quote

import websockets

from .command_agent import CommandAgent


def ws_url(base_url: str, agent_id: str) -> str:
    base = base_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    elif not base.startswith(("ws://", "wss://")):
        raise ValueError("CF_CONTROL_URL must start with https://, http://, ws:// or wss://")
    return f"{base}/ws?agent_id={quote(agent_id)}"


class CloudflareBrowserAgent:
    def __init__(self) -> None:
        self.base_url = os.environ["CF_CONTROL_URL"]
        self.token = os.environ["CF_CONTROL_TOKEN"]
        self.agent_id = os.getenv("CF_AGENT_ID", "main")
        self.cdp_url = os.getenv("CF_CDP_URL", "http://127.0.0.1:9222")
        self.command_agent = CommandAgent()
        self._send_lock = asyncio.Lock()

    async def send_json(self, ws, payload: dict) -> None:
        async with self._send_lock:
            await ws.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    async def send_state(self, ws, command_id: str | None = None) -> None:
        try:
            state = await self.command_agent.browser.status()
            if state.get("connected"):
                try:
                    state["viewport"] = await self.command_agent.browser.viewport()
                except Exception:
                    pass
            await self.send_json(ws, {
                "type": "state",
                "agent_id": self.agent_id,
                "command_id": command_id,
                "state": state,
                "ts": time.time(),
            })
        except Exception as exc:
            await self.send_json(ws, {
                "type": "event",
                "event": "state_error",
                "payload": {"error": f"{type(exc).__name__}: {exc}"},
            })

    async def send_screenshot(self, ws, command_id: str, args: dict) -> dict:
        quality = max(20, min(int(args.get("quality", 55)), 90))
        page = self.command_agent.browser.require_page()
        jpg = await page.screenshot(type="jpeg", quality=quality, full_page=False)

        header = json.dumps({
            "type": "screenshot",
            "agent_id": self.agent_id,
            "command_id": command_id,
            "mime": "image/jpeg",
            "quality": quality,
            "ts": int(time.time() * 1000),
        }, separators=(",", ":")).encode("utf-8")

        frame = struct.pack(">I", len(header)) + header + jpg
        async with self._send_lock:
            await ws.send(frame)

        return {"bytes": len(jpg), "quality": quality, "uploaded": True}

    async def heartbeat(self, ws) -> None:
        while True:
            await asyncio.sleep(10)
            await self.send_json(ws, {
                "type": "hello",
                "agent_id": self.agent_id,
                "ts": time.time(),
            })
            await self.send_state(ws)

    async def handle_command(self, ws, command: dict) -> None:
        command_id = str(command.get("id", ""))
        action = str(command.get("action", ""))
        args = command.get("args") or {}
        started = time.time()

        await self.send_json(ws, {
            "type": "started",
            "id": command_id,
            "action": action,
            "started_at": started,
        })

        try:
            if not self.command_agent.browser.page or self.command_agent.browser.page.is_closed():
                await self.command_agent.browser.start(
                    cdp_url=self.cdp_url,
                    launch_if_unavailable=True,
                    headless=False,
                )

            if action == "browser_screenshot":
                result = await self.send_screenshot(ws, command_id, args)
            else:
                result = await self.command_agent.execute(command)

            payload = {
                "type": "result",
                "id": command_id,
                "action": action,
                "ok": True,
                "result": result,
                "started_at": started,
                "finished_at": time.time(),
            }
        except Exception as exc:
            payload = {
                "type": "result",
                "id": command_id,
                "action": action,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "started_at": started,
                "finished_at": time.time(),
            }

        await self.send_json(ws, payload)
        await self.send_state(ws, command_id=command_id)

    async def session(self) -> None:
        await self.command_agent.browser.start(
            cdp_url=self.cdp_url,
            launch_if_unavailable=True,
            headless=False,
        )

        uri = ws_url(self.base_url, self.agent_id)
        headers = {"X-Control-Token": self.token}

        print(f"Connecting agent {self.agent_id!r} to {uri}")

        async with websockets.connect(
            uri,
            additional_headers=headers,
            max_size=8 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as ws:
            await self.send_json(ws, {
                "type": "hello",
                "agent_id": self.agent_id,
                "ts": time.time(),
                "version": "0.2.0",
            })
            await self.send_state(ws)

            heartbeat_task = asyncio.create_task(self.heartbeat(ws))
            try:
                async for raw in ws:
                    if not isinstance(raw, str):
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if msg.get("type") != "command":
                        continue

                    command = msg.get("command")
                    if isinstance(command, dict):
                        await self.handle_command(ws, command)
            finally:
                heartbeat_task.cancel()
                await asyncio.gather(heartbeat_task, return_exceptions=True)

    async def run_forever(self) -> None:
        delay = 1.0
        while True:
            try:
                await self.session()
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"WSS disconnected: {type(exc).__name__}: {exc}")
                print(f"Reconnecting in {delay:.1f}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 1.7, 15.0)


def main() -> None:
    asyncio.run(CloudflareBrowserAgent().run_forever())


if __name__ == "__main__":
    main()
