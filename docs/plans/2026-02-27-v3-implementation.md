# V3: Persistent Agentic Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add persistent agent memory, a tiered extraction strategy ladder (CSS → Playwright → Computer Use), and graceful failure with actionable next steps.

**Architecture:** The existing tool-use agent gets three new tools (browse_page, computer_use, remember/recall). The streaming agent gains escalation logic — when a tier fails, it proposes the next tier to the user. The automated runner becomes tier-aware with retry and health monitoring. Failures produce structured events with user-facing messages and expandable diagnostics.

**Tech Stack:** Python 3.9+, FastAPI, Playwright (async), Anthropic computer use API, React 18 + TypeScript + Tailwind CSS

---

### Task 1: Agent Memory Store

**Files:**
- Create: `eip/agent/memory.py`
- Create: `tests/test_memory.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from eip.agent.memory import AgentMemory
from eip.store.json_store import JsonStore


def test_remember_and_recall(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)

    memory.remember("example.com", "site_profile", "React SPA, needs JS rendering")
    entries = memory.recall("example.com")

    assert len(entries) == 1
    assert entries[0]["key"] == "site_profile"
    assert entries[0]["value"] == "React SPA, needs JS rendering"
    assert "created_at" in entries[0]


def test_recall_empty_domain(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)

    entries = memory.recall("unknown.com")
    assert entries == []


def test_remember_appends(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)

    memory.remember("example.com", "tier_1_failure", "CSS selectors returned 0 items")
    memory.remember("example.com", "tier_2_success", "Playwright worked, found 15 items")

    entries = memory.recall("example.com")
    assert len(entries) == 2
    assert entries[0]["key"] == "tier_1_failure"
    assert entries[1]["key"] == "tier_2_success"


def test_recall_formats_for_prompt(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)

    memory.remember("example.com", "site_profile", "Static HTML site")
    text = memory.recall_as_text("example.com")

    assert "site_profile" in text
    assert "Static HTML site" in text


def test_recall_as_text_empty(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)

    text = memory.recall_as_text("unknown.com")
    assert text == ""
```

**Step 2: Run test to verify it fails**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && python -m pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

from eip.store.json_store import JsonStore


class AgentMemory:
    """Persistent agent memory scoped by domain."""

    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def _domain_id(self, domain: str) -> str:
        """Normalize domain to a safe file ID."""
        return domain.replace(".", "_").replace("/", "_")

    def remember(self, domain: str, key: str, value: str) -> None:
        """Store a learning about a domain."""
        domain_id = self._domain_id(domain)
        existing = self.store.load("memory", domain_id)
        if existing is None:
            existing = {"domain": domain, "entries": []}

        existing["entries"].append({
            "key": key,
            "value": value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self.store.save("memory", domain_id, existing)

    def recall(self, domain: str) -> List[Dict]:
        """Load all memories for a domain."""
        domain_id = self._domain_id(domain)
        data = self.store.load("memory", domain_id)
        if data is None:
            return []
        return data.get("entries", [])

    def recall_as_text(self, domain: str) -> str:
        """Format memories as text for inclusion in agent system prompt."""
        entries = self.recall(domain)
        if not entries:
            return ""
        lines = [f"- {e['key']}: {e['value']}" for e in entries]
        return "\n".join(lines)

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from a URL."""
        parsed = urlparse(url)
        return parsed.netloc or url
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_memory.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add eip/agent/memory.py tests/test_memory.py
git commit -m "feat: add persistent agent memory store"
```

---

### Task 2: New Event Types (Escalation + Failure)

**Files:**
- Modify: `eip/agent/events.py`
- Modify: `tests/test_events.py`

**Step 1: Write the failing tests**

Add these to the end of `tests/test_events.py`:

```python
def test_escalation_proposal_event() -> None:
    event = AgentEvent(
        type=EventType.ESCALATION_PROPOSAL,
        message="CSS selectors found 0 items. This site loads content with JavaScript.",
        current_tier="css",
        proposed_tier="playwright",
    )
    d = event.to_dict()
    assert d["type"] == "escalation_proposal"
    assert d["current_tier"] == "css"
    assert d["proposed_tier"] == "playwright"


def test_failure_event() -> None:
    event = AgentEvent(
        type=EventType.FAILURE,
        failure_code="login_required",
        user_message="This page requires authentication to access.",
        next_steps=[
            {"type": "provide_credentials", "label": "Provide login credentials"},
            {"type": "change_url", "label": "Try a different page"},
        ],
        technical_details={"http_status": 302, "redirect_url": "https://example.com/login"},
    )
    d = event.to_dict()
    assert d["type"] == "failure"
    assert d["failure_code"] == "login_required"
    assert len(d["next_steps"]) == 2
    assert d["technical_details"]["http_status"] == 302


def test_all_event_types_v3() -> None:
    expected = {
        "status", "page_fetched", "thinking", "extraction_test",
        "proposal", "done", "error", "escalation_proposal", "failure",
    }
    actual = {e.value for e in EventType}
    assert expected == actual
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_events.py -v`
Expected: FAIL — `AttributeError` (no `ESCALATION_PROPOSAL` or `FAILURE` on EventType)

**Step 3: Update `eip/agent/events.py`**

Add two new enum values to `EventType`:

```python
    ESCALATION_PROPOSAL = "escalation_proposal"
    FAILURE = "failure"
```

Add new fields to `AgentEvent.__init__`:

```python
        self.current_tier = current_tier
        self.proposed_tier = proposed_tier
        self.failure_code = failure_code
        self.user_message = user_message
        self.next_steps = next_steps
        self.technical_details = technical_details
```

Add the new field names to the `to_dict()` iteration list:

```python
            "current_tier", "proposed_tier",
            "failure_code", "user_message", "next_steps", "technical_details",
```

Also update the existing `test_all_event_types_exist` test — rename it or remove it since `test_all_event_types_v3` supersedes it.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_events.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add eip/agent/events.py tests/test_events.py
git commit -m "feat: add escalation_proposal and failure event types"
```

---

### Task 3: Playwright Browser Tool

**Files:**
- Create: `eip/agent/browser.py`
- Create: `tests/test_browser.py`

**Step 1: Install Playwright**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && pip install playwright && playwright install chromium`

Add `playwright>=1.40.0` to `requirements.txt`.

**Step 2: Write the failing test**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from eip.agent.browser import BrowserTool


@pytest.mark.asyncio
async def test_browse_page_returns_html() -> None:
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>Rendered</body></html>")
    mock_page.title = AsyncMock(return_value="Test Page")
    mock_page.screenshot = AsyncMock(return_value=b"fake_png_bytes")
    mock_page.url = "https://example.com"
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    with patch("eip.agent.browser.async_playwright") as mock_pw:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.__aenter__ = AsyncMock(return_value=mock_pw_instance)
        mock_pw_instance.__aexit__ = AsyncMock(return_value=False)
        mock_pw.return_value = mock_pw_instance

        tool = BrowserTool()
        result = await tool.browse_page("https://example.com")

    assert "html" in result
    assert "Rendered" in result["html"]
    assert result["title"] == "Test Page"
    assert result["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_browse_page_with_actions() -> None:
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>After Actions</body></html>")
    mock_page.title = AsyncMock(return_value="After Click")
    mock_page.screenshot = AsyncMock(return_value=b"fake_png_bytes")
    mock_page.url = "https://example.com/page2"
    mock_page.close = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.click = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    with patch("eip.agent.browser.async_playwright") as mock_pw:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.__aenter__ = AsyncMock(return_value=mock_pw_instance)
        mock_pw_instance.__aexit__ = AsyncMock(return_value=False)
        mock_pw.return_value = mock_pw_instance

        tool = BrowserTool()
        result = await tool.browse_page(
            "https://example.com",
            actions=[
                {"action": "wait_for_selector", "selector": ".content"},
                {"action": "click", "selector": ".load-more"},
            ],
        )

    assert "After Actions" in result["html"]
    mock_page.wait_for_selector.assert_called_once_with(".content", timeout=10000)
    mock_page.click.assert_called_once_with(".load-more")


@pytest.mark.asyncio
async def test_browse_page_error_handling() -> None:
    with patch("eip.agent.browser.async_playwright") as mock_pw:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(side_effect=Exception("Browser crashed"))
        mock_pw_instance.__aenter__ = AsyncMock(return_value=mock_pw_instance)
        mock_pw_instance.__aexit__ = AsyncMock(return_value=False)
        mock_pw.return_value = mock_pw_instance

        tool = BrowserTool()
        result = await tool.browse_page("https://example.com")

    assert "error" in result
    assert "Browser crashed" in result["error"]
```

**Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_browser.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 4: Write the implementation**

```python
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
        """Launch headless browser, navigate to URL, execute actions, return rendered HTML.

        Args:
            url: The URL to navigate to.
            actions: Optional list of actions to perform before capturing HTML.
                Each action is a dict with "action" key and relevant params.
                Supported: wait_for_selector, click, scroll, fill, wait.
            timeout: Page load timeout in milliseconds.

        Returns:
            Dict with html, title, url, screenshot_b64, or error.
        """
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

                # Execute actions if provided
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
                    "html": html[:100000],  # Truncate for LLM context
                    "title": title,
                    "url": final_url,
                    "screenshot_b64": base64.b64encode(screenshot).decode("utf-8"),
                    "content_length": len(html),
                }
        except Exception as e:
            logger.error(f"Browser error for {url}: {e}")
            return {"error": str(e), "url": url}

    async def _execute_action(self, page: Any, action_def: Dict[str, Any]) -> None:
        """Execute a single browser action."""
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
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_browser.py -v`
Expected: All 3 tests PASS.

**Step 6: Commit**

```bash
git add eip/agent/browser.py tests/test_browser.py requirements.txt
git commit -m "feat: add Playwright browser tool for JS-rendered pages"
```

---

### Task 4: Register New Tools in AgentTools

**Files:**
- Modify: `eip/agent/tools.py`
- Modify: `tests/test_agent_tools.py`

**Step 1: Write the failing tests**

Add to `tests/test_agent_tools.py`:

```python
def test_tool_definitions_include_v3_tools(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    tools = AgentTools(store=store)
    defs = tools.get_tool_definitions()
    names = [d["name"] for d in defs]
    assert "browse_page" in names
    assert "remember" in names
    assert "recall" in names


@pytest.mark.asyncio
async def test_remember_tool(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    tools = AgentTools(store=store)
    result = await tools.execute_tool(
        "remember",
        {"domain": "example.com", "key": "site_profile", "value": "Static HTML"},
    )
    assert result["status"] == "remembered"


@pytest.mark.asyncio
async def test_recall_tool(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    tools = AgentTools(store=store)
    # Remember first
    await tools.execute_tool(
        "remember",
        {"domain": "example.com", "key": "site_profile", "value": "Static HTML"},
    )
    result = await tools.execute_tool("recall", {"domain": "example.com"})
    assert len(result["entries"]) == 1
    assert result["entries"][0]["value"] == "Static HTML"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agent_tools.py -v`
Expected: FAIL — `browse_page` not in tool definitions

**Step 3: Update `eip/agent/tools.py`**

Add imports at the top:

```python
from eip.agent.memory import AgentMemory
from eip.agent.browser import BrowserTool
```

Add to `__init__`:

```python
        self.memory = AgentMemory(store=store)
        self.browser = BrowserTool()
```

Add new methods:

```python
    async def browse_page(self, url: str, actions: List = None) -> Dict:
        return await self.browser.browse_page(url, actions=actions)

    def remember(self, domain: str, key: str, value: str) -> Dict:
        self.memory.remember(domain, key, value)
        return {"status": "remembered", "domain": domain, "key": key}

    def recall(self, domain: str) -> Dict:
        entries = self.memory.recall(domain)
        return {"domain": domain, "entries": entries}
```

Add to `execute_tool`:

```python
        elif name == "browse_page":
            return await self.browse_page(**arguments)
        elif name == "remember":
            return self.remember(**arguments)
        elif name == "recall":
            return self.recall(**arguments)
```

Add tool definitions to `get_tool_definitions()`:

```python
            {
                "name": "browse_page",
                "description": (
                    "Open a URL in a headless browser to render JavaScript content. "
                    "Returns the fully rendered HTML, a screenshot, and the page title. "
                    "Use this when fetch_page returns HTML that looks empty or has "
                    "placeholder content that JavaScript would normally fill in. "
                    "Optionally provide actions like click, scroll, wait_for_selector, fill."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to open in the browser",
                        },
                        "actions": {
                            "type": "array",
                            "description": (
                                "Optional browser actions to perform before capturing HTML. "
                                "Each action: {action: 'click'|'scroll'|'wait_for_selector'|'fill'|'wait', "
                                "selector?: string, value?: string, direction?: 'bottom'|'top', seconds?: number}"
                            ),
                            "items": {"type": "object"},
                        },
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "remember",
                "description": (
                    "Store a learning about a website domain in persistent memory. "
                    "Use this to record what you've learned about a site: whether it "
                    "needs JavaScript rendering, which selectors work, what failures "
                    "occurred, rate limits, etc. This memory persists across sessions."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "The website domain (e.g., 'example.com')",
                        },
                        "key": {
                            "type": "string",
                            "description": (
                                "Memory category: site_profile, tier_1_failure, "
                                "tier_2_success, selector_pattern, failure_pattern, etc."
                            ),
                        },
                        "value": {
                            "type": "string",
                            "description": "What you learned",
                        },
                    },
                    "required": ["domain", "key", "value"],
                },
            },
            {
                "name": "recall",
                "description": (
                    "Load all persistent memories for a website domain. "
                    "Call this before starting work on a site to check if you've "
                    "worked with it before and what you learned."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "The website domain (e.g., 'example.com')",
                        },
                    },
                    "required": ["domain"],
                },
            },
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agent_tools.py -v`
Expected: All tests PASS.

**Step 5: Run full suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add eip/agent/tools.py tests/test_agent_tools.py
git commit -m "feat: register browser, remember, and recall tools in agent"
```

---

### Task 5: Updated System Prompt + Escalation Logic

**Files:**
- Modify: `eip/agent/setup_agent.py`
- Create: `tests/test_escalation.py`

**Step 1: Write the failing test**

```python
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from eip.agent.events import EventType
from eip.agent.setup_agent import SetupAgent
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


def _make_mock_provider(responses):
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=responses)
    return provider


@pytest.mark.asyncio
async def test_escalation_proposal_emitted_on_zero_items(store: JsonStore) -> None:
    """When CSS extraction finds 0 items, agent should propose escalation to Playwright."""
    provider = _make_mock_provider([
        # Agent fetches page
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "fetch_page",
                    "input": {"url": "https://spa-site.com"},
                }
            ],
            "stop_reason": "tool_use",
        },
        # Agent tries CSS extraction — gets 0 items
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_2",
                    "name": "extract_with_selectors",
                    "input": {
                        "url": "https://spa-site.com",
                        "selectors": {"item_container": ".items", "title": "h2"},
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        # Agent recognizes failure and ends turn to propose escalation
        {
            "content": [{"type": "text", "text": "CSS extraction found 0 items. This appears to be a JavaScript-rendered site. I recommend trying Playwright browser rendering."}],
            "stop_reason": "end_turn",
        },
    ])

    agent = SetupAgent(provider=provider, store=store)
    agent.tools.fetch_page = AsyncMock(
        return_value={"html": "<html><div id='app'></div></html>", "status_code": 200, "url": "https://spa-site.com"}
    )
    agent.tools.extract_with_selectors = AsyncMock(
        return_value={"items": [], "count": 0}
    )

    events = []
    input_queue = asyncio.Queue()

    async for event in agent.run_streaming("Monitor spa-site.com", input_queue):
        events.append(event)
        if event.type == EventType.PROPOSAL:
            break

    event_types = [e.type for e in events]
    assert EventType.STATUS in event_types
    assert EventType.EXTRACTION_TEST in event_types
    # The proposal event should be emitted (the agent describes the escalation)
    assert EventType.PROPOSAL in event_types


@pytest.mark.asyncio
async def test_memory_loaded_into_system_prompt(store: JsonStore) -> None:
    """When agent has memory for a domain, it should be included in the prompt."""
    # Pre-populate memory
    from eip.agent.memory import AgentMemory
    memory = AgentMemory(store=store)
    memory.remember("example.com", "site_profile", "React SPA, needs Playwright")

    provider = _make_mock_provider([
        {
            "content": [{"type": "text", "text": "Based on my memory, I know this is a React SPA."}],
            "stop_reason": "end_turn",
        },
    ])

    agent = SetupAgent(provider=provider, store=store)
    input_queue = asyncio.Queue()

    events = []
    async for event in agent.run_streaming("Monitor https://example.com/news", input_queue):
        events.append(event)
        if event.type == EventType.PROPOSAL:
            break

    # Verify the system prompt included memory
    call_args = provider.complete.call_args_list[0]
    system = call_args.kwargs.get("system") or call_args[1].get("system") or call_args[0][0]
    assert "React SPA" in system or "memory" in system.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_escalation.py -v`
Expected: FAIL — memory not loaded into system prompt

**Step 3: Update `eip/agent/setup_agent.py`**

Add import:

```python
from eip.agent.memory import AgentMemory
```

Update `SYSTEM_PROMPT` to the V3 version:

```python
SYSTEM_PROMPT = """\
You are an AI agent that sets up web monitoring jobs. The user will describe what external \
information they want to monitor. Your job is to:

1. First, call recall() to check if you have any prior knowledge about this site's domain.
2. Fetch the target web page to understand its structure.
3. Identify the right CSS selectors to extract the information the user wants.
4. Test your selectors by calling extract_with_selectors to verify they work.
5. If the extraction looks good, save the job using save_job.
6. If CSS extraction returns 0 items or the page appears to use JavaScript rendering, \
   explain the issue to the user and recommend trying browse_page (Playwright) instead.
7. If Playwright is approved and works, save the job. Remember what you learned about this site.
8. Always call remember() to record what you learned about a site — whether something worked \
   or failed, what tier was needed, what selectors were effective.

Strategy tiers (try in order, get user approval before escalating):
- Tier 1: fetch_page + extract_with_selectors (cheapest, for static HTML)
- Tier 2: browse_page + extract_with_selectors (medium cost, for JS-rendered sites)
- Tier 3: Computer use (most expensive, for complex interactions — tell the user if needed)

When something fails, be specific about WHY it failed and WHAT the user can do about it. \
Never just say "it didn't work". Give concrete next steps.

For the schedule, choose an appropriate cron expression based on the content type:
- News/media releases: every 4 hours (0 */4 * * *)
- Market data: every 15 minutes (*/15 * * * *)
- Research/publications: daily (0 9 * * *)
- General monitoring: hourly (0 * * * *)
"""
```

Update `run_streaming()` to build the system prompt with memory. At the start of `run_streaming()`, before the `for turn` loop, add:

```python
        # Load agent memory for the domain
        memory = AgentMemory(store=self.store)
        domain = ""
        # Try to extract domain from user request
        import re
        url_match = re.search(r'https?://([^/\s]+)', user_request)
        if url_match:
            domain = url_match.group(1)

        system = SYSTEM_PROMPT
        if domain:
            memory_text = memory.recall_as_text(domain)
            if memory_text:
                system += f"\n\nYou have prior knowledge about {domain}:\n{memory_text}"
```

Then use `system` instead of `SYSTEM_PROMPT` in the `provider.complete()` call.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_escalation.py -v`
Expected: All 2 tests PASS.

**Step 5: Run full suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add eip/agent/setup_agent.py tests/test_escalation.py
git commit -m "feat: update agent system prompt with tiered strategy and memory loading"
```

---

### Task 6: Tier-Aware Runner

**Files:**
- Modify: `eip/runner/automated_runner.py`
- Modify: `tests/test_automated_runner.py`

**Step 1: Write the failing test**

Add to `tests/test_automated_runner.py`:

```python
@pytest.mark.asyncio
async def test_run_job_playwright_tier(tmp_path: Path) -> None:
    """When config has tier=playwright, runner should use browser tool."""
    store = JsonStore(base_dir=tmp_path)
    store.save("jobs", "job_pw", {
        "id": "job_pw",
        "name": "JS Site",
        "target_url": "https://spa-site.com",
        "status": "active",
    })
    store.save("configs", "job_pw", {
        "job_id": "job_pw",
        "strategy": "css_selector",
        "tier": "playwright",
        "selectors": {"item_container": ".item", "title": "h2"},
        "base_url": "https://spa-site.com",
        "playwright_actions": [
            {"action": "wait_for_selector", "selector": ".item"},
        ],
    })

    with patch("eip.runner.automated_runner.BrowserTool") as MockBT:
        mock_bt = AsyncMock()
        mock_bt.browse_page = AsyncMock(return_value={
            "html": '<div class="item"><h2>Article 1</h2></div>',
            "title": "SPA Site",
            "url": "https://spa-site.com",
        })
        MockBT.return_value = mock_bt

        result = await run_job("job_pw", store)

    assert result["success"] is True
    assert result["items_total"] == 1
    mock_bt.browse_page.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_automated_runner.py::test_run_job_playwright_tier -v`
Expected: FAIL

**Step 3: Update `eip/runner/automated_runner.py`**

Add import:

```python
from eip.agent.browser import BrowserTool
```

In the `run_job` function, after loading config, add tier-aware fetching. Replace the HTTP fetch block with:

```python
    tier = config.get("tier", "css")

    try:
        if tier == "playwright":
            browser = BrowserTool()
            actions = config.get("playwright_actions")
            browser_result = await browser.browse_page(target_url, actions=actions)
            if "error" in browser_result:
                return {"success": False, "error": f"Browser error: {browser_result['error']}", "run_id": run_id}
            html = browser_result["html"]
        else:
            # Default: HTTP fetch (tier css)
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(target_url)
                response.raise_for_status()
            html = response.text
    except httpx.HTTPError as e:
        return {"success": False, "error": f"HTTP error: {e}", "run_id": run_id}
```

Then use `html` instead of `response.text` in the `extract_items` call:

```python
    items = extract_items(html, config)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_automated_runner.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add eip/runner/automated_runner.py tests/test_automated_runner.py
git commit -m "feat: add tier-aware runner with Playwright support"
```

---

### Task 7: Runner Retry with Backoff

**Files:**
- Modify: `eip/runner/automated_runner.py`
- Create: `tests/test_runner_retry.py`

**Step 1: Write the failing test**

```python
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from eip.runner.automated_runner import run_job
from eip.store.json_store import JsonStore


@pytest.fixture
def store_with_job(tmp_path: Path) -> JsonStore:
    store = JsonStore(base_dir=tmp_path)
    store.save("jobs", "job_retry", {
        "id": "job_retry",
        "name": "Retry Test",
        "target_url": "https://flaky-site.com",
        "status": "active",
    })
    store.save("configs", "job_retry", {
        "job_id": "job_retry",
        "strategy": "css_selector",
        "selectors": {"item_container": ".item", "title": "h2"},
        "base_url": "https://flaky-site.com",
    })
    return store


@pytest.mark.asyncio
async def test_retry_on_transient_failure(store_with_job: JsonStore) -> None:
    """Runner should retry up to 3 times on 5xx errors."""
    mock_response = AsyncMock()
    mock_response.text = '<div class="item"><h2>Article</h2></div>'
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None

    mock_client = AsyncMock()
    # Fail twice, succeed on third
    mock_client.get = AsyncMock(
        side_effect=[
            httpx.HTTPStatusError("500", request=None, response=AsyncMock(status_code=500)),
            httpx.HTTPStatusError("503", request=None, response=AsyncMock(status_code=503)),
            mock_response,
        ]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("eip.runner.automated_runner.httpx.AsyncClient", return_value=mock_client):
        with patch("eip.runner.automated_runner.RETRY_DELAYS", [0, 0, 0]):
            result = await run_job("job_retry", store_with_job)

    assert result["success"] is True
    assert mock_client.get.call_count == 3


@pytest.mark.asyncio
async def test_retry_exhausted(store_with_job: JsonStore) -> None:
    """After 3 failed retries, runner should return failure."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=httpx.HTTPStatusError("500", request=None, response=AsyncMock(status_code=500))
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("eip.runner.automated_runner.httpx.AsyncClient", return_value=mock_client):
        with patch("eip.runner.automated_runner.RETRY_DELAYS", [0, 0, 0]):
            result = await run_job("job_retry", store_with_job)

    assert result["success"] is False
    assert "HTTP error" in result["error"]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_runner_retry.py -v`
Expected: FAIL — no retry logic, no `RETRY_DELAYS`

**Step 3: Update `eip/runner/automated_runner.py`**

Add at module level:

```python
import asyncio as _asyncio
import logging

logger = logging.getLogger(__name__)

RETRY_DELAYS = [1, 4, 16]  # Exponential backoff: 1s, 4s, 16s
```

Replace the HTTP fetch try/except block with retry logic:

```python
    try:
        if tier == "playwright":
            browser = BrowserTool()
            actions = config.get("playwright_actions")
            browser_result = await browser.browse_page(target_url, actions=actions)
            if "error" in browser_result:
                return {"success": False, "error": f"Browser error: {browser_result['error']}", "run_id": run_id}
            html = browser_result["html"]
        else:
            html = None
            last_error = None
            for attempt, delay in enumerate(RETRY_DELAYS):
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                        response = await client.get(target_url)
                        response.raise_for_status()
                    html = response.text
                    break
                except httpx.HTTPError as e:
                    last_error = e
                    logger.warning(f"Attempt {attempt + 1} failed for {target_url}: {e}")
                    if delay > 0:
                        await _asyncio.sleep(delay)

            if html is None:
                return {"success": False, "error": f"HTTP error: {last_error}", "run_id": run_id}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}", "run_id": run_id}
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_runner_retry.py -v`
Expected: All 2 tests PASS.

**Step 5: Run full suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add eip/runner/automated_runner.py tests/test_runner_retry.py
git commit -m "feat: add retry with exponential backoff to runner"
```

---

### Task 8: Health Monitoring

**Files:**
- Modify: `eip/runner/automated_runner.py`
- Create: `tests/test_health.py`

**Step 1: Write the failing test**

```python
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from eip.runner.automated_runner import run_job
from eip.store.json_store import JsonStore


@pytest.fixture
def store_with_failing_job(tmp_path: Path) -> JsonStore:
    store = JsonStore(base_dir=tmp_path)
    store.save("jobs", "job_health", {
        "id": "job_health",
        "name": "Failing Job",
        "target_url": "https://changed-site.com",
        "status": "active",
        "consecutive_failures": 2,  # Already failed twice
    })
    store.save("configs", "job_health", {
        "job_id": "job_health",
        "strategy": "css_selector",
        "selectors": {"item_container": ".old-class", "title": "h2"},
        "base_url": "https://changed-site.com",
    })
    return store


@pytest.mark.asyncio
async def test_consecutive_failures_tracked(store_with_failing_job: JsonStore) -> None:
    """When extraction returns 0 items, consecutive_failures should increment."""
    mock_response = AsyncMock()
    mock_response.text = "<html><body>No matching elements</body></html>"
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("eip.runner.automated_runner.httpx.AsyncClient", return_value=mock_client):
        with patch("eip.runner.automated_runner.RETRY_DELAYS", [0]):
            result = await run_job("job_health", store_with_failing_job)

    assert result["success"] is False
    # Check that consecutive_failures was incremented to 3
    job = store_with_failing_job.load("jobs", "job_health")
    assert job["consecutive_failures"] == 3
    assert job["status"] == "needs_reagent"


@pytest.mark.asyncio
async def test_consecutive_failures_reset_on_success(tmp_path: Path) -> None:
    """When extraction succeeds, consecutive_failures should reset to 0."""
    store = JsonStore(base_dir=tmp_path)
    store.save("jobs", "job_ok", {
        "id": "job_ok",
        "name": "Recovering Job",
        "target_url": "https://ok-site.com",
        "status": "active",
        "consecutive_failures": 2,
    })
    store.save("configs", "job_ok", {
        "job_id": "job_ok",
        "strategy": "css_selector",
        "selectors": {"item_container": ".item", "title": "h2"},
        "base_url": "https://ok-site.com",
    })

    mock_response = AsyncMock()
    mock_response.text = '<div class="item"><h2>Article</h2></div>'
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("eip.runner.automated_runner.httpx.AsyncClient", return_value=mock_client):
        with patch("eip.runner.automated_runner.RETRY_DELAYS", [0]):
            result = await run_job("job_ok", store)

    assert result["success"] is True
    job = store.load("jobs", "job_ok")
    assert job.get("consecutive_failures", 0) == 0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health.py -v`
Expected: FAIL — no `consecutive_failures` tracking

**Step 3: Update `eip/runner/automated_runner.py`**

In the `run_job` function, after the `if not items:` block, update to track consecutive failures:

```python
    if not items:
        failures = job.get("consecutive_failures", 0) + 1
        job["consecutive_failures"] = failures
        job["status"] = "needs_reagent"
        store.save("jobs", job_id, job)
        return {
            "success": False,
            "error": "Extraction returned no items — site may have changed",
            "run_id": run_id,
            "job_id": job_id,
            "consecutive_failures": failures,
        }
```

Before the `result = {` block (on successful extraction), add:

```python
    # Reset failure counter on success
    if job.get("consecutive_failures", 0) > 0:
        job["consecutive_failures"] = 0
        store.save("jobs", job_id, job)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_health.py -v`
Expected: All 2 tests PASS.

**Step 5: Run full suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add eip/runner/automated_runner.py tests/test_health.py
git commit -m "feat: add health monitoring with consecutive failure tracking"
```

---

### Task 9: Frontend — New Types + SSE Events

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/sse.ts`

**Step 1: Update `frontend/src/api/types.ts`**

Add new fields to `AgentEvent`:

```typescript
export interface AgentEvent {
  type: string;
  message?: string;
  url?: string;
  title?: string;
  content_length?: number;
  selectors?: Record<string, string>;
  sample_items?: Record<string, unknown>[];
  count?: number;
  job?: Record<string, unknown>;
  config?: Record<string, unknown>;
  sample_data?: Record<string, unknown>[];
  status?: string;
  // V3 additions
  current_tier?: string;
  proposed_tier?: string;
  failure_code?: string;
  user_message?: string;
  next_steps?: NextStep[];
  technical_details?: Record<string, unknown>;
}

export interface NextStep {
  type: string;
  label: string;
}
```

Add `tier` to `ExtractionConfig`:

```typescript
export interface ExtractionConfig {
  job_id: string;
  strategy: string;
  tier?: string;
  selectors: Record<string, string>;
  base_url: string;
  playwright_actions?: Record<string, unknown>[];
}
```

Add `consecutive_failures` to `Job`:

```typescript
export interface Job {
  id: string;
  name: string;
  target_url: string;
  schedule: string;
  status: string;
  created_at: string;
  consecutive_failures?: number;
}
```

**Step 2: Update `frontend/src/api/sse.ts`**

Add `escalation_proposal` and `failure` to the event types list:

```typescript
  const eventTypes = [
    'status',
    'page_fetched',
    'thinking',
    'extraction_test',
    'proposal',
    'done',
    'error',
    'escalation_proposal',
    'failure',
  ];
```

**Step 3: Verify TypeScript compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`

**Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/sse.ts
git commit -m "feat: add V3 types for escalation, failure events, and tier support"
```

---

### Task 10: Frontend — Failure Card Component

**Files:**
- Create: `frontend/src/components/FailureCard.tsx`

**Step 1: Create the component**

```tsx
import type { AgentEvent, NextStep } from '../api/types';
import { useState } from 'react';

interface FailureCardProps {
  event: AgentEvent;
  onAction: (step: NextStep) => void;
}

export default function FailureCard({ event, onAction }: FailureCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
          <span className="text-red-600 text-sm font-bold">!</span>
        </div>
        <div className="flex-1">
          <p className="text-red-800 font-medium">{event.user_message || event.message}</p>

          {event.next_steps && event.next_steps.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {event.next_steps.map((step, i) => (
                <button
                  key={i}
                  onClick={() => onAction(step)}
                  className="px-3 py-1.5 bg-white border border-red-200 rounded-lg text-sm text-red-700 hover:bg-red-100 font-medium"
                >
                  {step.label}
                </button>
              ))}
            </div>
          )}

          {event.technical_details && (
            <div className="mt-3">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="text-xs text-red-600 hover:text-red-700 underline"
              >
                {showDetails ? 'Hide technical details' : 'Show technical details'}
              </button>
              {showDetails && (
                <pre className="mt-2 p-3 bg-white rounded border text-xs text-gray-700 overflow-x-auto">
                  {JSON.stringify(event.technical_details, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`

**Step 3: Commit**

```bash
git add frontend/src/components/FailureCard.tsx
git commit -m "feat: add FailureCard component with layered error display"
```

---

### Task 11: Frontend — Updated AgentFeed + Escalation UI

**Files:**
- Modify: `frontend/src/components/AgentFeed.tsx`
- Modify: `frontend/src/pages/JobCreate.tsx`

**Step 1: Update `frontend/src/components/AgentFeed.tsx`**

Add new event renderers for `escalation_proposal` and `failure`:

```tsx
import { useState } from 'react';
import type { AgentEvent, NextStep } from '../api/types';

interface AgentFeedProps {
  events: AgentEvent[];
  onEscalationApprove?: (tier: string) => void;
  onEscalationReject?: () => void;
  onFailureAction?: (step: NextStep) => void;
}

export default function AgentFeed({ events, onEscalationApprove, onEscalationReject, onFailureAction }: AgentFeedProps) {
  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {events.map((event, i) => (
        <FeedItem
          key={i}
          event={event}
          onEscalationApprove={onEscalationApprove}
          onEscalationReject={onEscalationReject}
          onFailureAction={onFailureAction}
        />
      ))}
    </div>
  );
}

function FeedItem({
  event,
  onEscalationApprove,
  onEscalationReject,
  onFailureAction,
}: {
  event: AgentEvent;
  onEscalationApprove?: (tier: string) => void;
  onEscalationReject?: () => void;
  onFailureAction?: (step: NextStep) => void;
}) {
  const [showDetails, setShowDetails] = useState(false);

  switch (event.type) {
    case 'status':
      return (
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
          {event.message}
        </div>
      );
    case 'page_fetched':
      return (
        <div className="text-sm text-green-700 bg-green-50 p-2 rounded">
          Fetched: {event.url} ({event.content_length?.toLocaleString()} chars)
        </div>
      );
    case 'thinking':
      return (
        <div className="text-sm text-purple-700 bg-purple-50 p-2 rounded italic">
          {event.message}
        </div>
      );
    case 'extraction_test':
      return (
        <div className="text-sm bg-yellow-50 p-2 rounded">
          <span className="font-medium text-yellow-800">
            Extraction test: {event.count} items found
          </span>
        </div>
      );
    case 'escalation_proposal':
      return (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <p className="text-sm text-amber-800 font-medium mb-2">
            {event.message}
          </p>
          <p className="text-xs text-amber-600 mb-3">
            Current: {event.current_tier} → Proposed: {event.proposed_tier}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => onEscalationApprove?.(event.proposed_tier || 'playwright')}
              className="px-3 py-1.5 bg-amber-600 text-white rounded text-sm font-medium hover:bg-amber-700"
            >
              Approve {event.proposed_tier}
            </button>
            <button
              onClick={() => onEscalationReject?.()}
              className="px-3 py-1.5 bg-white border border-amber-300 text-amber-700 rounded text-sm hover:bg-amber-50"
            >
              Skip
            </button>
          </div>
        </div>
      );
    case 'failure':
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 font-medium">{event.user_message || event.message}</p>
          {event.next_steps && event.next_steps.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {event.next_steps.map((step, i) => (
                <button
                  key={i}
                  onClick={() => onFailureAction?.(step)}
                  className="px-3 py-1.5 bg-white border border-red-200 rounded text-sm text-red-700 hover:bg-red-100"
                >
                  {step.label}
                </button>
              ))}
            </div>
          )}
          {event.technical_details && (
            <div className="mt-2">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="text-xs text-red-600 underline"
              >
                {showDetails ? 'Hide details' : 'Technical details'}
              </button>
              {showDetails && (
                <pre className="mt-1 p-2 bg-white rounded border text-xs overflow-x-auto">
                  {JSON.stringify(event.technical_details, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      );
    case 'error':
      return (
        <div className="text-sm text-red-700 bg-red-50 p-2 rounded">
          Error: {event.message}
        </div>
      );
    default:
      return null;
  }
}
```

**Step 2: Update `frontend/src/pages/JobCreate.tsx`**

Add escalation and failure action handlers. Add new callbacks passed to `AgentFeed`:

After the existing `handleRefine` callback, add:

```tsx
  const handleEscalationApprove = useCallback(
    async (tier: string) => {
      if (!sessionId) return;
      try {
        await api.sendMessage(sessionId, `Approved. Please try using ${tier} to extract the data.`);
        setPhase('running');
      } catch {
        setError('Failed to approve escalation');
      }
    },
    [sessionId],
  );

  const handleEscalationReject = useCallback(async () => {
    if (!sessionId) return;
    try {
      await api.rejectSession(sessionId);
      setPhase('input');
      setSessionId(null);
      setEvents([]);
      setProposal(null);
    } catch {
      setError('Failed to reject');
    }
  }, [sessionId]);

  const handleFailureAction = useCallback(
    async (step: { type: string; label: string }) => {
      if (!sessionId) return;
      if (step.type === 'retry') {
        // Re-submit the same prompt
        handleSubmit();
      } else if (step.type === 'change_url') {
        setPhase('input');
        setEvents([]);
      } else if (step.type === 'escalate') {
        await api.sendMessage(sessionId, 'Please try the next extraction tier.');
        setPhase('running');
      } else {
        // For other types, send as a message
        await api.sendMessage(sessionId, `User action: ${step.label}`);
        setPhase('running');
      }
    },
    [sessionId, handleSubmit],
  );
```

Update the `AgentFeed` usage to pass the new props:

```tsx
          <AgentFeed
            events={events}
            onEscalationApprove={handleEscalationApprove}
            onEscalationReject={handleEscalationReject}
            onFailureAction={handleFailureAction}
          />
```

Also update the SSE handler to handle `escalation_proposal` and `failure` events:

```tsx
          if (event.type === 'proposal') {
            setProposal(event);
            setPhase('proposal');
          } else if (event.type === 'done') {
            setPhase('done');
          } else if (event.type === 'error') {
            setError(event.message || 'An error occurred');
            setPhase('input');
          } else if (event.type === 'failure') {
            // Failure stays visible in feed — don't change phase
          }
```

**Step 3: Verify TypeScript compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`

**Step 4: Commit**

```bash
git add frontend/src/components/AgentFeed.tsx frontend/src/pages/JobCreate.tsx
git commit -m "feat: add escalation proposal and failure action handling to UI"
```

---

### Task 12: Frontend — Job Health Indicator

**Files:**
- Modify: `frontend/src/pages/JobDetail.tsx`
- Modify: `frontend/src/components/StatusBadge.tsx`

**Step 1: Update `frontend/src/components/StatusBadge.tsx`**

Add `needs_reagent` status color:

```typescript
const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  paused: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-gray-100 text-gray-800',
  needs_reagent: 'bg-orange-100 text-orange-800',
};
```

**Step 2: Update `frontend/src/pages/JobDetail.tsx`**

Add a health indicator and re-discover button. After the Job Metadata card and before the Actions div, add:

```tsx
      {/* Health Indicator */}
      {job.consecutive_failures && job.consecutive_failures > 0 && (
        <div className={`rounded-lg p-4 mb-6 ${
          job.consecutive_failures >= 3
            ? 'bg-red-50 border border-red-200'
            : 'bg-yellow-50 border border-yellow-200'
        }`}>
          <div className="flex justify-between items-center">
            <div>
              <p className={`font-medium ${
                job.consecutive_failures >= 3 ? 'text-red-800' : 'text-yellow-800'
              }`}>
                {job.consecutive_failures >= 3
                  ? 'Extraction is failing — site may have changed'
                  : `${job.consecutive_failures} consecutive extraction issue(s)`
                }
              </p>
              <p className="text-sm text-gray-600 mt-1">
                {job.consecutive_failures >= 3
                  ? 'The agent needs to re-discover how to extract data from this site.'
                  : 'The agent will attempt re-discovery if failures continue.'
                }
              </p>
            </div>
            {job.consecutive_failures >= 3 && (
              <button
                onClick={() => navigate(`/jobs/new?rediscover=${id}`)}
                className="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700"
              >
                Re-discover
              </button>
            )}
          </div>
        </div>
      )}
```

Add `tier` display to the Job Metadata section, after the `Strategy` field:

```tsx
              {config.tier && (
                <div>
                  <dt className="text-gray-500">Extraction Tier</dt>
                  <dd className="text-gray-900 font-medium capitalize">{config.tier}</dd>
                </div>
              )}
```

**Step 3: Verify TypeScript compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`

**Step 4: Commit**

```bash
git add frontend/src/pages/JobDetail.tsx frontend/src/components/StatusBadge.tsx
git commit -m "feat: add job health indicator and re-discover button"
```

---

### Task 13: Final Integration Verification

**Files:** None (verification only)

**Step 1: Run full backend test suite**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 2: Verify frontend compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`
Expected: No errors.

**Step 3: Start backend and frontend**

```bash
# Terminal 1
cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && export $(cat .env | xargs) && source .venv/bin/activate && uvicorn eip.main:app --reload

# Terminal 2
cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npm run dev
```

**Step 4: Verify end-to-end**

Open http://localhost:5173 and verify:
- Dashboard loads
- "New Monitoring Job" navigates to creation page
- Submitting a prompt starts SSE stream
- Agent events render in the feed
- The UI handles the full flow

**Step 5: Commit any final fixes**

If anything needed fixing during integration, commit those changes.
