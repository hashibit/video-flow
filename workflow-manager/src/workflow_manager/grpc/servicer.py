"""gRPC service implementation."""

import json
import logging
from typing import Any

import grpc

from ..client.external_api import TaskStatus, get_external_api_client
from ..core.models import JobStatus
from ..core.services import JobService
from . import job_manager_pb2, job_manager_pb2_grpc  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

# Maximum retry times for a job
MAX_RETRY_TIMES = 10


class JobManagerServicer(job_manager_pb2_grpc.JobManagerServiceServicer):
    """Implementation of JobManagerService gRPC service."""

    def __init__(self) -> None:
        """Initialize servicer."""
        self.job_service = JobService()
        self.external_api = get_external_api_client()

    def GetJob(self, request: Any, context: Any) -> Any:
        """Get next available job for worker execution.

        This method:
        1. Gets one pending/retry job from database
        2. Transitions job to RUNNING state atomically
        3. Fetches task details from External API
        4. Updates task status to RUNNING in External API
        5. Returns job info to worker

        On error, rolls back job to RETRY state.

        Args:
            request: GetJobRequest with worker_id
            context: gRPC context

        Returns:
            GetJobResponse with JobInfo
        """
        worker_id = request.worker_id
        logger.info(f"GetJob request from worker: {worker_id}")

        try:
            # Get one runnable job and atomically mark it as RUNNING
            job = self.job_service.get_runnable_job()

            if job is None:
                logger.info("No pending jobs available")
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("No jobs available")
                return job_manager_pb2.GetJobResponse()

            logger.info(f"Allocated job {job.id} (task_id={job.task_id}) to worker {worker_id}")

            # Fetch task details from External API
            try:
                task_json = self.external_api.get_task(job.task_id)
            except Exception as e:
                logger.error(f"Failed to get task {job.task_id} from External API: {e}")
                # Rollback job to RETRY
                self._rollback_to_retry(job.id)
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Failed to fetch task details: {str(e)}")
                return job_manager_pb2.GetJobResponse()

            # Update task status to RUNNING in External API
            try:
                self.external_api.update_task_status(job.task_id, TaskStatus.RUNNING)
            except Exception as e:
                logger.error(f"Failed to update task {job.task_id} status to RUNNING: {e}")
                # Rollback job to RETRY
                self._rollback_to_retry(job.id)
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Failed to update task status: {str(e)}")
                return job_manager_pb2.GetJobResponse()

            # Create JobInfo response
            job_info = job_manager_pb2.JobInfo(
                id=job.id, task_id=job.task_id, task_json=task_json
            )

            response = job_manager_pb2.GetJobResponse(job_info=job_info)
            logger.info(f"Successfully allocated job {job.id} to worker {worker_id}")

            return response

        except Exception as e:
            logger.error(f"GetJob error: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return job_manager_pb2.GetJobResponse()

    def CreateReport(self, request: Any, context: Any) -> Any:
        """Submit job execution results.

        This method:
        1. Validates report is not empty
        2. Updates job status based on report validity
        3. Submits report to External API
        4. Updates task status in External API
        5. Handles retry logic if job failed

        Args:
            request: CreateReportRequest with job_id, task_id, and report
            context: gRPC context

        Returns:
            CreateReportResponse echoing the request
        """
        job_id = request.job_id
        task_id = request.task_id
        job_report = request.job_report

        logger.info(f"CreateReport request for job {job_id}, task {task_id}")

        try:
            # Get job from database
            job = self.job_service.get_job(job_id)
            if job is None:
                logger.error(f"Job {job_id} not found")
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Job {job_id} not found")
                return job_manager_pb2.CreateReportResponse()

            # Validate report is not empty
            report_value_json = job_report.value_json.strip()
            is_empty = not report_value_json or report_value_json == "{}"

            if is_empty:
                logger.warning(f"Empty report for job {job_id}, marking for retry")
                # Empty report means failure, increment retry counter
                new_retry_times = job.retry_times + 1

                if new_retry_times >= MAX_RETRY_TIMES:
                    # Max retries exceeded, mark as FAILED
                    logger.error(
                        f"Job {job_id} reached max retries ({MAX_RETRY_TIMES}), marking as FAILED"
                    )
                    self.job_service.update_job_status(job_id, JobStatus.FAILED)

                    # Update task status to FAILED in External API
                    try:
                        self.external_api.update_task_status(task_id, TaskStatus.FAILED)
                    except Exception as e:
                        logger.error(f"Failed to update task {task_id} status to FAILED: {e}")
                else:
                    # Still have retries left, mark as RETRY
                    from ..core.models import JobUpdate

                    self.job_service.update_job(
                        job_id, JobUpdate(status=JobStatus.RETRY, retry_times=new_retry_times)
                    )
                    logger.info(
                        f"Job {job_id} marked for retry "
                        f"(attempt {new_retry_times}/{MAX_RETRY_TIMES})"
                    )

                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Empty report received")
                return job_manager_pb2.CreateReportResponse(
                    job_id=job_id, task_id=task_id, job_report=job_report
                )

            # Valid report, mark job as SUCCESS
            logger.info(f"Job {job_id} completed successfully")
            self.job_service.update_job_status(job_id, JobStatus.SUCCESS)

            # Submit report to External API
            try:
                # Construct report JSON matching External API format
                report_data = {
                    "Id": task_id,
                    "Name": job_report.name,
                    "ValueJson": job_report.value_json,
                    "Message": job_report.message,
                }
                report_json = json.dumps(report_data)

                report_id = self.external_api.create_report(report_json)
                logger.info(f"Report {report_id} created for task {task_id}")
            except Exception as e:
                logger.error(f"Failed to submit report to External API: {e}")
                # Rollback to RETRY
                self._rollback_to_retry(job_id)
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Failed to submit report: {str(e)}")
                return job_manager_pb2.CreateReportResponse()

            # Update task status to SUCCESS in External API
            try:
                self.external_api.update_task_status(task_id, TaskStatus.SUCCESS)
            except Exception as e:
                logger.error(f"Failed to update task {task_id} status to SUCCESS: {e}")
                # Report already submitted, but status update failed
                # We still mark job as SUCCESS to avoid reprocessing
                logger.warning(
                    f"Job {job_id} marked as SUCCESS but task status update failed"
                )

            # Return response
            response = job_manager_pb2.CreateReportResponse(
                job_id=job_id, task_id=task_id, job_report=job_report
            )
            logger.info(f"Successfully processed report for job {job_id}")

            return response

        except Exception as e:
            logger.error(f"CreateReport error: {e}", exc_info=True)
            # On unexpected error, try to rollback to RETRY
            try:
                self._rollback_to_retry(job_id)
            except Exception as rollback_err:
                logger.error(f"Failed to rollback job {job_id}: {rollback_err}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return job_manager_pb2.CreateReportResponse()

    def Heartbeat(self, request: Any, context: Any) -> Any:
        """Handle worker heartbeat.

        Currently a simple acknowledgment. Can be extended to:
        - Track worker health
        - Detect stale jobs
        - Monitor worker load

        Args:
            request: HeartbeatRequest with worker_id and running job IDs
            context: gRPC context

        Returns:
            HeartbeatResponse acknowledging the heartbeat
        """
        worker_id = request.worker_id
        running_job_ids = list(request.running_job_ids)

        logger.debug(f"Heartbeat from worker {worker_id}, running jobs: {running_job_ids}")

        # Simple acknowledgment
        response = job_manager_pb2.HeartbeatResponse(worker_id=worker_id)

        return response

    def _rollback_to_retry(self, job_id: int) -> None:
        """Rollback job to RETRY state on error.

        Args:
            job_id: Job ID to rollback
        """
        try:
            job = self.job_service.get_job(job_id)
            if job is None:
                logger.error(f"Cannot rollback job {job_id}: not found")
                return

            new_retry_times = job.retry_times + 1

            if new_retry_times >= MAX_RETRY_TIMES:
                logger.error(
                    f"Job {job_id} reached max retries during rollback, marking as FAILED"
                )
                self.job_service.update_job_status(job_id, JobStatus.FAILED)
            else:
                from ..core.models import JobUpdate

                self.job_service.update_job(
                    job_id, JobUpdate(status=JobStatus.RETRY, retry_times=new_retry_times)
                )
                logger.info(
                    f"Job {job_id} rolled back to RETRY "
                    f"(attempt {new_retry_times}/{MAX_RETRY_TIMES})"
                )
        except Exception as e:
            logger.error(f"Failed to rollback job {job_id}: {e}", exc_info=True)
