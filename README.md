# Video Flow

A distributed video quality-inspection workflow system.

It performs multi-dimensional AI analysis on video content — speech recognition, face detection, OCR, banned-word detection, script compliance matching, and more — and produces structured quality-inspection reports automatically.

---

## Components

```
video-flow/
├── workflow-manager/   # Job scheduling hub (REST + gRPC)
└── workflow-worker/    # AI analysis execution node (DDD architecture)
```

| Component | Responsibility |
|-----------|----------------|
| **Workflow Manager** | Manages the job queue, distributes jobs to workers, collects results, interfaces with the external task platform |
| **Workflow Worker** | Pulls jobs, decodes video, runs AI services in parallel, generates inspection reports |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   External Task Platform                     │
│       Create tasks (REST)            Receive reports (REST)  │
└─────────────────┬───────────────────────────┬───────────────┘
                  │                           │
                  ▼                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Workflow Manager                         │
│  - REST API (FastAPI)          :8000                         │
│  - gRPC (JobManagerService)    :50051                        │
│  - PostgreSQL job queue                                      │
│  - Auto-scheduling + up to 10 retries                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ gRPC: GetJob / CreateReport / Heartbeat
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ Worker 1 │ │ Worker 2 │ │ Worker N │  (horizontal scale)
       └──────────┘ └──────────┘ └──────────┘
              │
              │ gRPC
   ┌──────────┼───────────────────────┐
   ▼          ▼                       ▼
┌──────┐  ┌──────────┐  ┌──────────────────────┐
│ AUC  │  │ Det /    │  │ OCR / Feature /      │
│(ASR) │  │ Track    │  │ Face Verify Services │
└──────┘  └──────────┘  └──────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose (for containerized deployment)

### Local Development

```bash
# Start Workflow Manager
cd workflow-manager
uv sync
cp .env.example .env    # edit as needed
uv run python -m workflow_manager

# Start Workflow Worker (new terminal)
cd workflow-worker
uv sync --all-extras
cp .env.example .env    # set WORKFLOW_WORKFLOW_MANAGER_HOST etc.
uv run python -m workflow_worker.interfaces.cli.worker
```

### Docker Compose Deployment

```bash
# Production (with PostgreSQL)
cd workflow-manager
docker-compose up -d

# Worker
cd workflow-worker
make build && make run
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design, module responsibilities, dependency rules |
| [Getting Started](docs/getting-started.md) | Local dev environment setup and running |
| [gRPC API Reference](docs/grpc-api.md) | Manager ↔ Worker communication protocol |
| [Deployment Guide](docs/deployment.md) | Docker and production deployment |
| [Workflow Manager README](workflow-manager/README.md) | Manager-specific documentation |
| [Workflow Worker README](workflow-worker/README.md) | Worker-specific documentation |

---

## Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.13+ |
| Package manager | uv |
| Manager web framework | FastAPI + Uvicorn |
| Manager database | SQLAlchemy + PostgreSQL / SQLite |
| Manager scheduler | APScheduler |
| Communication | gRPC + Protobuf |
| Worker async framework | asyncio |
| Video decoding | FFmpeg (ffmpeg-python) / gRPC Media Manager |
| Image processing | OpenCV |
| Object storage | MinIO (S3-compatible) |
| Containerization | Docker (multi-stage build) |
| Data validation | Pydantic v2 |
| Worker configuration | Dynaconf |
