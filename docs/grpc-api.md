# gRPC API 参考

Workflow Manager 与 Workflow Worker 通过 gRPC 通信。协议定义位于：

- `workflow-manager/src/workflow_manager/grpc/job_manager.proto`
- `workflow-worker/src/workflow_worker/interfaces/api/workflow_manager.proto`（客户端侧镜像）

---

## 服务定义

```protobuf
package task_workflow;

service JobManagerService {
  rpc GetJob(GetJobRequest) returns (GetJobResponse) {}
  rpc CreateReport(CreateReportRequest) returns (CreateReportResponse) {}
  rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse) {}
}
```

默认监听地址：`0.0.0.0:50051`（由 `GRPC_ENDPOINT` 配置）

---

## RPC 方法

### GetJob

Worker 轮询获取下一个待执行任务（约每 10 秒一次）。

Manager 原子性地将任务从 `PENDING`/`RETRY` 转为 `RUNNING`，并从外部平台拉取完整 task_json。

**请求**

```protobuf
message GetJobRequest {
  string worker_id = 1;  // Worker 唯一标识
}
```

**响应**

```protobuf
message GetJobResponse {
  JobInfo job_info = 1;  // 若无可用任务则为空
}

message JobInfo {
  uint64 id       = 1;   // job ID（Manager 内部）
  uint64 task_id  = 2;   // 外部任务平台 task ID
  string task_json = 3;  // 完整任务详情（JSON 字符串）
}
```

**task_json 结构示例**

```json
{
  "id": 67890,
  "name": "质检任务名称",
  "media": {
    "path": "/path/to/video.mp4",
    "url": "http://...",
    "meta": { "fps": "25", "width": 1920, "height": 1080, "duration": 3600 }
  },
  "rule": {
    "rule_sections": [
      {
        "id": 1,
        "name": "合规检查",
        "rule_points": [
          { "id": 10, "category": "banword", "banword_cfg": { "words": ["违禁词"] } },
          { "id": 11, "category": "subtitle", "subtitle_cfg": { "fps": 5 } }
        ]
      }
    ]
  },
  "participants": [
    { "name": "销售顾问", "cards": [] }
  ]
}
```

---

### CreateReport

Worker 完成任务后提交质检报告。

Manager 收到后：
1. 将报告提交至外部任务平台（`POST /report/create`）
2. 更新任务状态为 `SUCCESS`；若失败则进入重试逻辑

**请求**

```protobuf
message CreateReportRequest {
  uint64    job_id     = 1;
  uint64    task_id    = 2;
  JobReport job_report = 3;
}

message JobReport {
  uint64    id         = 1;
  string    name       = 2;
  string    value_json = 3;  // 报告内容（JSON 字符串）
  string    message    = 4;  // 错误或状态说明
  Timestamp created_at = 5;
}
```

**value_json 结构示例**

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
            "hit_words": ["违禁词"],
            "hit_times": [["00:01:23", "00:01:25"]]
          },
          "reasons": ["检测到违禁词：违禁词"]
        }
      ],
      "reasons": ["合规检查不通过"]
    }
  ],
  "reasons": [["合规检查不通过"]]
}
```

**响应**

```protobuf
message CreateReportResponse {
  uint64    job_id     = 1;
  uint64    task_id    = 2;
  JobReport job_report = 3;
}
```

---

### Heartbeat

Worker 定期发送心跳，上报当前正在执行的 job ID 列表。Manager 以此监控 Worker 存活状态，对超时未响应的 RUNNING 任务执行回滚。

**请求**

```protobuf
message HeartbeatRequest {
  string           worker_id       = 1;
  repeated uint64  running_job_ids = 2;  // 当前执行中的 job ID 列表
}
```

**响应**

```protobuf
message HeartbeatResponse {
  string worker_id = 1;
}
```

---

## 重试机制

```
Worker 返回空报告 / 任务执行失败
          │
          ▼
   Workflow Manager
          │
          ├── retry_times < 10  →  status = RETRY（等待下次 GetJob 重新分发）
          │
          └── retry_times >= 10 →  status = FAILED（通知外部平台）

Worker 心跳超时
          │
          ▼
   Manager 检测到 RUNNING 任务长时间无心跳
          │
          └──► 回滚至 RETRY
```

---

## 使用 grpcurl 手动测试

```bash
# 列出所有服务
grpcurl -plaintext localhost:50051 list

# 获取下一个任务
grpcurl -plaintext \
  -d '{"worker_id": "test-worker-1"}' \
  localhost:50051 task_workflow.JobManagerService/GetJob

# 提交报告
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

# 发送心跳
grpcurl -plaintext \
  -d '{"worker_id": "test-worker-1", "running_job_ids": [1, 2]}' \
  localhost:50051 task_workflow.JobManagerService/Heartbeat
```

---

## 生成 gRPC 代码

修改 proto 文件后需重新生成 Python 代码：

```bash
# Workflow Manager 端
cd workflow-manager
uv run python -m grpc_tools.protoc \
  -I./src/workflow_manager/grpc \
  --python_out=./src/workflow_manager/grpc \
  --grpc_python_out=./src/workflow_manager/grpc \
  ./src/workflow_manager/grpc/job_manager.proto

# Workflow Worker 端
cd workflow-worker
# 参考 src/workflow_worker/interfaces/api/build.sh
./src/workflow_worker/interfaces/api/build.sh
```
