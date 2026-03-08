.PHONY: help build build-no-cache push run stop logs shell clean test

# 默认目标
.DEFAULT_GOAL := help

# 变量
IMAGE_NAME := workflow-worker
VERSION ?= latest
REGISTRY ?=
FULL_IMAGE_NAME := $(REGISTRY)$(IMAGE_NAME):$(VERSION)
CONTAINER_NAME := workflow-worker

# 颜色
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

help: ## 显示帮助信息
	@echo "$(GREEN)Workflow Worker - Docker 命令$(NC)"
	@echo ""
	@echo "用法:"
	@echo "  make [target]"
	@echo ""
	@echo "可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "示例:"
	@echo "  make build              # 构建镜像"
	@echo "  make build VERSION=1.0  # 构建指定版本"
	@echo "  make run                # 运行容器"
	@echo "  make logs               # 查看日志"

build: ## 构建 Docker 镜像
	@echo "$(GREEN)构建镜像: $(FULL_IMAGE_NAME)$(NC)"
	docker build -t $(FULL_IMAGE_NAME) -f Dockerfile .
	@if [ "$(VERSION)" != "latest" ]; then \
		docker tag $(FULL_IMAGE_NAME) $(REGISTRY)$(IMAGE_NAME):latest; \
		echo "$(GREEN)✅ 已打标签: $(REGISTRY)$(IMAGE_NAME):latest$(NC)"; \
	fi
	@echo "$(GREEN)✅ 构建完成$(NC)"
	@docker images $(IMAGE_NAME) --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"

build-no-cache: ## 构建 Docker 镜像（无缓存）
	@echo "$(GREEN)构建镜像（无缓存）: $(FULL_IMAGE_NAME)$(NC)"
	docker build --no-cache -t $(FULL_IMAGE_NAME) -f Dockerfile .
	@echo "$(GREEN)✅ 构建完成$(NC)"

push: ## 推送镜像到仓库
	@echo "$(GREEN)推送镜像: $(FULL_IMAGE_NAME)$(NC)"
	docker push $(FULL_IMAGE_NAME)
	@if [ "$(VERSION)" != "latest" ]; then \
		docker push $(REGISTRY)$(IMAGE_NAME):latest; \
	fi
	@echo "$(GREEN)✅ 推送完成$(NC)"

run: ## 运行容器
	@echo "$(GREEN)启动容器: $(CONTAINER_NAME)$(NC)"
	@docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@docker rm $(CONTAINER_NAME) 2>/dev/null || true
	@docker run -d \
		--name $(CONTAINER_NAME) \
		--restart unless-stopped \
		-v $(PWD)/logs:/app/logs \
		-e PYTHONUNBUFFERED=1 \
		$(FULL_IMAGE_NAME)
	@echo "$(GREEN)✅ 容器已启动$(NC)"
	@docker ps --filter "name=$(CONTAINER_NAME)"

dev: ## 开发模式运行（挂载源码）
	@echo "$(GREEN)开发模式启动容器$(NC)"
	@docker stop $(CONTAINER_NAME)-dev 2>/dev/null || true
	@docker rm $(CONTAINER_NAME)-dev 2>/dev/null || true
	@docker run -d \
		--name $(CONTAINER_NAME)-dev \
		-v $(PWD)/src:/app/src \
		-v $(PWD)/logs:/app/logs \
		-e PYTHONUNBUFFERED=1 \
		$(FULL_IMAGE_NAME)
	@echo "$(GREEN)✅ 开发容器已启动$(NC)"

stop: ## 停止容器
	@echo "$(GREEN)停止容器: $(CONTAINER_NAME)$(NC)"
	@docker stop $(CONTAINER_NAME) 2>/dev/null || echo "容器未运行"
	@docker stop $(CONTAINER_NAME)-dev 2>/dev/null || true

restart: stop run ## 重启容器

logs: ## 查看容器日志
	@docker logs -f $(CONTAINER_NAME)

logs-dev: ## 查看开发容器日志
	@docker logs -f $(CONTAINER_NAME)-dev

shell: ## 进入容器 shell
	@echo "$(GREEN)进入容器: $(CONTAINER_NAME)$(NC)"
	@docker exec -it $(CONTAINER_NAME) bash

shell-dev: ## 进入开发容器 shell
	@echo "$(GREEN)进入开发容器: $(CONTAINER_NAME)-dev$(NC)"
	@docker exec -it $(CONTAINER_NAME)-dev bash

clean: ## 清理容器和镜像
	@echo "$(YELLOW)清理容器和镜像$(NC)"
	@docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@docker stop $(CONTAINER_NAME)-dev 2>/dev/null || true
	@docker rm $(CONTAINER_NAME) 2>/dev/null || true
	@docker rm $(CONTAINER_NAME)-dev 2>/dev/null || true
	@echo "$(GREEN)✅ 清理完成$(NC)"

clean-images: ## 清理所有 workflow-worker 镜像
	@echo "$(YELLOW)清理所有 $(IMAGE_NAME) 镜像$(NC)"
	@docker images $(IMAGE_NAME) -q | xargs -r docker rmi -f || true
	@echo "$(GREEN)✅ 清理完成$(NC)"

test: ## 运行测试
	@echo "$(GREEN)运行测试$(NC)"
	@docker run --rm \
		-v $(PWD)/src:/app/src \
		-v $(PWD)/tests:/app/tests \
		$(FULL_IMAGE_NAME) \
		pytest tests/

compose-up: ## 使用 docker-compose 启动
	docker-compose up -d

compose-down: ## 使用 docker-compose 停止
	docker-compose down

compose-logs: ## 查看 docker-compose 日志
	docker-compose logs -f

inspect: ## 查看镜像详细信息
	@echo "$(GREEN)镜像信息: $(FULL_IMAGE_NAME)$(NC)"
	@docker inspect $(FULL_IMAGE_NAME) | jq '.[0]'

ps: ## 查看运行中的容器
	@docker ps --filter "ancestor=$(IMAGE_NAME)"

size: ## 查看镜像大小
	@echo "$(GREEN)镜像大小:$(NC)"
	@docker images $(IMAGE_NAME) --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"

# 快速构建和运行
all: build run ## 构建并运行

# 开发流程
dev-build: build-no-cache dev ## 构建并进入开发模式
