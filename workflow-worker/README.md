# Workflow Worker

An AI-powered video quality-inspection worker service built on Domain-Driven Design (DDD). It pulls inspection jobs from Workflow Manager, analyzes video using multiple AI services in parallel (speech recognition, face detection, OCR, keyword detection, etc.), and returns structured quality reports.

**New to this project? Start with the [System Overview](docs/guides/SYSTEM_OVERVIEW.md).**

---

## Quick Start

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies
uv sync --all-extras
# or use the helper script
./scripts/install_deps.sh all

# Configure environment (copy and edit)
cp .env.example .env   # set WORKFLOW_WORKFLOW_MANAGER_HOST etc.

# Run the worker
uv run python -m workflow_worker.interfaces.cli.worker
```

---

## Docker

```bash
make build   # build Docker image
make run     # start container
make logs    # tail container logs
make stop    # stop container
```

---

## Development

```bash
uv run black src/          # format
uv run pylint src/         # lint
uv run basedpyright src/   # type-check
uv run pytest              # run tests
uv run pytest --cov        # run tests with coverage
```

---

## Key Environment Variables

| Variable | Description |
|----------|-------------|
| `WORKFLOW_WORKFLOW_MANAGER_HOST` | gRPC address of Workflow Manager (e.g. `localhost:50051`) |
| `WORKFLOW_MEDIA_DATA_SOURCE` | `local_ffmpeg` (default) or `media_manager` |
| `WORKFLOW_MEDIA_MANAGER_HOST` | HTTP base URL of Media Manager (when using `media_manager`) |
| `WORKFLOW_IS_DEBUG` | Set to `true` for verbose logging |

See [Interfaces & Dependencies](docs/guides/INTERFACES.md) for the full list.

---

## Documentation

| Document | Description |
|----------|-------------|
| [System Overview](docs/guides/SYSTEM_OVERVIEW.md) | What this project does and how it fits into the platform |
| [Data Flow](docs/guides/DATA_FLOW.md) | End-to-end sequence diagrams |
| [Module Reference](docs/guides/MODULES.md) | Per-job documentation |
| [Interfaces & Dependencies](docs/guides/INTERFACES.md) | gRPC proto, REST APIs, env vars |
| [Architecture Guide](docs/guides/ARCHITECTURE.md) | DDD layers and code conventions |
| [Docker Guide](docs/guides/DOCKER.md) | Build and deployment instructions |

---

## Project Structure

```
src/workflow_worker/
├── domain/          # Core business entities (Task, Rule, Report, Frame, …)
├── services/        # AI service clients (AUC, Det, Track, OCR, …)
├── applications/    # Job orchestration (JobRunner, individual Job classes)
├── infrastructure/  # Media pipeline (MediaStream, FrameChannel, FFmpeg)
├── interfaces/      # gRPC client, CLI entry point
└── shared/          # Config, logging, utilities
```

## License

Internal project. See company agreement for usage terms.
