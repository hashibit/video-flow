# Workflow Manager

Workflow task management system with REST API and gRPC support for task processing workflows.

## Features

- **Job Management**: Create, query, and list processing jobs via REST API
- **gRPC Services**: Worker communication for job distribution and result collection
- **Task Scheduling**: Automatic job scheduling with retry mechanism
- **Database Persistence**: SQLAlchemy ORM with SQLite/PostgreSQL support
- **External API Integration**: Seamless integration with external task API service
- **Retry Logic**: Automatic retry with configurable limits (max 10 attempts)
- **Status Tracking**: Comprehensive job status management (PENDING, RUNNING, RETRY, SUCCESS, FAILED, NO_NEED)

## Requirements

- **Python 3.13+** (required for modern syntax features)
- uv package manager

## Quick Start

```bash
# Install dependencies
uv sync

# Generate gRPC code from proto files (if modified)
uv run python -m grpc_tools.protoc \
  -I./src/workflow_manager/grpc \
  --python_out=./src/workflow_manager/grpc \
  --grpc_python_out=./src/workflow_manager/grpc \
  ./src/workflow_manager/grpc/job_manager.proto

# Run the server
uv run python -m workflow_manager

# Or use uvicorn directly for development
uv run uvicorn workflow_manager.__main__:app --reload --port 8000

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/workflow_manager --cov-report=html
```

## Architecture

### REST API Endpoints

- `GET /ping` - Health check
- `POST /api/v1/job/create_job` - Create a new job from task
- `POST /api/v1/job/get_job` - Get job details by ID
- `POST /api/v1/job/get_job_task` - Get task details (proxy to External API)
- `POST /api/v1/job/list_jobs` - List jobs with pagination and filtering

### gRPC Services

**JobManagerService** provides three RPC methods for worker communication:

1. **GetJob(GetJobRequest) → GetJobResponse**
   - Worker requests next available job
   - Returns JobInfo with task JSON
   - Atomically transitions job to RUNNING state
   - Fetches task details from External API

2. **CreateReport(CreateReportRequest) → CreateReportResponse**
   - Worker submits job execution results
   - Validates report and updates job status
   - Submits report to External API
   - Handles retry logic on failure

3. **Heartbeat(HeartbeatRequest) → HeartbeatResponse**
   - Workers send periodic health checks
   - Monitors worker status

### Job Status Flow

```
PENDING → RUNNING → SUCCESS
    ↓         ↓
  RETRY ←── (on failure)
    ↓
  FAILED (after max retries)
```

### External Dependencies

- **External API**: External service for task management and reporting
  - `GET /api/v1/task/get` - Fetch task details
  - `POST /api/v1/task/update` - Update task status
  - `POST /api/v1/report/create` - Submit job report

## Docker Deployment

### Production Deployment (with PostgreSQL)

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f workflow-manager

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

The production setup includes:
- Workflow Manager service (Python 3.13)
- PostgreSQL 16 database
- Persistent volumes for database
- Health checks for both services
- Automatic restart policy

Services are accessible at:
- HTTP API: http://localhost:8000
- gRPC: localhost:50051
- PostgreSQL: localhost:5432

### Development Deployment (with SQLite)

```bash
# Build and start in development mode
docker-compose -f docker-compose.dev.yml up -d

# With hot reload for code changes
docker-compose -f docker-compose.dev.yml up
```

Development setup features:
- SQLite database (no external DB required)
- Source code mounted as volume
- Hot reload enabled
- Debug mode active
- Verbose logging

### Building the Docker Image

```bash
# Build the image
docker build -t workflow-manager:latest .

# Run standalone container
docker run -d \
  -p 8000:8000 \
  -p 50051:50051 \
  -e DATABASE_URL=sqlite:///./data/workflow_manager.db \
  -e EXTERNAL_API_URL=http://external-api:8080 \
  -v $(pwd)/data:/data \
  workflow-manager:latest
```

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Application
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=sqlite:///./workflow_manager.db
# Or use PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/workflow_manager

# gRPC
GRPC_ENDPOINT=0.0.0.0:50051
GRPC_ENABLED=true

# External API
EXTERNAL_API_URL=http://external-api-service:8080
EXTERNAL_API_TIMEOUT=30

# Scheduler
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_SECONDS=5
```

### YAML Configuration

Alternatively, use `config/config.yaml` for structured configuration.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development guide including:
- Project structure
- Adding new features
- Running tests
- Code style guidelines
- gRPC proto compilation
