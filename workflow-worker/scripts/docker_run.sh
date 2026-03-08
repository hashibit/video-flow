#!/bin/bash
# Docker 容器运行脚本

set -e

# 配置
IMAGE_NAME="workflow-worker:latest"
CONTAINER_NAME="workflow-worker"

# 颜色输出
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# 停止并删除旧容器
cleanup() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "停止并删除旧容器: ${CONTAINER_NAME}"
        docker stop "${CONTAINER_NAME}" 2>/dev/null || true
        docker rm "${CONTAINER_NAME}" 2>/dev/null || true
    fi
}

# 运行容器
run_container() {
    log_info "启动容器: ${CONTAINER_NAME}"

    docker run -d \
        --name "${CONTAINER_NAME}" \
        --restart unless-stopped \
        -v "$(pwd)/logs:/app/logs" \
        -e PYTHONUNBUFFERED=1 \
        "${IMAGE_NAME}"

    log_info "✅ 容器已启动"
    log_info "查看日志: docker logs -f ${CONTAINER_NAME}"
}

# 主函数
main() {
    cleanup
    run_container

    # 显示容器状态
    docker ps --filter "name=${CONTAINER_NAME}"
}

main "$@"
