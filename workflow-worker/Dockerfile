# Multi-stage build for Workflow Worker
# Stage 1: Builder
FROM python:3.13-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_CACHE_DIR=/tmp/uv-cache

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies with uv
RUN uv sync --frozen --no-dev --no-editable

# Stage 2: Runtime
FROM python:3.13-slim as runtime

# Set labels
LABEL maintainer="workflow-worker"
LABEL description="Video Inspection Workflow Worker - DDD Architecture"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/workflow/.local/bin:$PATH \
    PYTHONPATH=/app/src:$PYTHONPATH \
    WORKFLOW_HOME=/app \
    WORKFLOW_LOGS=/app/logs

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    # FFmpeg for video processing
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    # Redis client (optional, for caching)
    redis-tools \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r workflow && \
    useradd -r -g workflow -d /app -s /sbin/nologin -c "Workflow Worker" workflow

# Create application directories
RUN mkdir -p /app/src /app/logs /app/tmp && \
    chown -R workflow:workflow /app

# Set working directory
WORKDIR /app

# Copy uv and virtual environment from builder
COPY --from=builder /root/.local/bin/uv /root/.local/bin/uv
COPY --from=builder /build/.venv /app/.venv

# Copy application code
COPY --chown=workflow:workflow src/ /app/src/
COPY --chown=workflow:workflow pyproject.toml /app/

# Copy protobuf files if they exist
COPY --chown=workflow:workflow src/workflow_worker/domain/entities/*.proto /app/src/workflow_worker/domain/entities/ 2>/dev/null || true
COPY --chown=workflow:workflow src/workflow_worker/interfaces/api/*.proto /app/src/workflow_worker/interfaces/api/ 2>/dev/null || true

# Set permissions
RUN chmod -R 755 /app/src && \
    chmod -R 777 /app/logs /app/tmp

# Switch to non-root user
USER workflow

# Expose ports (if needed)
# EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the application
CMD ["python", "-m", "workflow_worker.interfaces.cli.worker"]
