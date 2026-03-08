#!/bin/bash
# 依赖安装脚本 - 根据需要选择性安装依赖组

set -e

echo "🚀 Video Inspection Workflow - 依赖安装脚本"
echo "=============================================="
echo ""
echo "可用选项:"
echo "  all       - 安装所有依赖（推荐用于生产环境）"
echo "  core      - 仅核心依赖（已自动安装）"
echo "  grpc      - gRPC 和 Protobuf"
echo "  media     - 媒体处理 (numpy, opencv-python 等)"
echo "  storage   - 存储支持 (minio)"
echo "  async     - 异步支持 (janus)"
echo "  database  - 数据库 (psycopg2-binary)"
echo "  thrift    - Thrift 支持"
echo "  tools     - 其他工具包"
echo "  dev       - 开发工具"
echo ""

# 检查参数
if [ -z "$1" ]; then
    echo "用法: $0 <选项>"
    echo ""
    echo "示例:"
    echo "  $0 all           # 安装所有依赖"
    echo "  $0 grpc media    # 安装 gRPC 和媒体处理依赖"
    echo "  $0 dev           # 安装开发工具"
    exit 1
fi

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "❌ 错误: 虚拟环境不存在。请先运行 'uv sync'"
    exit 1
fi

# 安装指定的依赖组
echo "📦 安装依赖组: $@"
uv sync $@

echo ""
echo "✅ 安装完成！"
echo ""
echo "激活虚拟环境:"
echo "  source .venv/bin/activate"
echo ""
echo "运行项目:"
echo "  python -m workflow_worker.interfaces.cli.worker"
