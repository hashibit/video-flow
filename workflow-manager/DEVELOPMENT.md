# Development Guide

## Project Structure

```
workflow_manager/
├── src/
│   └── workflow_manager/   # Main package
│       ├── api/            # REST API handlers
│       │   ├── handlers/
│       │   │   ├── job_handler.py # Job-related endpoints
│       │   │   └── ping.py        # Health check
│       │   └── dependencies.py    # FastAPI dependencies
│       ├── client/         # External API clients
│       │   └── external_api.py    # External API client
│       ├── config/         # Configuration
│       │   ├── config.yaml # YAML config file
│       │   └── settings.py # Pydantic settings
│       ├── core/           # Core business logic
│       │   ├── database.py # Database session management
│       │   ├── models.py   # SQLAlchemy models and Pydantic schemas
│       │   ├── repositories.py # Data access layer (Repository pattern)
│       │   └── services.py # Business logic layer (Service pattern)
│       ├── grpc/           # gRPC services
│       │   ├── job_manager.proto # Protocol Buffers definition
│       │   ├── servicer.py       # gRPC servicer implementation
│       │   └── *.py        # Generated proto files (ignored in git)
│       ├── scheduler/      # Task scheduler
│       │   └── scheduler.py # APScheduler implementation
│       └── __main__.py     # Application entry point
├── tests/                  # Unit and integration tests
│   ├── conftest.py         # Pytest fixtures
│   ├── test_api.py         # API endpoint tests
│   ├── test_services.py    # Service layer tests
│   └── test_retry.py       # Retry mechanism tests
├── pyproject.toml          # Project dependencies and config
└── README.md               # Project documentation
```

## Setup Development Environment

```bash
# Install dependencies
uv sync

# Generate gRPC code from proto files (required after proto changes)
uv run python -m grpc_tools.protoc \
  -I./src/workflow_manager/grpc \
  --python_out=./src/workflow_manager/grpc \
  --grpc_python_out=./src/workflow_manager/grpc \
  ./src/workflow_manager/grpc/job_manager.proto

# Run the server (HTTP + gRPC)
uv run python -m workflow_manager

# Or use uvicorn for HTTP only (development)
uv run uvicorn workflow_manager.__main__:app --reload --port 8000

# Or use the run script
./run.sh

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/workflow_manager --cov-report=html
```

## gRPC Development

### Compiling Proto Files

When you modify `src/workflow_manager/grpc/job_manager.proto`, regenerate Python code:

```bash
uv run python -m grpc_tools.protoc \
  -I./src/workflow_manager/grpc \
  --python_out=./src/workflow_manager/grpc \
  --grpc_python_out=./src/workflow_manager/grpc \
  ./src/workflow_manager/grpc/job_manager.proto
```

This generates:
- `job_manager_pb2.py` - Message classes
- `job_manager_pb2_grpc.py` - Service stubs and servicers

### Testing gRPC Services

Use `grpcurl` for manual testing:

```bash
# List services
grpcurl -plaintext localhost:50051 list

# Call GetJob
grpcurl -plaintext -d '{"worker_id": "test-worker"}' \
  localhost:50051 task_workflow.JobManagerService/GetJob

# Call CreateReport
grpcurl -plaintext -d '{
  "job_id": 1,
  "task_id": 123,
  "job_report": {
    "name": "test_report",
    "value_json": "{\"result\": \"success\"}",
    "message": "Test completed"
  }
}' localhost:50051 task_workflow.JobManagerService/CreateReport
```

## API Testing

### Health Check
```bash
curl http://localhost:8000/ping
```

### Create Job
```bash
curl -X POST http://localhost:8000/api/v1/job/create_job \
  -H "Content-Type: application/json" \
  -d '{"task_id": 123, "project_name": "test_project"}'
```

### Get Job
```bash
curl -X POST http://localhost:8000/api/v1/job/get_job \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'
```

### List Jobs
```bash
curl -X POST http://localhost:8000/api/v1/job/list_jobs \
  -H "Content-Type: application/json" \
  -d '{"page": 1, "page_size": 10}'
```

## Database

### SQLite (default)
No additional setup needed.

### PostgreSQL
1. Install PostgreSQL
2. Update `DATABASE_URL` in `.env` or `config.yaml`:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/workflow_manager
   ```

### Reset Database
```python
from workflow_manager.core.database import drop_db, init_db

drop_db()  # Drop all tables
init_db()  # Recreate tables
```

## Adding New Features

### REST API Endpoint
1. Define request/response models in handler file
2. Implement handler function in `api/handlers/`
3. Add route to router
4. Add tests in `tests/test_api.py`

### gRPC Service Method
1. Update `grpc/job_manager.proto` with new messages/methods
2. Regenerate proto files
3. Implement method in `grpc/servicer.py`
4. Add tests

### Database Model
1. Define SQLAlchemy model in `core/models.py`
2. Add Pydantic schemas for API
3. Implement repository methods in `core/repositories.py`
4. Implement service methods in `core/services.py`
5. Add tests in `tests/test_services.py`

### External API Client
1. Add client class in `client/`
2. Implement API methods with error handling
3. Add retry logic if needed
4. Add integration tests

## Job Status Codes

**IMPORTANT**: Status codes must match Go version for compatibility:

```python
JobStatus.PENDING = 0       # Waiting to be scheduled
JobStatus.RUNNING = 1       # Currently being processed
JobStatus.RETRY = 2         # Failed, will retry
JobStatus.SUCCESS = 16      # Completed successfully
JobStatus.FAILED = 17       # Failed after max retries
JobStatus.NO_NEED = 32      # Skipped/not needed
```

## Retry Mechanism

- Maximum retry attempts: **10**
- Jobs with `retry_times < 10` are marked as `RETRY` on failure
- Jobs with `retry_times >= 10` are marked as `FAILED`
- RETRY jobs are picked up by scheduler after PENDING jobs

## Code Style

This project uses:
- **Ruff** for linting and formatting
- **Pytest** for testing
- **Type hints** for better IDE support

Run linters:
```bash
# Check code
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

## Architecture Patterns

- **Repository Pattern**: Data access abstraction (`core/repositories.py`)
- **Service Pattern**: Business logic layer (`core/services.py`)
- **Dependency Injection**: FastAPI dependencies (`api/dependencies.py`)
- **Singleton Pattern**: Global service instances (settings, clients)

## Error Handling

### gRPC Services
- Set appropriate `grpc.StatusCode` on errors
- Always rollback jobs to RETRY state on unexpected errors
- Log errors with context (job_id, task_id, worker_id)

### REST API
- Use FastAPI's `HTTPException` for client errors
- Return structured error responses
- Log internal errors with stack traces

### External API Calls
- Use timeout for all HTTP requests
- Implement retry logic for transient failures
- Validate response format before processing
