import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from eip.store.json_store import JsonStore

logger = logging.getLogger(__name__)


class JobScheduler:
    def __init__(self, store: JsonStore) -> None:
        self.store = store
        self._scheduler = BackgroundScheduler()

    @property
    def is_running(self) -> bool:
        return self._scheduler.running

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def schedule_job(self, job_id: str) -> None:
        job = self.store.load("jobs", job_id)
        if job is None:
            logger.warning(f"Cannot schedule unknown job: {job_id}")
            return

        cron_expr = job.get("schedule", "0 * * * *")
        trigger = CronTrigger.from_crontab(cron_expr)

        self._scheduler.add_job(
            self._run_job_sync,
            trigger=trigger,
            id=job_id,
            args=[job_id],
            replace_existing=True,
        )
        logger.info(f"Scheduled job {job_id} with cron: {cron_expr}")

    def unschedule_job(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def has_job(self, job_id: str) -> bool:
        return self._scheduler.get_job(job_id) is not None

    def load_all_jobs(self) -> None:
        jobs = self.store.list("jobs")
        for job in jobs:
            if job.get("status") == "active":
                self.schedule_job(job["id"])

    def _run_job_sync(self, job_id: str) -> None:
        from eip.runner.automated_runner import run_job

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(run_job(job_id, self.store))
            if result.get("success"):
                logger.info(
                    f"Job {job_id}: {result.get('items_new', 0)} new items"
                )
            else:
                logger.warning(f"Job {job_id} failed: {result.get('error')}")
        finally:
            loop.close()
