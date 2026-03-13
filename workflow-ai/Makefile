.PHONY: proto build run stop logs dev

# Regenerate shared gRPC stubs (delegates to workflow-proto)
proto:
	$(MAKE) -C ../workflow-proto proto

# Build Docker image
build:
	docker build -t workflow-ai:latest .

# Start all services via Docker Compose
run:
	docker compose up -d

# Stop containers
stop:
	docker compose down

# Tail logs
logs:
	docker compose logs -f workflow-ai

# Run locally
dev:
	uv run python -m workflow_ai
