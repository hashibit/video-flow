# Getting Started

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.13+ | Required by both services |
| [uv](https://docs.astral.sh/uv/) | latest | Package manager |
| FFmpeg | any | Required for local video decoding in the Worker |
| Docker | 20+ | Optional, for containerized deployment |

Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Start Workflow Manager

```bash
cd workflow-manager

# Install dependencies
uv sync

# Generate gRPC code (required on first run or after modifying the proto file)
uv run python -m grpc_tools.protoc \
  -I./src/workflow_manager/grpc \
  --python_out=./src/workflow_manager/grpc \
  --grpc_python_out=./src/workflow_manager/grpc \
  ./src/workflow_manager/grpc/job_manager.proto

# Copy and edit configuration
cp .env.example .env

# Start (HTTP :8000 + gRPC :50051)
uv run python -m workflow_manager
```

Verify the service is running:

```bash
curl http://localhost:8000/ping
# → {"status": "ok"}
```

---

## Start Workflow Worker

```bash
cd workflow-worker

# Install all dependencies (including media, gRPC, and other optional extras)
uv sync --all-extras
# or use the helper script
./scripts/install_deps.sh all

# Copy and edit configuration
cp .env.example .env
```

Minimum required variables in `.env`:

```bash
WORKFLOW_WORKFLOW_MANAGER_HOST=localhost:50051   # Manager gRPC address
WORKFLOW_MEDIA_DATA_SOURCE=local_ffmpeg          # Video decode backend
```

```bash
# Start the Worker
uv run python -m workflow_worker.interfaces.cli.worker
```

---

## Configuration Reference

### Workflow Manager (`.env`)

```bash
# Application
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Database (SQLite for dev, PostgreSQL for production)
DATABASE_URL=sqlite:///./workflow_manager.db
# DATABASE_URL=postgresql://user:password@localhost:5432/workflow_manager

# gRPC
GRPC_ENDPOINT=0.0.0.0:50051
GRPC_ENABLED=true

# External task platform
EXTERNAL_API_URL=http://external-api-service:8080
EXTERNAL_API_TIMEOUT=30

# Scheduler
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_SECONDS=5
```

### Workflow Worker — key variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_WORKFLOW_MANAGER_HOST` | — | Manager gRPC address (required) |
| `WORKFLOW_MEDIA_DATA_SOURCE` | `local_ffmpeg` | `local_ffmpeg` or `media_manager` |
| `WORKFLOW_MEDIA_MANAGER_HOST` | — | Media Manager HTTP base URL (required when using `media_manager`) |
| `WORKFLOW_IS_DEBUG` | `false` | Enable verbose logging |

Full variable list: [workflow-worker/docs/guides/INTERFACES.md](../workflow-worker/docs/guides/INTERFACES.md)

---

## Running Tests

```bash
# Workflow Manager
cd workflow-manager
uv run pytest
uv run pytest --cov=src/workflow_manager --cov-report=html

# Workflow Worker
cd workflow-worker
uv run pytest
uv run pytest --cov
```

---

## Development Tools

### Workflow Manager

```bash
uv run ruff check .           # lint
uv run ruff check --fix .     # auto-fix
uv run ruff format .          # format
uv run mypy src/              # type-check
```

### Workflow Worker

```bash
uv run black src/             # format
uv run pylint src/            # lint
uv run basedpyright src/      # type-check
```

---

## API Quick Reference

Once the Manager is running, use these REST endpoints:

```bash
# Create a job (task_id comes from the external task platform)
curl -X POST http://localhost:8000/api/v1/job/create_job \
  -H "Content-Type: application/json" \
  -d '{"task_id": 123, "project_name": "test_project"}'

# Get job details by ID
curl -X POST http://localhost:8000/api/v1/job/get_job \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'

# List jobs with pagination
curl -X POST http://localhost:8000/api/v1/job/list_jobs \
  -H "Content-Type: application/json" \
  -d '{"page": 1, "page_size": 10}'
```
