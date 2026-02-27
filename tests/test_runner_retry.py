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
