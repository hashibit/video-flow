"""Data repositories with modern Python 3.13 features."""

from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult

from .database import get_session
from .models import Job, JobStatus

# Allowed sort columns to prevent dunder attribute access
_ALLOWED_SORT_COLUMNS = frozenset(
    {"id", "created_time", "updated_time", "status", "project_name", "retry_times"}
)


class JobRepository:
    """Repository for Job operations using modern Python patterns."""

    __slots__ = ()  # Memory optimization

    def create(self, job: Job) -> Job:
        """Create a new job.

        Args:
            job: Job instance to create

        Returns:
            Created job with assigned ID

        Raises:
            SQLAlchemyError: If database operation fails
        """
        with get_session() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def get_by_id(self, job_id: int) -> Job | None:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job instance or None if not found
        """
        with get_session() as session:
            stmt = select(Job).where(Job.id == job_id, Job.deleted == 0)
            return cast(Job | None, session.execute(stmt).scalar_one_or_none())

    def list_jobs(
        self,
        *,
        project_name: str | None = None,
        status: JobStatus | None = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "created_time",
        sort_order: str = "desc",
    ) -> tuple[Sequence[Job], int]:
        """List jobs with filters and pagination.

        Args:
            project_name: Filter by project name
            status: Filter by job status
            page: Page number (1-indexed)
            page_size: Items per page
            sort_by: Column name to sort by
            sort_order: "asc" or "desc"

        Returns:
            Tuple of (job list, total count)
        """
        with get_session() as session:
            query = select(Job).where(Job.deleted == 0)

            if project_name:
                query = query.where(Job.project_name == project_name)
            if status is not None:
                query = query.where(Job.status == status)

            # Get total count
            count_stmt = select(func.count()).select_from(query.subquery())
            total = session.execute(count_stmt).scalar() or 0

            # Apply sorting (whitelist to prevent dunder attribute access)
            safe_sort_by = sort_by if sort_by in _ALLOWED_SORT_COLUMNS else "created_time"
            sort_column = getattr(Job, safe_sort_by)
            match sort_order:
                case "desc":
                    query = query.order_by(sort_column.desc())
                case _:
                    query = query.order_by(sort_column.asc())

            # Apply pagination
            query = query.offset((page - 1) * page_size).limit(page_size)

            items = session.execute(query).scalars().all()
            return items, total

    def update(self, job: Job) -> Job:
        """Update an existing job.

        Args:
            job: Job instance with updated fields

        Returns:
            Updated job instance (refreshed from database)
        """
        with get_session() as session:
            merged = session.merge(job)
            session.commit()
            session.refresh(merged)
            return merged

    def update_status(self, job_id: int, status: JobStatus) -> Job | None:
        """Update job status atomically.

        Args:
            job_id: Job identifier
            status: New status

        Returns:
            Updated job or None if not found
        """
        with get_session() as session:
            stmt = (
                update(Job)
                .where(Job.id == job_id)
                .values(status=status, updated_time=datetime.now())
            )
            session.execute(stmt)
            session.commit()
            return self.get_by_id(job_id)

    def count_pending(self) -> int:
        """Count pending and retry jobs available for scheduling.

        Returns:
            Count of schedulable jobs
        """
        with get_session() as session:
            stmt = select(func.count()).where(
                Job.status.in_([JobStatus.PENDING, JobStatus.RETRY]), Job.deleted == 0
            )
            return session.execute(stmt).scalar() or 0

    def get_one_pending_for_update(self) -> Job | None:
        """Get one pending or retry job and lock it for update.

        Uses SELECT FOR UPDATE for atomic job acquisition.
        Priority: PENDING jobs first, then RETRY jobs ordered by retry_times.

        Returns:
            Locked job transitioned to RUNNING, or None if no jobs available
        """
        with get_session() as session:
            # First try to get a PENDING job
            stmt = (
                select(Job)
                .where(Job.status == JobStatus.PENDING, Job.deleted == 0)
                .order_by(Job.created_time.asc())
                .with_for_update()
                .limit(1)
            )
            job = cast(Job | None, session.execute(stmt).scalar_one_or_none())

            # If no PENDING job, try to get a RETRY job
            if job is None:
                stmt = (
                    select(Job)
                    .where(Job.status == JobStatus.RETRY, Job.deleted == 0)
                    .order_by(Job.retry_times.asc(), Job.created_time.asc())
                    .with_for_update()
                    .limit(1)
                )
                job = cast(Job | None, session.execute(stmt).scalar_one_or_none())

            if job:
                job.status = JobStatus.RUNNING
                job.updated_time = datetime.now()
                session.commit()
                session.refresh(job)

            return job

    def delete(self, job_id: int) -> bool:
        """Soft delete a job.

        Args:
            job_id: Job identifier

        Returns:
            True if job was deleted, False if not found
        """
        with get_session() as session:
            stmt = (
                update(Job)
                .where(Job.id == job_id)
                .values(deleted=1, updated_time=datetime.now())
            )
            result = cast(CursorResult[tuple[()]], session.execute(stmt))
            session.commit()
            return bool(result.rowcount > 0)
