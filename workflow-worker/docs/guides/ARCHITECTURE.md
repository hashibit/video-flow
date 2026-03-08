# Workflow Worker - DDD Architecture Documentation

## Project Overview

**Workflow Worker** is a video inspection workflow processing system based on DDD (Domain-Driven Design) architecture.

The project is built with Python 3.13+ and modern tooling (uv package manager).

---

## Architecture Layers

```
src/workflow_worker/
├── domain/              # Domain Layer
│   ├── entities/        # Entities (formerly models)
│   ├── value_objects/   # Value Objects
│   └── repositories/    # Repository Interfaces
│
├── services/            # Service Layer
│   ├── ai/              # AI Services
│   │   ├── human_detection/
│   │   ├── ocr/
│   │   ├── face_verification/
│   │   └── auc/
│   └── media/           # Media Services
│
├── applications/        # Application Layer
│   ├── jobs/            # Job Implementations (formerly modules)
│   ├── workflows/       # Workflow Orchestration
│   └── use_cases/       # Use Cases
│
├── infrastructure/      # Infrastructure Layer
│   ├── media/           # Media Processing Framework
│   ├── external/        # External Service Clients
│   ├── persistence/     # Persistence
│   └── messaging/       # Message Queue
│
├── interfaces/          # Interface Layer
│   ├── api/             # gRPC API (formerly apis)
│   ├── cli/             # Command Line Interface
│   └── events/          # Event Handling
│
└── shared/              # Shared Modules
    ├── config/          # Configuration
    ├── logging/         # Logging
    ├── utils/           # Utility Functions
    └── exceptions/      # Exception Definitions
```

---

## Layer Responsibilities

### 1. Domain Layer

**Responsibility**: Encapsulate core business logic and rules

- **entities/** - Business entities
  - `Task` - Task entity
  - `Rule` - Rule entity
  - `Report` - Report entity
  - Various task configuration and result entities

- **value_objects/** - Value objects
  - Immutable value types
  - Representations of domain concepts

- **repositories/** - Repository interfaces
  - Define data access contracts
  - Implemented by infrastructure layer

**Characteristics**:
- ✅ No dependencies on other layers
- ✅ Pure business logic
- ✅ Independently testable

---

### 2. Services Layer

**Responsibility**: Orchestrate business logic, integrate AI services

- **ai/** - AI algorithm services
  - `HumanDetectionService` - Face detection
  - `PersonTrackingService` - Person tracking
  - `OCRService` - OCR recognition
  - `FaceVerificationService` - Face verification
  - `AUCService` - Audio content审查

- **media/** - Media services
  - Video processing services
  - Audio processing services

**Characteristics**:
- ✅ Coordinate multiple domain objects
- ✅ Interact with external AI services
- ✅ Stateless
- ✅ Depend on domain, used by applications

---

### 3. Applications Layer

**Responsibility**: Task orchestration and workflow management

- **jobs/** - Job implementations
  - `PersonTrackingJob` - Person tracking job
  - `CardRecognitionJob` - Card recognition job
  - `OCRJob` - OCR job
  - `BannedWordDetectionJob` - Banned word detection
  - etc...

- **workflows/** - Workflows
  - `JobRunner` - Job runner
  - `TaskContext` - Task context

- **use_cases/** - Use cases
  - Business use case implementations

**Characteristics**:
- ✅ Orchestrate domain objects and services
- ✅ Implement business use cases
- ✅ Thin layer, no business logic

---

### 4. Infrastructure Layer

**Responsibility**: Provide technical support and external integration

- **media/** - Media processing framework
  - `DataSource` - Data source abstraction
  - `FrameChannel` - Frame channel
  - `StreamFactory` - Stream factory

- **external/** - External services
  - `MediaAPIClient` - Media API client

- **persistence/** - Persistence
  - Database access implementations

- **messaging/** - Message queue
  - Message publish/subscribe

**Characteristics**:
- ✅ Implement technical details
- ✅ Depend on domain interfaces
- ✅ Replaceable

---

### 5. Interfaces Layer

**Responsibility**: Interact with the outside world

- **api/** - gRPC API
  - Protobuf definitions
  - gRPC service implementations

- **cli/** - Command line interface
  - `worker.py` - Main entry point

- **events/** - Event handling
  - `EventFactory` - Event factory
  - Event handlers

**Characteristics**:
- ✅ Handle user requests
- ✅ Thin layer, delegate to applications
- ✅ No business logic

---

### 6. Shared Module

**Responsibility**: Cross-layer utilities and configuration

- **config/** - Configuration management
  - Dynaconf configuration

- **logging/** - Logging
  - Unified logging interface

- **utils/** - Utility functions
  - Common utilities

- **exceptions/** - Exceptions
  - Custom exceptions

**Characteristics**:
- ✅ Used by all layers
- ✅ No business logic

---

## Dependency Rules

### Dependency Direction

```
Interfaces → Applications → Services → Domain
                   ↓              ↓
             Infrastructure ←────┘
                   ↑
                   └── Shared (all layers)
```

**Key Principles**:
1. ✅ Domain layer has no dependencies
2. ✅ Outer layers depend on inner layers
3. ✅ Dependency inversion: Infrastructure implements interfaces defined by Domain

### Examples

```python
# ✅ Correct: Applications calls Services
from workflow_worker.services.ai import HumanDetectionService

# ✅ Correct: Infrastructure implements Domain interface
from workflow_worker.domain.repositories import TaskRepository

# ❌ Wrong: Domain should not depend on Infrastructure
from workflow_worker.infrastructure.media import DataSource  # Forbidden!

# ✅ Correct: All layers can use Shared
from workflow_worker.shared.logging import get_logger
```

---

## Naming Conventions

### Package Imports

```python
# Import domain entities
from workflow_worker.domain.entities import Task, Rule

# Import services
from workflow_worker.services.ai import HumanDetectionService

# Import application layer
from workflow_worker.applications.jobs import PersonTrackingJob

# Import infrastructure
from workflow_worker.infrastructure.media import DataSource

# Import interfaces
from workflow_worker.interfaces.api import job_manager_pb2

# Import shared modules
from workflow_worker.shared.logging import get_logger
```

### Module Naming

| Type | Naming | Example |
|------|--------|---------|
| Entity | Noun | `Task`, `Rule`, `Report` |
| Value Object | Adjective + Noun | `TimeInterval`, `Score` |
| Service | Noun + Service | `HumanDetectionService` |
| Repository | Noun + Repository | `TaskRepository` |
| Use Case | Verb + Noun | `ProcessVideo`, `CreateReport` |
| Job | Noun + Job | `PersonTrackingJob` |

---

## Testing Strategy

### Unit Tests

```
tests/
├── unit/
│   ├── domain/         # Domain layer tests
│   ├── services/       # Service layer tests
│   ├── applications/   # Application layer tests
│   └── shared/         # Shared module tests
```

### Integration Tests

```
tests/
├── integration/
│   ├── api/            # API tests
│   ├── workflows/      # Workflow tests
│   └── jobs/           # Job tests
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific layer tests
uv run pytest tests/unit/domain/

# With coverage
uv run pytest --cov=src/workflow_worker
```

---

## Development Guide

### Adding New Features

#### 1. Define Domain Entities (Domain)

```python
# src/workflow_worker/domain/entities/my_entity.py
from pydantic import BaseModel

class MyEntity(BaseModel):
    """Domain entity"""
    id: str
    name: str
```

#### 2. Implement Service (Services)

```python
# src/workflow_worker/services/my_service.py
from workflow_worker.domain.entities import MyEntity

class MyService:
    """Service"""
    def process(self, entity: MyEntity) -> MyEntity:
        # Business logic
        return entity
```

#### 3. Implement Use Case (Applications)

```python
# src/workflow_worker/applications/use_cases/my_use_case.py
from workflow_worker.domain.entities import MyEntity
from workflow_worker.services.my_service import MyService

class MyUseCase:
    """Use case"""
    def __init__(self, service: MyService):
        self.service = service

    def execute(self, data: dict) -> MyEntity:
        entity = MyEntity(**data)
        return self.service.process(entity)
```

#### 4. Add Interface (Interfaces)

```python
# src/workflow_worker/interfaces/api/my_api.py
from workflow_worker.applications.use_cases import MyUseCase

def handle_request(data: dict):
    use_case = MyUseCase()
    result = use_case.execute(data)
    return result
```

---

## FAQ

### Q1: Why adopt DDD?

A: DDD provides a clear layered architecture that makes code easier to:
- Understand and maintain
- Test
- Scale
- Collaborate as a team

### Q2: Can the Domain layer depend on other layers?

A: **No**. The Domain layer must remain independent and not depend on any other layers. This ensures the purity of business logic.

### Q3: When should I create a new Service?

A: When you need to:
- Orchestrate multiple domain objects
- Interact with external services
- Implement cross-entity business logic

### Q4: Can the Infrastructure layer call the Applications layer?

A: **No**. Dependency direction should be unidirectional: Interfaces → Applications → Services → Domain.

---

## References

- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Python Package Structure](https://docs.python-guide.org/writing/structure/)
