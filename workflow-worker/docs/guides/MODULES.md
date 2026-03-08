# Module Reference

Each **Job** in the applications layer corresponds to one or more `RulePoint` categories in the task. The `factory.py` reads the rule configuration and instantiates the appropriate jobs.

---

## Job Execution Phases

Jobs run in two sequential phases. Phase 2 starts only after all Phase 1 jobs complete and the media stream is drained.

| Phase | Jobs | Reason |
|-------|------|--------|
| 1 | All frame-based and audio jobs | Consume video/audio in parallel |
| 2 | BannedWordDetection, ScriptMatching | Depend on Phase 1 transcription output |

---

## Phase 1 Jobs

### SpeechRecognitionJob
- **Category**: `speech`
- **Input**: Audio URL from `task.media.url`
- **What it does**: Submits audio to the AUC (Audio Understanding Chain) gRPC service, polls for completion, applies post-processing (text cleaning, timestamp alignment)
- **Output stored in TaskContext**: `Dialogue` with a list of `Utterance` objects and word-level timestamps
- **AI service**: `AUCService` (gRPC)

### PersonTrackingJob
- **Category**: `person_tracking` / `verification`
- **Input**: Video frames via `FrameChannel` (25 fps)
- **What it does**:
  1. Detects faces and bodies in each frame via `DetService`
  2. Extracts face features via `FeatureService`
  3. Tracks persons across frames via `TrackService`
  4. Compares detected persons against reference photos of participants
- **Output stored in TaskContext**: `PersonTrackingJobResult` — per-person presence timeline
- **AI services**: `DetService`, `FeatureService`, `TrackService` (all gRPC)

### SubtitleMatchingJob
- **Category**: `subtitle`
- **Input**: Video frames via `FrameChannel` (configurable fps, default 5)
- **What it does**: Runs OCR on each frame to extract on-screen text, then matches against expected subtitle content
- **Output stored in TaskContext**: `SubtitleJobResult` — matched/unmatched subtitle segments
- **AI service**: `GeneralOCRService` (gRPC)

### CardRecognitionJob
- **Category**: `card_recognition`
- **Input**: Video frames via `FrameChannel`
- **What it does**: Detects and reads identity cards or other card types from frames using specialized OCR
- **Output stored in TaskContext**: Card recognition results with field values
- **AI service**: `IDCardOCRService` (gRPC)

### SignatureRecognitionJob
- **Category**: `signature`
- **Input**: Video frames via `FrameChannel`
- **What it does**: Detects handwritten signatures in frames; uses handwriting OCR for content if needed
- **Output stored in TaskContext**: Signature presence / content results
- **AI service**: `HandwritingOCRService` (gRPC)

### DocumentRecognitionJob
- **Category**: `document`
- **Input**: Video frames via `FrameChannel`
- **What it does**: Classifies and reads structured documents (contracts, forms, certificates) from frames
- **Output stored in TaskContext**: Document type and extracted fields
- **AI service**: `DocumentOCRService` (gRPC)

---

## Phase 2 Jobs

### BannedWordDetectionJob
- **Category**: `banword`
- **Input**: `Dialogue` from `SpeechRecognitionJob` (stored in TaskContext)
- **What it does**: Scans transcribed speech for words/phrases listed in `banword_cfg.words`; records hit positions with timestamps
- **Output stored in TaskContext**: `BannedWordDetectionReport`
- **AI service**: None (pure string matching)

### ScriptMatchingJob
- **Category**: `script`
- **Input**: `Dialogue` from `SpeechRecognitionJob`
- **What it does**: Checks that the agent's speech follows a predefined script (`script_cfg`); computes coverage and order compliance
- **Output stored in TaskContext**: `ScriptMatchingReport`
- **AI service**: None (text matching logic)

---

## ReportJob (final step)

Runs after all phase-1 and phase-2 jobs complete.

- **Input**: All results stored in `TaskContext`
- **What it does**:
  1. Iterates over every `RuleSection` and `RulePoint`
  2. Pulls the matching job result from `TaskContext`
  3. Determines pass / fail for each rule point
  4. Collects failure reasons
  5. Builds the final `Report` object
- **Output**: `Report` with `status` (passed / failed), per-section / per-rule-point results, and human-readable `reasons`

---

## AI Service Catalogue

| Service class | Protocol | What it provides |
|---------------|----------|-----------------|
| `AUCService` | gRPC | Speech-to-text with word timestamps |
| `DetService` | gRPC | Face + body bounding boxes per frame |
| `FeatureService` | gRPC | 512-dim face embedding vector |
| `TrackService` | gRPC | Cross-frame person identity tracking |
| `GeneralOCRService` | gRPC | Generic printed text recognition |
| `IDCardOCRService` | gRPC | Identity card structured fields |
| `DocumentOCRService` | gRPC | Document / form recognition |
| `HandwritingOCRService` | gRPC | Handwritten text recognition |

All AI services extend `GRPCService`, which handles channel lifecycle, retry on transient errors, and structured error logging.

---

## TaskContext — Shared State Between Jobs

`TaskContext` is created per task and passed to every job. It provides:

- **Frame channels** (`frame_channels: dict[JobName, FrameChannel]`) — each job registers its channel before the media stream starts
- **Event channels** (`event_channels: dict[JobName, EventCollector]`) — jobs publish intermediate events here
- **Result storage** — jobs write final results (e.g. `Dialogue`, `PersonTrackingJobResult`) so Phase 2 jobs can read them
- **Shared logger** — unified logging with task / job context

```
                ┌──────────────────────────────────────┐
                │             TaskContext               │
                │                                       │
                │  frame_channels:                      │
                │    "subtitle_job" → FrameChannel(5fps)│
                │    "det_job"      → FrameChannel(25fp)│
                │    ...                                │
                │                                       │
                │  results:                             │
                │    "speech"   → Dialogue              │
                │    "tracking" → PersonTrackingResult  │
                │    ...                                │
                └──────────────────────────────────────┘
                          ▲              ▲
                   writes │              │ reads
                 (Phase 1)│              │(Phase 2)
```
