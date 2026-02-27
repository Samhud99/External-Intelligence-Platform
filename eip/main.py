from contextlib import asynccontextmanager

from fastapi import FastAPI

from eip.api.jobs import create_jobs_router
from eip.api.results import create_results_router
from eip.config import settings
from eip.scheduler.scheduler import JobScheduler
from eip.store.json_store import JsonStore


def create_app(store=None) -> FastAPI:
    if store is None:
        settings.ensure_dirs()
        store = JsonStore(base_dir=settings.data_dir)

    scheduler = JobScheduler(store=store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler.start()
        scheduler.load_all_jobs()
        yield
        scheduler.stop()

    app = FastAPI(
        title="External Intelligence Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.scheduler = scheduler
    app.include_router(create_jobs_router(store))
    app.include_router(create_results_router(store))
    return app


app = create_app()
