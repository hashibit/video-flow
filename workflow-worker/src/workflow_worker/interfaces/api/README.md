# Job API Interface

This directory contains the Protocol Buffer definitions for the Job Management API.

## Files

- `common.proto` - Common message definitions shared across services
- `job_manager.proto` - Job Manager service definitions (task submission, management)
- `job_worker.proto` - Job Worker service definitions (task execution, status reporting)

## Compilation

### Quick Start

Simply run the build script:

```bash
./build.sh
```

### Manual Compilation

```bash
# Compile common messages
python3 -m grpc_tools.protoc -I./ --python_out=./ --pyi_out=./ common.proto

# Compile job manager (service + messages)
python3 -m grpc_tools.protoc -I./ --python_out=./ --pyi_out=./ --grpc_python_out=./ job_manager.proto

# Compile job worker (service + messages)
python3 -m grpc_tools.protoc -I./ --python_out=./ --pyi_out=./ --grpc_python_out=./ job_worker.proto
```

## Clean Generated Files

```bash
./clean.sh
```

## Generated Files

After compilation, the following Python files are generated:

```
common_pb2.py          - Common message classes
common_pb2.pyi         - Type stubs for common messages

job_manager_pb2.py          - Job Manager message classes
job_manager_pb2.pyi         - Type stubs for Job Manager messages
job_manager_pb2_grpc.py     - Job Manager gRPC service classes

job_worker_pb2.py          - Job Worker message classes
job_worker_pb2.pyi         - Type stubs for Job Worker messages
job_worker_pb2_grpc.py     - Job Worker gRPC service classes
```

## Dependencies

Install required packages:

```bash
pip install grpcio-tools
```

Or via uv:

```bash
uv add grpcio-tools
```

## Related

- **Media Service**: External Media service proto files are located at `../../infrastructure/external/media/`
