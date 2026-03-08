#!/usr/bin/env bash
# Clean all compiled proto files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🧹 Cleaning all compiled proto files..."
rm -rf *_pb2.py *_pb2_grpc.py *.pyi
echo "✅ Clean completed"