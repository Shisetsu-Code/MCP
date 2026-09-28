from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


DEFAULT_ALLOWED_HOSTS = (
    "yggdrasilgaming.com",
    "staticdemo.yggdrasilgaming.com",
    "demo.yggdrasilgaming.com",
)


@dataclass
class BrowserController:
    playwright: Playwright | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    network: list[dict[str, Any]] = field(default_factory=list)
    _response_tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        raw = os.getenv("MCP_ALLOWED_HOSTS", ",".join(DEFAULT_ALLOWED_HOSTS))
        return tuple(x.strip().lower() for x in raw.split(",") if x.strip())

    def _check_url(self, url: str) -> None:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            raise ValueError("URL must include a hostname")
        if not any(host == allowed or host.endswith("." + allowed) for allowed in self.allowed_hosts):
            raise ValueError(
                f"Host {host!r} is not allowed. Configure MCP_ALLOWED_HOSTS to permit it."
            )

    async def start(
        self,
        *,
        cdp_url: str = "http://127.0.0.1:9222",
        launch_if_unavailable: bool = True,
        headless: bool = False,
    ) -> dict[str, Any]:
        async with self._lock:
            if self.page and not self.page.is_closed():
                return await self.status()

            self.playwright = await async_playwright().start()

            try:
                self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)
                contexts = self.browser.contexts
                self.context = contexts[0] if contexts else None
            except Exception:
                if not launch_if_unavailable:
                    await self.playwright.stop()
                    self.playwright = None
                    raise
                self.browser = await self.playwright.chromium.launch(headless=headless)
                self.context = await self.browser.new_context(
                    viewport={"width": 1440, "height": 1000}
                )

            if self.context is None:
                self.context = await self.browser.new_context(
                    viewport={"width": 1440, "height": 1000}
                )

            pages = self.context.pages
            self.page = pages[0] if pages else await self.context.new_page()
            self._attach_page(self.page)

            self.context.on("page", self._on_new_page)
            return await self.status()

    def _on_new_page(self, page: Page) -> None:
        self.page = page
        self._attach_page(page)

    def _attach_page(self, page: Page) -> None:
        page.on("request", self._on_request)
        page.on("response", self._on_response)

    def _on_request(self, request) -> None:
        self.network.append(
            {
                "kind": "request",
                "ts": time.time(),
                "method": request.method,
                "url": request.url,
                "resource_type": request.resource_type,
                "post_data": request.post_data,
                "headers": self._redact_headers(request.headers),
            }
        )
        self._trim_network()

    def _on_response(self, response) -> None:
        task = asyncio.create_task(self._capture_response(response))
        self._response_tasks.add(task)
        task.add_done_callback(self._response_tasks.discard)

    async def _capture_response(self, response) -> None:
        item: dict[str, Any] = {
            "kind": "response",
            "ts": time.time(),
            "method": response.request.method,
            "url": response.url,
            "status": response.status,
            "headers": self._redact_headers(response.headers),
            "body": None,
        }
        ctype = (response.headers.get("content-type") or "").lower()
        if any(x in ctype for x in ("json", "text", "javascript", "xml", "form")):
            try:
                text = await response.text()
                item["body"] = text[: int(os.getenv("MCP_MAX_BODY_CHARS", "250000"))]
            except Exception as exc:
                item["body_error"] = str(exc)

        self.network.append(item)
        self._trim_network()

    @staticmethod
    def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
        sensitive = {"authorization", "cookie", "set-cookie", "proxy-authorization"}
        return {k: ("<redacted>" if k.lower() in sensitive else v) for k, v in headers.items()}

    def _trim_network(self) -> None:
        limit = int(os.getenv("MCP_MAX_NETWORK_EVENTS", "5000"))
        if len(self.network) > limit:
            del self.network[: len(self.network) - limit]

    def require_page(self) -> Page:
        if not self.page or self.page.is_closed():
            raise RuntimeError("Browser is not started. Call browser_start first.")
        return self.page

    async def status(self) -> dict[str, Any]:
        page = self.page
        return {
            "connected": bool(page and not page.is_closed()),
            "url": page.url if page and not page.is_closed() else None,
            "title": await page.title() if page and not page.is_closed() else None,
            "pages": len(self.context.pages) if self.context else 0,
            "network_events": len(self.network),
            "allowed_hosts": list(self.allowed_hosts),
        }

    async def open(self, url: str, wait_until: str = "domcontentloaded") -> dict[str, Any]:
        self._check_url(url)
        page = self.require_page()
        response = await page.goto(url, wait_until=wait_until, timeout=90_000)
        return {
            "url": page.url,
            "title": await page.title(),
            "status": response.status if response else None,
        }

    async def tabs(self) -> list[dict[str, Any]]:
        if not self.context:
            return []
        out = []
        for idx, page in enumerate(self.context.pages):
            out.append(
                {
                    "index": idx,
                    "active": page is self.page,
                    "url": page.url,
                    "title": await page.title(),
                }
            )
        return out

    async def select_tab(self, index: int) -> dict[str, Any]:
        if not self.context:
            raise RuntimeError("Browser is not started")
        pages = self.context.pages
        if index < 0 or index >= len(pages):
            raise IndexError(f"Tab index out of range: {index}")
        self.page = pages[index]
        await self.page.bring_to_front()
        return await self.status()

    async def viewport(self) -> dict[str, Any]:
        page = self.require_page()
        size = page.viewport_size
        if size:
            return {"width": size["width"], "height": size["height"], "source": "viewport"}
        dims = await page.evaluate("() => ({width: window.innerWidth, height: window.innerHeight})")
        return {"width": int(dims["width"]), "height": int(dims["height"]), "source": "window"}

    async def click(self, x: float, y: float) -> dict[str, Any]:
        page = self.require_page()
        await page.mouse.click(x, y)
        return {"clicked": {"x": x, "y": y}, "url": page.url}

    async def click_relative(self, rx: float, ry: float) -> dict[str, Any]:
        if not (0 <= rx <= 1 and 0 <= ry <= 1):
            raise ValueError("rx and ry must be between 0 and 1")
        page = self.require_page()
        vp = await self.viewport()
        x = vp["width"] * rx
        y = vp["height"] * ry
        await page.mouse.click(x, y)
        return {
            "clicked_relative": {"rx": rx, "ry": ry},
            "clicked_absolute": {"x": x, "y": y},
            "viewport": vp,
            "url": page.url,
        }

    async def click_text(self, text: str, exact: bool = False) -> dict[str, Any]:
        page = self.require_page()
        locator = page.get_by_text(text, exact=exact)
        count = await locator.count()
        if count == 0:
            raise ValueError(f"No visible text match for {text!r}")
        await locator.first.click(timeout=10_000)
        return {"matched": count, "clicked": text, "url": page.url}

    async def type_text(self, text: str) -> dict[str, Any]:
        page = self.require_page()
        await page.keyboard.type(text)
        return {"typed_chars": len(text)}

    async def press(self, key: str) -> dict[str, Any]:
        page = self.require_page()
        await page.keyboard.press(key)
        return {"pressed": key}

    async def wait(self, milliseconds: int) -> dict[str, Any]:
        page = self.require_page()
        milliseconds = max(0, min(milliseconds, 60_000))
        await page.wait_for_timeout(milliseconds)
        return {"waited_ms": milliseconds}

    async def screenshot(self) -> bytes:
        page = self.require_page()
        return await page.screenshot(type="png", full_page=False)

    async def network_clear(self) -> dict[str, Any]:
        count = len(self.network)
        self.network.clear()
        return {"cleared": count}

    async def wait_for_network(
        self,
        *,
        contains: str,
        kind: str | None = None,
        timeout_ms: int = 10000,
        since_index: int | None = None,
    ) -> list[dict[str, Any]]:
        deadline = time.time() + max(0, min(timeout_ms, 60000)) / 1000
        start = len(self.network) if since_index is None else max(0, since_index)

        while time.time() < deadline:
            if self._response_tasks:
                await asyncio.gather(*tuple(self._response_tasks), return_exceptions=True)

            events = self.network[start:]
            needle = contains.lower()
            matches = [e for e in events if needle in str(e.get("url", "")).lower()]
            if kind:
                matches = [e for e in matches if e.get("kind") == kind]

            if matches:
                return matches

            await asyncio.sleep(0.1)

        return []

    async def network_events(
        self,
        *,
        contains: str | None = None,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self._response_tasks:
            await asyncio.gather(*tuple(self._response_tasks), return_exceptions=True)

        events = self.network
        if contains:
            needle = contains.lower()
            events = [e for e in events if needle in str(e.get("url", "")).lower()]
        if kind:
            events = [e for e in events if e.get("kind") == kind]
        limit = max(1, min(limit, 500))
        return events[-limit:]

    async def evaluate(self, expression: str) -> Any:
        if os.getenv("MCP_ENABLE_EVAL", "0") != "1":
            raise PermissionError("browser_eval is disabled. Set MCP_ENABLE_EVAL=1 to enable it.")
        page = self.require_page()
        return await page.evaluate(expression)

    async def close(self) -> None:
        async with self._lock:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.browser = None
            self.context = None
            self.page = None
            self.playwright = None
