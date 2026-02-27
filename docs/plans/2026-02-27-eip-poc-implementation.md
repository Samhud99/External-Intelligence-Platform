# EIP Proof of Concept Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working proof of concept that demonstrates the two-phase EIP loop: AI agent discovers extraction strategy from natural language, automated runner executes it on schedule, results stored as JSON.

**Architecture:** FastAPI REST API with a pluggable AI agent layer (Claude first) for job setup, a lightweight automated runner using httpx + BeautifulSoup for scheduled extraction, file-based JSON storage, and APScheduler for cron-based execution.

**Tech Stack:** Python 3.12+, FastAPI, httpx, BeautifulSoup4, APScheduler, Anthropic SDK, pytest

---

### Task 1: Project Scaffolding

**Files:**
- Create: `eip/config.py`
- Create: `eip/__init__.py`
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `eip/api/__init__.py`
- Create: `eip/agent/__init__.py`
- Create: `eip/runner/__init__.py`
- Create: `eip/store/__init__.py`
- Create: `eip/scheduler/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "eip"
version = "0.1.0"
description = "External Intelligence Platform - Proof of Concept"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 2: Create requirements.txt**

```
fastapi>=0.115.0
uvicorn>=0.32.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
apscheduler>=3.10.0
anthropic>=0.40.0
pydantic>=2.10.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
pytest-httpx>=0.34.0
```

**Step 3: Create eip/config.py**

```python
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    data_dir: Path = Path("data")
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-6"
    log_level: str = "INFO"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def configs_dir(self) -> Path:
        return self.data_dir / "configs"

    @property
    def results_dir(self) -> Path:
        return self.data_dir / "results"

    def ensure_dirs(self) -> None:
        for d in [self.jobs_dir, self.configs_dir, self.results_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
```

**Step 4: Create empty `__init__.py` files**

Create empty files at:
- `eip/__init__.py`
- `eip/api/__init__.py`
- `eip/agent/__init__.py`
- `eip/runner/__init__.py`
- `eip/store/__init__.py`
- `eip/scheduler/__init__.py`
- `tests/__init__.py`

**Step 5: Create virtual environment and install dependencies**

Run: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
Expected: All packages install successfully.

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: scaffold project structure and dependencies"
```

---

### Task 2: JSON Store Layer

**Files:**
- Create: `eip/store/json_store.py`
- Create: `tests/test_store.py`

**Step 1: Write the failing tests**

```python
import json
from pathlib import Path

import pytest

from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


def test_save_and_load(store: JsonStore) -> None:
    data = {"id": "abc", "name": "test"}
    store.save("things", "abc", data)
    loaded = store.load("things", "abc")
    assert loaded == data


def test_load_missing_returns_none(store: JsonStore) -> None:
    assert store.load("things", "missing") is None


def test_list_collection(store: JsonStore) -> None:
    store.save("things", "a", {"id": "a"})
    store.save("things", "b", {"id": "b"})
    items = store.list("things")
    ids = {item["id"] for item in items}
    assert ids == {"a", "b"}


def test_list_empty_collection(store: JsonStore) -> None:
    assert store.list("things") == []


def test_delete(store: JsonStore) -> None:
    store.save("things", "abc", {"id": "abc"})
    store.delete("things", "abc")
    assert store.load("things", "abc") is None


def test_delete_missing_does_not_raise(store: JsonStore) -> None:
    store.delete("things", "nonexistent")  # should not raise
```

**Step 2: Run tests to verify they fail**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && python -m pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eip.store.json_store'`

**Step 3: Write the implementation**

```python
import json
from pathlib import Path


class JsonStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def _collection_dir(self, collection: str) -> Path:
        d = self.base_dir / collection
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, collection: str, item_id: str, data: dict) -> None:
        path = self._collection_dir(collection) / f"{item_id}.json"
        path.write_text(json.dumps(data, indent=2, default=str))

    def load(self, collection: str, item_id: str) -> dict | None:
        path = self._collection_dir(collection) / f"{item_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list(self, collection: str) -> list[dict]:
        d = self._collection_dir(collection)
        items = []
        for path in sorted(d.glob("*.json")):
            items.append(json.loads(path.read_text()))
        return items

    def delete(self, collection: str, item_id: str) -> None:
        path = self._collection_dir(collection) / f"{item_id}.json"
        if path.exists():
            path.unlink()
```

**Step 4: Run tests to verify they pass**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && python -m pytest tests/test_store.py -v`
Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
git add eip/store/json_store.py tests/test_store.py
git commit -m "feat: add file-based JSON store layer"
```

---

### Task 3: Automated Runner — Extraction Engine

**Files:**
- Create: `eip/runner/automated_runner.py`
- Create: `tests/test_runner.py`

**Step 1: Write the failing tests**

```python
import pytest

from eip.runner.automated_runner import extract_items


SAMPLE_HTML = """
<html><body>
<div class="articles">
  <div class="article">
    <h2><a href="/news/first-article">First Article</a></h2>
    <span class="date">2026-02-27</span>
    <p class="summary">Summary of the first article.</p>
  </div>
  <div class="article">
    <h2><a href="/news/second-article">Second Article</a></h2>
    <span class="date">2026-02-26</span>
    <p class="summary">Summary of the second article.</p>
  </div>
</div>
</body></html>
"""


def test_extract_items_with_css_selectors() -> None:
    config = {
        "strategy": "css_selector",
        "selectors": {
            "item_container": ".articles .article",
            "title": "h2 a",
            "date": ".date",
            "summary": ".summary",
            "link": "h2 a@href",
        },
        "base_url": "https://example.com",
    }
    items = extract_items(SAMPLE_HTML, config)
    assert len(items) == 2
    assert items[0]["title"] == "First Article"
    assert items[0]["date"] == "2026-02-27"
    assert items[0]["summary"] == "Summary of the first article."
    assert items[0]["url"] == "https://example.com/news/first-article"


def test_extract_items_absolute_url_preserved() -> None:
    html = """
    <div class="items"><div class="item">
      <a href="https://other.com/page">Link</a>
    </div></div>
    """
    config = {
        "strategy": "css_selector",
        "selectors": {
            "item_container": ".items .item",
            "title": "a",
            "link": "a@href",
        },
        "base_url": "https://example.com",
    }
    items = extract_items(html, config)
    assert items[0]["url"] == "https://other.com/page"


def test_extract_items_empty_html_returns_empty() -> None:
    config = {
        "strategy": "css_selector",
        "selectors": {
            "item_container": ".nonexistent",
            "title": "h2",
        },
        "base_url": "https://example.com",
    }
    items = extract_items("<html><body></body></html>", config)
    assert items == []
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def extract_items(html: str, config: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = config.get("selectors", {})
    base_url = config.get("base_url", "")

    container_selector = selectors.get("item_container", "")
    if not container_selector:
        return []

    containers = soup.select(container_selector)
    items = []

    for container in containers:
        item: dict = {}
        for field, selector in selectors.items():
            if field == "item_container":
                continue

            # Handle @attr syntax for extracting attributes (e.g. "a@href")
            attr = None
            if "@" in selector:
                selector, attr = selector.rsplit("@", 1)

            el = container.select_one(selector)
            if el is None:
                continue

            if attr:
                value = el.get(attr, "")
            else:
                value = el.get_text(strip=True)

            # Resolve relative URLs for link fields
            if field == "link" and value and not value.startswith(("http://", "https://")):
                value = urljoin(base_url, value)

            # Store link fields as "url" in output
            if field == "link":
                item["url"] = value
            else:
                item[field] = value

        if item:
            items.append(item)

    return items
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_runner.py -v`
Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add eip/runner/automated_runner.py tests/test_runner.py
git commit -m "feat: add CSS selector extraction engine"
```

---

### Task 4: Change Detection

**Files:**
- Create: `eip/runner/change_detector.py`
- Create: `tests/test_change_detector.py`

**Step 1: Write the failing tests**

```python
from eip.runner.change_detector import detect_changes


def test_all_new_when_no_previous() -> None:
    current = [
        {"title": "Article A", "url": "https://example.com/a"},
        {"title": "Article B", "url": "https://example.com/b"},
    ]
    result = detect_changes(current, previous=None)
    assert all(item["is_new"] for item in result)
    assert len(result) == 2


def test_detect_new_items() -> None:
    previous = [
        {"title": "Article A", "url": "https://example.com/a"},
    ]
    current = [
        {"title": "Article A", "url": "https://example.com/a"},
        {"title": "Article B", "url": "https://example.com/b"},
    ]
    result = detect_changes(current, previous)
    new_items = [i for i in result if i["is_new"]]
    old_items = [i for i in result if not i["is_new"]]
    assert len(new_items) == 1
    assert new_items[0]["title"] == "Article B"
    assert len(old_items) == 1


def test_no_changes() -> None:
    items = [{"title": "A", "url": "https://example.com/a"}]
    result = detect_changes(items, items)
    assert not any(item["is_new"] for item in result)


def test_uses_url_for_comparison_when_available() -> None:
    previous = [{"title": "Old Title", "url": "https://example.com/a"}]
    current = [{"title": "New Title", "url": "https://example.com/a"}]
    result = detect_changes(current, previous)
    assert not result[0]["is_new"]


def test_falls_back_to_title_hash() -> None:
    previous = [{"title": "Article A"}]
    current = [{"title": "Article A"}, {"title": "Article B"}]
    result = detect_changes(current, previous)
    new_items = [i for i in result if i["is_new"]]
    assert len(new_items) == 1
    assert new_items[0]["title"] == "Article B"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_change_detector.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
import hashlib


def _item_key(item: dict) -> str:
    if "url" in item and item["url"]:
        return item["url"]
    title = item.get("title", "")
    return hashlib.sha256(title.encode()).hexdigest()


def detect_changes(
    current: list[dict], previous: list[dict] | None
) -> list[dict]:
    if previous is None:
        return [{**item, "is_new": True} for item in current]

    previous_keys = {_item_key(item) for item in previous}
    result = []
    for item in current:
        key = _item_key(item)
        result.append({**item, "is_new": key not in previous_keys})
    return result
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_change_detector.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add eip/runner/change_detector.py tests/test_change_detector.py
git commit -m "feat: add change detection for extracted items"
```

---

### Task 5: Full Automated Runner (Fetch + Extract + Detect + Store)

**Files:**
- Modify: `eip/runner/automated_runner.py`
- Create: `tests/test_automated_runner.py`

**Step 1: Write the failing tests**

These tests use `pytest-httpx` to mock HTTP calls.

```python
import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from eip.runner.automated_runner import run_job
from eip.store.json_store import JsonStore


SAMPLE_HTML = """
<html><body>
<div class="articles">
  <div class="article">
    <h2><a href="/news/first">First</a></h2>
    <span class="date">2026-02-27</span>
  </div>
</div>
</body></html>
"""


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def job() -> dict:
    return {
        "id": "job_test",
        "name": "Test Job",
        "target_url": "https://example.com/articles",
        "schedule": "0 * * * *",
        "status": "active",
    }


@pytest.fixture
def config() -> dict:
    return {
        "job_id": "job_test",
        "strategy": "css_selector",
        "selectors": {
            "item_container": ".articles .article",
            "title": "h2 a",
            "date": ".date",
            "link": "h2 a@href",
        },
        "base_url": "https://example.com",
    }


async def test_run_job_success(
    httpx_mock: HTTPXMock, store: JsonStore, job: dict, config: dict
) -> None:
    httpx_mock.add_response(url="https://example.com/articles", text=SAMPLE_HTML)
    store.save("jobs", "job_test", job)
    store.save("configs", "job_test", config)

    result = await run_job("job_test", store)

    assert result["success"] is True
    assert result["items_total"] == 1
    assert result["items"][0]["title"] == "First"
    # Result should be persisted
    results = store.list("results/job_test")
    assert len(results) == 1


async def test_run_job_marks_needs_reagent_on_empty_extraction(
    httpx_mock: HTTPXMock, store: JsonStore, job: dict, config: dict
) -> None:
    httpx_mock.add_response(
        url="https://example.com/articles",
        text="<html><body>nothing here</body></html>",
    )
    store.save("jobs", "job_test", job)
    store.save("configs", "job_test", config)

    result = await run_job("job_test", store)

    assert result["success"] is False
    updated_job = store.load("jobs", "job_test")
    assert updated_job["status"] == "needs_reagent"


async def test_run_job_missing_config_returns_error(
    store: JsonStore, job: dict
) -> None:
    store.save("jobs", "job_test", job)

    result = await run_job("job_test", store)

    assert result["success"] is False
    assert "error" in result
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_automated_runner.py -v`
Expected: FAIL — `ImportError` (run_job doesn't exist yet)

**Step 3: Write the implementation**

Add `run_job` to `eip/runner/automated_runner.py` (append to existing file):

```python
import uuid
from datetime import datetime, timezone

import httpx

from eip.runner.change_detector import detect_changes
from eip.store.json_store import JsonStore


async def run_job(job_id: str, store: JsonStore) -> dict:
    job = store.load("jobs", job_id)
    if job is None:
        return {"success": False, "error": f"Job {job_id} not found"}

    config = store.load("configs", job_id)
    if config is None:
        return {"success": False, "error": f"No extraction config for job {job_id}"}

    target_url = job["target_url"]
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(target_url)
            response.raise_for_status()
    except httpx.HTTPError as e:
        return {"success": False, "error": f"HTTP error: {e}", "run_id": run_id}

    items = extract_items(response.text, config)

    if not items:
        job["status"] = "needs_reagent"
        store.save("jobs", job_id, job)
        return {
            "success": False,
            "error": "Extraction returned no items — site may have changed",
            "run_id": run_id,
            "job_id": job_id,
        }

    # Load previous run for change detection
    previous_results = store.list(f"results/{job_id}")
    previous_items = None
    if previous_results:
        latest = sorted(previous_results, key=lambda r: r.get("ran_at", ""))[-1]
        previous_items = latest.get("items")

    items_with_changes = detect_changes(items, previous_items)
    new_count = sum(1 for i in items_with_changes if i.get("is_new"))

    result = {
        "run_id": run_id,
        "job_id": job_id,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "runner_type": "automated",
        "items": items_with_changes,
        "items_total": len(items_with_changes),
        "items_new": new_count,
        "success": True,
    }

    store.save(f"results/{job_id}", run_id, result)
    return result
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_automated_runner.py -v`
Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add eip/runner/automated_runner.py tests/test_automated_runner.py
git commit -m "feat: add full automated runner with fetch, extract, change detection"
```

---

### Task 6: Model Provider Abstraction + Claude Provider

**Files:**
- Create: `eip/agent/provider.py`
- Create: `tests/test_provider.py`

**Step 1: Write the failing tests**

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eip.agent.provider import ClaudeProvider, ModelProvider


def test_claude_provider_implements_protocol() -> None:
    provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
    assert isinstance(provider, ModelProvider)


async def test_claude_provider_complete_calls_api() -> None:
    provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Hello")]
    mock_response.stop_reason = "end_turn"
    mock_response.model = "claude-sonnet-4-6"

    with patch.object(
        provider.client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        result = await provider.complete(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert result["stop_reason"] == "end_turn"
        mock_create.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_provider.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
from typing import Any, Protocol, runtime_checkable

import anthropic


@runtime_checkable
class ModelProvider(Protocol):
    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict: ...


class ClaudeProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self.client.messages.create(**kwargs)

        return {
            "content": [
                {"type": block.type, "text": getattr(block, "text", None)}
                if block.type == "text"
                else {
                    "type": block.type,
                    "id": getattr(block, "id", None),
                    "name": getattr(block, "name", None),
                    "input": getattr(block, "input", None),
                }
                for block in response.content
            ],
            "stop_reason": response.stop_reason,
            "model": response.model,
        }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_provider.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add eip/agent/provider.py tests/test_provider.py
git commit -m "feat: add model provider abstraction with Claude implementation"
```

---

### Task 7: Agent Tools

**Files:**
- Create: `eip/agent/tools.py`
- Create: `tests/test_agent_tools.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from eip.agent.tools import AgentTools
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def tools(store: JsonStore) -> AgentTools:
    return AgentTools(store=store)


SAMPLE_HTML = """
<html><body>
<div class="items"><div class="item">
  <h3><a href="/page/1">Title One</a></h3>
  <p class="desc">Description one</p>
</div></div>
</body></html>
"""


async def test_fetch_page(httpx_mock: HTTPXMock, tools: AgentTools) -> None:
    httpx_mock.add_response(url="https://example.com", text="<html>Hello</html>")
    result = await tools.fetch_page("https://example.com")
    assert "Hello" in result["html"]
    assert result["status_code"] == 200


async def test_extract_with_selectors(
    httpx_mock: HTTPXMock, tools: AgentTools
) -> None:
    httpx_mock.add_response(url="https://example.com/page", text=SAMPLE_HTML)
    result = await tools.extract_with_selectors(
        url="https://example.com/page",
        selectors={
            "item_container": ".items .item",
            "title": "h3 a",
            "desc": ".desc",
            "link": "h3 a@href",
        },
        base_url="https://example.com",
    )
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "Title One"


def test_save_job(tools: AgentTools, store: JsonStore) -> None:
    job_def = {
        "name": "Test",
        "target_url": "https://example.com",
        "schedule": "0 * * * *",
    }
    extraction_config = {
        "strategy": "css_selector",
        "selectors": {"item_container": ".item", "title": "h3"},
        "base_url": "https://example.com",
    }
    result = tools.save_job(job_def, extraction_config)
    assert "job_id" in result
    # Verify persisted
    job = store.load("jobs", result["job_id"])
    assert job is not None
    assert job["name"] == "Test"
    config = store.load("configs", result["job_id"])
    assert config is not None


def test_tool_definitions(tools: AgentTools) -> None:
    defs = tools.get_tool_definitions()
    names = {d["name"] for d in defs}
    assert names == {"fetch_page", "extract_with_selectors", "save_job"}
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_tools.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from eip.runner.automated_runner import extract_items
from eip.store.json_store import JsonStore


class AgentTools:
    def __init__(self, store: JsonStore) -> None:
        self.store = store

    async def fetch_page(self, url: str) -> dict:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            return {
                "html": response.text[:50000],  # Truncate for LLM context
                "status_code": response.status_code,
                "url": str(response.url),
            }

    async def extract_with_selectors(
        self, url: str, selectors: dict, base_url: str = ""
    ) -> dict:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            config = {
                "strategy": "css_selector",
                "selectors": selectors,
                "base_url": base_url or url,
            }
            items = extract_items(response.text, config)
            return {"items": items, "count": len(items)}

    def save_job(self, job_definition: dict, extraction_config: dict) -> dict:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        job = {
            "id": job_id,
            "name": job_definition.get("name", "Unnamed job"),
            "target_url": job_definition["target_url"],
            "description": job_definition.get("description", ""),
            "schedule": job_definition.get("schedule", "0 * * * *"),
            "status": "active",
            "created_at": now,
        }
        self.store.save("jobs", job_id, job)

        config = {
            "job_id": job_id,
            **extraction_config,
            "created_at": now,
        }
        self.store.save("configs", job_id, config)

        return {"job_id": job_id, "job": job, "config": config}

    async def execute_tool(self, name: str, arguments: dict) -> Any:
        if name == "fetch_page":
            return await self.fetch_page(**arguments)
        elif name == "extract_with_selectors":
            return await self.extract_with_selectors(**arguments)
        elif name == "save_job":
            return self.save_job(**arguments)
        else:
            return {"error": f"Unknown tool: {name}"}

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "fetch_page",
                "description": "Fetch a web page and return its HTML content. Use this to examine the structure of a target website.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to fetch"},
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "extract_with_selectors",
                "description": "Test CSS selectors against a web page to extract structured items. Use '@attr' syntax for attributes (e.g. 'a@href' to get the href). The 'item_container' selector identifies repeating items. Other selectors extract fields within each item.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to extract from"},
                        "selectors": {
                            "type": "object",
                            "description": "Map of field names to CSS selectors. Must include 'item_container'. Use '@attr' for attributes (e.g. 'a@href').",
                        },
                        "base_url": {
                            "type": "string",
                            "description": "Base URL for resolving relative links",
                        },
                    },
                    "required": ["url", "selectors"],
                },
            },
            {
                "name": "save_job",
                "description": "Save a monitoring job and its extraction config. Call this after you have validated that the selectors extract the right data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "job_definition": {
                            "type": "object",
                            "description": "Job metadata: name, target_url, description, schedule (cron expression)",
                            "properties": {
                                "name": {"type": "string"},
                                "target_url": {"type": "string"},
                                "description": {"type": "string"},
                                "schedule": {"type": "string"},
                            },
                            "required": ["name", "target_url"],
                        },
                        "extraction_config": {
                            "type": "object",
                            "description": "Extraction strategy: strategy, selectors, base_url",
                        },
                    },
                    "required": ["job_definition", "extraction_config"],
                },
            },
        ]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agent_tools.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add eip/agent/tools.py tests/test_agent_tools.py
git commit -m "feat: add agent tools (fetch, extract, save)"
```

---

### Task 8: Setup Agent (Agentic Loop)

**Files:**
- Create: `eip/agent/setup_agent.py`
- Create: `tests/test_setup_agent.py`

**Step 1: Write the failing tests**

```python
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from eip.agent.setup_agent import SetupAgent
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


def _make_mock_provider(responses: list[dict]) -> AsyncMock:
    """Create a mock provider that returns a sequence of responses."""
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=responses)
    return provider


async def test_setup_agent_creates_job(store: JsonStore) -> None:
    """Simulate: agent fetches page, extracts, then saves job."""
    provider = _make_mock_provider([
        # First call: agent decides to fetch_page
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "fetch_page",
                    "input": {"url": "https://example.com/news"},
                }
            ],
            "stop_reason": "tool_use",
        },
        # Second call: agent tries extract_with_selectors
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_2",
                    "name": "extract_with_selectors",
                    "input": {
                        "url": "https://example.com/news",
                        "selectors": {
                            "item_container": ".articles .article",
                            "title": "h2 a",
                            "link": "h2 a@href",
                        },
                        "base_url": "https://example.com",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        # Third call: agent saves the job
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_3",
                    "name": "save_job",
                    "input": {
                        "job_definition": {
                            "name": "Monitor Example News",
                            "target_url": "https://example.com/news",
                            "description": "Track news articles",
                            "schedule": "0 */4 * * *",
                        },
                        "extraction_config": {
                            "strategy": "css_selector",
                            "selectors": {
                                "item_container": ".articles .article",
                                "title": "h2 a",
                                "link": "h2 a@href",
                            },
                            "base_url": "https://example.com",
                        },
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        # Fourth call: agent responds with summary
        {
            "content": [{"type": "text", "text": "Job created successfully."}],
            "stop_reason": "end_turn",
        },
    ])

    # Mock the agent tools' HTTP calls
    agent = SetupAgent(provider=provider, store=store)
    agent.tools.fetch_page = AsyncMock(
        return_value={"html": "<html>page html</html>", "status_code": 200, "url": "https://example.com/news"}
    )
    agent.tools.extract_with_selectors = AsyncMock(
        return_value={"items": [{"title": "Article 1", "url": "https://example.com/1"}], "count": 1}
    )

    result = await agent.run("Monitor example.com/news for new articles")

    assert result["success"] is True
    assert "job_id" in result
    # Job should be persisted
    jobs = store.list("jobs")
    assert len(jobs) == 1


async def test_setup_agent_max_turns_limit(store: JsonStore) -> None:
    """Agent should stop after max_turns to prevent infinite loops."""
    # Provider always returns tool calls — should hit limit
    infinite_tool_call = {
        "content": [
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "fetch_page",
                "input": {"url": "https://example.com"},
            }
        ],
        "stop_reason": "tool_use",
    }
    provider = _make_mock_provider([infinite_tool_call] * 20)

    agent = SetupAgent(provider=provider, store=store, max_turns=3)
    agent.tools.fetch_page = AsyncMock(
        return_value={"html": "<html></html>", "status_code": 200, "url": "https://example.com"}
    )

    result = await agent.run("Monitor something")

    assert result["success"] is False
    assert "max turns" in result.get("error", "").lower()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_setup_agent.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
import json
import logging
from typing import Any

from eip.agent.provider import ModelProvider
from eip.agent.tools import AgentTools
from eip.store.json_store import JsonStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an AI agent that sets up web monitoring jobs. The user will describe what external \
information they want to monitor. Your job is to:

1. Fetch the target web page to understand its structure.
2. Identify the right CSS selectors to extract the information the user wants.
3. Test your selectors by calling extract_with_selectors to verify they work.
4. If the extraction looks good, save the job using save_job.
5. If the extraction doesn't look right, try different selectors and test again.

Be methodical: fetch the page first, study the HTML structure, pick selectors, \
test them, iterate if needed, then save.

For the schedule, choose an appropriate cron expression based on the content type:
- News/media releases: every 4 hours (0 */4 * * *)
- Market data: every 15 minutes (*/15 * * * *)
- Research/publications: daily (0 9 * * *)
- General monitoring: hourly (0 * * * *)
"""


class SetupAgent:
    def __init__(
        self,
        provider: ModelProvider,
        store: JsonStore,
        max_turns: int = 10,
    ) -> None:
        self.provider = provider
        self.store = store
        self.tools = AgentTools(store=store)
        self.max_turns = max_turns

    async def run(self, user_request: str) -> dict:
        messages: list[dict] = [
            {"role": "user", "content": user_request},
        ]
        tool_defs = self.tools.get_tool_definitions()
        job_id = None

        for turn in range(self.max_turns):
            response = await self.provider.complete(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tool_defs,
            )

            # Check if the model wants to use a tool
            if response["stop_reason"] == "tool_use":
                tool_results = []
                for block in response["content"]:
                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_input = block["input"]
                        logger.info(f"Agent calling tool: {tool_name}")

                        tool_result = await self.tools.execute_tool(
                            tool_name, tool_input
                        )

                        # Track if save_job was called
                        if tool_name == "save_job" and "job_id" in tool_result:
                            job_id = tool_result["job_id"]

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": json.dumps(tool_result, default=str),
                            }
                        )

                # Add assistant message and tool results
                messages.append({"role": "assistant", "content": response["content"]})
                messages.append({"role": "user", "content": tool_results})

            elif response["stop_reason"] == "end_turn":
                # Agent is done
                text = ""
                for block in response["content"]:
                    if block["type"] == "text":
                        text += block.get("text", "")

                if job_id:
                    return {
                        "success": True,
                        "job_id": job_id,
                        "summary": text,
                    }
                else:
                    return {
                        "success": False,
                        "error": "Agent finished without creating a job",
                        "summary": text,
                    }
            else:
                return {
                    "success": False,
                    "error": f"Unexpected stop reason: {response['stop_reason']}",
                }

        return {
            "success": False,
            "error": f"Agent exceeded max turns ({self.max_turns})",
        }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_setup_agent.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add eip/agent/setup_agent.py tests/test_setup_agent.py
git commit -m "feat: add setup agent with agentic tool-use loop"
```

---

### Task 9: API Endpoints — Job CRUD & Results

**Files:**
- Create: `eip/api/jobs.py`
- Create: `eip/api/results.py`
- Create: `eip/main.py`
- Create: `tests/test_api.py`

**Step 1: Write the failing tests**

```python
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from eip.main import create_app
from eip.store.json_store import JsonStore


@pytest.fixture
def tmp_store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def client(tmp_store: JsonStore) -> TestClient:
    app = create_app(store=tmp_store)
    return TestClient(app)


@pytest.fixture
def seeded_client(tmp_store: JsonStore) -> TestClient:
    """Client with a pre-existing job and results."""
    tmp_store.save("jobs", "job_1", {
        "id": "job_1",
        "name": "Test Job",
        "target_url": "https://example.com",
        "schedule": "0 * * * *",
        "status": "active",
        "created_at": "2026-02-27T00:00:00Z",
    })
    tmp_store.save("configs", "job_1", {
        "job_id": "job_1",
        "strategy": "css_selector",
        "selectors": {"item_container": ".item", "title": "h2"},
        "base_url": "https://example.com",
    })
    tmp_store.save("results/job_1", "run_1", {
        "run_id": "run_1",
        "job_id": "job_1",
        "ran_at": "2026-02-27T01:00:00Z",
        "runner_type": "automated",
        "items": [{"title": "Article 1", "is_new": True}],
        "items_total": 1,
        "items_new": 1,
        "success": True,
    })
    app = create_app(store=tmp_store)
    return TestClient(app)


def test_list_jobs_empty(client: TestClient) -> None:
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() == []


def test_list_jobs(seeded_client: TestClient) -> None:
    response = seeded_client.get("/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["id"] == "job_1"


def test_get_job(seeded_client: TestClient) -> None:
    response = seeded_client.get("/jobs/job_1")
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["id"] == "job_1"
    assert "config" in data


def test_get_job_not_found(client: TestClient) -> None:
    response = client.get("/jobs/nonexistent")
    assert response.status_code == 404


def test_delete_job(seeded_client: TestClient) -> None:
    response = seeded_client.delete("/jobs/job_1")
    assert response.status_code == 200
    response = seeded_client.get("/jobs/job_1")
    assert response.status_code == 404


def test_patch_job_pause(seeded_client: TestClient) -> None:
    response = seeded_client.patch("/jobs/job_1", json={"status": "paused"})
    assert response.status_code == 200
    job = seeded_client.get("/jobs/job_1").json()["job"]
    assert job["status"] == "paused"


def test_get_results(seeded_client: TestClient) -> None:
    response = seeded_client.get("/jobs/job_1/results")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["run_id"] == "run_1"


def test_get_single_result(seeded_client: TestClient) -> None:
    response = seeded_client.get("/jobs/job_1/results/run_1")
    assert response.status_code == 200
    assert response.json()["run_id"] == "run_1"


def test_create_job_invokes_agent(client: TestClient, tmp_store: JsonStore) -> None:
    mock_result = {
        "success": True,
        "job_id": "job_new",
        "summary": "Created monitoring job",
    }
    with patch("eip.api.jobs.get_setup_agent") as mock_get_agent:
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/jobs/create",
            json={"request": "Monitor example.com for news"},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["job_id"] == "job_new"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write eip/api/results.py**

```python
from fastapi import APIRouter, HTTPException

from eip.store.json_store import JsonStore

router = APIRouter()


def create_results_router(store: JsonStore) -> APIRouter:
    r = APIRouter()

    @r.get("/jobs/{job_id}/results")
    def list_results(job_id: str) -> list[dict]:
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return store.list(f"results/{job_id}")

    @r.get("/jobs/{job_id}/results/{run_id}")
    def get_result(job_id: str, run_id: str) -> dict:
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        result = store.load(f"results/{job_id}", run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found")
        return result

    return r
```

**Step 4: Write eip/api/jobs.py**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from eip.store.json_store import JsonStore

router = APIRouter()

# Placeholder — replaced at app creation with a real factory
_store: JsonStore | None = None
_agent_factory = None


class CreateJobRequest(BaseModel):
    request: str


class PatchJobRequest(BaseModel):
    status: str | None = None
    schedule: str | None = None


def get_setup_agent():
    """Get a SetupAgent instance. Overridden in tests."""
    from eip.agent.provider import ClaudeProvider
    from eip.agent.setup_agent import SetupAgent
    from eip.config import settings

    provider = ClaudeProvider(
        api_key=settings.anthropic_api_key,
        model=settings.default_model,
    )
    return SetupAgent(provider=provider, store=_store)


def create_jobs_router(store: JsonStore) -> APIRouter:
    global _store
    _store = store
    r = APIRouter()

    @r.get("/jobs")
    def list_jobs() -> list[dict]:
        return store.list("jobs")

    @r.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        config = store.load("configs", job_id)
        return {"job": job, "config": config}

    @r.post("/jobs/create")
    async def create_job(body: CreateJobRequest) -> dict:
        agent = get_setup_agent()
        result = await agent.run(body.request)
        return result

    @r.post("/jobs/{job_id}/run")
    async def trigger_run(job_id: str) -> dict:
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        from eip.runner.automated_runner import run_job
        return await run_job(job_id, store)

    @r.patch("/jobs/{job_id}")
    def patch_job(job_id: str, body: PatchJobRequest) -> dict:
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if body.status is not None:
            job["status"] = body.status
        if body.schedule is not None:
            job["schedule"] = body.schedule
        store.save("jobs", job_id, job)
        return job

    @r.delete("/jobs/{job_id}")
    def delete_job(job_id: str) -> dict:
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        store.delete("jobs", job_id)
        store.delete("configs", job_id)
        return {"deleted": job_id}

    return r
```

**Step 5: Write eip/main.py**

```python
from fastapi import FastAPI

from eip.api.jobs import create_jobs_router
from eip.api.results import create_results_router
from eip.config import settings
from eip.store.json_store import JsonStore


def create_app(store: JsonStore | None = None) -> FastAPI:
    if store is None:
        settings.ensure_dirs()
        store = JsonStore(base_dir=settings.data_dir)

    app = FastAPI(title="External Intelligence Platform", version="0.1.0")
    app.include_router(create_jobs_router(store))
    app.include_router(create_results_router(store))
    return app


app = create_app()
```

**Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py -v`
Expected: All 10 tests PASS.

**Step 7: Commit**

```bash
git add eip/api/jobs.py eip/api/results.py eip/main.py tests/test_api.py
git commit -m "feat: add REST API endpoints for jobs and results"
```

---

### Task 10: Scheduler

**Files:**
- Create: `eip/scheduler/scheduler.py`
- Create: `tests/test_scheduler.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from eip.scheduler.scheduler import JobScheduler
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def scheduler(store: JsonStore) -> JobScheduler:
    return JobScheduler(store=store)


def test_scheduler_starts_and_stops(scheduler: JobScheduler) -> None:
    scheduler.start()
    assert scheduler.is_running
    scheduler.stop()
    assert not scheduler.is_running


def test_schedule_job(scheduler: JobScheduler, store: JsonStore) -> None:
    store.save("jobs", "job_1", {
        "id": "job_1",
        "name": "Test",
        "target_url": "https://example.com",
        "schedule": "0 * * * *",
        "status": "active",
    })
    scheduler.start()
    scheduler.schedule_job("job_1")
    assert scheduler.has_job("job_1")
    scheduler.stop()


def test_unschedule_job(scheduler: JobScheduler, store: JsonStore) -> None:
    store.save("jobs", "job_1", {
        "id": "job_1",
        "name": "Test",
        "target_url": "https://example.com",
        "schedule": "0 * * * *",
        "status": "active",
    })
    scheduler.start()
    scheduler.schedule_job("job_1")
    scheduler.unschedule_job("job_1")
    assert not scheduler.has_job("job_1")
    scheduler.stop()


def test_load_all_active_jobs(scheduler: JobScheduler, store: JsonStore) -> None:
    store.save("jobs", "active_1", {
        "id": "active_1",
        "schedule": "0 * * * *",
        "status": "active",
    })
    store.save("jobs", "paused_1", {
        "id": "paused_1",
        "schedule": "0 * * * *",
        "status": "paused",
    })
    scheduler.start()
    scheduler.load_all_jobs()
    assert scheduler.has_job("active_1")
    assert not scheduler.has_job("paused_1")
    scheduler.stop()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from eip.store.json_store import JsonStore

logger = logging.getLogger(__name__)


class JobScheduler:
    def __init__(self, store: JsonStore) -> None:
        self.store = store
        self._scheduler = BackgroundScheduler()

    @property
    def is_running(self) -> bool:
        return self._scheduler.running

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def schedule_job(self, job_id: str) -> None:
        job = self.store.load("jobs", job_id)
        if job is None:
            logger.warning(f"Cannot schedule unknown job: {job_id}")
            return

        cron_expr = job.get("schedule", "0 * * * *")
        trigger = CronTrigger.from_crontab(cron_expr)

        self._scheduler.add_job(
            self._run_job_sync,
            trigger=trigger,
            id=job_id,
            args=[job_id],
            replace_existing=True,
        )
        logger.info(f"Scheduled job {job_id} with cron: {cron_expr}")

    def unschedule_job(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def has_job(self, job_id: str) -> bool:
        return self._scheduler.get_job(job_id) is not None

    def load_all_jobs(self) -> None:
        jobs = self.store.list("jobs")
        for job in jobs:
            if job.get("status") == "active":
                self.schedule_job(job["id"])

    def _run_job_sync(self, job_id: str) -> None:
        from eip.runner.automated_runner import run_job

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(run_job(job_id, self.store))
            if result.get("success"):
                logger.info(
                    f"Job {job_id}: {result.get('items_new', 0)} new items"
                )
            else:
                logger.warning(f"Job {job_id} failed: {result.get('error')}")
        finally:
            loop.close()
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add eip/scheduler/scheduler.py tests/test_scheduler.py
git commit -m "feat: add APScheduler-based job scheduler"
```

---

### Task 11: Wire Scheduler Into FastAPI App

**Files:**
- Modify: `eip/main.py`

**Step 1: Update main.py to start/stop scheduler on app lifecycle**

Replace the full contents of `eip/main.py` with:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from eip.api.jobs import create_jobs_router
from eip.api.results import create_results_router
from eip.config import settings
from eip.scheduler.scheduler import JobScheduler
from eip.store.json_store import JsonStore


def create_app(store: JsonStore | None = None) -> FastAPI:
    if store is None:
        settings.ensure_dirs()
        store = JsonStore(base_dir=settings.data_dir)

    scheduler = JobScheduler(store=store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler.start()
        scheduler.load_all_jobs()
        yield
        scheduler.stop()

    app = FastAPI(
        title="External Intelligence Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.scheduler = scheduler
    app.include_router(create_jobs_router(store))
    app.include_router(create_results_router(store))
    return app


app = create_app()
```

**Step 2: Run all tests to verify nothing broke**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 3: Commit**

```bash
git add eip/main.py
git commit -m "feat: wire scheduler into FastAPI app lifecycle"
```

---

### Task 12: End-to-End Smoke Test

**Files:**
- Create: `tests/test_e2e.py`

**Step 1: Write an end-to-end test**

This test exercises the full flow: create a job (with mocked agent), trigger a run (with mocked HTTP), query results.

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from eip.main import create_app
from eip.store.json_store import JsonStore


SAMPLE_HTML = """
<html><body>
<div class="news">
  <div class="article">
    <h2><a href="/article/1">Breaking News</a></h2>
    <span class="date">2026-02-27</span>
    <p class="summary">Something happened.</p>
  </div>
  <div class="article">
    <h2><a href="/article/2">Other News</a></h2>
    <span class="date">2026-02-26</span>
    <p class="summary">Something else happened.</p>
  </div>
</div>
</body></html>
"""


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def client(store: JsonStore) -> TestClient:
    app = create_app(store=store)
    return TestClient(app)


def _seed_job(store: JsonStore) -> str:
    """Manually seed a job + config as if the agent created it."""
    job_id = "job_e2e"
    store.save("jobs", job_id, {
        "id": job_id,
        "name": "E2E Test Job",
        "target_url": "https://example.com/news",
        "schedule": "0 * * * *",
        "status": "active",
        "created_at": "2026-02-27T00:00:00Z",
    })
    store.save("configs", job_id, {
        "job_id": job_id,
        "strategy": "css_selector",
        "selectors": {
            "item_container": ".news .article",
            "title": "h2 a",
            "date": ".date",
            "summary": ".summary",
            "link": "h2 a@href",
        },
        "base_url": "https://example.com",
    })
    return job_id


async def test_full_flow(
    httpx_mock: HTTPXMock, store: JsonStore, client: TestClient
) -> None:
    # Step 1: Seed a job (simulating what the agent would create)
    job_id = _seed_job(store)

    # Step 2: Verify job is listed
    response = client.get("/jobs")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Step 3: Trigger a manual run
    httpx_mock.add_response(
        url="https://example.com/news", text=SAMPLE_HTML
    )
    response = client.post(f"/jobs/{job_id}/run")
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["items_total"] == 2
    assert result["items_new"] == 2  # All new on first run

    # Step 4: Query results
    response = client.get(f"/jobs/{job_id}/results")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["items_total"] == 2

    # Step 5: Run again — items should no longer be "new"
    httpx_mock.add_response(
        url="https://example.com/news", text=SAMPLE_HTML
    )
    response = client.post(f"/jobs/{job_id}/run")
    result = response.json()
    assert result["success"] is True
    assert result["items_new"] == 0  # No new items on second run
```

**Step 2: Run the test**

Run: `python -m pytest tests/test_e2e.py -v`
Expected: PASS.

**Step 3: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: add end-to-end smoke test for full job lifecycle"
```

---

### Task 13: Configuration and Run Script

**Files:**
- Create: `.env.example`
- Modify: `eip/config.py` to read from environment

**Step 1: Create .env.example**

```
ANTHROPIC_API_KEY=your-api-key-here
EIP_DATA_DIR=data
EIP_DEFAULT_MODEL=claude-sonnet-4-6
EIP_LOG_LEVEL=INFO
```

**Step 2: Update config.py to read from environment**

```python
import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    data_dir: Path = Path(os.getenv("EIP_DATA_DIR", "data"))
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    default_model: str = os.getenv("EIP_DEFAULT_MODEL", "claude-sonnet-4-6")
    log_level: str = os.getenv("EIP_LOG_LEVEL", "INFO")

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def configs_dir(self) -> Path:
        return self.data_dir / "configs"

    @property
    def results_dir(self) -> Path:
        return self.data_dir / "results"

    def ensure_dirs(self) -> None:
        for d in [self.jobs_dir, self.configs_dir, self.results_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
```

**Step 3: Run all tests to make sure nothing broke**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add .env.example eip/config.py
git commit -m "feat: add env-based configuration and .env.example"
```

---

### Task 14: Final Verification and .gitignore

**Files:**
- Create: `.gitignore`

**Step 1: Create .gitignore**

```
.venv/
__pycache__/
*.pyc
data/
.env
*.egg-info/
.pytest_cache/
```

**Step 2: Run the full test suite one final time**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS.

**Step 3: Verify the app starts**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && ANTHROPIC_API_KEY=test uvicorn eip.main:app --host 0.0.0.0 --port 8000 &; sleep 2; curl -s http://localhost:8000/jobs | python -m json.tool; kill %1`
Expected: Returns `[]` (empty jobs list). App starts and responds.

**Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

## Summary

| Task | What it builds |
|------|---------------|
| 1 | Project scaffolding, dependencies, config |
| 2 | JSON file store (CRUD for any collection) |
| 3 | CSS selector extraction engine |
| 4 | Change detection (new/existing item diffing) |
| 5 | Full automated runner (fetch + extract + detect + store) |
| 6 | Model provider abstraction + Claude implementation |
| 7 | Agent tools (fetch_page, extract_with_selectors, save_job) |
| 8 | Setup agent (agentic tool-use loop) |
| 9 | REST API endpoints (job CRUD, results, agent-powered creation) |
| 10 | APScheduler-based job scheduler |
| 11 | Wire scheduler into FastAPI lifecycle |
| 12 | End-to-end smoke test |
| 13 | Environment-based config + .env.example |
| 14 | Final verification + .gitignore |
