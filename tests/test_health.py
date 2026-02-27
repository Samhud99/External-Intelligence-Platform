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
        "consecutive_failures": 2,
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
        # Also patch RETRY_DELAYS if it exists (from Task 7)
        try:
            with patch("eip.runner.automated_runner.RETRY_DELAYS", [0]):
                result = await run_job("job_health", store_with_failing_job)
        except AttributeError:
            result = await run_job("job_health", store_with_failing_job)

    assert result["success"] is False
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
        try:
            with patch("eip.runner.automated_runner.RETRY_DELAYS", [0]):
                result = await run_job("job_ok", store)
        except AttributeError:
            result = await run_job("job_ok", store)

    assert result["success"] is True
    job = store.load("jobs", "job_ok")
    assert job.get("consecutive_failures", 0) == 0
