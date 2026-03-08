# 部署指南

## 架构概览

```
                 ┌─────────────────────┐
                 │   Workflow Manager   │
                 │   :8000  (REST)      │
                 │   :50051 (gRPC)      │
                 │   PostgreSQL :5432   │
                 └──────────┬──────────┘
                            │ gRPC
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │  Worker 1  │  │  Worker 2  │  │  Worker N  │
     └────────────┘  └────────────┘  └────────────┘
```

---

## Workflow Manager 部署

### 生产环境（Docker Compose + PostgreSQL）

```bash
cd workflow-manager

# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f workflow-manager

# 停止
docker-compose down

# 停止并清除数据卷
docker-compose down -v
```

`docker-compose.yml` 包含：
- Workflow Manager 服务（Python 3.13）
- PostgreSQL 16 数据库
- 持久化数据卷
- 健康检查
- 自动重启策略

服务端口：

| 服务 | 端口 |
|------|------|
| HTTP API | 8000 |
| gRPC | 50051 |
| PostgreSQL | 5432 |

### 开发环境（SQLite，热重载）

```bash
cd workflow-manager
docker-compose -f docker-compose.dev.yml up
```

特点：SQLite 数据库（无需外部 DB）、源码挂载、热重载。

### 单容器运行

```bash
# 构建镜像
docker build -t workflow-manager:latest .

# 运行
docker run -d \
  -p 8000:8000 \
  -p 50051:50051 \
  -e DATABASE_URL=sqlite:///./data/workflow_manager.db \
  -e EXTERNAL_API_URL=http://external-api:8080 \
  -v $(pwd)/data:/data \
  workflow-manager:latest
```

---

## Workflow Worker 部署

```bash
cd workflow-worker

# 构建镜像
make build

# 启动容器
make run

# 查看日志
make logs

# 停止
make stop
```

或直接使用脚本：

```bash
./scripts/docker_build.sh
./scripts/docker_run.sh
```

### Worker 关键环境变量

| 变量 | 示例值 | 说明 |
|------|--------|------|
| `WORKFLOW_WORKFLOW_MANAGER_HOST` | `workflow-manager:50051` | Manager gRPC 地址 |
| `WORKFLOW_MEDIA_DATA_SOURCE` | `local_ffmpeg` | 视频解码方式 |
| `WORKFLOW_MEDIA_MANAGER_HOST` | `http://media-manager:8080` | 媒体服务地址（可选）|
| `WORKFLOW_IS_DEBUG` | `false` | 调试日志 |

---

## 多 Worker 扩展

每个 Worker 实例最多并发执行 **4 个任务**。通过增加 Worker 实例数量实现水平扩展。

所有 Worker 指向同一个 Manager 的 gRPC 地址即可，Manager 侧无需额外配置。

```yaml
# docker-compose.yml 示例（多 Worker）
services:
  workflow-manager:
    image: workflow-manager:latest
    ports:
      - "8000:8000"
      - "50051:50051"

  worker-1:
    image: workflow-worker:latest
    environment:
      WORKFLOW_WORKFLOW_MANAGER_HOST: workflow-manager:50051

  worker-2:
    image: workflow-worker:latest
    environment:
      WORKFLOW_WORKFLOW_MANAGER_HOST: workflow-manager:50051

  worker-3:
    image: workflow-worker:latest
    environment:
      WORKFLOW_WORKFLOW_MANAGER_HOST: workflow-manager:50051
```

---

## 健康检查

```bash
# Manager HTTP 健康检查
curl http://localhost:8000/ping

# gRPC 连通性（需要 grpcurl）
grpcurl -plaintext localhost:50051 list
```

---

## 数据库管理

### PostgreSQL 连接字符串

```
DATABASE_URL=postgresql://user:password@host:5432/workflow_manager
```

### 重置数据库（仅开发环境）

```python
from workflow_manager.core.database import drop_db, init_db

drop_db()   # 删除所有表
init_db()   # 重新创建表
```

### 备份（PostgreSQL）

```bash
# 备份
docker exec workflow-manager-db pg_dump -U postgres workflow_manager > backup.sql

# 恢复
docker exec -i workflow-manager-db psql -U postgres workflow_manager < backup.sql
```

---

## 日志

两个服务均将结构化日志输出到 stdout，便于接入 ELK、Loki 等日志系统。

Worker 开启调试日志：

```bash
WORKFLOW_IS_DEBUG=true uv run python -m workflow_worker.interfaces.cli.worker
```

Manager 开启调试模式：

```bash
DEBUG=true uv run python -m workflow_manager
```
