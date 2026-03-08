"""Test business services."""

import pytest

from workflow_manager.core.models import JobCreate, JobStatus
from workflow_manager.core.services import JobService


@pytest.fixture
def job_service(test_session):
    """Create job service with test session."""
    # Note: This would need to be adjusted to use test session
    return JobService()


def test_create_job(job_service):
    """Test job creation."""
    data = JobCreate(task_id=123, project_name="test_project")
    job = job_service.create_job(data)

    assert job.id > 0
    assert job.task_id == 123
    assert job.project_name == "test_project"
    assert job.status == JobStatus.PENDING
    assert job.retry_times == 0


def test_get_job(job_service):
    """Test getting a job."""
    # Create a job first
    data = JobCreate(task_id=456, project_name="test_project")
    created = job_service.create_job(data)

    # Get the job
    retrieved = job_service.get_job(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.task_id == 456


def test_list_jobs(job_service):
    """Test listing jobs."""
    # Create multiple jobs
    for i in range(3):
        data = JobCreate(task_id=100 + i, project_name="list_test")
        job_service.create_job(data)

    # List jobs
    items, total = job_service.list_jobs(page=1, page_size=10)
    assert len(items) >= 3
    assert total >= 3


def test_get_runnable_job(job_service):
    """Test getting a runnable job."""
    # Create a pending job
    data = JobCreate(task_id=789, project_name="runnable_test")
    job_service.create_job(data)

    # Get runnable job
    runnable = job_service.get_runnable_job()
    assert runnable is not None
    assert runnable.status == JobStatus.RUNNING
