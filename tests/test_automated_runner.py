import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

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


@pytest.mark.asyncio
async def test_run_job_playwright_tier(tmp_path: Path) -> None:
    """When config has tier=playwright, runner should use browser tool."""
    store = JsonStore(base_dir=tmp_path)
    store.save(
        "jobs",
        "job_pw",
        {
            "id": "job_pw",
            "name": "JS Site",
            "target_url": "https://spa-site.com",
            "status": "active",
        },
    )
    store.save(
        "configs",
        "job_pw",
        {
            "job_id": "job_pw",
            "strategy": "css_selector",
            "tier": "playwright",
            "selectors": {"item_container": ".item", "title": "h2"},
            "base_url": "https://spa-site.com",
            "playwright_actions": [
                {"action": "wait_for_selector", "selector": ".item"},
            ],
        },
    )

    with patch("eip.runner.automated_runner.BrowserTool") as MockBT:
        mock_bt = AsyncMock()
        mock_bt.browse_page = AsyncMock(
            return_value={
                "html": '<div class="item"><h2>Article 1</h2></div>',
                "title": "SPA Site",
                "url": "https://spa-site.com",
            }
        )
        MockBT.return_value = mock_bt
        result = await run_job("job_pw", store)

    assert result["success"] is True
    assert result["items_total"] == 1
    mock_bt.browse_page.assert_called_once()
