# Workflow Worker — Documentation Index

## Start Here

| I want to... | Go to |
|-------------|-------|
| Understand what this project does | [System Overview](guides/SYSTEM_OVERVIEW.md) |
| See the data flow end-to-end | [Data Flow](guides/DATA_FLOW.md) |
| Learn about each analysis module | [Module Reference](guides/MODULES.md) |
| Understand gRPC / API interfaces | [Interfaces & Dependencies](guides/INTERFACES.md) |
| Understand the code structure (DDD) | [Architecture Guide](guides/ARCHITECTURE.md) |
| Run or deploy with Docker | [Docker Guide](guides/DOCKER.md) |

---

## Guides

### Understanding the System
- **[System Overview](guides/SYSTEM_OVERVIEW.md)** — What Workflow Worker does, how it fits into the larger platform, deployment topology, and technology stack
- **[Data Flow](guides/DATA_FLOW.md)** — End-to-end sequence diagrams: job pickup → frame dispatch → analysis → report delivery
- **[Module Reference](guides/MODULES.md)** — Per-job documentation: inputs, outputs, AI services used, and how jobs share state via TaskContext
- **[Interfaces & Dependencies](guides/INTERFACES.md)** — gRPC proto definitions, REST API calls, environment variables, and domain type reference

### Code Architecture
- **[Architecture Guide](guides/ARCHITECTURE.md)** — DDD layer responsibilities, dependency rules, naming conventions, and how to add new features

### Operations
- **[Docker Guide](guides/DOCKER.md)** — Multi-stage build, docker-compose, environment variables, health checks

---

## Project Layout

```
workflow-worker/
├── src/workflow_worker/
│   ├── domain/          # Entities, value objects (no external deps)
│   ├── services/        # AI service clients (gRPC)
│   ├── applications/    # Job orchestration, workflows
│   ├── infrastructure/  # Media pipeline, external HTTP clients
│   ├── interfaces/      # gRPC client, CLI worker entry point
│   └── shared/          # Config, logging, utilities
├── docs/
│   ├── index.md         # (this file)
│   └── guides/
│       ├── SYSTEM_OVERVIEW.md
│       ├── DATA_FLOW.md
│       ├── MODULES.md
│       ├── INTERFACES.md
│       ├── ARCHITECTURE.md
│       └── DOCKER.md
├── test/
├── scripts/
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

---

**Last updated**: 2026-03-07
