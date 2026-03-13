FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv --no-cache-dir

# Copy shared proto stubs first (workspace dependency)
COPY ../workflow-proto/gen-python/ /app/workflow-proto/gen-python/

COPY pyproject.toml .
COPY src/ src/

# Install dependencies (workflow-proto comes from the local workspace path)
RUN uv pip install --system --no-cache ".[all]" \
    && uv pip install --system --no-cache /app/workflow-proto/gen-python

EXPOSE 50100 50101 50102 50103 50104 50105 50106

CMD ["python", "-m", "workflow_ai"]
