# Video Flow

视频质检工作流系统（Video Quality Inspection Workflow System）。

该系统对视频内容进行多维度 AI 分析（语音识别、人脸检测、OCR、违禁词检测、台词匹配等），自动生成结构化质检报告。

---

## 系统组成

```
video-flow/
├── workflow-manager/   # 任务调度中心（REST + gRPC 服务）
└── workflow-worker/    # AI 分析执行节点（DDD 架构）
```

| 组件 | 职责 |
|------|------|
| **Workflow Manager** | 管理任务队列、向 Worker 分发任务、收集执行结果、对接外部任务平台 |
| **Workflow Worker** | 拉取任务、解码视频、并行调用 AI 服务、生成质检报告 |

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     External Task Platform                   │
│         创建任务 (REST)              接收报告 (REST)           │
└─────────────────┬───────────────────────────┬───────────────┘
                  │                           │
                  ▼                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      Workflow Manager                        │
│  - REST API (FastAPI)     :8000                              │
│  - gRPC (JobManagerService)  :50051                          │
│  - PostgreSQL 任务队列                                        │
│  - 自动调度 + 最多 10 次重试                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ gRPC: GetJob / CreateReport / Heartbeat
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ Worker 1 │ │ Worker 2 │ │ Worker N │   （水平扩展）
       └──────────┘ └──────────┘ └──────────┘
              │
              │ gRPC
   ┌──────────┼────────────────────┐
   ▼          ▼                    ▼
┌──────┐  ┌─────────┐  ┌──────────────────────┐
│ AUC  │  │ Det/    │  │ OCR / Feature /      │
│(ASR) │  │ Track   │  │ Face Verify Services │
└──────┘  └─────────┘  └──────────────────────┘
```

---

## 快速开始

### 前置依赖

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 包管理器
- Docker & Docker Compose（容器化部署）

### 本地开发

```bash
# 启动 Workflow Manager
cd workflow-manager
uv sync
cp .env.example .env    # 按需修改配置
uv run python -m workflow_manager

# 启动 Workflow Worker（新终端）
cd workflow-worker
uv sync --all-extras
cp .env.example .env    # 设置 WORKFLOW_WORKFLOW_MANAGER_HOST 等
uv run python -m workflow_worker.interfaces.cli.worker
```

### Docker Compose 部署

```bash
# 生产环境（PostgreSQL）
cd workflow-manager
docker-compose up -d

# Worker
cd workflow-worker
make build && make run
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [系统架构](docs/architecture.md) | 整体设计、模块职责、依赖关系 |
| [快速上手](docs/getting-started.md) | 本地开发环境搭建与运行 |
| [gRPC API 参考](docs/grpc-api.md) | Manager ↔ Worker 通信协议详解 |
| [部署指南](docs/deployment.md) | Docker / 生产环境部署 |
| [Workflow Manager 文档](workflow-manager/README.md) | Manager 详细文档 |
| [Workflow Worker 文档](workflow-worker/README.md) | Worker 详细文档 |

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.13+ |
| 包管理 | uv |
| Manager Web 框架 | FastAPI + Uvicorn |
| Manager 数据库 | SQLAlchemy + PostgreSQL / SQLite |
| Manager 调度器 | APScheduler |
| 通信协议 | gRPC + Protobuf |
| Worker 异步框架 | asyncio |
| 视频解码 | FFmpeg (ffmpeg-python) / gRPC Media Manager |
| 图像处理 | OpenCV |
| 对象存储 | MinIO (S3 兼容) |
| 容器化 | Docker（多阶段构建） |
| 数据校验 | Pydantic v2 |
| Worker 配置 | Dynaconf |
