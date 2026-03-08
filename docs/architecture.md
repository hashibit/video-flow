# 系统架构

## 整体设计

Video Flow 是一个分布式视频质检系统，由两个核心服务组成：

- **Workflow Manager**：任务控制中心，负责任务入队、分发、状态管理和结果收集。
- **Workflow Worker**：执行节点，负责视频解码、多路 AI 分析和报告生成。

两者通过 gRPC 通信，支持 Worker 水平扩展。

---

## 服务职责

### Workflow Manager

```
src/workflow_manager/
├── api/            # REST API（FastAPI）
│   └── handlers/   # create_job / get_job / list_jobs / ping
├── client/         # 外部任务平台 HTTP 客户端
├── config/         # 配置（YAML + .env）
├── core/           # 业务核心
│   ├── models.py       # SQLAlchemy 模型 + Pydantic 模式
│   ├── repositories.py # 数据访问层（Repository 模式）
│   ├── services.py     # 业务逻辑层
│   └── database.py     # 数据库会话管理
├── grpc/           # gRPC 服务端（JobManagerService）
└── scheduler/      # APScheduler 定时调度
```

**架构模式**：Repository + Service + Dependency Injection（FastAPI）

**状态机**：

```
PENDING ──► RUNNING ──► SUCCESS
    ▲            │
    │     (失败)  ▼
  RETRY ◄─────────
    │
    └──► FAILED（重试次数 ≥ 10）
```

任务状态码与 Go 版本保持兼容：

| 状态 | 值 | 含义 |
|------|----|------|
| PENDING | 0 | 等待调度 |
| RUNNING | 1 | 执行中 |
| RETRY | 2 | 失败，等待重试 |
| SUCCESS | 16 | 成功 |
| FAILED | 17 | 超过最大重试次数 |
| NO_NEED | 32 | 跳过 |

---

### Workflow Worker

Worker 采用 **DDD（领域驱动设计）** 分层架构：

```
src/workflow_worker/
├── domain/          # 领域层：核心业务实体，无任何外部依赖
│   └── entities/    # Task, Rule, Report, Frame, Dialogue, …
│
├── services/        # 服务层：AI 算法服务客户端（gRPC）
│   └── ai/
│       ├── auc/     # 语音识别（AUC Service / ASR）
│       ├── det/     # 人体检测（Detection Service）
│       ├── feat/    # 特征提取
│       ├── track/   # 跨帧人物追踪（Track Service）
│       └── ocr/     # 多种 OCR（通用、手写、身份证、文档）
│
├── applications/    # 应用层：任务编排与业务流程
│   ├── jobs/        # 各类 Job 实现（每个 RulePoint 对应一个 Job）
│   └── workflows/   # JobRunner（任务生命周期管理）
│
├── infrastructure/  # 基础设施层：技术实现细节
│   ├── media_stream/  # 视频解码管道（FFmpeg / gRPC Media Manager）
│   ├── external/      # 外部服务 HTTP 客户端
│   └── circular_queue.py  # 环形帧缓冲队列
│
├── interfaces/      # 接口层：对外暴露能力
│   ├── api/         # gRPC 客户端（连接 Workflow Manager）
│   ├── cli/         # 命令行入口（worker.py）
│   └── events/      # 事件工厂
│
└── shared/          # 跨层通用模块
    ├── config/      # Dynaconf 配置
    ├── logging/     # 统一日志
    └── utils/       # 工具函数
```

**依赖方向**（严格遵守）：

```
Interfaces → Applications → Services → Domain
                   │               │
             Infrastructure ◄──────┘
                   ▲
                   └── Shared（所有层均可使用）
```

---

## 视频分析流水线

Worker 收到任务后，按以下流程并行处理：

```
Job Runner
    │
    ├─► 解析 TaskJSON → Task 实体
    ├─► 创建 MediaStream（FFmpeg 解码 / gRPC 媒体服务）
    ├─► 按 RulePoint 实例化 Job 列表
    │
    ├─► 第一阶段（并行，消费帧队列）
    │       SpeechRecognitionJob    → AUC gRPC → Dialogue
    │       PersonTrackingJob       → Det + Track gRPC
    │       SubtitleMatchingJob     → OCR gRPC
    │       CardRecognitionJob      → OCR gRPC
    │       DocumentRecognitionJob  → OCR gRPC
    │       SignatureRecognitionJob → OCR gRPC
    │
    ├─► 第二阶段（依赖第一阶段结果）
    │       BannedWordDetectionJob  → 使用 Dialogue 文本
    │       ScriptMatchingJob       → 使用 Dialogue 文本
    │
    └─► ReportJob → 聚合结果 → 生成 Report JSON
```

### 帧分发机制

```
视频源（FFmpeg / gRPC）
        │
        ▼
  CircularQueue（1024 帧环形缓冲）
        │
        └─► dispatch_thread 按各模块 FPS 分发
                │
       ┌────────┼────────┬────────┐
       ▼        ▼        ▼        ▼
  FrameChannel  Channel  Channel  …
  (OCR, 5fps) (Det,25fps)(Trk,25fps)
```

每个 `FrameChannel` 是独立的环形队列，各 Job 只消费自己的队列，互不干扰。

---

## 关键数据实体

| 实体 | 说明 |
|------|------|
| `Task` | 一次质检任务：视频信息、规则树、参与人员 |
| `Rule / RuleSection / RulePoint` | 规则三级层次，每个 RulePoint 对应一类检测 |
| `Job` | 对应一个 RulePoint 的执行单元 |
| `Frame` | 从视频解码出的单帧图像 |
| `FrameChannel` | 供某类算法消费的帧队列（含 FPS 控制）|
| `Dialogue` | ASR 识别结果：话语列表 + 词级时间戳 |
| `Report` | 每个 RulePoint 的检测结果，汇总为最终质检报告 |

---

## 扩展性

- **Worker 水平扩展**：无状态设计，多 Worker 实例同时连接同一 Manager，每实例最多并发 4 个任务。
- **新增检测类型**：在 `applications/jobs/` 下新增 Job 类，在 `JobFactory` 中注册，无需修改其他层。
- **数据库切换**：Manager 支持 SQLite（开发）和 PostgreSQL（生产），通过 `DATABASE_URL` 切换。
- **视频源切换**：Worker 支持本地 FFmpeg 和远程 gRPC Media Manager，通过 `WORKFLOW_MEDIA_DATA_SOURCE` 切换。
