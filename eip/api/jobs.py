from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from eip.store.json_store import JsonStore

# Module-level store reference, set by create_jobs_router
_store = None


class CreateJobRequest(BaseModel):
    request: str


class PatchJobRequest(BaseModel):
    status: Optional[str] = None
    schedule: Optional[str] = None


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


def create_jobs_router(store: JsonStore) -> APIRouter:
    global _store
    _store = store
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
        agent = get_setup_agent()
        result = await agent.run(body.request)
        return result

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
