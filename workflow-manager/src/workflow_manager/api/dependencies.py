"""FastAPI dependencies."""

from ..core.services import JobService

_job_service: JobService | None = None


def get_job_service() -> JobService:
    """Get job service instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service
