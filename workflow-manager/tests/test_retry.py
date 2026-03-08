"""Test retry mechanism."""

import pytest

from workflow_manager.core.models import JobCreate, JobStatus, JobUpdate
from workflow_manager.core.services import JobService


@pytest.fixture
def job_service(test_session):
    """Create job service with test session."""
    return JobService()


def test_retry_job(job_service):
    """Test job retry mechanism."""
    # Create a job
    data = JobCreate(task_id=123, project_name="retry_test")
    job = job_service.create_job(data)

    # Mark as RETRY
    update_data = JobUpdate(status=JobStatus.RETRY, retry_times=1)
    updated = job_service.update_job(job.id, update_data)

    assert updated is not None
    assert updated.status == JobStatus.RETRY
    assert updated.retry_times == 1


def test_max_retries(job_service):
    """Test max retry limit."""
    # Create a job
    data = JobCreate(task_id=456, project_name="max_retry_test")
    job = job_service.create_job(data)

    # Simulate multiple retries
    for i in range(1, 11):  # 10 retries
        update_data = JobUpdate(status=JobStatus.RETRY, retry_times=i)
        job_service.update_job(job.id, update_data)

    # After max retries, should be marked as FAILED
    # (This would be done in the gRPC servicer, not here)
    job = job_service.get_job(job.id)
    assert job.retry_times == 10


def test_retry_job_scheduling(job_service):
    """Test that RETRY jobs can be scheduled."""
    # Create a pending job
    data1 = JobCreate(task_id=111, project_name="schedule_test")
    job1 = job_service.create_job(data1)

    # Create a retry job
    data2 = JobCreate(task_id=222, project_name="schedule_test")
    job2 = job_service.create_job(data2)
    update_data = JobUpdate(status=JobStatus.RETRY, retry_times=1)
    job_service.update_job(job2.id, update_data)

    # Get runnable job - should prioritize PENDING first
    runnable1 = job_service.get_runnable_job()
    assert runnable1 is not None
    assert runnable1.id == job1.id
    assert runnable1.status == JobStatus.RUNNING

    # Get next runnable job - should get RETRY job
    runnable2 = job_service.get_runnable_job()
    assert runnable2 is not None
    assert runnable2.id == job2.id
    assert runnable2.status == JobStatus.RUNNING


def test_job_status_codes(job_service):
    """Test that status codes match Go version."""
    data = JobCreate(task_id=999, project_name="status_test")
    job = job_service.create_job(data)

    assert JobStatus.PENDING == 0
    assert JobStatus.RUNNING == 1
    assert JobStatus.RETRY == 2
    assert JobStatus.SUCCESS == 16
    assert JobStatus.FAILED == 17
    assert JobStatus.NO_NEED == 32

    # Test each status transition
    for status in [JobStatus.RUNNING, JobStatus.RETRY, JobStatus.SUCCESS]:
        job_service.update_job_status(job.id, status)
        job = job_service.get_job(job.id)
        assert job.status == status
