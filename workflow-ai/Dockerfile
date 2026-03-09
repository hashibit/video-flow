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

COPY pyproject.toml .
COPY src/ src/
COPY proto/ proto/

# Install dependencies (core + grpc; ML extras are optional and added at build time)
RUN uv pip install --system --no-cache ".[all]"

# Generate gRPC stubs
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./src/workflow_ai/grpc \
    --grpc_python_out=./src/workflow_ai/grpc \
    ./proto/*.proto

EXPOSE 50100 50101 50102 50103 50104 50105 50106

CMD ["python", "-m", "workflow_ai"]
