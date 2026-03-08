"""Task scheduler implementation."""

import asyncio
import logging
import threading

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..core.models import Job
from ..core.services import JobService

logger = logging.getLogger(__name__)


class Scheduler:
    """Task scheduler."""

    def __init__(self, job_service: JobService, interval_seconds: int = 5):
        """Initialize scheduler.

        Args:
            job_service: Job service instance
            interval_seconds: Polling interval in seconds
        """
        self.job_service = job_service
        self.interval_seconds = interval_seconds
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(
            self._schedule_one, "interval", seconds=interval_seconds, id="schedule_jobs"
        )
        self._running = False

    def start(self) -> None:
        """Start the scheduler."""
        if not self._running:
            self.scheduler.start()
            self._running = True
            logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Scheduler stopped")

    async def schedule_one(self) -> Job | None:
        """Schedule one job.

        Returns:
            The scheduled job or None if no job is available
        """
        return await self._schedule_one()

    async def _schedule_one(self) -> Job | None:
        """Internal method to schedule one job.

        Note: This scheduler only detects available jobs. Actual job execution
        is handled by workers via gRPC GetJob() calls. Jobs are already marked
        as RUNNING by get_runnable_job(), so no further action is needed here.
        """
        try:
            # Check if there are runnable jobs
            # This is just for logging/monitoring purposes
            # Workers will actually fetch jobs via gRPC
            count = await asyncio.to_thread(self.job_service.repository.count_pending)
            if count > 0:
                logger.debug(f"Available jobs for scheduling: {count}")
            return None
        except Exception as e:
            logger.error(f"Error checking jobs: {e}", exc_info=True)
            return None

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running


_scheduler: Scheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler(interval_seconds: int = 5) -> Scheduler:
    """Get global scheduler instance.

    Args:
        interval_seconds: Polling interval in seconds

    Returns:
        Scheduler instance
    """
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                job_service = JobService()
                _scheduler = Scheduler(job_service, interval_seconds)
    return _scheduler


def reset_scheduler() -> None:
    """Reset scheduler (useful for testing)."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
    _scheduler = None
