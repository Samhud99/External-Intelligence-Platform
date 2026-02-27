import base64
import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class BrowserTool:
    """Playwright-based browser tool for JS-rendered pages."""

    async def browse_page(
        self,
        url: str,
        actions: Optional[List[Dict[str, Any]]] = None,
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()
                await page.goto(url, timeout=timeout, wait_until="networkidle")

                if actions:
                    for action_def in actions:
                        await self._execute_action(page, action_def)

                html = await page.content()
                title = await page.title()
                screenshot = await page.screenshot(type="png")
                final_url = page.url

                await context.close()
                await browser.close()

                return {
                    "html": html[:100000],
                    "title": title,
                    "url": final_url,
                    "screenshot_b64": base64.b64encode(screenshot).decode("utf-8"),
                    "content_length": len(html),
                }
        except Exception as e:
            logger.error(f"Browser error for {url}: {e}")
            return {"error": str(e), "url": url}

    async def _execute_action(self, page: Any, action_def: Dict[str, Any]) -> None:
        action = action_def["action"]
        selector = action_def.get("selector", "")
        value = action_def.get("value", "")
        timeout = action_def.get("timeout", 10000)

        if action == "wait_for_selector":
            await page.wait_for_selector(selector, timeout=timeout)
        elif action == "click":
            await page.click(selector)
        elif action == "fill":
            await page.fill(selector, value)
        elif action == "scroll":
            direction = action_def.get("direction", "bottom")
            if direction == "bottom":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            else:
                await page.evaluate("window.scrollTo(0, 0)")
        elif action == "wait":
            import asyncio
            await asyncio.sleep(action_def.get("seconds", 2))
        else:
            logger.warning(f"Unknown browser action: {action}")
