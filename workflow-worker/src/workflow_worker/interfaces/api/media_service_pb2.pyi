from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class NotifyStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    normal: _ClassVar[NotifyStatus]
    failed: _ClassVar[NotifyStatus]
    finish: _ClassVar[NotifyStatus]
    start: _ClassVar[NotifyStatus]

class Code(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    unknown: _ClassVar[Code]
    success: _ClassVar[Code]
    error: _ClassVar[Code]
normal: NotifyStatus
failed: NotifyStatus
finish: NotifyStatus
start: NotifyStatus
unknown: Code
success: Code
error: Code

class Word(_message.Message):
    __slots__ = ("text", "start_ts", "end_ts")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    START_TS_FIELD_NUMBER: _ClassVar[int]
    END_TS_FIELD_NUMBER: _ClassVar[int]
    text: str
    start_ts: int
    end_ts: int
    def __init__(self, text: _Optional[str] = ..., start_ts: _Optional[int] = ..., end_ts: _Optional[int] = ...) -> None: ...

class Utterance(_message.Message):
    __slots__ = ("text", "words", "start_ts", "end_ts")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    WORDS_FIELD_NUMBER: _ClassVar[int]
    START_TS_FIELD_NUMBER: _ClassVar[int]
    END_TS_FIELD_NUMBER: _ClassVar[int]
    text: str
    words: _containers.RepeatedCompositeFieldContainer[Word]
    start_ts: int
    end_ts: int
    def __init__(self, text: _Optional[str] = ..., words: _Optional[_Iterable[_Union[Word, _Mapping]]] = ..., start_ts: _Optional[int] = ..., end_ts: _Optional[int] = ...) -> None: ...

class Audio(_message.Message):
    __slots__ = ("url", "text", "utterances", "start_ts", "end_ts")
    URL_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    UTTERANCES_FIELD_NUMBER: _ClassVar[int]
    START_TS_FIELD_NUMBER: _ClassVar[int]
    END_TS_FIELD_NUMBER: _ClassVar[int]
    url: str
    text: str
    utterances: _containers.RepeatedCompositeFieldContainer[Utterance]
    start_ts: int
    end_ts: int
    def __init__(self, url: _Optional[str] = ..., text: _Optional[str] = ..., utterances: _Optional[_Iterable[_Union[Utterance, _Mapping]]] = ..., start_ts: _Optional[int] = ..., end_ts: _Optional[int] = ...) -> None: ...

class Image(_message.Message):
    __slots__ = ("data", "url", "ts", "frame_number")
    DATA_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    FRAME_NUMBER_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    url: str
    ts: int
    frame_number: int
    def __init__(self, data: _Optional[bytes] = ..., url: _Optional[str] = ..., ts: _Optional[int] = ..., frame_number: _Optional[int] = ...) -> None: ...

class FetchMediaDataRequest(_message.Message):
    __slots__ = ("media_id", "timeout")
    MEDIA_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    media_id: int
    timeout: int
    def __init__(self, media_id: _Optional[int] = ..., timeout: _Optional[int] = ...) -> None: ...

class FetchMediaDataResponse(_message.Message):
    __slots__ = ("code", "message", "task_id", "status", "audio", "image")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    AUDIO_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    code: Code
    message: str
    task_id: int
    status: NotifyStatus
    audio: Audio
    image: Image
    def __init__(self, code: _Optional[_Union[Code, str]] = ..., message: _Optional[str] = ..., task_id: _Optional[int] = ..., status: _Optional[_Union[NotifyStatus, str]] = ..., audio: _Optional[_Union[Audio, _Mapping]] = ..., image: _Optional[_Union[Image, _Mapping]] = ...) -> None: ...
