from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from eip.scheduler.scheduler import JobScheduler
from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


@pytest.fixture
def scheduler(store: JsonStore) -> JobScheduler:
    return JobScheduler(store=store)


def test_scheduler_starts_and_stops(scheduler: JobScheduler) -> None:
    scheduler.start()
    assert scheduler.is_running
    scheduler.stop()
    assert not scheduler.is_running


def test_schedule_job(scheduler: JobScheduler, store: JsonStore) -> None:
    store.save("jobs", "job_1", {
        "id": "job_1",
        "name": "Test",
        "target_url": "https://example.com",
        "schedule": "0 * * * *",
        "status": "active",
    })
    scheduler.start()
    scheduler.schedule_job("job_1")
    assert scheduler.has_job("job_1")
    scheduler.stop()


def test_unschedule_job(scheduler: JobScheduler, store: JsonStore) -> None:
    store.save("jobs", "job_1", {
        "id": "job_1",
        "name": "Test",
        "target_url": "https://example.com",
        "schedule": "0 * * * *",
        "status": "active",
    })
    scheduler.start()
    scheduler.schedule_job("job_1")
    scheduler.unschedule_job("job_1")
    assert not scheduler.has_job("job_1")
    scheduler.stop()


def test_load_all_active_jobs(scheduler: JobScheduler, store: JsonStore) -> None:
    store.save("jobs", "active_1", {
        "id": "active_1",
        "schedule": "0 * * * *",
        "status": "active",
    })
    store.save("jobs", "paused_1", {
        "id": "paused_1",
        "schedule": "0 * * * *",
        "status": "paused",
    })
    scheduler.start()
    scheduler.load_all_jobs()
    assert scheduler.has_job("active_1")
    assert not scheduler.has_job("paused_1")
    scheduler.stop()
