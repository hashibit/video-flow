#!/usr/bin/env bash
# Compile all proto files for the project

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔨 Compiling all proto files..."

# Compile workflow_common.proto (messages only)
python3 -m grpc_tools.protoc -I./ --python_out=./ --pyi_out=./ workflow_common.proto

# Compile workflow_manager.proto (service + messages)
python3 -m grpc_tools.protoc -I./ --python_out=./ --pyi_out=./ --grpc_python_out=./ workflow_manager.proto

# Compile workflow_worker.proto (service + messages)
python3 -m grpc_tools.protoc -I./ --python_out=./ --pyi_out=./ --grpc_python_out=./ workflow_worker.proto

# Compile media_service.proto (service + messages - contains both service and model definitions)
python3 -m grpc_tools.protoc -I./ --python_out=./ --pyi_out=./ --grpc_python_out=./ media_service.proto

echo "✅ All proto files compiled successfully"
echo ""
echo "📁 Generated files:"
ls -lh *_pb2*.py *.pyi 2>/dev/null || echo "  No Python files generated yet"