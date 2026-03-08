"""Core data models."""

from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class JobStatus(IntEnum):
    """Job status enumeration.

    Status codes aligned with Go version:
    - PENDING (0): Waiting to be scheduled
    - RUNNING (1): Currently being processed by worker
    - RETRY (2): Failed and will be retried
    - SUCCESS (16): Completed successfully
    - FAILED (17): Failed after max retries
    - NO_NEED (32): Skipped/not needed
    """

    PENDING = 0
    RUNNING = 1
    RETRY = 2
    SUCCESS = 16
    FAILED = 17
    NO_NEED = 32


class Job(Base):
    """Job database model."""

    __tablename__ = "engine_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    project_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Integer, nullable=False, default=JobStatus.PENDING)
    retry_times: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, task_id={self.task_id}, status={self.status})>"


# Pydantic models for API


class JobBase(BaseModel):
    """Base job model."""

    task_id: int = Field(..., description="Associated task ID")
    project_name: str = Field(..., max_length=128, description="Project name")


class JobCreate(JobBase):
    """Job creation model."""

    pass


class JobResponse(JobBase):
    """Job response model."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: JobStatus
    retry_times: int
    events: str
    created_time: datetime
    updated_time: datetime


class JobUpdate(BaseModel):
    """Job update model."""

    status: JobStatus | None = None
    retry_times: int | None = None
    events: str | None = None


class JobListParams(BaseModel):
    """Job list query parameters."""

    project_name: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)
    sort_by: str = "created_time"
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class JobListResponse(BaseModel):
    """Job list response."""

    items: list[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
