import asyncio
import os

from workflow_worker.domain.entities.audio import Audio, AudioMeta
from workflow_worker.domain.entities.task import Task, MediaMeta
from workflow_worker.shared.utils.env import get_env
from workflow_worker.shared.utils.media import gather_batch_frames, extract_video_metadata, extract_audio
from workflow_worker.infrastructure.media_stream.base import AbstractDataSource
from workflow_worker.infrastructure.media_stream.model import StreamMessage
from workflow_worker.infrastructure.media_stream.s3_hook import S3Hook

_env = get_env()


class DataSourceFFmpeg(AbstractDataSource):
    """Reads media from a local file, decoding video with FFmpeg and uploading audio to S3."""

    def __init__(
        self,
        task: Task,
        media_url: str = "",
        decode_fps: int = 60,
        decode_batch_size: int = 1,
    ):
        super().__init__(task)
        self.media_url = media_url
        self.decode_fps = decode_fps
        self.decode_batch_size = decode_batch_size
        self.audio: Audio | None = None

    def extract_metadata(self) -> MediaMeta:
        meta = extract_video_metadata(self.media_url)
        self.logger.info(f"video metadata: {meta}")
        _resolution = meta.get("resolution")
        _size = meta.get("size")
        _duration = meta.get("duration")
        _bitrate = meta.get("bitrate")
        _fps = meta.get("fps")
        _width = meta.get("width")
        _height = meta.get("height")
        _format_name = meta.get("format_name")
        self.task.media.meta = MediaMeta(
            resolution=str(_resolution) if _resolution is not None else None,
            size=str(_size) if _size is not None else None,
            duration=float(_duration) if _duration is not None else None,
            bitrate=str(_bitrate) if _bitrate is not None else None,
            fps=str(_fps) if _fps is not None else None,
            width=int(_width) if _width is not None else None,
            height=int(_height) if _height is not None else None,
            format_name=str(_format_name) if _format_name is not None else None,
        )
        return self.task.media.meta

    async def setup(self, decode_fps: int = 0) -> None:
        if decode_fps:
            self.logger.info(f"overriding decode_fps {self.decode_fps} → {decode_fps}")
            self.decode_fps = decode_fps
        self.logger.info(f"setup with decode_fps={self.decode_fps}")

        local_dir = f"/tmp/{self.task.id}"
        os.makedirs(local_dir, exist_ok=True)
        local_audio = f"{local_dir}/audio.pcm"
        extract_audio(self.media_url, local_audio, "pcm")

        s3_key = f"task_{self.task.id}/audio.pcm"
        with open(local_audio, "rb") as f:
            S3Hook().load_file_obj(f, s3_key, _env.s3_bucket, replace=True)

        audio_url = f"minio://{_env.s3_bucket}/{s3_key}"
        self.logger.info(f"audio uploaded to: {audio_url}")
        self.audio = Audio(
            url=audio_url,
            meta=AudioMeta(codec="pcm", sample_rate=16000, channels=2, bits=16),
        )

    async def stream(self, callback) -> None:
        self.logger.info(f"streaming audio: {self.audio}")
        await callback(StreamMessage(id=-100, audio=self.audio))

        meta = self.task.media.meta
        assert meta is not None, "media metadata must be set before streaming"
        self.logger.info(
            f"streaming video: {meta.width}x{meta.height}, "
            f"fps={self.decode_fps}, batch_size={self.decode_batch_size}"
        )
        frame_id = 0
        for batch in gather_batch_frames(
            self.media_url, meta.width, meta.height,
            fps=self.decode_fps, batch_size=self.decode_batch_size,
        ):
            for frame in batch.frames:
                frame_id = frame.frame_number
                if await callback(StreamMessage(id=frame_id, image=frame)):
                    self.logger.info("streaming stopped by callback")
                    return
                await asyncio.sleep(0)

        await callback(StreamMessage(id=frame_id + 1, is_last=True))
