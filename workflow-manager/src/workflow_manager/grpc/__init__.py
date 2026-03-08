"""gRPC services."""

import logging
from concurrent import futures

import grpc

from .job_manager_pb2_grpc import add_JobManagerServiceServicer_to_server
from .servicer import JobManagerServicer

logger = logging.getLogger(__name__)


def serve_grpc(address: str) -> grpc.Server:
    """Start gRPC server.

    Args:
        address: Server address (e.g., "0.0.0.0:50051")

    Returns:
        Running gRPC server instance
    """
    # Create server with thread pool
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add servicer
    add_JobManagerServiceServicer_to_server(JobManagerServicer(), server)

    # Bind to address
    server.add_insecure_port(address)

    # Start server
    server.start()
    logger.info(f"gRPC server started on {address}")

    return server


def stop_grpc_server(server: grpc.Server, grace_period: int = 5) -> None:
    """Stop gRPC server gracefully.

    Args:
        server: gRPC server instance
        grace_period: Grace period in seconds for ongoing requests
    """
    logger.info("Stopping gRPC server...")
    server.stop(grace_period)
    logger.info("gRPC server stopped")
