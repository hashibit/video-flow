# System Overview

## What is Workflow Worker?

Workflow Worker is the execution node of a video quality-inspection workflow system. It pulls inspection jobs from Workflow Manager, runs multi-dimensional AI analysis on video (face detection, speech recognition, OCR, keyword detection, script matching, etc.), and produces a structured quality-inspection report.

---

## System Context

The full system consists of three main actors:

```
┌──────────────────────────────────────────────────────────────────┐
│                     External Task Platform                        │
│  - Creates and manages inspection tasks                           │
│  - Receives completed inspection reports                          │
└──────────────┬────────────────────────────────┬──────────────────┘
               │ REST (task creation)            │ REST (report delivery)
               ▼                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Workflow Manager                            │
│  - Manages the job queue (PostgreSQL)                             │
│  - Distributes jobs to workers via gRPC                           │
│  - Receives execution results from workers                        │
│  - Auto-retry mechanism (up to 10 attempts)                       │
│  - REST API for front-end / admin systems                         │
└──────────────┬───────────────────────────────────────────────────┘
               │ gRPC: GetJob / CreateReport / Heartbeat
               │ Up to 4 concurrent jobs per worker
               ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Workflow Worker  (this project)                  │
│  - Polls and executes quality-inspection tasks                    │
│  - Decodes video frames → dispatches to per-algorithm queues      │
│  - Calls multiple AI microservices via gRPC                       │
│  - Aggregates results → generates inspection report               │
└────┬──────────────────┬──────────────────────┬───────────────────┘
     │ gRPC             │ gRPC                  │ gRPC / HTTP
     ▼                  ▼                       ▼
┌─────────┐     ┌──────────────┐     ┌────────────────────┐
│   AUC   │     │ Det Service  │     │  OCR / Feature /   │
│  (ASR)  │     │  Track Svc   │     │  Face Verify Svcs  │
└─────────┘     └──────────────┘     └────────────────────┘
```

---

## What Does Workflow Worker Do?

Given an inspection task, the worker:

1. **Decodes the video** — uses FFmpeg or a media manager gRPC service to decode frames
2. **Dispatches frames** — routes frames to per-module queues at configurable FPS rates
3. **Runs modules in parallel** — multiple analysis modules execute concurrently:
   - Speech-to-text (AUC Service)
   - Face / body detection (DetService)
   - Cross-frame person tracking (TrackService)
   - Subtitle OCR, ID-card OCR, handwriting OCR, document OCR
   - Banned keyword detection
   - Script compliance matching
   - Signature / document recognition
4. **Generates a report** — after all modules finish, aggregates results, evaluates each rule point, and produces a final report
5. **Returns results** — sends the report back to Workflow Manager via gRPC

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Task** | One inspection job: video info, inspection rules, participant data |
| **Rule / RuleSection / RulePoint** | Rule hierarchy: Rule → Section → individual check item |
| **Job** | Internal processing unit for one RulePoint |
| **Report** | Detection result for each rule point; aggregated into the full inspection report |
| **Frame** | Single decoded image from the video |
| **FrameChannel** | Per-algorithm frame queue (circular buffer) |
| **EventCollector** | Event queue produced by algorithm modules |
| **MediaStream** | Manages the full lifecycle of video decoding and frame dispatch |

---

## Deployment Topology

```
                ┌─────────────────────┐
                │   Workflow Manager   │
                │   :8000  (REST)      │
                │   :50051 (gRPC)      │
                │   PostgreSQL         │
                └──────────┬──────────┘
                           │ gRPC
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Worker 1  │  │  Worker 2  │  │  Worker N  │
    │ (this repo)│  │            │  │            │
    └────────────┘  └────────────┘  └────────────┘
```

Each Worker instance handles up to **4 concurrent tasks** and scales horizontally.

---

## Technology Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.13+ |
| Package manager | uv |
| Type checker | basedpyright 1.31.0 |
| Data validation | Pydantic v2 |
| Async framework | asyncio |
| Communication | gRPC + Protobuf |
| Video decoding | FFmpeg (ffmpeg-python) / gRPC Media Manager |
| Image processing | OpenCV (cv2) |
| Configuration | Dynaconf + Pydantic-Settings |
| Object storage | MinIO (S3-compatible) |
| Containerization | Docker (multi-stage build) |
