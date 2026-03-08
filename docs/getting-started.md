# 快速上手

## 前置要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | 3.13+ | 两个服务均需要 |
| [uv](https://docs.astral.sh/uv/) | 最新版 | 包管理器 |
| FFmpeg | 任意版本 | Worker 本地视频解码需要 |
| Docker | 20+ | 容器化部署（可选） |

安装 uv：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 启动 Workflow Manager

```bash
cd workflow-manager

# 安装依赖
uv sync

# 生成 gRPC 代码（首次运行或修改 proto 后执行）
uv run python -m grpc_tools.protoc \
  -I./src/workflow_manager/grpc \
  --python_out=./src/workflow_manager/grpc \
  --grpc_python_out=./src/workflow_manager/grpc \
  ./src/workflow_manager/grpc/job_manager.proto

# 复制并编辑配置
cp .env.example .env

# 启动（同时启动 HTTP :8000 和 gRPC :50051）
uv run python -m workflow_manager
```

验证服务正常：

```bash
curl http://localhost:8000/ping
# → {"status": "ok"}
```

---

## 启动 Workflow Worker

```bash
cd workflow-worker

# 安装全部依赖（含媒体处理、gRPC 等可选依赖）
uv sync --all-extras
# 或使用辅助脚本
./scripts/install_deps.sh all

# 复制并编辑配置
cp .env.example .env
```

`.env` 中至少需要设置：

```bash
WORKFLOW_WORKFLOW_MANAGER_HOST=localhost:50051   # Manager gRPC 地址
WORKFLOW_MEDIA_DATA_SOURCE=local_ffmpeg          # 视频解码方式
```

```bash
# 启动 Worker
uv run python -m workflow_worker.interfaces.cli.worker
```

---

## 配置说明

### Workflow Manager（`.env`）

```bash
# 基础
DEBUG=false
HOST=0.0.0.0
PORT=8000

# 数据库（开发用 SQLite，生产用 PostgreSQL）
DATABASE_URL=sqlite:///./workflow_manager.db
# DATABASE_URL=postgresql://user:password@localhost:5432/workflow_manager

# gRPC
GRPC_ENDPOINT=0.0.0.0:50051
GRPC_ENABLED=true

# 外部任务平台
EXTERNAL_API_URL=http://external-api-service:8080
EXTERNAL_API_TIMEOUT=30

# 调度器
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_SECONDS=5
```

### Workflow Worker（`.env`）关键变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WORKFLOW_WORKFLOW_MANAGER_HOST` | — | Manager gRPC 地址（必填） |
| `WORKFLOW_MEDIA_DATA_SOURCE` | `local_ffmpeg` | `local_ffmpeg` 或 `media_manager` |
| `WORKFLOW_MEDIA_MANAGER_HOST` | — | Media Manager HTTP 地址（当 source=media_manager 时必填）|
| `WORKFLOW_IS_DEBUG` | `false` | 开启后打印详细日志 |

完整变量列表见 [workflow-worker/docs/guides/INTERFACES.md](../workflow-worker/docs/guides/INTERFACES.md)。

---

## 运行测试

```bash
# Workflow Manager
cd workflow-manager
uv run pytest
uv run pytest --cov=src/workflow_manager --cov-report=html

# Workflow Worker
cd workflow-worker
uv run pytest
uv run pytest --cov
```

---

## 开发工具

### Workflow Manager

```bash
# 代码检查
uv run ruff check .
# 自动修复
uv run ruff check --fix .
# 格式化
uv run ruff format .
# 类型检查
uv run mypy src/
```

### Workflow Worker

```bash
uv run black src/          # 格式化
uv run pylint src/         # Lint
uv run basedpyright src/   # 类型检查
```

---

## 创建一个测试任务

Manager 启动后，可以通过 REST API 创建任务：

```bash
# 创建任务（task_id 来自外部任务平台）
curl -X POST http://localhost:8000/api/v1/job/create_job \
  -H "Content-Type: application/json" \
  -d '{"task_id": 123, "project_name": "test_project"}'

# 查询任务状态
curl -X POST http://localhost:8000/api/v1/job/get_job \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'

# 分页查询任务列表
curl -X POST http://localhost:8000/api/v1/job/list_jobs \
  -H "Content-Type: application/json" \
  -d '{"page": 1, "page_size": 10}'
```
