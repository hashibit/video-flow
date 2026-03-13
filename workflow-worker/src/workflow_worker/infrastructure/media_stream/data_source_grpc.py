import asyncio

import grpc

from workflow_worker.shared.utils.env import get_env
from workflow_worker.infrastructure.external import media_api
from workflow_proto.media_service_pb2 import NotifyStatus, Code
from workflow_proto.media_service_pb2 import FetchMediaDataRequest, FetchMediaDataResponse
from workflow_proto.media_service_pb2_grpc import MediaServiceStub
from workflow_worker.domain.entities.audio import Audio, Word, Utterance, AudioMeta
from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.task import Task, MediaMeta
from workflow_worker.infrastructure.media_stream.base import AbstractDataSource
from workflow_worker.infrastructure.media_stream.model import StreamMessage

_env = get_env()


class DataSourceGRPC(AbstractDataSource):
    """Reads media from a remote media manager service via gRPC."""

    def __init__(
        self,
        task: Task,
        media_manager_host: str = "",
        decode_fps: int = 120,
        decode_batch_size: int = 1,
        total_timeout: int = 24 * 3600,
    ):
        super().__init__(task)
        self.media_manager_host = media_manager_host
        self.media_worker_endpoint = ""
        self.decode_fps = decode_fps
        self.decode_batch_size = decode_batch_size
        self.media_job_id = 0
        self.total_timeout = total_timeout

    def extract_metadata(self) -> MediaMeta:
        self.logger.info("Extracting media metadata...")
        self.task.media.meta = media_api.get_media_metadata(self.media_manager_host, self.task.id)
        self.logger.info(f"Metadata: {self.task.media.meta}")
        return self.task.media.meta

    async def setup(self, decode_fps: int = 0) -> None:
        if decode_fps:
            self.logger.info(f"overriding decode_fps {self.decode_fps} → {decode_fps}")
            self.decode_fps = decode_fps
        self.logger.info(f"setup with decode_fps={self.decode_fps}")

        self.media_job_id, self.media_worker_endpoint = media_api.create_media(
            self.media_manager_host, self.task.id, self.decode_fps
        )
        env_override = _env.get_media_worker_host()
        if env_override:
            self.logger.warning(
                f"Overriding media worker endpoint ({self.media_worker_endpoint}) "
                f"→ ({env_override}) via env var"
            )
            self.media_worker_endpoint = env_override

        await self._wait_until_ready()

    async def stream(self, callback) -> None:
        limit = 3
        for attempt in range(1, limit + 1):
            if await self._stream(callback):
                self.logger.info("Media stream completed.")
                return
            self.logger.warning(f"Stream attempt {attempt}/{limit} failed, retrying...")
            await asyncio.sleep(1)
        raise RuntimeError(f"Media stream failed after {limit} attempts.")

    async def _wait_until_ready(self, limit: int = 30) -> None:
        for attempt in range(limit):
            if media_api.is_data_ready(self.media_manager_host, self.media_job_id):
                self.logger.info("Media server ready.")
                return
            self.logger.info(f"Media server not ready, attempt {attempt + 1}/{limit}...")
            await asyncio.sleep(1)
        raise RuntimeError(f"Media server not ready after {limit} checks.")

    def _connect(self, channel) -> MediaServiceStub | None:
        try:
            grpc.channel_ready_future(channel).result(timeout=10)
            self.logger.info(f"Connected to media worker: {self.media_worker_endpoint}")
            return MediaServiceStub(channel)
        except grpc.FutureTimeoutError:
            self.logger.error(f"Connection timeout: {self.media_worker_endpoint}")
            return None
        except Exception:
            import traceback
            self.logger.error(f"Connection error:\n{traceback.format_exc()}")
            return None

    async def _stream(self, callback) -> bool:
        with grpc.insecure_channel(self.media_worker_endpoint) as channel:
            stub = self._connect(channel)
            if not stub:
                return False
            responses = None
            try:
                timeout = self._calc_timeout()
                self.logger.info(f"Fetching media, timeout={timeout}s")
                responses = stub.FetchMediaData(
                    FetchMediaDataRequest(media_id=self.media_job_id, timeout=timeout)
                )
                for rsp in responses:
                    await asyncio.sleep(0)
                    if rsp.code != Code.success:
                        raise RuntimeError(f"gRPC error code={rsp.code}: {rsp.message}")
                    stopped = await callback(self._parse_response(rsp))
                    if stopped:
                        self.logger.info("Streaming stopped by callback.")
                        return True
            except grpc.RpcError:
                import traceback
                self.logger.error(f"gRPC stream error:\n{traceback.format_exc()}")
                if responses is not None:
                    responses.cancel()
                return False
        return True

    def _calc_timeout(self) -> int:
        if self.task.media.meta and self.task.media.meta.duration:
            return min(self.total_timeout, int(self.task.media.meta.duration / 1000 * 10))
        return self.total_timeout

    @staticmethod
    def _parse_response(rsp: FetchMediaDataResponse) -> StreamMessage:
        msg = StreamMessage(id=0, is_last=(rsp.status == NotifyStatus.finish))
        which = rsp.WhichOneof("data")
        if which == "audio":
            utterances = [
                Utterance(
                    text=ut.text,
                    start_ts=ut.start_ts,
                    end_ts=ut.end_ts,
                    words=[Word(text=w.text, start_ts=w.start_ts, end_ts=w.end_ts) for w in ut.words],
                )
                for ut in rsp.audio.utterances
            ]
            msg.audio = Audio(
                url=rsp.audio.url,
                text=rsp.audio.text,
                utterance=utterances,
                meta=AudioMeta(codec="mp3", sample_rate=16000, channels=2, bits=16),
            )
        elif which == "image":
            msg.image = Frame(
                frame_number=rsp.image.frame_number,
                url=rsp.image.url,
                data=rsp.image.data,
                timestamp=rsp.image.ts,
            )
            msg.id = rsp.image.frame_number
        return msg
