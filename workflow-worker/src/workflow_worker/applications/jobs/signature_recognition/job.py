
from typing import Any

from workflow_worker.domain.entities.tasks.common.ocr.result import OCRTrackingResult
from workflow_worker.domain.entities.tasks.signature_recognition.config import (
    SignatureRecognitionJobCfg,
    SingleSignatureRecognitionJobCfg,
)
from workflow_worker.domain.entities.tasks.signature_recognition.result import (
    SignOCRRecogResult,
    SignatureRecognitionJobResult,
)
from workflow_worker.domain.entities.rule import RulePoint, SignatureInfo
from workflow_worker.domain.entities.service.ocr import OCRInfoType
from workflow_worker.domain.entities.task import Participant, Task
from workflow_worker.applications.jobs.common.ocr.ocr_id_generator import OCRIDGenerator
from workflow_worker.applications.jobs.common.ocr.ocr_info_manager import OCRInfoManager
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.ocr import HandwritingOCRService
from workflow_worker.shared.utils.frame import (
    decode_image,
    encode_image,
    get_image_bytes,
    get_storage_url,
)
from workflow_worker.shared.utils.visualization import draw_box, draw_polygon
from workflow_worker.applications.jobs.module import ModuleBase
from workflow_worker.applications.jobs.model import JobName
from workflow_worker.infrastructure.media_stream.utils import gather_batch_frames_from_generator
from workflow_worker.infrastructure.media_stream.frame_channel import FrameChannel
from workflow_worker.applications.workflows.task_context import TaskContext

logger = get_logger(__name__)


class SignatureRecognitionJob(ModuleBase):
    def __init__(self, task) -> None:
        super().__init__(task)
        self.required_jobs: list[Any] = []
        self.id_generator = OCRIDGenerator()
        self.sign_tracker: OCRInfoManager | None = None
        self.id_mapper: dict[str, Any] = {}

    def parse_task(self, task: Task) -> SignatureRecognitionJobCfg:
        fps = task.rule.fps if task.rule else 2.0
        self.sign_tracker = OCRInfoManager(
            ocr_type=OCRInfoType.HANDWRITING_OCR_TYPE, fps=fps
        )
        configs = []
        if task.rule:
            for rule_section in task.rule.rule_sections:
                for rule_point in rule_section.rule_points:
                    if rule_point:
                        configs.extend(self._get_sign_recog_cfg(rule_point, task.participants))  # pyright: ignore[reportArgumentType]
        return SignatureRecognitionJobCfg(
            fps=fps, batch_size=10, media=task.media, configs=configs
        )

    def _get_sign_recog_cfg(
        self, rule_point: RulePoint, participants: list[Participant]
    ) -> list[SingleSignatureRecognitionJobCfg]:
        """Parse sign recog config from rule_point.

        Args:
            rule_point (RulePoint): The rule point needs to check.
            participants (list[Participant]): The all participants in the task.
        """
        sign_cfgs: list[Any] = []
        if not rule_point.document_cfgs:
            return sign_cfgs
        # Parse sign cfgs from document_cfgs
        for cfg in rule_point.document_cfgs:
            if not cfg:
                continue
            for signature_info in cfg.signature_infos:
                if not signature_info:
                    continue
# If handwriting detection is not needed, skip the subsequent info extraction
                detection_flag = signature_info.signature_detection_flag
                if not detection_flag:
                    return sign_cfgs
                # Parse detection & recog threshold
                recog_threshold = signature_info.signer_threshold
                recog_threshold = 0.4 if recog_threshold < 0 else recog_threshold
                detect_threshold = signature_info.signature_threshold
                detect_threshold = 0.7 if detect_threshold < 0 else detect_threshold

                signer_role = signature_info.signer_role
                signature_flag = signature_info.signature_flag
                for participant in participants:
                    role = participant.role
                    name = participant.name
                    if signer_role in [role, "*"]:
                        if not signature_flag:
                            continue
                        sign_id, flag = self.id_generator.get_ocr_id(
                            "sign",
                            {"name": {"text": name}},
                        )
                        # Skip if the content has been registed
                        if flag:
                            continue
                        # Build the matching relation between rule_point uuid & sign_id
                        self.id_mapper[sign_id] = rule_point.id
                        single_cfg = SingleSignatureRecognitionJobCfg(
                            id=rule_point.id,
                            frame_infos={},
                            text=name or "",
                            sign_id=sign_id,
                            detection_threshold=detect_threshold,
                            recog_threshold=recog_threshold,
                            need_recog=signature_flag,
                        )
                        sign_cfgs.append(single_cfg)
                if not signature_flag or len(sign_cfgs) == 0:
                    sign_id = self.id_generator.get_detection_ocr_id(
                        OCRInfoType.HANDWRITING_OCR_TYPE
                    )
                    single_cfg = SingleSignatureRecognitionJobCfg(
                        id=rule_point.id,
                        frame_infos={},
                        text="",
                        sign_id=sign_id,
                        detection_threshold=detect_threshold,
                        recog_threshold=recog_threshold,
                        need_recog=False,
                    )
                    sign_cfgs.append(single_cfg)
        return sign_cfgs

    def _get_signer_name(
        self, signature_info: SignatureInfo, participants: list[Participant]
    ):
        """Get signer name from participants using role.

        Args:
            signature_info (SignatureInfo): The signature info containes role.
            participants (list[Participant]): The all participants in the task.
        """
        signer_role = signature_info.signer_role
        for participant in participants:
            role = participant.role
            name = participant.name
            if signer_role in [role, "*"]:
                return name
        return ""

    def run(self, job_cfg: SignatureRecognitionJobCfg, task_context: TaskContext):
        frame_ch = task_context.frame_channels[JobName.SignatureRecognition]
        _event_ch = task_context.event_channels[JobName.SignatureRecognition]

        ai_result: list[Any] = []
        job_results: list[Any] = []

        # Registe sign contents into sign_tracker
        assert self.sign_tracker is not None
        self._register(job_cfg)

        # Grab video & frame infos from job_cfg
        fps = job_cfg.fps
        batch_size = job_cfg.batch_size
        media_meta = job_cfg.media.meta

        # Abort when job_cfg is empty
        if len(job_cfg.configs) <= 0:
            return SignatureRecognitionJobResult(ai_result=ai_result, results=job_results)

        # Init handwriting service
        sign_service = HandwritingOCRService()

        tracking_results = []

        media_fps = 25
        if media_meta and media_meta.fps:
            media_fps = int(float(media_meta.fps))
        process_fps = fps
        process_step = int(media_fps / process_fps)

        assert isinstance(frame_ch, FrameChannel)
        frame_gen = frame_ch.output()
        for frames in gather_batch_frames_from_generator(frame_gen, process_step, batch_size):
            sign_ocr_results = sign_service.run(frames)
            for ocr_result, frame in zip(sign_ocr_results, frames.frames):
                tracking_result = self.sign_tracker.process(ocr_result, frame)
                if tracking_result:
                    tracking_results.append(tracking_result)

        # Make sure all sign tracking result published.
        tracking_result = self.sign_tracker.over()
        if tracking_result:
            tracking_results.append(tracking_result)

        # Parse job_results & ai_result
        for tracking_result in tracking_results:
            id, job_result = self._parse(tracking_result)
            img_bytes = get_image_bytes(job_result.frame)
            if img_bytes is not None:
                cv_img = decode_image(img_bytes)  # pyright: ignore[reportArgumentType]
                bbox = job_result.bbox
                if bbox and len(bbox) == 4:
                    draw_box(cv_img, bbox, (0, 255, 0))
                elif bbox and len(bbox) == 8:
                    draw_polygon(cv_img, bbox, (0, 255, 0))
                drawed_img_bytes = encode_image(cv_img)
                url = get_storage_url(self.task_uuid, drawed_img_bytes)
                job_result.url = url
                job_result.frame.url = url
                job_result.frame.data = None
            ai_result.append(job_result)
            job_results.append((id, job_result))
        return SignatureRecognitionJobResult(ai_result=ai_result, results=job_results)

    def _register(self, job_cfg: SignatureRecognitionJobCfg):
        """Registe sign contents into job_tracker.

        Args:
            job_cfg (SignatureRecognitionJobCfg): The job configs parse from task.
        """
        assert self.sign_tracker is not None
        for cfg in job_cfg.configs:
            sign_contents = {}
            # Fill recognition content when recognition is needed
            if cfg.need_recog:
                sign_contents["name"] = {
                    "text": cfg.text,
                    "similarity_threshold": cfg.recog_threshold,
                }
                self.sign_tracker.need_recognition = True

            self.sign_tracker.append_contents(
                cfg.sign_id, sign_contents, key_fields=["name"]
            )

    def _parse(
        self, tracking_result: OCRTrackingResult
    ) -> tuple[str, SignOCRRecogResult]:
        """Parse SignOCRRecogResult from OCRTrackingResult.

        Args:
            tracking_result (OCRTrackingResult): The ocr tracking result from
                ocr manager.

        Returns:
            tuple[str, SignOCRRecogResult]: The rule_point uuid & sign recog result.
                Set rule_point uuid as sign ocr detection_id when the OCRTrackingResult
                is detection result.
        """
        sign_id = tracking_result.tracking_id
        # Set rule_point_id as sign_id if sign_id has not registed.
        rule_point_id = self.id_mapper.get(sign_id, sign_id)
        # Parse origin text from expected_contents
        origin_texts = []
        for content in tracking_result.expected_contents.values():
            origin_texts.append(content["text"])
        # Parse recog text & confidence from recoginized_contents
        recog_texts = []
        recog_confidences = []
        for content in tracking_result.recoginized_contents.values():
            recog_texts.append(content["text"])
            recog_confidences.append(content["similarity"])
        sign_ocr_recog_result = SignOCRRecogResult(
            frame=tracking_result.frame,
            time=tracking_result.time_patch,
            bbox=list(filter(None, tracking_result.bbox)) if tracking_result.bbox else [],  # pyright: ignore[reportArgumentType]
            detect_confidence=tracking_result.confidence or 0.0,
            origin_keys=tracking_result.keys,
            origin_texts=origin_texts,
            recog_texts=recog_texts,
            recog_confidence=recog_confidences,
        )
        return (rule_point_id, sign_ocr_recog_result)
