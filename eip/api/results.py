from fastapi import APIRouter, HTTPException

from eip.store.json_store import JsonStore


def create_results_router(store: JsonStore) -> APIRouter:
    r = APIRouter()

    @r.get("/jobs/{job_id}/results")
    def list_results(job_id: str):
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return store.list(f"results/{job_id}")

    @r.get("/jobs/{job_id}/results/{run_id}")
    def get_result(job_id: str, run_id: str):
        job = store.load("jobs", job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        result = store.load(f"results/{job_id}", run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found")
        return result

    return r
