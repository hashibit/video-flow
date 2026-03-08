# Interfaces & Dependencies

## External Interfaces

### 1. Workflow Manager — gRPC (outbound, as client)

The worker connects to Workflow Manager as a gRPC client.

**Endpoint**: configured via `WORKFLOW_WORKFLOW_MANAGER_HOST` env var
**Proto file**: `src/workflow_worker/interfaces/api/workflow_manager_pb2*.py`

#### `GetJob`
```protobuf
rpc GetJob(GetJobRequest) returns (GetJobResponse)

message GetJobRequest {
  string worker_id = 1;
}
message GetJobResponse {
  JobInfo job_info = 1;
}
message JobInfo {
  uint64 id       = 1;   // job DB id
  uint64 task_id  = 2;   // task id in external system
  string task_json = 3;  // full Task JSON
}
```
Called every 10 seconds. Returns `NOT_FOUND` if no runnable job is available.

#### `CreateReport`
```protobuf
rpc CreateReport(CreateReportRequest) returns (CreateReportResponse)

message CreateReportRequest {
  uint64    job_id    = 1;
  uint64    task_id   = 2;
  JobReport job_report = 3;
}
message JobReport {
  uint64    id         = 1;
  string    name       = 2;
  string    value_json = 3;  // serialised Report object
  string    message    = 4;
  google.protobuf.Timestamp created_at = 5;
}
```

#### `Heartbeat`
```protobuf
rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse)

message HeartbeatRequest {
  string          worker_id      = 1;
  repeated uint64 running_job_ids = 2;
}
```
Sent every 5 seconds to indicate the worker is alive.

---

### 2. AI Services — gRPC (outbound, as client)

All AI services use gRPC. Endpoints are configured in YAML files under `engine/configs/service/`.

#### AUC Service (Speech Recognition)

**Config**: `engine/configs/service/auc.yaml`

```protobuf
// submit audio for recognition
rpc SubmitAudio(SubmitAudioRequest) returns (SubmitAudioResponse)

// poll for result
rpc GetAudioResult(GetAudioResultRequest) returns (GetAudioResultResponse)
```

Result type: `Dialogue { utterances: [Utterance { text, start_ms, end_ms, words: [Word] }] }`

#### Det Service (Human Detection)

**Config**: `engine/configs/service/human_detection.yaml`

```protobuf
rpc Detect(DetectRequest) returns (DetectResponse)
// DetectRequest: list of base64-encoded frames
// DetectResponse: list of DetectionResult { faces: [BBox], bodies: [BBox] }
```

#### Track Service (Person Tracking)

**Config**: `engine/configs/service/person_tracking.yaml`

Maintains cross-frame identity by combining detection + feature embeddings.

#### Feature Service (Face Embedding)

**Config**: `engine/configs/service/face_verification.yaml`

```protobuf
rpc ExtractFeature(FeatureRequest) returns (FeatureResponse)
// FeatureResponse: 512-dim float vector
```

#### OCR Services

**Configs**: `engine/configs/service/ocr_*.yaml`

| Class | Use case |
|-------|---------|
| `GeneralOCRService` | Generic printed text |
| `IDCardOCRService` | Identity cards |
| `DocumentOCRService` | Documents / forms |
| `HandwritingOCRService` | Handwritten text |

---

### 3. Media Manager — HTTP REST (outbound, optional)

Used when `WORKFLOW_MEDIA_DATA_SOURCE=media_manager` (alternative to local FFmpeg).

**Config**: `WORKFLOW_MEDIA_MANAGER_HOST`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/manager/v1/create` | Allocate a media-processing task |
| GET | `/manager/v1/ready?media_id=X` | Check media readiness |
| GET | `/manager/v1/media_metadata?task_id=X` | Fetch video metadata |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WORKFLOW_WORKFLOW_MANAGER_HOST` | Yes | — | gRPC address of Workflow Manager (e.g. `localhost:50051`) |
| `WORKFLOW_MEDIA_MANAGER_HOST` | Conditional | — | HTTP base URL of Media Manager (needed when `media_data_source=media_manager`) |
| `WORKFLOW_MEDIA_DATA_SOURCE` | No | `local_ffmpeg` | `local_ffmpeg` or `media_manager` |
| `WORKFLOW_S3_ENDPOINT` | No | — | MinIO / S3 endpoint URL |
| `WORKFLOW_S3_ACCESS_KEY` | No | — | S3 access key |
| `WORKFLOW_S3_SECRET_KEY` | No | — | S3 secret key |
| `WORKFLOW_S3_BUCKET` | No | — | S3 bucket name |
| `WORKFLOW_IS_DEBUG` | No | `false` | Enable debug logging |

---

## AI Service Configuration (Dynaconf YAML)

Each AI service reads its gRPC host/port from a YAML file. Example (`engine/configs/service/auc.yaml`):

```yaml
host: auc-service
port: 50052
timeout: 60
max_retries: 3
```

Override at runtime with env vars prefixed `IDRS_ENGINE_CONF_`, e.g.:
```bash
IDRS_ENGINE_CONF_AUC__HOST=my-auc-host
```

---

## Internal Module Interfaces

### Job Interface (ABC)

```python
class Job(ABC):
    @abstractmethod
    async def run(self, task_context: TaskContext) -> None: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
```

### GRPCService Interface (ABC)

```python
class GRPCService(Service, ABC):
    host: str
    port: int

    def get_channel(self) -> grpc.Channel: ...
    def close_channel(self) -> None: ...
```

### MediaStream Interface

```python
class MediaStream:
    def register_frame_channel(self, name: str, channel: FrameChannel) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...

class FrameChannel:
    fps: float
    queue: CircularQueue[Frame]
    def put(self, frame: Frame) -> None: ...
    def get(self) -> Frame | None: ...
```

---

## Key Domain Types

```python
# Task input
class Task:
    id: int
    name: str
    media: Media          # video URL / path / metadata
    scenario: Scenario    # rule configuration tree
    rule: Rule | None
    participants: list[Participant]

class Media:
    path: str
    url: str
    meta: MediaMeta | None  # fps, width, height, duration

class RulePoint:
    id: int
    category: str           # banword | subtitle | verification | ...
    banword_cfg: BanwordCfg | None
    subtitle_cfg: SubtitleCfg | None
    script_cfg: ScriptCfg | None
    verification_cfgs: list[VerificationCfg | None]
    document_cfgs: list[DocumentCfg | None]

# Report output
class Report:
    status: str             # "passed" | "failed"
    rule_section_reports: list[RuleSectionReport]
    reasons: list[list[str]]

class RulePointReport:
    id: int
    banword_detection_report: BannedWordDetectionReport | None
    subtitle_matching_report: SubtitleMatchingReport | None
    person_tracking_report: PersonTrackingReport | None
    script_match_report: ScriptMatchingReport | None
    reasons: list[str]
```
