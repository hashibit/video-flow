import asyncio
import json
from workflow_worker.shared.logging._logging import get_logger
import uuid

import grpc

from workflow_worker.domain.entities.report import Report
from workflow_worker.shared.utils.common import snake_case_to_pascal_case
from workflow_worker.shared.utils.env import get_env

from workflow_worker.interfaces.api.workflow_common_pb2 import JobInfo, JobReport
from workflow_worker.interfaces.api.workflow_manager_pb2 import GetJobResponse, GetJobRequest, HeartbeatRequest, CreateReportResponse, \
    CreateReportRequest
from workflow_worker.interfaces.api.workflow_manager_pb2_grpc import JobManagerServiceStub
from workflow_worker.applications.workflows.job_runner import job_runner


MAX_RUNNING_JOBS = 4

env = get_env()


def _get_manager_stub(channel, logger) -> JobManagerServiceStub | None:
    endpoint = env.get_workflow_manager_host()
    fut = grpc.channel_ready_future(channel)
    try:
        # 10 seconds
        fut.result(timeout=10)
    except grpc.FutureTimeoutError:
        logger.error(f"timeout when make grpc channel to {endpoint}")
        return None
    except Exception:
        import traceback
        logger.error(f"exception when make grpc channel to {endpoint}, tb:")
        logger.error(traceback.format_exc())
        return None

    stub = JobManagerServiceStub(channel)
    return stub


class Worker:
    def __init__(self):
        self.worker_id = "worker-" + str(uuid.uuid4())[0:4]
        self.logger = get_logger(self.worker_id)

    async def send_heartbeat(self):
        while True:
            await asyncio.sleep(5)

            endpoint = env.get_workflow_manager_host()
            with grpc.insecure_channel(endpoint) as channel:
                stub = _get_manager_stub(channel, self.logger)
                if not stub:
                    self.logger.error(f"cannot get manager grpc stub for {endpoint}")
                    return

                try:
                    stub.Heartbeat(HeartbeatRequest(worker_id=self.worker_id))
                    self.logger.debug("send heartbeat ok.")
                except grpc.RpcError as rpc_error:
                    self.logger.error(f"Received gRPC error: {rpc_error}")
                except asyncio.TimeoutError:
                    import traceback
                    self.logger.error("grpc: send heartbeat exception.")
                    self.logger.error(traceback.format_exc())

    # async def fetch_one_job_mock(self) -> JobInfo | None:
    #     return JobInfo(id=1, task_id=123)

    # async def send_job_report_mock(self, job_id: int, task_id: int, report: JobReport) -> int:
    #     return -1

    async def fetch_one_job(self) -> JobInfo | None:
        endpoint = env.get_workflow_manager_host()
        with grpc.insecure_channel(endpoint) as channel:
            stub = _get_manager_stub(channel, self.logger)
            if stub is None:
                self.logger.error(f"cannot get manager grpc stub for {endpoint}")
                return None

            try:
                resp: GetJobResponse = stub.GetJob(GetJobRequest(worker_id=""))
            except grpc.RpcError as rpc_error:
                self.logger.error(f"Received gRPC error: {rpc_error}")
                return None

            if not resp.job_info or not resp.job_info.id:
                return None
            return resp.job_info

    async def send_job_report(self, job_info: JobInfo, report_json_str: str | None, run_msg: str) -> int:
        endpoint = env.get_workflow_manager_host()
        with grpc.insecure_channel(endpoint) as channel:
            stub = _get_manager_stub(channel, self.logger)
            if stub is None:
                self.logger.error(f"cannot get manager grpc stub for {endpoint}")
                return 0

            job_report = JobReport(valueJson=report_json_str, message=run_msg)

#           # Empty report_json_str indicates an execution error, but we still call
#           # stub.CreateReport to notify the manager. TODO: use a dedicated interface later.
            try:
                resp: CreateReportResponse = stub.CreateReport(
                    CreateReportRequest(job_id=job_info.id, task_id=job_info.task_id, job_report=job_report)
                )
            except grpc.RpcError as rpc_error:
                self.logger.error(f"Received gRPC error: {rpc_error}")
                return 0

            if report_json_str:
                return resp.job_report.id

            self.logger.error("report json str is None, so, report_id: 0")
            return 0

    async def schedule_jobs(self, thread_index: int):
        while True:
#           # wait 10s then fetch next job
            await asyncio.sleep(10)
            self.logger.info("")
            self.logger.info(f"{self.worker_id}-thread-{thread_index} schedule...")
            if len(job_runner.running_jobs) >= MAX_RUNNING_JOBS:
                self.logger.info("job_runner has running jobs, don't fetch new jobs")
                self.logger.info("")
                continue
            job_info = await self.fetch_one_job()
            if job_info is None:
                self.logger.info("No job from job_manager.")
                self.logger.info("")
                continue

            job_id = job_info.id
            task_id = job_info.task_id
            self.logger.info(f"fetched one job from job_manager, job_id: {job_id}, task_id: {task_id},"
                             f"give it to job_runner.")
            self.logger.info("")

            # report = mock_job_report()
            # report_id = await self.send_job_report(job_id, task_id, report)

            report = await job_runner.run_job(job_info)
            if type(report) is Report:
                report_json = json.loads(report.json())
                report_json = snake_case_to_pascal_case(report_json, only_key=True)
                report_json_str = json.dumps(report_json)
                report_msg = "job finished success"
                self.logger.info("send job report to job_manager.")
            else:
                report_json_str = None
                report_msg = str(report)
                self.logger.info("send nil job report to job_manager (to mark failed).")

            report_id = await self.send_job_report(job_info, report_json_str, report_msg)

            self.logger.info(f">>>>>>> Task-{task_id} run finished, "
                             f"job manager returned report_id: {report_id} <<<<<<<<<\n\n\n")

    def _schedule_job(self, job_info):
        pass
