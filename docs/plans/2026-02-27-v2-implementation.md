# V2: UI & Agent Transparency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a React frontend with live SSE streaming of agent discovery, session-based job creation with user review/refinement, and a full dashboard for job management.

**Architecture:** Backend gets event types, a streaming agent method, in-memory session management, and SSE endpoints. Frontend is a React + TypeScript SPA with Vite and Tailwind that connects to the existing FastAPI backend via REST + SSE.

**Tech Stack:** Python 3.9+, FastAPI, SSE (sse-starlette), React 18, TypeScript, Vite, Tailwind CSS, React Router v6

---

### Task 1: Agent Event Types

**Files:**
- Create: `eip/agent/events.py`
- Create: `tests/test_events.py`

**Step 1: Write the failing test**

```python
import json

from eip.agent.events import AgentEvent, EventType


def test_status_event_to_dict() -> None:
    event = AgentEvent(type=EventType.STATUS, message="Fetching page...")
    d = event.to_dict()
    assert d["type"] == "status"
    assert d["message"] == "Fetching page..."


def test_extraction_test_event_to_dict() -> None:
    event = AgentEvent(
        type=EventType.EXTRACTION_TEST,
        selectors={"item_container": ".article", "title": "h2"},
        sample_items=[{"title": "Test"}],
        count=1,
    )
    d = event.to_dict()
    assert d["type"] == "extraction_test"
    assert d["count"] == 1
    assert len(d["sample_items"]) == 1


def test_proposal_event_to_dict() -> None:
    event = AgentEvent(
        type=EventType.PROPOSAL,
        job={"name": "Test Job", "target_url": "https://example.com"},
        config={"strategy": "css_selector", "selectors": {}},
        sample_data=[{"title": "Article 1"}],
    )
    d = event.to_dict()
    assert d["type"] == "proposal"
    assert d["job"]["name"] == "Test Job"
    assert len(d["sample_data"]) == 1


def test_event_to_sse_format() -> None:
    event = AgentEvent(type=EventType.STATUS, message="Working...")
    sse = event.to_sse()
    assert sse.startswith("event: status\ndata: ")
    payload = json.loads(sse.split("data: ", 1)[1])
    assert payload["message"] == "Working..."


def test_all_event_types_exist() -> None:
    expected = {"status", "page_fetched", "thinking", "extraction_test", "proposal", "done", "error"}
    actual = {e.value for e in EventType}
    assert expected == actual
```

**Step 2: Run test to verify it fails**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && python -m pytest tests/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
import json
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(Enum):
    STATUS = "status"
    PAGE_FETCHED = "page_fetched"
    THINKING = "thinking"
    EXTRACTION_TEST = "extraction_test"
    PROPOSAL = "proposal"
    DONE = "done"
    ERROR = "error"


class AgentEvent:
    def __init__(
        self,
        type: EventType,
        message: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        content_length: Optional[int] = None,
        selectors: Optional[Dict] = None,
        sample_items: Optional[List[Dict]] = None,
        count: Optional[int] = None,
        job: Optional[Dict] = None,
        config: Optional[Dict] = None,
        sample_data: Optional[List[Dict]] = None,
        status: Optional[str] = None,
    ) -> None:
        self.type = type
        self.message = message
        self.url = url
        self.title = title
        self.content_length = content_length
        self.selectors = selectors
        self.sample_items = sample_items
        self.count = count
        self.job = job
        self.config = config
        self.sample_data = sample_data
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": self.type.value}
        for key in [
            "message", "url", "title", "content_length",
            "selectors", "sample_items", "count",
            "job", "config", "sample_data", "status",
        ]:
            val = getattr(self, key)
            if val is not None:
                d[key] = val
        return d

    def to_sse(self) -> str:
        return f"event: {self.type.value}\ndata: {json.dumps(self.to_dict(), default=str)}"
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_events.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add eip/agent/events.py tests/test_events.py
git commit -m "feat: add agent event types for SSE streaming"
```

---

### Task 2: Streaming Setup Agent

**Files:**
- Modify: `eip/agent/setup_agent.py`
- Create: `tests/test_streaming_agent.py`

**Step 1: Write the failing test**

```python
import asyncio
import json
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


async def test_run_streaming_emits_events(store: JsonStore) -> None:
    provider = _make_mock_provider([
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
        # Agent sends text summary (end_turn) — triggers proposal
        {
            "content": [{"type": "text", "text": "I found 2 articles. Here is my proposed configuration."}],
            "stop_reason": "end_turn",
        },
    ])

    agent = SetupAgent(provider=provider, store=store)
    agent.tools.fetch_page = AsyncMock(
        return_value={"html": "<html>page</html>", "status_code": 200, "url": "https://example.com/news"}
    )
    agent.tools.extract_with_selectors = AsyncMock(
        return_value={
            "items": [{"title": "Article 1", "url": "https://example.com/1"}],
            "count": 1,
        }
    )

    events = []
    input_queue = asyncio.Queue()

    async for event in agent.run_streaming("Monitor example.com", input_queue):
        events.append(event)

    event_types = [e.type for e in events]
    # Should have at least: status (fetching), page_fetched, status (extracting), extraction_test, proposal
    assert EventType.STATUS in event_types
    assert EventType.PROPOSAL in event_types


async def test_run_streaming_waits_for_confirmation(store: JsonStore) -> None:
    provider = _make_mock_provider([
        {
            "content": [{"type": "text", "text": "Here is my proposal."}],
            "stop_reason": "end_turn",
        },
        # After confirmation, agent saves the job
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "save_job",
                    "input": {
                        "job_definition": {
                            "name": "Test",
                            "target_url": "https://example.com",
                        },
                        "extraction_config": {
                            "strategy": "css_selector",
                            "selectors": {"item_container": ".item", "title": "h2"},
                            "base_url": "https://example.com",
                        },
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "content": [{"type": "text", "text": "Job saved."}],
            "stop_reason": "end_turn",
        },
    ])

    agent = SetupAgent(provider=provider, store=store)
    input_queue = asyncio.Queue()

    # Pre-load confirmation so the agent doesn't block forever
    await input_queue.put({"type": "confirm"})

    events = []
    async for event in agent.run_streaming("Monitor example.com", input_queue):
        events.append(event)

    event_types = [e.type for e in events]
    assert EventType.PROPOSAL in event_types
    assert EventType.DONE in event_types
    # Job should be saved
    jobs = store.list("jobs")
    assert len(jobs) == 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_streaming_agent.py -v`
Expected: FAIL — `AttributeError: 'SetupAgent' has no attribute 'run_streaming'`

**Step 3: Write the implementation**

Add the following to the existing `eip/agent/setup_agent.py` — keep the existing `run()` method intact and add `run_streaming()` below it. Also add new imports at the top of the file.

Add these imports to the top (alongside existing imports):

```python
import asyncio
from eip.agent.events import AgentEvent, EventType
```

Add this method to the `SetupAgent` class after the existing `run()` method:

```python
    async def run_streaming(self, user_request: str, input_queue: asyncio.Queue):
        """Yield AgentEvents as the agent works. Pauses at proposal for user input."""
        messages: List[Dict] = [
            {"role": "user", "content": user_request},
        ]
        tool_defs = self.tools.get_tool_definitions()
        job_id = None
        last_extraction = None
        last_selectors = None
        awaiting_input = False

        for turn in range(self.max_turns):
            response = await self.provider.complete(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tool_defs,
            )

            if response["stop_reason"] == "tool_use":
                tool_results = []
                for block in response["content"]:
                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_input = block["input"]

                        # Emit status event before tool execution
                        if tool_name == "fetch_page":
                            yield AgentEvent(
                                type=EventType.STATUS,
                                message=f"Fetching {tool_input.get('url', '')}...",
                            )
                        elif tool_name == "extract_with_selectors":
                            yield AgentEvent(
                                type=EventType.STATUS,
                                message="Testing extraction selectors...",
                            )
                        elif tool_name == "save_job":
                            yield AgentEvent(
                                type=EventType.STATUS,
                                message="Saving monitoring job...",
                            )

                        tool_result = await self.tools.execute_tool(
                            tool_name, tool_input
                        )

                        # Emit events after tool execution
                        if tool_name == "fetch_page":
                            yield AgentEvent(
                                type=EventType.PAGE_FETCHED,
                                url=tool_result.get("url", ""),
                                content_length=len(tool_result.get("html", "")),
                            )
                        elif tool_name == "extract_with_selectors":
                            last_extraction = tool_result
                            last_selectors = tool_input.get("selectors", {})
                            items = tool_result.get("items", [])
                            yield AgentEvent(
                                type=EventType.EXTRACTION_TEST,
                                selectors=last_selectors,
                                sample_items=items[:5],
                                count=tool_result.get("count", 0),
                            )
                        elif tool_name == "save_job" and "job_id" in tool_result:
                            job_id = tool_result["job_id"]

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": json.dumps(tool_result, default=str),
                            }
                        )

                messages.append({"role": "assistant", "content": response["content"]})
                messages.append({"role": "user", "content": tool_results})

            elif response["stop_reason"] == "end_turn":
                text = ""
                for block in response["content"]:
                    if block["type"] == "text":
                        text += block.get("text", "")

                if job_id:
                    # Job was saved — we're done
                    yield AgentEvent(
                        type=EventType.DONE,
                        status="completed",
                        message=text,
                    )
                    return

                # Agent finished a round without saving — present proposal
                proposal_job = {
                    "target_url": user_request,
                    "description": text,
                }
                proposal_config = {}
                if last_selectors:
                    proposal_config["selectors"] = last_selectors
                sample = []
                if last_extraction:
                    sample = last_extraction.get("items", [])[:5]

                yield AgentEvent(
                    type=EventType.PROPOSAL,
                    job=proposal_job,
                    config=proposal_config,
                    sample_data=sample,
                    message=text,
                )

                # Wait for user input
                try:
                    user_input = await asyncio.wait_for(input_queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    yield AgentEvent(
                        type=EventType.ERROR,
                        message="Session timed out waiting for input",
                    )
                    return

                if user_input.get("type") == "confirm":
                    # Tell agent to save the job
                    messages.append({"role": "assistant", "content": response["content"]})
                    messages.append({
                        "role": "user",
                        "content": "The user has approved this configuration. Please save the job now using save_job.",
                    })
                elif user_input.get("type") == "reject":
                    yield AgentEvent(
                        type=EventType.DONE,
                        status="cancelled",
                        message="User rejected the proposal",
                    )
                    return
                elif user_input.get("type") == "message":
                    # User refinement
                    messages.append({"role": "assistant", "content": response["content"]})
                    messages.append({
                        "role": "user",
                        "content": user_input.get("content", ""),
                    })
                    yield AgentEvent(
                        type=EventType.STATUS,
                        message="Processing your feedback...",
                    )
            else:
                yield AgentEvent(
                    type=EventType.ERROR,
                    message=f"Unexpected stop reason: {response['stop_reason']}",
                )
                return

        yield AgentEvent(
            type=EventType.ERROR,
            message=f"Agent exceeded max turns ({self.max_turns})",
        )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_streaming_agent.py -v`
Expected: All 2 tests PASS.

**Step 5: Run full suite for regressions**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (existing tests unaffected since `run()` is unchanged).

**Step 6: Commit**

```bash
git add eip/agent/setup_agent.py eip/agent/events.py tests/test_streaming_agent.py tests/test_events.py
git commit -m "feat: add streaming agent with event emission and user input queue"
```

---

### Task 3: Session Manager

**Files:**
- Create: `eip/api/sessions.py`
- Create: `tests/test_sessions.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sessions.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from eip.store.json_store import JsonStore


class SessionStatus(Enum):
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class SessionManager:
    def __init__(self, store: JsonStore) -> None:
        self.store = store
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}

    def create(self, request: str) -> str:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = {
            "session_id": session_id,
            "request": request,
            "status": SessionStatus.RUNNING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._queues[session_id] = asyncio.Queue()
        self._event_queues[session_id] = asyncio.Queue()
        return session_id

    def get(self, session_id: str) -> Optional[Dict]:
        return self._sessions.get(session_id)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["status"] = status.value

    def get_input_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(session_id)

    def get_event_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        return self._event_queues.get(session_id)

    def send_message(self, session_id: str, message: Dict) -> None:
        queue = self._queues.get(session_id)
        if queue:
            queue.put_nowait(message)

    def send_event(self, session_id: str, event: Any) -> None:
        queue = self._event_queues.get(session_id)
        if queue:
            queue.put_nowait(event)

    def cancel(self, session_id: str) -> None:
        self.update_status(session_id, SessionStatus.CANCELLED)
        # Unblock any waiting queue
        queue = self._queues.get(session_id)
        if queue:
            queue.put_nowait({"type": "reject"})

    def list_sessions(self) -> List[Dict]:
        return list(self._sessions.values())
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sessions.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add eip/api/sessions.py tests/test_sessions.py
git commit -m "feat: add in-memory session manager for agent creation flow"
```

---

### Task 4: SSE + Session API Endpoints

**Files:**
- Modify: `eip/api/jobs.py`
- Modify: `eip/main.py`
- Create: `tests/test_session_api.py`

**Step 1: Install sse-starlette**

Add `sse-starlette>=2.0.0` to `requirements.txt` and run:

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && pip install sse-starlette>=2.0.0`

**Step 2: Write the failing test**

```python
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
```

**Step 3: Modify eip/api/jobs.py**

Replace the full contents of `eip/api/jobs.py` with:

```python
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from eip.api.sessions import SessionManager
from eip.store.json_store import JsonStore

_store = None
_session_manager = None


class CreateJobRequest(BaseModel):
    request: str


class PatchJobRequest(BaseModel):
    status: Optional[str] = None
    schedule: Optional[str] = None


class MessageRequest(BaseModel):
    content: str


def get_setup_agent():
    from eip.agent.provider import ClaudeProvider
    from eip.agent.setup_agent import SetupAgent
    from eip.config import settings

    provider = ClaudeProvider(
        api_key=settings.anthropic_api_key,
        model=settings.default_model,
    )
    return SetupAgent(provider=provider, store=_store)


async def _run_agent_streaming(session_id: str, request: str) -> None:
    """Background task: run the agent and push events to the session's event queue."""
    agent = get_setup_agent()
    input_queue = _session_manager.get_input_queue(session_id)
    try:
        async for event in agent.run_streaming(request, input_queue):
            _session_manager.send_event(session_id, event)
    except Exception as e:
        from eip.agent.events import AgentEvent, EventType
        _session_manager.send_event(
            session_id,
            AgentEvent(type=EventType.ERROR, message=str(e)),
        )
    finally:
        _session_manager.send_event(session_id, None)  # Signal stream end


def create_jobs_router(store: JsonStore, session_manager: SessionManager) -> APIRouter:
    global _store, _session_manager
    _store = store
    _session_manager = session_manager
    r = APIRouter()

    @r.get("/jobs")
    def list_jobs():
        return store.list("jobs")

    @r.get("/jobs/{job_id}")
    def get_job(job_id: str):
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        config = store.load("configs", job_id)
        return {"job": job, "config": config}

    @r.post("/jobs/create")
    async def create_job(body: CreateJobRequest):
        session_id = _session_manager.create(body.request)
        asyncio.create_task(_run_agent_streaming(session_id, body.request))
        return {"session_id": session_id}

    @r.get("/jobs/create/{session_id}/stream")
    async def stream_events(session_id: str):
        session = _session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        event_queue = _session_manager.get_event_queue(session_id)

        async def event_generator():
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield {
                    "event": event.type.value,
                    "data": json.dumps(event.to_dict(), default=str),
                }

        return EventSourceResponse(event_generator())

    @r.post("/jobs/create/{session_id}/message")
    async def send_message(session_id: str, body: MessageRequest):
        session = _session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        _session_manager.send_message(session_id, {"type": "message", "content": body.content})
        return {"status": "sent"}

    @r.post("/jobs/create/{session_id}/confirm")
    async def confirm_session(session_id: str):
        session = _session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        _session_manager.send_message(session_id, {"type": "confirm"})
        return {"status": "confirmed"}

    @r.post("/jobs/create/{session_id}/reject")
    async def reject_session(session_id: str):
        session = _session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        _session_manager.cancel(session_id)
        return {"status": "rejected"}

    @r.post("/jobs/{job_id}/run")
    async def trigger_run(job_id: str):
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        from eip.runner.automated_runner import run_job
        return await run_job(job_id, store)

    @r.patch("/jobs/{job_id}")
    def patch_job(job_id: str, body: PatchJobRequest):
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
    def delete_job(job_id: str):
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        store.delete("jobs", job_id)
        store.delete("configs", job_id)
        return {"deleted": job_id}

    return r
```

**Step 4: Update eip/main.py**

Replace the full contents of `eip/main.py` with:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eip.api.jobs import create_jobs_router
from eip.api.results import create_results_router
from eip.api.sessions import SessionManager
from eip.config import settings
from eip.scheduler.scheduler import JobScheduler
from eip.store.json_store import JsonStore


def create_app(store=None) -> FastAPI:
    if store is None:
        settings.ensure_dirs()
        store = JsonStore(base_dir=settings.data_dir)

    scheduler = JobScheduler(store=store)
    session_manager = SessionManager(store=store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler.start()
        scheduler.load_all_jobs()
        yield
        scheduler.stop()

    app = FastAPI(
        title="External Intelligence Platform",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.scheduler = scheduler
    app.state.session_manager = session_manager
    app.include_router(create_jobs_router(store, session_manager))
    app.include_router(create_results_router(store))
    return app


app = create_app()
```

**Step 5: Update tests/test_api.py for new signature**

The existing `test_api.py` calls `create_app(store=tmp_store)` which now works because `create_app` creates its own `SessionManager`. However, the `test_create_job_invokes_agent` test patches `eip.api.jobs.get_setup_agent` — this still works. BUT the `POST /jobs/create` endpoint now returns `{"session_id": ...}` instead of the agent result directly. Update the test:

In `tests/test_api.py`, replace `test_create_job_invokes_agent` with:

```python
def test_create_job_returns_session(client: TestClient, tmp_store: JsonStore) -> None:
    with patch("eip.api.jobs.get_setup_agent") as mock_get_agent:
        mock_agent = AsyncMock()
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/jobs/create",
            json={"request": "Monitor example.com for news"},
        )

    assert response.status_code == 200
    assert "session_id" in response.json()
```

**Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_session_api.py tests/test_api.py -v`
Expected: All tests PASS.

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 7: Commit**

```bash
git add eip/api/jobs.py eip/main.py eip/api/sessions.py requirements.txt tests/test_session_api.py tests/test_api.py
git commit -m "feat: add SSE streaming endpoints and session-based job creation"
```

---

### Task 5: Frontend Scaffolding

**Files:**
- Create: `frontend/` directory with Vite + React + TypeScript + Tailwind

**Step 1: Check that node/npm is available**

Run: `node --version && npm --version`
Expected: Node 18+ and npm 9+

**Step 2: Scaffold the React project**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && npm create vite@latest frontend -- --template react-ts`
Expected: Creates `frontend/` directory with React + TypeScript template.

**Step 3: Install dependencies**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npm install && npm install -D tailwindcss @tailwindcss/vite react-router-dom`

**Step 4: Configure Tailwind**

Replace `frontend/src/index.css` with:

```css
@import "tailwindcss";
```

Add the Tailwind Vite plugin to `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/jobs': 'http://localhost:8000',
    },
  },
})
```

**Step 5: Clean up default Vite files**

- Delete `frontend/src/App.css`
- Delete `frontend/src/assets/` directory
- Replace `frontend/src/App.tsx` with a minimal placeholder:

```tsx
function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <h1 className="text-2xl font-bold p-8">External Intelligence Platform</h1>
    </div>
  )
}

export default App
```

- Replace `frontend/src/main.tsx` with:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

**Step 6: Verify the frontend starts**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npm run dev &; sleep 3; curl -s http://localhost:5173 | head -5; kill %1`
Expected: HTML response from the Vite dev server.

**Step 7: Commit**

```bash
cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform"
echo "node_modules/" >> .gitignore
git add frontend/ .gitignore
git commit -m "feat: scaffold React + TypeScript + Tailwind frontend"
```

---

### Task 6: API Client + SSE Helper

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/sse.ts`
- Create: `frontend/src/api/types.ts`

**Step 1: Create type definitions**

Create `frontend/src/api/types.ts`:

```typescript
export interface Job {
  id: string
  name: string
  target_url: string
  description: string
  schedule: string
  status: string
  created_at: string
}

export interface ExtractionConfig {
  job_id: string
  strategy: string
  selectors: Record<string, string>
  base_url: string
}

export interface RunResult {
  run_id: string
  job_id: string
  ran_at: string
  runner_type: string
  items: ExtractedItem[]
  items_total: number
  items_new: number
  success: boolean
  error?: string
}

export interface ExtractedItem {
  title?: string
  date?: string
  summary?: string
  url?: string
  is_new?: boolean
  [key: string]: unknown
}

export interface AgentEvent {
  type: string
  message?: string
  url?: string
  title?: string
  content_length?: number
  selectors?: Record<string, string>
  sample_items?: ExtractedItem[]
  count?: number
  job?: Partial<Job>
  config?: Partial<ExtractionConfig>
  sample_data?: ExtractedItem[]
  status?: string
}
```

**Step 2: Create the REST API client**

Create `frontend/src/api/client.ts`:

```typescript
const BASE_URL = '/jobs'

export async function listJobs() {
  const res = await fetch(BASE_URL)
  return res.json()
}

export async function getJob(jobId: string) {
  const res = await fetch(`${BASE_URL}/${jobId}`)
  if (!res.ok) throw new Error('Job not found')
  return res.json()
}

export async function createSession(request: string) {
  const res = await fetch(`${BASE_URL}/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request }),
  })
  return res.json()
}

export async function sendMessage(sessionId: string, content: string) {
  const res = await fetch(`${BASE_URL}/create/${sessionId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  return res.json()
}

export async function confirmSession(sessionId: string) {
  const res = await fetch(`${BASE_URL}/create/${sessionId}/confirm`, {
    method: 'POST',
  })
  return res.json()
}

export async function rejectSession(sessionId: string) {
  const res = await fetch(`${BASE_URL}/create/${sessionId}/reject`, {
    method: 'POST',
  })
  return res.json()
}

export async function triggerRun(jobId: string) {
  const res = await fetch(`${BASE_URL}/${jobId}/run`, { method: 'POST' })
  return res.json()
}

export async function patchJob(jobId: string, updates: Record<string, string>) {
  const res = await fetch(`${BASE_URL}/${jobId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  return res.json()
}

export async function deleteJob(jobId: string) {
  const res = await fetch(`${BASE_URL}/${jobId}`, { method: 'DELETE' })
  return res.json()
}

export async function getResults(jobId: string) {
  const res = await fetch(`${BASE_URL}/${jobId}/results`)
  return res.json()
}

export async function getResult(jobId: string, runId: string) {
  const res = await fetch(`${BASE_URL}/${jobId}/results/${runId}`)
  return res.json()
}
```

**Step 3: Create the SSE helper**

Create `frontend/src/api/sse.ts`:

```typescript
import type { AgentEvent } from './types'

export function subscribeToStream(
  sessionId: string,
  onEvent: (event: AgentEvent) => void,
  onError?: (error: Event) => void,
  onClose?: () => void,
): () => void {
  const url = `/jobs/create/${sessionId}/stream`
  const eventSource = new EventSource(url)

  const eventTypes = [
    'status', 'page_fetched', 'thinking',
    'extraction_test', 'proposal', 'done', 'error',
  ]

  for (const type of eventTypes) {
    eventSource.addEventListener(type, (e: MessageEvent) => {
      const data = JSON.parse(e.data) as AgentEvent
      onEvent(data)

      if (type === 'done' || type === 'error') {
        eventSource.close()
        onClose?.()
      }
    })
  }

  eventSource.onerror = (e) => {
    onError?.(e)
    eventSource.close()
    onClose?.()
  }

  // Return cleanup function
  return () => eventSource.close()
}
```

**Step 4: Verify TypeScript compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`
Expected: No errors.

**Step 5: Commit**

```bash
git add frontend/src/api/
git commit -m "feat: add API client, SSE helper, and TypeScript types"
```

---

### Task 7: Layout + Routing

**Files:**
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/StatusBadge.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`

**Step 1: Create Layout component**

Create `frontend/src/components/Layout.tsx`:

```tsx
import { Link, Outlet, useLocation } from 'react-router-dom'

export default function Layout() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-gray-900">
            External Intelligence Platform
          </Link>
          <Link
            to="/jobs/new"
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            New Monitoring Job
          </Link>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
```

**Step 2: Create StatusBadge component**

Create `frontend/src/components/StatusBadge.tsx`:

```tsx
const STATUS_STYLES: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  paused: 'bg-yellow-100 text-yellow-800',
  needs_reagent: 'bg-red-100 text-red-800',
}

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || 'bg-gray-100 text-gray-800'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
```

**Step 3: Create placeholder pages**

Create `frontend/src/pages/Dashboard.tsx`:

```tsx
export default function Dashboard() {
  return <div>Dashboard placeholder</div>
}
```

Create `frontend/src/pages/JobCreate.tsx`:

```tsx
export default function JobCreate() {
  return <div>Job Create placeholder</div>
}
```

Create `frontend/src/pages/JobDetail.tsx`:

```tsx
export default function JobDetail() {
  return <div>Job Detail placeholder</div>
}
```

Create `frontend/src/pages/ResultsViewer.tsx`:

```tsx
export default function ResultsViewer() {
  return <div>Results Viewer placeholder</div>
}
```

**Step 4: Wire up routing in App.tsx**

Replace `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import JobCreate from './pages/JobCreate'
import JobDetail from './pages/JobDetail'
import ResultsViewer from './pages/ResultsViewer'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/jobs/new" element={<JobCreate />} />
          <Route path="/jobs/:jobId" element={<JobDetail />} />
          <Route path="/jobs/:jobId/results/:runId" element={<ResultsViewer />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
```

**Step 5: Verify it compiles and runs**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`
Expected: No errors.

**Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: add layout, routing, and placeholder pages"
```

---

### Task 8: Dashboard Page

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/components/JobCard.tsx`

**Step 1: Create JobCard component**

Create `frontend/src/components/JobCard.tsx`:

```tsx
import { Link } from 'react-router-dom'
import type { Job } from '../api/types'
import StatusBadge from './StatusBadge'
import { triggerRun, patchJob, deleteJob } from '../api/client'

interface Props {
  job: Job
  onUpdate: () => void
}

export default function JobCard({ job, onUpdate }: Props) {
  const handleRunNow = async () => {
    await triggerRun(job.id)
    onUpdate()
  }

  const handleTogglePause = async () => {
    const newStatus = job.status === 'active' ? 'paused' : 'active'
    await patchJob(job.id, { status: newStatus })
    onUpdate()
  }

  const handleDelete = async () => {
    if (!confirm(`Delete "${job.name}"?`)) return
    await deleteJob(job.id)
    onUpdate()
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <Link to={`/jobs/${job.id}`} className="text-lg font-semibold text-gray-900 hover:text-blue-600">
          {job.name}
        </Link>
        <StatusBadge status={job.status} />
      </div>
      <p className="text-sm text-gray-500 mb-1 truncate">{job.target_url}</p>
      {job.description && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{job.description}</p>
      )}
      <div className="text-xs text-gray-400 mb-3">
        Schedule: <code className="bg-gray-100 px-1 rounded">{job.schedule}</code>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleRunNow}
          className="text-xs px-3 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
        >
          Run Now
        </button>
        <button
          onClick={handleTogglePause}
          className="text-xs px-3 py-1 bg-gray-50 text-gray-700 rounded hover:bg-gray-100"
        >
          {job.status === 'active' ? 'Pause' : 'Resume'}
        </button>
        <button
          onClick={handleDelete}
          className="text-xs px-3 py-1 bg-red-50 text-red-700 rounded hover:bg-red-100"
        >
          Delete
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Implement Dashboard page**

Replace `frontend/src/pages/Dashboard.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Job } from '../api/types'
import { listJobs } from '../api/client'
import JobCard from '../components/JobCard'

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)

  const fetchJobs = async () => {
    try {
      const data = await listJobs()
      setJobs(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchJobs() }, [])

  if (loading) {
    return <p className="text-gray-500">Loading jobs...</p>
  }

  if (jobs.length === 0) {
    return (
      <div className="text-center py-16">
        <h2 className="text-xl font-semibold text-gray-700 mb-2">No monitoring jobs yet</h2>
        <p className="text-gray-500 mb-6">Create your first job to start monitoring external sources.</p>
        <Link
          to="/jobs/new"
          className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700"
        >
          Create Monitoring Job
        </Link>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-800 mb-4">Monitoring Jobs</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {jobs.map((job) => (
          <JobCard key={job.id} job={job} onUpdate={fetchJobs} />
        ))}
      </div>
    </div>
  )
}
```

**Step 3: Verify it compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`
Expected: No errors.

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: implement dashboard page with job cards"
```

---

### Task 9: Job Creation Page

**Files:**
- Modify: `frontend/src/pages/JobCreate.tsx`
- Create: `frontend/src/components/AgentFeed.tsx`
- Create: `frontend/src/components/ExtractionPreview.tsx`
- Create: `frontend/src/components/ChatInput.tsx`

**Step 1: Create AgentFeed component**

Create `frontend/src/components/AgentFeed.tsx`:

```tsx
import type { AgentEvent } from '../api/types'

interface Props {
  events: AgentEvent[]
}

export default function AgentFeed({ events }: Props) {
  return (
    <div className="space-y-2">
      {events.map((event, i) => (
        <div key={i} className="flex items-start gap-2">
          <EventIcon type={event.type} />
          <EventContent event={event} />
        </div>
      ))}
    </div>
  )
}

function EventIcon({ type }: { type: string }) {
  const icons: Record<string, string> = {
    status: 'text-blue-500',
    page_fetched: 'text-green-500',
    thinking: 'text-purple-500',
    extraction_test: 'text-orange-500',
    proposal: 'text-indigo-500',
    done: 'text-green-600',
    error: 'text-red-500',
  }
  const color = icons[type] || 'text-gray-400'
  return <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${color} bg-current`} />
}

function EventContent({ event }: { event: AgentEvent }) {
  switch (event.type) {
    case 'status':
      return <p className="text-sm text-gray-600">{event.message}</p>
    case 'page_fetched':
      return (
        <p className="text-sm text-gray-600">
          Fetched <code className="bg-gray-100 px-1 rounded text-xs">{event.url}</code>
          {event.content_length && ` (${Math.round(event.content_length / 1024)}KB)`}
        </p>
      )
    case 'thinking':
      return <p className="text-sm text-purple-600 italic">{event.message}</p>
    case 'extraction_test':
      return (
        <div>
          <p className="text-sm text-gray-600">
            Tested selectors — found <strong>{event.count}</strong> items
          </p>
        </div>
      )
    case 'proposal':
      return <p className="text-sm font-medium text-indigo-700">Ready for your review</p>
    case 'done':
      return <p className="text-sm font-medium text-green-700">{event.message || 'Complete'}</p>
    case 'error':
      return <p className="text-sm text-red-600">{event.message}</p>
    default:
      return <p className="text-sm text-gray-500">{event.message || event.type}</p>
  }
}
```

**Step 2: Create ExtractionPreview component**

Create `frontend/src/components/ExtractionPreview.tsx`:

```tsx
import type { ExtractedItem } from '../api/types'

interface Props {
  items: ExtractedItem[]
  selectors?: Record<string, string>
}

export default function ExtractionPreview({ items, selectors }: Props) {
  if (items.length === 0) return null

  const columns = Object.keys(items[0]).filter(k => k !== 'is_new')

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {selectors && (
        <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
          <p className="text-xs text-gray-500 font-medium">Extraction Selectors</p>
          <div className="flex flex-wrap gap-2 mt-1">
            {Object.entries(selectors).map(([field, selector]) => (
              <span key={field} className="text-xs bg-white px-2 py-1 rounded border border-gray-200">
                <span className="font-medium">{field}:</span> <code>{selector}</code>
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              {columns.map(col => (
                <th key={col} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {items.map((item, i) => (
              <tr key={i} className="hover:bg-gray-50">
                {columns.map(col => (
                  <td key={col} className="px-4 py-2 text-gray-700 max-w-xs truncate">
                    {typeof item[col] === 'string' && item[col]?.startsWith('http')
                      ? <a href={item[col] as string} target="_blank" className="text-blue-600 hover:underline">{item[col] as string}</a>
                      : String(item[col] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

**Step 3: Create ChatInput component**

Create `frontend/src/components/ChatInput.tsx`:

```tsx
import { useState } from 'react'

interface Props {
  onSend: (message: string) => void
  placeholder?: string
  disabled?: boolean
}

export default function ChatInput({ onSend, placeholder = 'Refine your request...', disabled = false }: Props) {
  const [value, setValue] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!value.trim() || disabled) return
    onSend(value.trim())
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Send
      </button>
    </form>
  )
}
```

**Step 4: Implement the JobCreate page**

Replace `frontend/src/pages/JobCreate.tsx`:

```tsx
import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import type { AgentEvent, ExtractedItem } from '../api/types'
import { createSession, sendMessage, confirmSession, rejectSession } from '../api/client'
import { subscribeToStream } from '../api/sse'
import AgentFeed from '../components/AgentFeed'
import ExtractionPreview from '../components/ExtractionPreview'
import ChatInput from '../components/ChatInput'

type Phase = 'input' | 'running' | 'proposal' | 'done'

export default function JobCreate() {
  const navigate = useNavigate()
  const [request, setRequest] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>('input')
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [proposal, setProposal] = useState<AgentEvent | null>(null)
  const [sampleItems, setSampleItems] = useState<ExtractedItem[]>([])
  const [selectors, setSelectors] = useState<Record<string, string>>({})

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!request.trim()) return

    setPhase('running')
    setEvents([])
    setProposal(null)
    setSampleItems([])

    const { session_id } = await createSession(request)
    setSessionId(session_id)

    subscribeToStream(
      session_id,
      (event) => {
        setEvents(prev => [...prev, event])

        if (event.type === 'extraction_test') {
          setSampleItems(event.sample_items || [])
          setSelectors(event.selectors || {})
        }

        if (event.type === 'proposal') {
          setProposal(event)
          setSampleItems(event.sample_data || [])
          setPhase('proposal')
        }

        if (event.type === 'done') {
          setPhase('done')
          // If job was created, redirect to dashboard after a short delay
          if (event.status === 'completed') {
            setTimeout(() => navigate('/'), 1500)
          }
        }
      },
      () => {
        // On error, stay on page
      },
    )
  }, [request, navigate])

  const handleConfirm = useCallback(async () => {
    if (!sessionId) return
    setPhase('running')
    await confirmSession(sessionId)
  }, [sessionId])

  const handleReject = useCallback(async () => {
    if (!sessionId) return
    await rejectSession(sessionId)
    setPhase('input')
    setEvents([])
    setSessionId(null)
  }, [sessionId])

  const handleRefine = useCallback(async (message: string) => {
    if (!sessionId) return
    setPhase('running')
    setEvents(prev => [...prev, { type: 'status', message: `You: ${message}` }])
    await sendMessage(sessionId, message)
  }, [sessionId])

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-lg font-semibold text-gray-800 mb-6">New Monitoring Job</h2>

      {/* Input phase */}
      {phase === 'input' && (
        <form onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            What do you want to monitor?
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="e.g. Monitor homeaffairs.gov.au for new media releases"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <button
              type="submit"
              disabled={!request.trim()}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              Start
            </button>
          </div>
        </form>
      )}

      {/* Agent activity feed */}
      {events.length > 0 && (
        <div className="mt-6 bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-3">Agent Activity</h3>
          <AgentFeed events={events} />
        </div>
      )}

      {/* Extraction preview */}
      {sampleItems.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Extracted Data Preview</h3>
          <ExtractionPreview items={sampleItems} selectors={selectors} />
        </div>
      )}

      {/* Proposal review */}
      {phase === 'proposal' && proposal && (
        <div className="mt-6 bg-indigo-50 border border-indigo-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-indigo-800 mb-2">Proposed Configuration</h3>
          {proposal.message && (
            <p className="text-sm text-gray-700 mb-4">{proposal.message}</p>
          )}
          <div className="flex gap-3 mb-4">
            <button
              onClick={handleConfirm}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700"
            >
              Approve & Create Job
            </button>
            <button
              onClick={handleReject}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-300"
            >
              Start Over
            </button>
          </div>
          <ChatInput
            onSend={handleRefine}
            placeholder="Or refine: e.g. 'Only monitor articles from 2026'"
          />
        </div>
      )}

      {/* Done state */}
      {phase === 'done' && (
        <div className="mt-6 bg-green-50 border border-green-200 rounded-lg p-4 text-center">
          <p className="text-green-800 font-medium">Monitoring job created! Redirecting to dashboard...</p>
        </div>
      )}

      {/* Loading indicator */}
      {phase === 'running' && (
        <div className="mt-4 flex items-center gap-2 text-sm text-gray-500">
          <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />
          Agent is working...
        </div>
      )}
    </div>
  )
}
```

**Step 5: Verify it compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`
Expected: No errors.

**Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: implement job creation page with live agent feed and proposal review"
```

---

### Task 10: Job Detail Page

**Files:**
- Modify: `frontend/src/pages/JobDetail.tsx`

**Step 1: Implement the page**

Replace `frontend/src/pages/JobDetail.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import type { Job, ExtractionConfig, RunResult } from '../api/types'
import { getJob, getResults, triggerRun, patchJob, deleteJob } from '../api/client'
import StatusBadge from '../components/StatusBadge'

export default function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [job, setJob] = useState<Job | null>(null)
  const [config, setConfig] = useState<ExtractionConfig | null>(null)
  const [results, setResults] = useState<RunResult[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    if (!jobId) return
    try {
      const [jobData, resultsData] = await Promise.all([
        getJob(jobId),
        getResults(jobId),
      ])
      setJob(jobData.job)
      setConfig(jobData.config)
      setResults(resultsData)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [jobId])

  const handleRunNow = async () => {
    if (!jobId) return
    await triggerRun(jobId)
    fetchData()
  }

  const handleTogglePause = async () => {
    if (!jobId || !job) return
    const newStatus = job.status === 'active' ? 'paused' : 'active'
    await patchJob(jobId, { status: newStatus })
    fetchData()
  }

  const handleDelete = async () => {
    if (!jobId || !confirm('Delete this job?')) return
    await deleteJob(jobId)
    navigate('/')
  }

  if (loading) return <p className="text-gray-500">Loading...</p>
  if (!job) return <p className="text-red-500">Job not found</p>

  return (
    <div>
      <Link to="/" className="text-sm text-blue-600 hover:underline mb-4 inline-block">Back to Dashboard</Link>

      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{job.name}</h2>
            <p className="text-sm text-gray-500 mt-1">{job.target_url}</p>
          </div>
          <StatusBadge status={job.status} />
        </div>

        {job.description && <p className="text-sm text-gray-600 mb-4">{job.description}</p>}

        <div className="grid grid-cols-2 gap-4 text-sm mb-4">
          <div>
            <span className="text-gray-500">Schedule:</span>{' '}
            <code className="bg-gray-100 px-2 py-0.5 rounded">{job.schedule}</code>
          </div>
          <div>
            <span className="text-gray-500">Created:</span>{' '}
            {new Date(job.created_at).toLocaleDateString()}
          </div>
        </div>

        {config && config.selectors && (
          <div className="mb-4">
            <p className="text-xs text-gray-500 font-medium mb-1">Extraction Selectors</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(config.selectors).map(([field, selector]) => (
                <span key={field} className="text-xs bg-gray-50 px-2 py-1 rounded border">
                  <span className="font-medium">{field}:</span> <code>{selector}</code>
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <button onClick={handleRunNow} className="text-sm px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Run Now
          </button>
          <button onClick={handleTogglePause} className="text-sm px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
            {job.status === 'active' ? 'Pause' : 'Resume'}
          </button>
          <button onClick={handleDelete} className="text-sm px-4 py-2 bg-red-50 text-red-700 rounded-lg hover:bg-red-100">
            Delete
          </button>
        </div>
      </div>

      <h3 className="text-lg font-semibold text-gray-800 mb-3">Run History</h3>
      {results.length === 0 ? (
        <p className="text-gray-500 text-sm">No runs yet. Click "Run Now" to trigger the first extraction.</p>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Items</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">New</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {results.sort((a, b) => b.ran_at.localeCompare(a.ran_at)).map((r) => (
                <tr key={r.run_id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-700">{new Date(r.ran_at).toLocaleString()}</td>
                  <td className="px-4 py-2 text-gray-700">{r.items_total}</td>
                  <td className="px-4 py-2">
                    {r.items_new > 0
                      ? <span className="text-green-600 font-medium">{r.items_new} new</span>
                      : <span className="text-gray-400">0</span>
                    }
                  </td>
                  <td className="px-4 py-2">{r.success ? <span className="text-green-600">OK</span> : <span className="text-red-600">Failed</span>}</td>
                  <td className="px-4 py-2">
                    <Link to={`/jobs/${jobId}/results/${r.run_id}`} className="text-blue-600 hover:underline text-xs">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Verify it compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/pages/JobDetail.tsx
git commit -m "feat: implement job detail page with run history"
```

---

### Task 11: Results Viewer Page

**Files:**
- Modify: `frontend/src/pages/ResultsViewer.tsx`

**Step 1: Implement the page**

Replace `frontend/src/pages/ResultsViewer.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import type { RunResult } from '../api/types'
import { getResult } from '../api/client'
import ExtractionPreview from '../components/ExtractionPreview'

export default function ResultsViewer() {
  const { jobId, runId } = useParams<{ jobId: string; runId: string }>()
  const [result, setResult] = useState<RunResult | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!jobId || !runId) return
    getResult(jobId, runId)
      .then(setResult)
      .finally(() => setLoading(false))
  }, [jobId, runId])

  if (loading) return <p className="text-gray-500">Loading...</p>
  if (!result) return <p className="text-red-500">Result not found</p>

  return (
    <div>
      <Link to={`/jobs/${jobId}`} className="text-sm text-blue-600 hover:underline mb-4 inline-block">
        Back to Job
      </Link>

      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">Run Result</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
          <div>
            <span className="text-gray-500 block">Run ID</span>
            <code className="text-xs">{result.run_id}</code>
          </div>
          <div>
            <span className="text-gray-500 block">Time</span>
            {new Date(result.ran_at).toLocaleString()}
          </div>
          <div>
            <span className="text-gray-500 block">Total Items</span>
            <span className="text-lg font-semibold">{result.items_total}</span>
          </div>
          <div>
            <span className="text-gray-500 block">New Items</span>
            <span className="text-lg font-semibold text-green-600">{result.items_new}</span>
          </div>
        </div>
        {!result.success && result.error && (
          <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700 mb-4">
            {result.error}
          </div>
        )}
      </div>

      <h3 className="text-lg font-semibold text-gray-800 mb-3">Extracted Items</h3>
      <ExtractionPreview items={result.items} />
    </div>
  )
}
```

**Step 2: Verify it compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/pages/ResultsViewer.tsx
git commit -m "feat: implement results viewer page"
```

---

### Task 12: Final Integration and Verification

**Files:**
- Modify: `requirements.txt` (ensure sse-starlette is listed)
- No new files

**Step 1: Verify backend tests all pass**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS.

**Step 2: Verify frontend compiles**

Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npx tsc --noEmit`
Expected: No errors.

**Step 3: Start both servers and manually test**

Terminal 1 (backend):
Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform" && source .venv/bin/activate && export $(cat .env | xargs) && uvicorn eip.main:app --port 8000 --reload`

Terminal 2 (frontend):
Run: `cd "/Users/sam_hudson/Documents/MyCode/External Intelligence Platform/frontend" && npm run dev`

Open http://localhost:5173 — should see empty dashboard with "Create Monitoring Job" button.

**Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final integration verification for V2"
```

---

## Summary

| Task | What it builds | Type |
|------|---------------|------|
| 1 | Agent event types (dataclasses) | Backend |
| 2 | Streaming setup agent (run_streaming) | Backend |
| 3 | Session manager (in-memory) | Backend |
| 4 | SSE endpoints + session API + CORS | Backend |
| 5 | React + Vite + Tailwind scaffolding | Frontend |
| 6 | API client + SSE helper + types | Frontend |
| 7 | Layout + routing + placeholder pages | Frontend |
| 8 | Dashboard page with job cards | Frontend |
| 9 | Job creation page (agent feed, preview, chat) | Frontend |
| 10 | Job detail page with run history | Frontend |
| 11 | Results viewer page | Frontend |
| 12 | Final integration verification | Both |
