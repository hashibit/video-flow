"""Job API handlers."""

import math
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ...core.models import JobCreate, JobResponse
from ...core.services import JobService

router = APIRouter(prefix="/api/v1/job", tags=["jobs"])

# Singleton service
_job_service: JobService | None = None


def get_job_service() -> JobService:
    """Get job service instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service


# Request models


class CreateJobRequest(BaseModel):
    """Create job request."""

    task_id: int = Field(..., description="Associated task ID")
    project_name: str = Field(..., description="Project name")


class GetJobRequest(BaseModel):
    """Get job request."""

    id: int = Field(..., description="Job ID")


class GetJobTaskRequest(BaseModel):
    """Get job task request."""

    id: int = Field(..., description="Job ID")


class ListJobsRequest(BaseModel):
    """List jobs request."""

    project_name: str | None = Field(None, description="Filter by project name")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Items per page")
    sort_by: str = Field("created_time", description="Sort field")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


# Response models


class CreateJobResponse(BaseModel):
    """Create job response."""

    id: int


class JobTaskResponse(BaseModel):
    """Job task response."""

    task_id: int
    status: str
    # Add other task fields as needed


# API endpoints


@router.post("/create_job", response_model=CreateJobResponse)
async def create_job(request: CreateJobRequest) -> CreateJobResponse:
    """Create a new job."""
    service = get_job_service()
    job_data = JobCreate(task_id=request.task_id, project_name=request.project_name)
    job = service.create_job(job_data)
    return CreateJobResponse(id=job.id)


@router.post("/get_job", response_model=JobResponse)
async def get_job(request: GetJobRequest) -> JobResponse:
    """Get job by ID."""
    service = get_job_service()
    job = service.get_job(request.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {request.id} not found"
        )
    return JobResponse.model_validate(job)


@router.post("/get_job_task", response_model=dict[str, Any])
async def get_job_task(request: GetJobTaskRequest) -> dict[str, Any]:
    """Get job task details (proxy to external API)."""
    service = get_job_service()
    job = service.get_job(request.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {request.id} not found"
        )

    # TODO: Proxy to external API
    # For now, return task info from the job
    return {
        "task_id": job.task_id,
        "job_id": job.id,
        "status": job.status,
        "project_name": job.project_name,
    }


@router.post("/list_jobs", response_model=dict[str, Any])
async def list_jobs(request: ListJobsRequest) -> dict[str, Any]:
    """List jobs with pagination."""
    service = get_job_service()
    items, total = service.list_jobs(
        project_name=request.project_name,
        page=request.page,
        page_size=request.page_size,
        sort_by=request.sort_by,
        sort_order=request.sort_order,
    )

    total_pages = math.ceil(total / request.page_size) if total > 0 else 0

    return {
        "items": [JobResponse.model_validate(job) for job in items],
        "total": total,
        "page": request.page,
        "page_size": request.page_size,
        "total_pages": total_pages,
    }
