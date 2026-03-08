# Multi-stage Dockerfile for Workflow Manager
# Based on Python 3.13

# Stage 1: Builder stage
FROM python:3.13-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv pip install --system --no-cache \
    fastapi>=0.115.0 \
    uvicorn>=0.32.0 \
    sqlalchemy>=2.0.36 \
    alembic>=1.13.0 \
    pydantic>=2.10.0 \
    pydantic-settings>=2.6.0 \
    psycopg2-binary>=2.9.10 \
    grpcio>=1.67.0 \
    grpcio-tools>=1.67.0 \
    python-multipart>=0.0.12 \
    pyyaml>=6.0.2 \
    croniter>=3.0.3 \
    apscheduler>=3.10.4 \
    httpx>=0.28.0

# Stage 2: Runtime stage
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    mkdir -p /app /data && \
    chown -R appuser:appuser /app /data

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Generate gRPC code if needed
RUN python -m grpc_tools.protoc \
    -I./src/workflow_manager/grpc \
    --python_out=./src/workflow_manager/grpc \
    --grpc_python_out=./src/workflow_manager/grpc \
    ./src/workflow_manager/grpc/job_manager.proto || true

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8000 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ping')" || exit 1

# Default command
CMD ["python", "-m", "workflow_manager"]
