#!/usr/bin/env bash
# Regenerate gRPC Python stubs from all .proto files.
# Run from the workflow-ai directory: ./src/workflow_ai/grpc/build.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PROTO_DIR="${REPO_ROOT}/../../proto"
OUT_DIR="${SCRIPT_DIR}"

echo "Proto source : ${PROTO_DIR}"
echo "Output target: ${OUT_DIR}"

python -m grpc_tools.protoc \
    -I"${PROTO_DIR}" \
    --python_out="${OUT_DIR}" \
    --grpc_python_out="${OUT_DIR}" \
    "${PROTO_DIR}"/*.proto

echo "Done. Generated files in ${OUT_DIR}:"
ls "${OUT_DIR}"/*_pb2*.py 2>/dev/null || echo "  (none)"
