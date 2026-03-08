# gRPC API Reference

Workflow Manager and Workflow Worker communicate exclusively over gRPC. The protocol is defined in:

- `workflow-manager/src/workflow_manager/grpc/job_manager.proto`
- `workflow-worker/src/workflow_worker/interfaces/api/workflow_manager.proto` (client-side mirror)

---

## Service Definition

```protobuf
package task_workflow;

service JobManagerService {
  rpc GetJob(GetJobRequest) returns (GetJobResponse) {}
  rpc CreateReport(CreateReportRequest) returns (CreateReportResponse) {}
  rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse) {}
}
```

Default listen address: `0.0.0.0:50051` (configured via `GRPC_ENDPOINT`)

---

## RPC Methods

### GetJob

The Worker polls for the next available job approximately every 10 seconds.

The Manager atomically transitions the job from `PENDING`/`RETRY` to `RUNNING` and fetches the full task details from the external platform.

**Request**

```protobuf
message GetJobRequest {
  string worker_id = 1;  // Unique identifier of the worker
}
```

**Response**

```protobuf
message GetJobResponse {
  JobInfo job_info = 1;  // Empty if no job is available
}

message JobInfo {
  uint64 id        = 1;  // Internal job ID (Manager)
  uint64 task_id   = 2;  // External task platform task ID
  string task_json = 3;  // Full task details (JSON string)
}
```

**`task_json` structure example**

```json
{
  "id": 67890,
  "name": "Inspection Task Name",
  "media": {
    "path": "/path/to/video.mp4",
    "url": "http://...",
    "meta": { "fps": "25", "width": 1920, "height": 1080, "duration": 3600 }
  },
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
  "participants": [
    { "name": "Sales Agent", "cards": [] }
  ]
}
```

---

### CreateReport

The Worker submits the inspection report after completing a job.

Upon receipt, the Manager:
1. Forwards the report to the external platform (`POST /report/create`)
2. Updates job status to `SUCCESS`; triggers retry logic on failure

**Request**

```protobuf
message CreateReportRequest {
  uint64    job_id     = 1;
  uint64    task_id    = 2;
  JobReport job_report = 3;
}

message JobReport {
  uint64    id         = 1;
  string    name       = 2;
  string    value_json = 3;  // Report content (JSON string)
  string    message    = 4;  // Error or status message
  Timestamp created_at = 5;
}
```

**`value_json` structure example**

```json
{
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
}
```

**Response**

```protobuf
message CreateReportResponse {
  uint64    job_id     = 1;
  uint64    task_id    = 2;
  JobReport job_report = 3;
}
```

---

### Heartbeat

Workers send periodic heartbeats reporting the list of currently running job IDs. The Manager uses this to detect stale `RUNNING` jobs and roll them back when a Worker goes offline.

**Request**

```protobuf
message HeartbeatRequest {
  string           worker_id       = 1;
  repeated uint64  running_job_ids = 2;  // Currently executing job IDs
}
```

**Response**

```protobuf
message HeartbeatResponse {
  string worker_id = 1;
}
```

---

## Retry Behavior

```
Worker returns empty report / job execution fails
          │
          ▼
   Workflow Manager
          │
          ├── retry_times < 10  →  status = RETRY
          │                        re-queued for next GetJob call
          │
          └── retry_times >= 10 →  status = FAILED
                                   external platform notified

Worker heartbeat timeout
          │
          ▼
   Manager detects stale RUNNING job
          │
          └──► rolls back to RETRY
```

---

## Manual Testing with grpcurl

```bash
# List all services
grpcurl -plaintext localhost:50051 list

# Fetch the next available job
grpcurl -plaintext \
  -d '{"worker_id": "test-worker-1"}' \
  localhost:50051 task_workflow.JobManagerService/GetJob

# Submit a report
grpcurl -plaintext \
  -d '{
    "job_id": 1,
    "task_id": 123,
    "job_report": {
      "name": "test_report",
      "value_json": "{\"status\": \"success\"}",
      "message": ""
    }
  }' \
  localhost:50051 task_workflow.JobManagerService/CreateReport

# Send a heartbeat
grpcurl -plaintext \
  -d '{"worker_id": "test-worker-1", "running_job_ids": [1, 2]}' \
  localhost:50051 task_workflow.JobManagerService/Heartbeat
```

---

## Regenerating gRPC Code

Run these commands after modifying any `.proto` file:

```bash
# Manager side
cd workflow-manager
uv run python -m grpc_tools.protoc \
  -I./src/workflow_manager/grpc \
  --python_out=./src/workflow_manager/grpc \
  --grpc_python_out=./src/workflow_manager/grpc \
  ./src/workflow_manager/grpc/job_manager.proto

# Worker side
cd workflow-worker
./src/workflow_worker/interfaces/api/build.sh
```
