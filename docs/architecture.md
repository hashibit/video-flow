# Architecture

## Overview

Video Flow is a distributed video quality-inspection system consisting of two core services:

- **Workflow Manager** — the control hub: job queuing, distribution, state management, and result collection.
- **Workflow Worker** — the execution node: video decoding, parallel AI analysis, and report generation.

The two services communicate via gRPC. Workers scale horizontally.

---

## Workflow Manager

### Directory Structure

```
src/workflow_manager/
├── api/            # REST API (FastAPI)
│   └── handlers/   # create_job / get_job / list_jobs / ping
├── client/         # External task platform HTTP client
├── config/         # Configuration (YAML + .env)
├── core/           # Business core
│   ├── models.py       # SQLAlchemy models + Pydantic schemas
│   ├── repositories.py # Data access layer (Repository pattern)
│   ├── services.py     # Business logic layer
│   └── database.py     # Database session management
├── grpc/           # gRPC server (JobManagerService)
└── scheduler/      # APScheduler periodic dispatcher
```

**Patterns used**: Repository, Service, Dependency Injection (FastAPI)

### Job State Machine

```
PENDING ──► RUNNING ──► SUCCESS
    ▲            │
    │    (fail)  ▼
  RETRY ◄─────────
    │
    └──► FAILED  (retry_times >= 10)
```

Status codes are kept compatible with the Go version:

| Status | Value | Meaning |
|--------|-------|---------|
| PENDING | 0 | Waiting to be scheduled |
| RUNNING | 1 | Currently executing |
| RETRY | 2 | Failed, will be retried |
| SUCCESS | 16 | Completed successfully |
| FAILED | 17 | Exceeded max retry limit |
| NO_NEED | 32 | Skipped / not required |

---

## Workflow Worker

The Worker follows a **DDD (Domain-Driven Design)** layered architecture.

### Directory Structure

```
src/workflow_worker/
├── domain/          # Domain layer: core business entities, no external deps
│   └── entities/    # Task, Rule, Report, Frame, Dialogue, …
│
├── services/        # Service layer: AI algorithm gRPC clients
│   └── ai/
│       ├── auc/     # Speech recognition (AUC Service / ASR)
│       ├── det/     # Human body detection
│       ├── feat/    # Feature extraction
│       ├── track/   # Cross-frame person tracking
│       └── ocr/     # OCR variants (general, handwriting, ID card, document)
│
├── applications/    # Application layer: job orchestration
│   ├── jobs/        # Individual Job implementations (one per RulePoint type)
│   └── workflows/   # JobRunner (task lifecycle management)
│
├── infrastructure/  # Infrastructure layer: technical implementation details
│   ├── media_stream/  # Video decode pipeline (FFmpeg / gRPC Media Manager)
│   ├── external/      # External service HTTP client
│   └── circular_queue.py  # Ring-buffer frame queue
│
├── interfaces/      # Interface layer: external-facing entry points
│   ├── api/         # gRPC client stubs (connects to Workflow Manager)
│   ├── cli/         # CLI entry point (worker.py)
│   └── events/      # Event factory
│
└── shared/          # Cross-layer utilities
    ├── config/      # Dynaconf configuration
    ├── logging/     # Unified logging
    └── utils/       # Helper functions
```

### Dependency Direction (strictly enforced)

```
Interfaces → Applications → Services → Domain
                   │               │
             Infrastructure ◄──────┘
                   ▲
                   └── Shared  (usable by all layers)
```

---

## Video Analysis Pipeline

After receiving a job, the Worker processes it in the following stages:

```
JobRunner
    │
    ├─► Parse task_json → Task entity
    ├─► Create MediaStream (FFmpeg decode / gRPC media service)
    ├─► Instantiate Jobs from RulePoint list (via JobFactory)
    │
    ├─► Phase 1 — parallel jobs (consume frame queues)
    │       SpeechRecognitionJob    → AUC gRPC    → Dialogue
    │       PersonTrackingJob       → Det + Track gRPC
    │       SubtitleMatchingJob     → OCR gRPC
    │       CardRecognitionJob      → OCR gRPC
    │       DocumentRecognitionJob  → OCR gRPC
    │       SignatureRecognitionJob → OCR gRPC
    │
    ├─► Phase 2 — dependent jobs (use Phase 1 results)
    │       BannedWordDetectionJob  → uses Dialogue text
    │       ScriptMatchingJob       → uses Dialogue text
    │
    └─► ReportJob → aggregate results → build Report JSON
```

### Frame Distribution Pipeline

```
Video source (FFmpeg / gRPC Media Manager)
        │
        ▼
  CircularQueue  (ring buffer, 1024 frames)
        │
        └─► dispatch_thread fans out frames at per-module FPS
                │
       ┌────────┼────────┬────────┐
       ▼        ▼        ▼        ▼
  FrameChannel Channel  Channel   …
  (OCR, 5fps) (Det,25fps)(Trk,25fps)
```

Each `FrameChannel` is an independent ring queue. Jobs only consume from their own channel.

---

## Control Flow & Data Flow

### Vertical Control Flow

A job request flows top-down through every architectural layer:

```
External Platform  (REST POST /jobs)
    │
    ▼
workflow-manager
    · Enqueues job → PENDING
    · APScheduler dispatches to waiting workers
    │ gRPC: GetJob → JobInfo
    ▼
Interfaces Layer  ·  interfaces/cli/worker.py
    · Polls every 10 s, maintains ≤4 concurrent tasks
    · Parses JobInfo, launches run_job()
    │
    ▼
Applications Layer  ·  applications/workflows/job_runner.py
    · Deserializes task_json → Task entity
    · Creates TaskContext (attaches frame/event channels)
    · Two-phase orchestration (Phase 1: media modules → Phase 2: analysis modules)
    │
    ├─► applications/modules/factory.py
    │       Instantiates Modules per RulePoint, registers channels
    │
    ▼
Infrastructure Layer  ·  infrastructure/media_stream/
    · Starts three-thread pipeline: stream / dispatch / stat
    · Decodes video frames, fans out to each FrameChannel at per-module FPS
    │
    ▼
Services Layer  ·  services/ai/{auc, det, feat, track, ocr}/
    · Each Module calls its gRPC client
    · Delegates actual inference to workflow-ai
    │ AI inference results
    ▼
Domain Layer  ·  domain/entities/
    · Task / Report / Dialogue / Frame …
    · Zero external dependencies — pure business structures
```

Each layer depends only on layers further inward. The Domain layer is the innermost core and knows nothing about frameworks or I/O.

---

### Horizontal Data Flow

How media and analysis results move between components at the same level:

```
Video URL / file
    │
    ▼
DataSource  (FFmpeg decode / gRPC Media Manager)
    │
    ▼
CircularQueue  (ring buffer, 1024 frames)
    │
    ▼  dispatch_thread fans out frames at per-module FPS
    ┌──────────┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼
OCR ch     Det ch    Track ch   Card ch    Audio
 5 fps      25 fps    25 fps      5 fps
    │          │          │          │          │
    │          └────┬─────┘          │          │
    │               │                │          │
    ▼               ▼                ▼          ▼
SubtitleMatching  PersonTracking  Card/Sign  SpeechRecognition
  (OCR gRPC)    (Det+Track gRPC)  (OCR gRPC)  (AUC/ASR gRPC)
    │               │                │          │
    └───────────────┴────────────────┴──────────┘
                            │
                     ←── Phase 1 complete; results written to TaskContext ──►

                            │  Phase 2 consumes Phase 1 results
                    ┌───────┴──────────┐
                    ▼                  ▼
             ScriptMatching    BannedWordDetection
            (dialogue vs script)  (forbidden words)
                    │                  │
                    └────────┬─────────┘
                             │
                             ▼
                        TaskContext
                     ┌─────────────────┐
                     │ speech_result   │
                     │ tracking_result │
                     │ subtitle_result │
                     │ script_result   │
                     │ banned_result   │
                     └────────┬────────┘
                              │
                              ▼
                        ReportModule
                  aggregates per RulePoint → Report JSON
                              │
                              │ gRPC: CreateReport
                              ▼
                       workflow-manager
                  updates job status → submits to external platform
```

**Why two phases?** Phase 1 modules consume the frame stream independently and in parallel — each module has its own isolated FrameChannel ring buffer, so a slow module does not block others. Phase 2 starts only after Phase 1 finishes, avoiding contention between media I/O and text analysis.

---

## Key Domain Entities

| Entity | Description |
|--------|-------------|
| `Task` | One inspection job: video info, rule tree, participant data |
| `Rule / RuleSection / RulePoint` | Three-level rule hierarchy; each RulePoint is one detection type |
| `Job` | Execution unit for a single RulePoint |
| `Frame` | A single decoded image from the video |
| `FrameChannel` | Per-algorithm frame queue with FPS control |
| `Dialogue` | ASR output: list of utterances + word-level timestamps |
| `Report` | Detection result per RulePoint; aggregated into the final inspection report |

---

## Scalability

- **Horizontal Worker scaling**: Workers are stateless. Multiple instances connect to the same Manager; each handles up to 4 concurrent tasks.
- **Adding a new detection type**: Add a Job class under `applications/jobs/`, register it in `JobFactory` — no other layers need to change.
- **Database swap**: Manager supports SQLite (development) and PostgreSQL (production) via `DATABASE_URL`.
- **Video source swap**: Worker supports local FFmpeg and a remote gRPC Media Manager via `WORKFLOW_MEDIA_DATA_SOURCE`.
