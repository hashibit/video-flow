from workflow_worker.domain.entities.tasks.speech_recognition.result import (
    SpeechRecognitionResult,
)
from workflow_worker.domain.entities.service.auc import AUCServiceResult
from workflow_worker.services.ai.auc.service import AUCService
from workflow_worker.applications.jobs.module import ModuleBase
from workflow_worker.applications.jobs.model import JobName
from workflow_worker.infrastructure.media_stream.frame_channel import FrameChannel
from workflow_worker.infrastructure.media_stream.s3_hook import S3Hook
from workflow_worker.applications.workflows.task_context import TaskContext


class SpeechRecognitionJob(ModuleBase):
    def __init__(self, task) -> None:
        super().__init__(task)
        self.required_jobs = ["script_matching"]

    def run(self, task_context: TaskContext) -> SpeechRecognitionResult | None:
        frame_ch = task_context.frame_channels[JobName.SpeechRecognition]
        assert isinstance(frame_ch, FrameChannel)
        _event_ch = task_context.event_channels[JobName.SpeechRecognition]

        audio = None
        frame_gen = frame_ch.output()
        for frame in frame_gen:
            if not frame.audio:
                continue
            audio = frame.audio
            break

        logger = task_context.get_task_logger().getChild("Module.SpeechRecognitionJob")
        logger.info(f"SpeechRecognitionJob.run close frame_gen, audio is none ? {audio is None}")
        frame_gen.close()
        if audio is None:
            return None

        if audio.url and audio.url.startswith("minio://"):
            s3 = S3Hook()
            path = audio.url.split("minio://")[1]
            bucket = path.split("/")[0]
            file_path = "/".join(path.split("/")[1:])
            audio.url = s3.generate_presigned_url(
                client_method="get_object",
                params={"Bucket": bucket, "Key": file_path},
                expires_in=3600,
            )
            logger.info(f"presigned audio url: {audio.url}")

        task_context.set_audio_object(audio)

        service = AUCService(logger=logger)
        # Get audio recognition result
        logger.info("AUCService.run with audio.")
        auc_service_result: AUCServiceResult = service.run(audio)
        logger.info(f"AUCService.run get result, dialog: {auc_service_result.dialogue.text}.")

        if task_context.task.ignore_invalid_time_range == 1:
            offset = task_context.task.media.video_valid_start_time
            logger.info(f'before auc result offset= {offset}')
            if offset is not None and offset > 0:
                for ut in auc_service_result.dialogue.utterances:
                    ut.start_time += offset
                    ut.end_time += offset
                    for w in ut.words:
                        w.start_time += offset
                        w.end_time += offset
            logger.info(f'auc result to= {auc_service_result}')
        task_context.set_auc_service_result(auc_service_result)

        # no need for saving word-level info
        # for i in range(len(auc_service_result.dialogue.utterances)):
        #     auc_service_result.dialogue.utterances[i].words = []
        return SpeechRecognitionResult(ai_result={"auc": auc_service_result, })
