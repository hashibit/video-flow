"""Test API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from workflow_manager.__main__ import app
from workflow_manager.config import reset_settings


@pytest.fixture(scope="function")
async def client():
    """Create test client."""
    reset_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_ping(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_create_job(client: AsyncClient):
    """Test create job endpoint."""
    response = await client.post(
        "/api/v1/job/create_job",
        json={"task_id": 123, "project_name": "test_project"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["id"] > 0


@pytest.mark.asyncio
async def test_get_job(client: AsyncClient):
    """Test get job endpoint."""
    # First create a job
    create_response = await client.post(
        "/api/v1/job/create_job",
        json={"task_id": 456, "project_name": "test_project"},
    )
    job_id = create_response.json()["id"]

    # Get the job
    response = await client.post(
        "/api/v1/job/get_job",
        json={"id": job_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["task_id"] == 456


@pytest.mark.asyncio
async def test_list_jobs(client: AsyncClient):
    """Test list jobs endpoint."""
    response = await client.post(
        "/api/v1/job/list_jobs",
        json={"page": 1, "page_size": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
