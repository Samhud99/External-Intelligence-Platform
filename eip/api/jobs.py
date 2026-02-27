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
    """Get a SetupAgent instance. Overridden in tests via patch."""
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
