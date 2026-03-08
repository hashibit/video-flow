# Deployment Guide

## Topology

```
                 ┌─────────────────────┐
                 │   Workflow Manager   │
                 │   :8000  (REST)      │
                 │   :50051 (gRPC)      │
                 │   PostgreSQL :5432   │
                 └──────────┬──────────┘
                            │ gRPC
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │  Worker 1  │  │  Worker 2  │  │  Worker N  │
     └────────────┘  └────────────┘  └────────────┘
```

---

## Workflow Manager

### Production (Docker Compose + PostgreSQL)

```bash
cd workflow-manager

docker-compose up -d             # build and start
docker-compose logs -f workflow-manager  # tail logs
docker-compose down              # stop
docker-compose down -v           # stop and remove volumes
```

`docker-compose.yml` includes:
- Workflow Manager service (Python 3.13)
- PostgreSQL 16 database
- Persistent data volume
- Health checks for both services
- Automatic restart policy

Exposed ports:

| Service | Port |
|---------|------|
| HTTP API | 8000 |
| gRPC | 50051 |
| PostgreSQL | 5432 |

### Development (SQLite, hot reload)

```bash
cd workflow-manager
docker-compose -f docker-compose.dev.yml up
```

Features: SQLite database (no external DB needed), source code mounted as volume, hot reload enabled.

### Standalone Container

```bash
docker build -t workflow-manager:latest .

docker run -d \
  -p 8000:8000 \
  -p 50051:50051 \
  -e DATABASE_URL=sqlite:///./data/workflow_manager.db \
  -e EXTERNAL_API_URL=http://external-api:8080 \
  -v $(pwd)/data:/data \
  workflow-manager:latest
```

---

## Workflow Worker

```bash
cd workflow-worker

make build   # build Docker image
make run     # start container
make logs    # tail container logs
make stop    # stop container
```

Or use the scripts directly:

```bash
./scripts/docker_build.sh
./scripts/docker_run.sh
```

### Key Environment Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `WORKFLOW_WORKFLOW_MANAGER_HOST` | `workflow-manager:50051` | Manager gRPC address |
| `WORKFLOW_MEDIA_DATA_SOURCE` | `local_ffmpeg` | Video decode backend |
| `WORKFLOW_MEDIA_MANAGER_HOST` | `http://media-manager:8080` | Media service address (optional) |
| `WORKFLOW_IS_DEBUG` | `false` | Enable verbose logging |

---

## Scaling Workers

Each Worker instance handles up to **4 concurrent tasks**. Scale horizontally by adding more Worker containers — all pointing at the same Manager gRPC address.

```yaml
# docker-compose.yml example with multiple workers
services:
  workflow-manager:
    image: workflow-manager:latest
    ports:
      - "8000:8000"
      - "50051:50051"

  worker-1:
    image: workflow-worker:latest
    environment:
      WORKFLOW_WORKFLOW_MANAGER_HOST: workflow-manager:50051

  worker-2:
    image: workflow-worker:latest
    environment:
      WORKFLOW_WORKFLOW_MANAGER_HOST: workflow-manager:50051

  worker-3:
    image: workflow-worker:latest
    environment:
      WORKFLOW_WORKFLOW_MANAGER_HOST: workflow-manager:50051
```

No Manager-side configuration changes are needed when adding workers.

---

## Health Checks

```bash
# Manager HTTP health check
curl http://localhost:8000/ping

# gRPC connectivity (requires grpcurl)
grpcurl -plaintext localhost:50051 list
```

---

## Database Management

### PostgreSQL connection string

```
DATABASE_URL=postgresql://user:password@host:5432/workflow_manager
```

### Reset database (development only)

```python
from workflow_manager.core.database import drop_db, init_db

drop_db()   # drop all tables
init_db()   # recreate tables
```

### Backup and restore (PostgreSQL)

```bash
# Backup
docker exec workflow-manager-db \
  pg_dump -U postgres workflow_manager > backup.sql

# Restore
docker exec -i workflow-manager-db \
  psql -U postgres workflow_manager < backup.sql
```

---

## Logging

Both services write structured logs to stdout, making them compatible with log aggregation systems such as ELK or Loki.

Enable debug logging:

```bash
# Worker
WORKFLOW_IS_DEBUG=true uv run python -m workflow_worker.interfaces.cli.worker

# Manager
DEBUG=true uv run python -m workflow_manager
```
