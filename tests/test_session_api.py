import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from eip.main import create_app
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def client(store: JsonStore) -> TestClient:
    app = create_app(store=store)
    return TestClient(app)


def test_create_session(client: TestClient) -> None:
    with patch("eip.api.jobs.get_setup_agent") as mock_get:
        mock_agent = AsyncMock()
        mock_get.return_value = mock_agent

        response = client.post(
            "/jobs/create",
            json={"request": "Monitor example.com"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data


def test_send_message_to_session(client: TestClient) -> None:
    with patch("eip.api.jobs.get_setup_agent") as mock_get:
        mock_agent = AsyncMock()
        mock_get.return_value = mock_agent

        create_resp = client.post(
            "/jobs/create",
            json={"request": "Monitor example.com"},
        )
        session_id = create_resp.json()["session_id"]

    response = client.post(
        f"/jobs/create/{session_id}/message",
        json={"content": "I only want articles from 2026"},
    )
    assert response.status_code == 200


def test_confirm_session(client: TestClient) -> None:
    with patch("eip.api.jobs.get_setup_agent") as mock_get:
        mock_agent = AsyncMock()
        mock_get.return_value = mock_agent

        create_resp = client.post(
            "/jobs/create",
            json={"request": "Monitor example.com"},
        )
        session_id = create_resp.json()["session_id"]

    response = client.post(f"/jobs/create/{session_id}/confirm")
    assert response.status_code == 200


def test_reject_session(client: TestClient) -> None:
    with patch("eip.api.jobs.get_setup_agent") as mock_get:
        mock_agent = AsyncMock()
        mock_get.return_value = mock_agent

        create_resp = client.post(
            "/jobs/create",
            json={"request": "Monitor example.com"},
        )
        session_id = create_resp.json()["session_id"]

    response = client.post(f"/jobs/create/{session_id}/reject")
    assert response.status_code == 200


def test_session_not_found(client: TestClient) -> None:
    response = client.post("/jobs/create/sess_nonexistent/confirm")
    assert response.status_code == 404
