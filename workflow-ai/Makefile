.PHONY: proto build run stop logs dev clean

# Regenerate gRPC Python stubs from proto files
proto:
	python -m grpc_tools.protoc \
		-I./proto \
		--python_out=./src/workflow_ai/grpc \
		--grpc_python_out=./src/workflow_ai/grpc \
		./proto/*.proto
	@echo "gRPC stubs generated."

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

# Run locally (requires uv and generated stubs)
dev: proto
	uv run python -m workflow_ai

# Clean generated pb2 files
clean:
	find src/workflow_ai/grpc -name "*_pb2*.py" -delete
