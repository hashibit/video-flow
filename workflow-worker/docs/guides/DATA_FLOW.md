# Data Flow

## End-to-End Flow

```
External Platform        Workflow Manager               Workflow Worker
       │                        │                               │
       │─POST /job/create_job──>│                               │
       │  { task_id }           │                               │
       │                        │ persist job (PENDING)         │
       │                        │                               │
       │                        │<──GetJob(worker_id)───────────│ (polls every 10 s)
       │                        │                               │
       │                        │──GET /task/get ──────────────>│ (fetch task_json)
       │                        │<──{ task details }────────────│
       │                        │                               │
       │                        │──POST /task/update            │ (status=RUNNING)
       │                        │                               │
       │                        │──GetJobResponse──────────────>│
       │                        │  { job_id, task_json }        │
       │                        │                               │
       │                        │              ┌────────────────┤
       │                        │              │ Execute task   │
       │                        │              │ (see below)    │
       │                        │              └────────────────┤
       │                        │                               │
       │                        │<──CreateReport(report)────────│
       │                        │                               │
       │                        │──POST /report/create ────────>│ (submit report)
       │                        │──POST /task/update ──────────>│ (status=SUCCESS)
       │<──notification─────────│                               │
```

---

## Task Execution Inside the Worker

```
           JobRunner.run_job(JobInfo)
                       │
                       ▼
           ┌───────────────────────┐
           │ 1. Parse Task JSON    │
           │    Task.from_dict()   │
           └───────────┬───────────┘
                       │
                       ▼
           ┌───────────────────────┐
           │ 2. Create TaskContext │
           │    & MediaStream      │
           └───────────┬───────────┘
                       │
                       ▼
           ┌───────────────────────┐
           │ 3. Instantiate Jobs   │
           │    factory.create()   │
           │    One Job per        │
           │    RulePoint          │
           └───────────┬───────────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
  ┌──────────────────┐  ┌──────────────────────┐
  │  Media Pipeline  │  │ Phase 1: Parallel Jobs│
  │                  │  │                       │
  │ stream_thread    │  │  SpeechRecognition    │
  │  reads frames    │  │  PersonTracking       │
  │  from source     │  │  SubtitleMatching     │
  │                  │  │  CardRecognition      │
  │ dispatch_thread  │  │  ...                  │
  │  filters by FPS  │  │                       │
  │  fans out frames │  │ (consume FrameChannels│
  │  to FrameChannels│  │  concurrently)        │
  │                  │  └────────┬──────────────┘
  │ stat_thread      │           │
  │  tracks FPS stats│           │ all frames consumed
  └──────────────────┘           ▼
                       ┌──────────────────────┐
                       │ Phase 2: Dependent   │
                       │ Jobs                 │
                       │                      │
                       │  BannedWordDetect    │
                       │  ScriptMatching      │
                       │  (use Phase 1 data)  │
                       └────────┬─────────────┘
                                │
                                ▼
                       ┌──────────────────────┐
                       │  ReportJob.run()      │
                       │  Aggregate results    │
                       │  Evaluate each rule   │
                       │  Build Report object  │
                       └────────┬─────────────┘
                                │
                                ▼
                           Report JSON
```

---

## Frame Distribution Pipeline

```
Video file / Media Service
        │
        │  (FFmpeg decode / gRPC stream)
        ▼
┌────────────────────────────────────┐
│           MediaStream               │
│  ┌──────────────────────────────┐  │
│  │  CircularQueue (1024 frames) │  │
│  └──────────────────────────────┘  │
└────────────────┬───────────────────┘
                 │  dispatch_thread fans out (filtered by FPS)
                 │
     ┌───────────┼───────────┬─────────────┐
     ▼           ▼           ▼             ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Channel │ │ Channel │ │ Channel │ │ Channel │
│  OCR    │ │   Det   │ │  Track  │ │  ...    │
│  5 fps  │ │ 25 fps  │ │ 25 fps  │ │         │
│  ring   │ │  ring   │ │  ring   │ │  ring   │
│  queue  │ │  queue  │ │  queue  │ │  queue  │
└────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
     ▼           ▼           ▼            ▼
SubtitleJob  DetService  TrackService   ...
```

Each FrameChannel has its own FPS setting; modules only consume frames from their own queue.

---

## Audio Data Flow

```
Task.media.url
      │
      ▼
SpeechRecognitionJob
      │
      │  1. Submit audio URL to AUC service
      ▼
AUCService.submit_audio()
      │
      │  2. Poll until transcription completes
      ▼
AUCService.get_result()
      │
      │  3. Post-process (clean text, align timestamps)
      ▼
Dialogue { utterances: [Utterance], words: [Word] }
      │
      │  4. Store in TaskContext
      ▼
BannedWordDetectionJob / ScriptMatchingJob
(Phase 2 jobs consume the transcription)
```

---

## gRPC Message Structures

### GetJobResponse — task received by worker

```json
{
  "id": 12345,
  "task_id": 67890,
  "task_json": {
    "name": "Inspection Task Name",
    "id": 67890,
    "media": {
      "path": "/path/to/video.mp4",
      "url": "http://...",
      "meta": { "fps": "25", "width": 1920, "height": 1080, "duration": 3600 }
    },
    "scenario": { "rules": [] },
    "rule": {
      "rule_sections": [
        {
          "id": 1,
          "name": "Compliance Check",
          "rule_points": [
            { "id": 10, "category": "banword", "banword_cfg": { "words": ["forbidden"] } },
            { "id": 11, "category": "subtitle", "subtitle_cfg": { "fps": 5 } }
          ]
        }
      ]
    },
    "participants": [{ "name": "Agent", "cards": [] }]
  }
}
```

### CreateReportRequest — report sent back by worker

```json
{
  "job_id": 12345,
  "task_id": 67890,
  "job_report": {
    "id": 12345,
    "name": "Inspection Report",
    "value_json": {
      "status": "failed",
      "rule_section_reports": [
        {
          "id": 1,
          "rule_point_reports": [
            {
              "id": 10,
              "banword_detection_report": {
                "hit_words": ["forbidden"],
                "hit_times": [["00:01:23", "00:01:25"]]
              },
              "reasons": ["Banned word detected: forbidden"]
            }
          ],
          "reasons": ["Compliance check failed"]
        }
      ],
      "reasons": [["Compliance check failed"]]
    },
    "message": "",
    "created_at": "2026-03-07T10:00:00Z"
  }
}
```

---

## Error Handling & Retry

```
Worker returns empty report
        │
        ▼
Workflow Manager
        │
        ├── retry_times < 10  →  status = RETRY
        │                        re-queued for next GetJob call
        │
        └── retry_times >= 10 →  status = FAILED
                                 external platform notified

Worker goes offline (heartbeat timeout)
        │
        ▼
Manager detects stale RUNNING jobs
        │
        └──> rolls job back to RETRY
```
