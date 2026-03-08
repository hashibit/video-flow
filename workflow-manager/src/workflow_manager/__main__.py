"""Main application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api.handlers import job_handler, ping
from .config import get_settings
from .core.database import init_db
from .scheduler import get_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan manager."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Start gRPC server if enabled
    grpc_server = None
    if settings.grpc_enabled:
        from .grpc import serve_grpc, stop_grpc_server

        grpc_server = serve_grpc(settings.grpc_endpoint)
        logger.info(f"gRPC server started on {settings.grpc_endpoint}")

    # Start scheduler if enabled
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = get_scheduler(settings.scheduler_interval_seconds)
        scheduler.start()
        logger.info("Scheduler started")

    yield

    # Cleanup
    if scheduler:
        scheduler.stop()
        logger.info("Scheduler stopped")

    if grpc_server:
        from .grpc import stop_grpc_server

        stop_grpc_server(grpc_server)
        logger.info("gRPC server stopped")

    logger.info("Application stopped")


# Create FastAPI app
app = FastAPI(
    title="Workflow Manager",
    description="Workflow task management system",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(ping.router)
app.include_router(job_handler.router)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": str(exc)},
    )


def main() -> None:
    """Run the application."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
