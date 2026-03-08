"""Business logic services with modern Python 3.13 features."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from .models import Job, JobCreate, JobStatus, JobUpdate
from .repositories import JobRepository


@dataclass(slots=True)
class JobService:
    """Service for job business logic using modern patterns."""

    repository: JobRepository = field(default_factory=JobRepository)

    def create_job(self, data: JobCreate) -> Job:
        """Create a new job.

        Args:
            data: Job creation data

        Returns:
            Created job instance

        Raises:
            ValueError: If data is invalid
        """
        job = Job(
            task_id=data.task_id,
            project_name=data.project_name,
            status=JobStatus.PENDING,
            retry_times=0,
            events="",
        )
        return self.repository.create(job)

    def get_job(self, job_id: int) -> Job | None:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job instance or None if not found
        """
        return self.repository.get_by_id(job_id)

    def list_jobs(
        self,
        *,
        project_name: str | None = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "created_time",
        sort_order: str = "desc",
    ) -> tuple[Sequence[Job], int]:
        """List jobs with pagination.

        Args:
            project_name: Filter by project name
            page: Page number (1-indexed)
            page_size: Items per page
            sort_by: Column to sort by
            sort_order: "asc" or "desc"

        Returns:
            Tuple of (job list, total count)
        """
        return self.repository.list_jobs(
            project_name=project_name,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def update_job(self, job_id: int, data: JobUpdate) -> Job | None:
        """Update job with provided data.

        Args:
            job_id: Job identifier
            data: Fields to update

        Returns:
            Updated job or None if not found
        """
        job = self.repository.get_by_id(job_id)
        if not job:
            return None

        # Apply updates using pattern matching
        match data:
            case JobUpdate(status=status) if status is not None:
                job.status = status
            case _:
                pass

        if data.retry_times is not None:
            job.retry_times = data.retry_times
        if data.events is not None:
            job.events = data.events

        return self.repository.update(job)

    def get_runnable_job(self) -> Job | None:
        """Get one runnable job and mark it as running.

        Atomically acquires a pending or retry job and transitions it to RUNNING.

        Returns:
            Job ready for execution, or None if no jobs available
        """
        count = self.repository.count_pending()
        if count == 0:
            return None
        return self.repository.get_one_pending_for_update()

    def update_job_status(
        self, job_id: int, status: JobStatus, *, events: str | None = None
    ) -> Job | None:
        """Update job status and optionally add events.

        Args:
            job_id: Job identifier
            status: New status
            events: Event log to append

        Returns:
            Updated job or None if not found
        """
        job = self.repository.update_status(job_id, status)
        if job and events:
            job.events = f"{job.events}\n{events}" if job.events else events
            return self.repository.update(job)
        return job

    def transition_job_status(self, job: Job, target_status: JobStatus) -> bool:
        """Transition job to target status with validation.

        Args:
            job: Job instance
            target_status: Desired status

        Returns:
            True if transition succeeded, False otherwise

        Raises:
            ValueError: If transition is invalid
        """
        # Validate status transitions using match-case
        match (job.status, target_status):
            case (JobStatus.PENDING, JobStatus.RUNNING):
                allowed = True
            case (JobStatus.RETRY, JobStatus.RUNNING):
                allowed = True
            case (JobStatus.RUNNING, JobStatus.SUCCESS | JobStatus.FAILED | JobStatus.RETRY):
                allowed = True
            case (JobStatus.RETRY, JobStatus.FAILED):
                allowed = True
            case _:
                allowed = False

        if not allowed:
            raise ValueError(
                f"Invalid status transition: {job.status.name} -> {target_status.name}"
            )

        job.status = target_status
        self.repository.update(job)
        return True
