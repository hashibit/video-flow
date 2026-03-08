import workflow_common_pb2 as _workflow_common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PollEventsRequest(_message.Message):
    __slots__ = ("job_info", "last_event_id")
    JOB_INFO_FIELD_NUMBER: _ClassVar[int]
    LAST_EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    job_info: _workflow_common_pb2.JobInfo
    last_event_id: int
    def __init__(self, job_info: _Optional[_Union[_workflow_common_pb2.JobInfo, _Mapping]] = ..., last_event_id: _Optional[int] = ...) -> None: ...

class PollEventsResponse(_message.Message):
    __slots__ = ("events",)
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[_workflow_common_pb2.JobEvent]
    def __init__(self, events: _Optional[_Iterable[_Union[_workflow_common_pb2.JobEvent, _Mapping]]] = ...) -> None: ...

class StopRunningJobResponse(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: int
    def __init__(self, job_id: _Optional[int] = ...) -> None: ...
