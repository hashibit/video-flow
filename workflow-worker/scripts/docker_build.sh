#!/bin/bash
# Docker 镜像构建脚本

set -e

# 配置
IMAGE_NAME="workflow-worker"
VERSION="${VERSION:-latest}"
REGISTRY="${REGISTRY:-}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助
show_help() {
    cat << EOF
Docker 镜像构建脚本

用法: $0 [选项]

选项:
    -v, --version VERSION    设置版本号（默认: latest）
    -r, --registry REGISTRY  设置镜像仓库
    -p, --push              构建后推送到仓库
    -n, --no-cache          使用 --no-cache 构建
    -h, --help              显示此帮助信息

示例:
    $0                       # 构建 workflow-worker:latest
    $0 -v 0.1.0              # 构建 workflow-worker:0.1.0
    $0 -v 0.1.0 -p           # 构建并推送
    $0 -r myregistry.com -v 0.1.0 -p  # 推送到私有仓库

EOF
}

# 解析参数
PUSH=false
NO_CACHE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2/"
            shift 2
            ;;
        -p|--push)
            PUSH=true
            shift
            ;;
        -n|--no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 构建镜像
FULL_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${VERSION}"

log_info "开始构建镜像: ${FULL_IMAGE_NAME}"
log_info "版本: ${VERSION}"
log_info "无缓存: ${NO_CACHE:-否}"

# 使用 BuildKit
export DOCKER_BUILDKIT=1

# 构建
docker build \
    ${NO_CACHE} \
    -t "${FULL_IMAGE_NAME}" \
    -f Dockerfile \
    .

if [ $? -eq 0 ]; then
    log_info "✅ 镜像构建成功: ${FULL_IMAGE_NAME}"

    # 显示镜像大小
    IMAGE_SIZE=$(docker images "${FULL_IMAGE_NAME}" --format "{{.Size}}")
    log_info "镜像大小: ${IMAGE_SIZE}"

    # 打标签 latest
    if [ "${VERSION}" != "latest" ]; then
        docker tag "${FULL_IMAGE_NAME}" "${REGISTRY}${IMAGE_NAME}:latest"
        log_info "✅ 已打标签: ${REGISTRY}${IMAGE_NAME}:latest"
    fi

    # 推送
    if [ "${PUSH}" = true ]; then
        log_info "推送镜像到仓库..."
        docker push "${FULL_IMAGE_NAME}"

        if [ "${VERSION}" != "latest" ]; then
            docker push "${REGISTRY}${IMAGE_NAME}:latest"
        fi

        log_info "✅ 镜像推送成功"
    fi
else
    log_error "❌ 镜像构建失败"
    exit 1
fi

log_info "完成！"
