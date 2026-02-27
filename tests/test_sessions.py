import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from eip.api.sessions import SessionManager, SessionStatus
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def manager(store: JsonStore) -> SessionManager:
    return SessionManager(store=store)


def test_create_session(manager: SessionManager) -> None:
    session_id = manager.create("Monitor example.com")
    assert session_id.startswith("sess_")
    session = manager.get(session_id)
    assert session is not None
    assert session["status"] == SessionStatus.RUNNING.value
    assert session["request"] == "Monitor example.com"


def test_get_missing_session(manager: SessionManager) -> None:
    assert manager.get("sess_nonexistent") is None


def test_send_message(manager: SessionManager) -> None:
    session_id = manager.create("Monitor example.com")
    manager.send_message(session_id, {"type": "confirm"})
    # Message should be in the queue
    session = manager.get(session_id)
    assert session is not None


def test_list_sessions(manager: SessionManager) -> None:
    manager.create("Job A")
    manager.create("Job B")
    sessions = manager.list_sessions()
    assert len(sessions) == 2


def test_cancel_session(manager: SessionManager) -> None:
    session_id = manager.create("Monitor example.com")
    manager.cancel(session_id)
    session = manager.get(session_id)
    assert session["status"] == SessionStatus.CANCELLED.value
