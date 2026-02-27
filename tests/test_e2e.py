import json
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
