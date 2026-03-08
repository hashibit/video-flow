# Docker Build Guide

## Image Overview

The `workflow-worker` Docker image is based on **Python 3.13-slim**, using multi-stage builds to optimize image size.

### Features

- ✅ Standard Python 3.13 official image
- ✅ No internal company dependencies
- ✅ Multi-stage build (reduced image size)
- ✅ Runs as non-root user
- ✅ Health check included
- ✅ uv package management
- ✅ Includes FFmpeg (video processing)

---

## Quick Start

### Build Image

```bash
# Basic build
docker build -t workflow-worker:latest .

# With build arguments (optional)
docker build \
  --build-arg VERSION=0.1.0 \
  -t workflow-worker:0.1.0 \
  .

# View image info
docker images workflow-worker
```

### Run Container

```bash
# Basic run
docker run -d --name workflow-worker workflow-worker:latest

# With environment variables
docker run -d \
  --name workflow-worker \
  -e WORKFLOW_MANAGER_HOST=192.168.1.100:50051 \
  -e MEDIA_MANAGER_HOST=192.168.1.101:50052 \
  workflow-worker:latest

# Mount log directory
docker run -d \
  --name workflow-worker \
  -v $(pwd)/logs:/app/logs \
  workflow-worker:latest

# View logs
docker logs -f workflow-worker
```

### Using Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f workflow-worker

# Stop services
docker-compose down

# Rebuild and start
docker-compose up -d --build
```

---

## Image Structure

### Multi-stage Build

**Stage 1: Builder**
```dockerfile
FROM python:3.13-slim as builder
# Install build tools
# Install uv
# Install dependencies
```

**Stage 2: Runtime**
```dockerfile
FROM python:3.13-slim as runtime
# Install runtime dependencies (FFmpeg, etc.)
# Copy build artifacts
# Configure non-root user
```

### Image Layers

```
workflow-worker:latest (~400MB)
├── python:3.13-slim (~125MB)
├── System dependencies (FFmpeg, etc.) (~50MB)
├── Python virtual environment (~200MB)
└── Application code (~25MB)
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYTHONUNBUFFERED` | Disable Python output buffering | `1` |
| `IDRS_ENGINE_ENV` | Runtime environment | `development` |
| `WORKFLOW_MANAGER_HOST` | Workflow Manager address | - |
| `MEDIA_MANAGER_HOST` | Media Manager address | - |
| `WORKFLOW_HOME` | Application home directory | `/app` |
| `WORKFLOW_LOGS` | Log directory | `/app/logs` |

### Volume Mounts

| Path | Description |
|------|-------------|
| `/app/src` | Application source code (read-only) |
| `/app/logs` | Log files |
| `/app/tmp` | Temporary files |

### Ports

Expose ports as needed:

```dockerfile
EXPOSE 8000  # HTTP API
EXPOSE 50051 # gRPC
```

---

## Production Deployment

### Optimized Build

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker build -t workflow-worker:latest .

# Export image
docker save workflow-worker:latest | gzip > workflow-worker.tar.gz

# Import image
docker load < workflow-worker.tar.gz
```

### Security Hardening

```dockerfile
# 1. Use non-root user
USER workflow

# 2. Read-only filesystem
docker run --read-only --tmpfs /tmp workflow-worker:latest

# 3. Resource limits
docker run -m 2g --cpus 2 workflow-worker:latest

# 4. Security scan
docker scan workflow-worker:latest
```

### Deploy to Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workflow-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: workflow-worker
  template:
    metadata:
      labels:
        app: workflow-worker
    spec:
      containers:
      - name: worker
        image: workflow-worker:latest
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        env:
        - name: WORKFLOW_MANAGER_HOST
          value: "workflow-manager:50051"
```

---

## Troubleshooting

### Build Failures

```bash
# View build logs
docker build --no-cache -t workflow-worker:latest . 2>&1 | tee build.log

# Common issues
# 1. uv installation fails → Check network connection
# 2. Dependency installation fails → Check pyproject.toml
# 3. Protobuf generation fails → Check .proto files
```

### Runtime Errors

```bash
# Enter container for debugging
docker exec -it workflow-worker bash

# Check environment
python --version  # Should be 3.13.x
pip list          # View installed packages

# View logs
docker logs workflow-worker
docker logs --tail 100 workflow-worker
```

### Performance Optimization

```bash
# 1. Reduce image size
docker history workflow-worker:latest  # View image layers

# 2. Optimize dependencies
# Remove unnecessary dependencies in pyproject.toml

# 3. Use Alpine image (smaller but may have compatibility issues)
FROM python:3.13-alpine
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build image
        run: docker build -t workflow-worker:${{ github.sha }} .

      - name: Login to registry
        run: docker login -u ${{ secrets.DOCKER_USERNAME }} -p ${{ secrets.DOCKER_PASSWORD }}

      - name: Push image
        run: docker push workflow-worker:${{ github.sha }}
```

### GitLab CI

```yaml
build:
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t workflow-worker:$CI_COMMIT_SHA .
    - docker push workflow-worker:$CI_COMMIT_SHA
```

---

## References

- [Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Python Docker Official Images](https://hub.docker.com/_/python)
- [uv Documentation](https://github.com/astral-sh/uv)
- [Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
