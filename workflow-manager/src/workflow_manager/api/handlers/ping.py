"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "message": "Workflow Manager is running"}
