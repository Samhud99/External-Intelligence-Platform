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
