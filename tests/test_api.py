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
