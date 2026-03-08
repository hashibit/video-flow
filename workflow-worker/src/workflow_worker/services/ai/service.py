"""Base service classes for AI services."""
import time
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable

import grpc

from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.shared.utils.env import resolve_service_target

_module_logger = get_logger(__name__)


def require_cache(func):
    """Decorator to require caching for service results."""
    return func


def timed(label: str = ""):
    """Decorator that logs the wall-clock duration of a service method call.

    Usage:
        @timed("grpc_call")
        def predict(self, frame): ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            op = label or func.__name__
            t0 = time.monotonic()
            try:
                return func(self, *args, **kwargs)
            finally:
                ms = (time.monotonic() - t0) * 1000
                svc_logger = getattr(self, "logger", _module_logger)
                svc_logger.info("[%s] %s: %.1fms", getattr(self, "name", type(self).__name__), op, ms)
        return wrapper
    return decorator


class Service(ABC):
    """Base class for all AI services."""

    def __init__(self, name: str, version: str = "v1", description: str = ""):
        self.name = name
        self.version = version
        self.description = description

    @abstractmethod
    def run(self, *args, **kwargs):
        pass


class GRPCService(Service, ABC):
    """Base class for AI services that communicate via gRPC.

    Handles channel creation, stub initialization, and error response logging
    so subclasses only need to implement their business logic.
    """

    def __init__(self, target: str, stub_class, name: str, version: str = "v1", description: str = ""):
        super().__init__(name, version, description)
        self.channel = grpc.insecure_channel(resolve_service_target(target))
        self.stub = stub_class(self.channel)

    @staticmethod
    def _log_grpc_error(base_resp, message: str, logger=None) -> None:
        (_module_logger if logger is None else logger).error({
            "status_code": base_resp.status_code,
            "status_message": base_resp.status_message,
            "extra": base_resp.extra,
            "message": message,
        })
