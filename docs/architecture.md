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

### Vertical Control Flow（纵向控制流）

一个任务请求自上而下穿越所有层级：

```
外部平台 (REST POST /jobs)
    │
    ▼
workflow-manager
    · JobManagerServicer 入队 → PENDING
    · APScheduler 定期投递给 Worker
    │ gRPC: GetJob → JobInfo
    ▼
Interfaces Layer  ·  interfaces/cli/worker.py
    · 每 10 s 轮询，维持 ≤4 并发任务
    · 解析 JobInfo，启动 run_job()
    │
    ▼
Applications Layer  ·  applications/workflows/job_runner.py
    · 反序列化 task_json → Task 实体
    · 创建 TaskContext（挂载 frame/event 通道）
    · 两阶段编排（Phase 1 媒体模块 → Phase 2 分析模块）
    │
    ├─► applications/modules/factory.py
    │       按 RulePoint 实例化各 Module，注册通道
    │
    ▼
Infrastructure Layer  ·  infrastructure/media_stream/
    · 启动三线程管道：stream / dispatch / stat
    · 解码视频，按 FPS 分发到各 FrameChannel
    │
    ▼
Services Layer  ·  services/ai/{auc, det, feat, track, ocr}/
    · Module 调用对应 gRPC 客户端
    · 请求 workflow-ai 完成实际推理
    │ AI 推理结果
    ▼
Domain Layer  ·  domain/entities/
    · Task / Report / Dialogue / Frame …
    · 零外部依赖，纯业务结构
```

每层只向内依赖；Domain 是最内核，对框架和 I/O 一无所知。

---

### Horizontal Data Flow（横向数据流）

同层组件之间，媒体和分析结果的流向：

```
视频 URL / 文件
    │
    ▼
DataSource（ffmpeg 解码 / gRPC Media Manager）
    │
    ▼
CircularQueue（环形缓冲，1024 帧）
    │
    ▼  dispatch_thread 按模块 FPS 扇出
    ┌──────────┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼
OCR 通道   Det 通道  Track 通道  Card 通道  音频
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
                       ← Phase 1 结束，结果写入 TaskContext →

                            │  以 Phase 1 结果为输入
                    ┌───────┴──────────┐
                    ▼                  ▼
             ScriptMatching    BannedWordDetection
              (对比台词文本)      (过滤违禁词)
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
                    按 RulePoint 聚合 → Report JSON
                              │
                              │ gRPC: CreateReport
                              ▼
                       workflow-manager
                    更新状态 → 上报外部平台
```

**两阶段的意义**：Phase 1 各模块独立消费帧流，互不干扰；Phase 2 在 Phase 1 完成后才启动，避免音视频资源与文本分析竞争。每个 FrameChannel 是独立的环形队列，一个模块阻塞不影响其他模块。

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
