"""External API client for task management."""

import logging
import threading
from enum import IntEnum

import httpx
from pydantic import BaseModel

from ..config import get_settings

logger = logging.getLogger(__name__)


class TaskStatus(IntEnum):
    """Task status enumeration matching external API."""

    UNKNOWN = 0
    READY = 1  # Ready for automated processing
    RUNNING = 2  # Automated processing in progress
    READY_FOR_HUMAN = 3  # Ready for human review
    SUCCESS = 4  # Completed successfully
    FAILED = 5  # Task execution failed


class GetTaskRequest(BaseModel):
    """Request to get task details."""

    Id: int


class UpdateStatusRequest(BaseModel):
    """Request to update task status."""

    Id: int
    Status: int


class ExternalAPIClient:
    """Client for communicating with external API service."""

    def __init__(self, base_url: str | None = None, timeout: int = 30):
        """Initialize External API client.

        Args:
            base_url: Base URL for the external API. If None, uses config.
            timeout: Request timeout in seconds
        """
        self.settings = get_settings()
        self.base_url = base_url or self.settings.external_api_url
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def __del__(self) -> None:
        """Cleanup HTTP client."""
        try:
            self.client.close()
        except Exception:
            pass

    def get_task(self, task_id: int) -> str:
        """Get task details by ID.

        Args:
            task_id: Task ID

        Returns:
            Task details as JSON string

        Raises:
            httpx.HTTPError: If request fails
            ValueError: If response format is invalid
        """
        if not self.base_url:
            raise ValueError("External API URL not configured")

        url = f"{self.base_url}/api/v1/task/get"
        payload = GetTaskRequest(Id=task_id).model_dump()

        logger.info(f"GetTask request: {url}, payload: {payload}")

        try:
            response = self.client.post(
                url, json=payload, headers={"Content-Type": "application/json", "Action": "GetTask"}
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"GetTask response: {data}")

            # Extract Result field which contains the task JSON
            if "Result" not in data:
                raise ValueError("Response missing 'Result' field")

            task_json = data["Result"]
            # If Result is a dict/object, convert to JSON string
            if isinstance(task_json, dict):
                import json

                return json.dumps(task_json)
            elif isinstance(task_json, str):
                return task_json
            else:
                raise ValueError(f"Unexpected Result type: {type(task_json)}")

        except httpx.HTTPError as e:
            logger.error(f"GetTask failed: {e}")
            raise
        except Exception as e:
            logger.error(f"GetTask error: {e}")
            raise

    def update_task_status(self, task_id: int, status: TaskStatus) -> int:
        """Update task status.

        Args:
            task_id: Task ID
            status: New task status

        Returns:
            Task ID if successful

        Raises:
            httpx.HTTPError: If request fails
        """
        if not self.base_url:
            raise ValueError("External API URL not configured")

        url = f"{self.base_url}/api/v1/task/update"
        payload = UpdateStatusRequest(Id=task_id, Status=int(status)).model_dump()

        logger.info(f"UpdateTaskStatus request: {url}, payload: {payload}")

        try:
            response = self.client.post(
                url, json=payload, headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"UpdateTaskStatus response: {data}")

            return task_id

        except httpx.HTTPError as e:
            logger.error(f"UpdateTaskStatus failed: {e}")
            raise
        except Exception as e:
            logger.error(f"UpdateTaskStatus error: {e}")
            raise

    def create_report(self, report_json: str) -> int:
        """Submit job report.

        Args:
            report_json: Report data as JSON string (must contain task ID)

        Returns:
            Report ID if successful

        Raises:
            httpx.HTTPError: If request fails
            ValueError: If response format is invalid
        """
        if not self.base_url:
            raise ValueError("External API URL not configured")

        url = f"{self.base_url}/api/v1/report/create"

        logger.info(f"CreateReport request: {url}, payload: {report_json}")

        try:
            response = self.client.post(
                url, content=report_json, headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"CreateReport response: {data}")

            # Extract Result field which contains the report ID
            if "Result" not in data:
                raise ValueError("Response missing 'Result' field")

            report_id = data["Result"]
            if isinstance(report_id, int):
                return report_id
            elif isinstance(report_id, str):
                return int(report_id)
            else:
                raise ValueError(f"Unexpected Result type: {type(report_id)}")

        except httpx.HTTPError as e:
            logger.error(f"CreateReport failed: {e}")
            raise
        except Exception as e:
            logger.error(f"CreateReport error: {e}")
            raise


# Singleton instance
_client: ExternalAPIClient | None = None
_client_lock = threading.Lock()


def get_external_api_client() -> ExternalAPIClient:
    """Get global External API client instance.

    Returns:
        ExternalAPIClient instance
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = ExternalAPIClient()
    return _client


def reset_external_api_client() -> None:
    """Reset client instance (useful for testing)."""
    global _client
    _client = None
