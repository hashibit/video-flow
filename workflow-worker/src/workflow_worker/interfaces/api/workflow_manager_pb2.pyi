import workflow_common_pb2 as _workflow_common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetJobRequest(_message.Message):
    __slots__ = ("worker_id",)
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    def __init__(self, worker_id: _Optional[str] = ...) -> None: ...

class GetJobResponse(_message.Message):
    __slots__ = ("job_info",)
    JOB_INFO_FIELD_NUMBER: _ClassVar[int]
    job_info: _workflow_common_pb2.JobInfo
    def __init__(self, job_info: _Optional[_Union[_workflow_common_pb2.JobInfo, _Mapping]] = ...) -> None: ...

class CreateReportRequest(_message.Message):
    __slots__ = ("job_id", "task_id", "job_report")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    JOB_REPORT_FIELD_NUMBER: _ClassVar[int]
    job_id: int
    task_id: int
    job_report: _workflow_common_pb2.JobReport
    def __init__(self, job_id: _Optional[int] = ..., task_id: _Optional[int] = ..., job_report: _Optional[_Union[_workflow_common_pb2.JobReport, _Mapping]] = ...) -> None: ...

class CreateReportResponse(_message.Message):
    __slots__ = ("job_id", "task_id", "job_report")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    JOB_REPORT_FIELD_NUMBER: _ClassVar[int]
    job_id: int
    task_id: int
    job_report: _workflow_common_pb2.JobReport
    def __init__(self, job_id: _Optional[int] = ..., task_id: _Optional[int] = ..., job_report: _Optional[_Union[_workflow_common_pb2.JobReport, _Mapping]] = ...) -> None: ...

class HeartbeatRequest(_message.Message):
    __slots__ = ("worker_id", "running_job_ids")
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    RUNNING_JOB_IDS_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    running_job_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, worker_id: _Optional[str] = ..., running_job_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class HeartbeatResponse(_message.Message):
    __slots__ = ("worker_id",)
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    def __init__(self, worker_id: _Optional[str] = ...) -> None: ...
