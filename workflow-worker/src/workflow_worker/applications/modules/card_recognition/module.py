
from typing import Any

from workflow_worker.domain.entities.tasks.card_recognition.config import (
    CardRecognitionJobCfg,
    SingleCardRecognitionJobCfg,
)
from workflow_worker.domain.entities.tasks.card_recognition.result import (
    CardOCRRecogResult,
    CardRecognitionJobResult,
)
from workflow_worker.domain.entities.tasks.common.ocr.result import OCRTrackingResult
from workflow_worker.domain.entities.rule import RulePoint
from workflow_worker.domain.entities.service.ocr import OCRInfoType
from workflow_worker.domain.entities.task import Participant, Task
from workflow_worker.applications.modules.common.ocr.ocr_id_generator import OCRIDChecker, OCRIDGenerator
from workflow_worker.applications.modules.common.ocr.ocr_info_manager import IDCardOCRInfoManager, OCRInfoManager
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.ocr import IDCardOCRService, MultiCardOCRService
from workflow_worker.shared.utils.frame import (
    decode_image,
    encode_image,
    get_image_bytes,
    get_storage_url,
)
from workflow_worker.shared.utils.visualization import draw_box, draw_polygon
from workflow_worker.applications.modules.module import ModuleBase
from workflow_worker.applications.modules.model import JobName
from workflow_worker.infrastructure.media_stream.utils import gather_batch_frames_from_generator
from workflow_worker.infrastructure.media_stream.frame_channel import FrameChannel
from workflow_worker.applications.workflows.task_context import TaskContext

logger = get_logger(__name__)


class CardRecognitionModule(ModuleBase):
    """Card recognition quality inspection task"""

    def __init__(self, task) -> None:
        super().__init__(task)
        self.required_jobs: list[Any] = []
        self.id_generator = OCRIDGenerator()
        self.id_mapper: dict[str, Any] = {}
        self.card_tracker: dict[Any, Any] = {}
        self.card_services: dict[str, Any] = {}
        self.support_card_types = {
            "id_card": OCRInfoType.ID_CARD_OCR_TYPE,
            "employee_card": OCRInfoType.EMPLOYEE_CARD_OCR_TYPE,
            "practicing_certificate": OCRInfoType.PRACTICING_CERTIFICATE_OCR_TYPE,
        }

    def parse_task(self, task: Task) -> CardRecognitionJobCfg:
        """Parse card recog config from task.

        Args:
            task (Task): The task configs.
        """
        configs = []
        if task.rule:
            for rule_section in task.rule.rule_sections:
                for rule_point in rule_section.rule_points:
                    if rule_point:
                        configs.extend(self._get_card_recog_cfg(rule_point, task.participants))  # type: ignore[arg-type] # pyright: ignore[reportArgumentType]
        return CardRecognitionJobCfg(
            fps=task.rule.fps if task.rule else 2.0, batch_size=10, media=task.media, configs=configs
        )

    def _get_card_recog_cfg(
        self, rule_point: RulePoint, participants: list[Participant]
    ) -> list[SingleCardRecognitionJobCfg]:
        """Parse card recog config from rule_point.

        Args:
            rule_point (RulePoint): The rule point needs to check.
        """
        card_cfgs: list[Any] = []
        if not rule_point.verification_cfgs:
            return card_cfgs
        # Parse card cfgs from verification_cfgs
        for cfg in rule_point.verification_cfgs:
            if not cfg:
                continue
            card_type = cfg.card_type
            if card_type not in self.support_card_types:
                continue

            # Get detection id of card by card_type
            ocr_type = self.support_card_types[card_type]
            detect_card_id = self.id_generator.get_detection_ocr_id(ocr_type)

            detect_threshold = cfg.card_detection_threshold
            # 0.7 is the default detect_threshold when card_detection_threshold is less than 0
            detect_threshold = 0.7 if detect_threshold < 0 else detect_threshold
            card_content_flag = cfg.card_content_flag

            for participant in participants:
                if not card_content_flag:
                    continue
                for card in participant.cards:
                    contents = {}
                    # Parse card contents if card_content_flag set to True
                    for field_info in cfg.field_infos:
                        if not field_info:
                            continue
                        key = field_info.field_key
                        # Skip if card has not spec key
                        if not hasattr(card, key):
                            continue
                        # Skip if text is None or ""
                        text = getattr(card, key)
                        if not text:
                            continue
                        recog_threshold = field_info.field_text_threshold
                        # 0.4 is the default recog_threshold when field_text_threshold is less than 0.
                        recog_threshold = (
                            0.4 if recog_threshold < 0 else recog_threshold
                        )
                        contents[key] = {
                            "text": text,
                            "similarity_threshold": recog_threshold,
                        }
                    card_id, flag = self.id_generator.get_ocr_id(card_type, contents)
                    # Skip if the same content has been registed into id_generator
                    if flag:
                        continue
                    # Build the matching relation between rule_point uuid & card_id
                    self.id_mapper[card_id] = rule_point.id
                    single_cfg = SingleCardRecognitionJobCfg(
                        id=rule_point.id,
                        frame_infos={},
                        card_infos=contents,  # type: ignore[arg-type]
                        card_id=card_id,
                        need_detection=True,  # Detection is needed by default
                        detection_threshold=detect_threshold,
                        need_recog=card_content_flag,
                    )
                    card_cfgs.append(single_cfg)
            if not card_content_flag or len(card_cfgs) <= 0:
                single_cfg = SingleCardRecognitionJobCfg(
                    id=rule_point.id,
                    frame_infos={},
                    card_infos={},
                    card_id=detect_card_id,
                    need_detection=True,  # Detection is needed by default
                    detection_threshold=detect_threshold,
                    need_recog=False,
                )
                card_cfgs.append(single_cfg)
        return card_cfgs

    def run(self, job_cfg: CardRecognitionJobCfg, task_context: TaskContext):
        frame_ch = task_context.frame_channels[JobName.CardRecognition]
        _event_ch = task_context.event_channels[JobName.CardRecognition]

        # Grab video & frame infos from job_cfg
        fps = job_cfg.fps
        batch_size = job_cfg.batch_size
        media_meta = job_cfg.media.meta

        # Abort when job_cfg is empty
        if len(job_cfg.configs) <= 0:
            return

        # Init card services & ocr_info manager
        for cfg in job_cfg.configs:
            card_type = OCRIDChecker.get_ocr_type(cfg.card_id)
            if card_type == OCRInfoType.ID_CARD_OCR_TYPE:
                self.card_services["id_card"] = IDCardOCRService()
                self.card_tracker[card_type] = IDCardOCRInfoManager(card_type, fps)
            elif card_type in [
                OCRInfoType.EMPLOYEE_CARD_OCR_TYPE,
                OCRInfoType.PRACTICING_CERTIFICATE_OCR_TYPE,
            ]:
                self.card_services["multi_card"] = MultiCardOCRService()
                self.card_tracker[card_type] = OCRInfoManager(card_type, fps)

        # Registe card contents into card_tracker
        self._register(job_cfg)

        tracking_results: dict[Any, Any] = {
            OCRInfoType.ID_CARD_OCR_TYPE: [],
            OCRInfoType.EMPLOYEE_CARD_OCR_TYPE: [],
            OCRInfoType.PRACTICING_CERTIFICATE_OCR_TYPE: [],
        }

        media_fps = 25
        if media_meta and media_meta.fps:
            media_fps = int(float(media_meta.fps))
        process_fps = fps
        process_step = int(media_fps / process_fps)

        assert isinstance(frame_ch, FrameChannel)
        frame_gen = frame_ch.output()
        # Gather frames in batch_size count.
        for frames in gather_batch_frames_from_generator(frame_gen, process_step, batch_size):
            ocr_results = {"id_card": None, "multi_card": None}
            # Get all card ocr service into ocr_results
            for service_type, service in self.card_services.items():
                ocr_results[service_type] = service.run(frames)

            # Track spec ocr_result with ocrinfo_manager controlled by card_type
            for card_type, info_manager in self.card_tracker.items():
                # Get card_ocr_result by card_type
                if card_type == OCRInfoType.ID_CARD_OCR_TYPE:
                    card_ocr_results = ocr_results["id_card"]
                else:
                    card_ocr_results = ocr_results["multi_card"]
                if card_ocr_results is None:
                    continue
                for card_ocr_result, frame in zip(card_ocr_results, frames.frames):
                    tracking_result = info_manager.process(card_ocr_result, frame)
                    if tracking_result:
                        tracking_results[card_type].append(tracking_result)

        # Make sure all card tracking result published.
        for card_type, info_manager in self.card_tracker.items():
            tracking_result = info_manager.over()
            if tracking_result:
                tracking_results[card_type].append(tracking_result)

        # Parse job_results & ai_result
        ai_result: list[Any] = []
        job_results: list[Any] = []
        for card_tracking_results in tracking_results.values():
            for card_tracking_result in card_tracking_results:
                id, job_result = self._parse(card_tracking_result)
                img_bytes = get_image_bytes(job_result.frame)
                if img_bytes is not None:
                    cv_img = decode_image(img_bytes)  # pyright: ignore[reportArgumentType]
                    bbox = job_result.bbox
                    if bbox and len(bbox) == 4:
                        draw_box(cv_img, bbox, (0, 255, 0))
                    elif bbox and len(bbox) == 8:
                        draw_polygon(cv_img, bbox, (0, 255, 0))
                    drawed_img_bytes = encode_image(cv_img)  # pyright: ignore[reportArgumentType]
                    url = get_storage_url(self.task_uuid, drawed_img_bytes)
                    job_result.url = url
                    job_result.frame.url = url
                    job_result.frame.data = None
                ai_result.append(job_result)
                job_results.append((id, job_result))
        return CardRecognitionJobResult(ai_result=ai_result, results=job_results)

    def _register(self, job_cfg: CardRecognitionJobCfg) -> None:
        """Register doc contents into job_tracker.

        Args:
            job_cfg (CardRecognitionJobCfg): The job configs parse from task.
        """
        for cfg in job_cfg.configs:
            # Get ocr info tracker
            card_type = OCRIDChecker.get_ocr_type(cfg.card_id)
            tracker: OCRInfoManager = self.card_tracker[card_type]  # pyright: ignore[reportArgumentType]

            card_contents = {}
            # Fill recognition content when recognition is needed
            if cfg.need_recog:
                card_contents = cfg.card_infos
                tracker.need_recognition = True
            tracker.append_contents(
                cfg.card_id, card_contents, key_fields=cfg.recog_keys  # type: ignore[arg-type] # pyright: ignore[reportArgumentType]
            )

    def _parse(
        self, tracking_result: OCRTrackingResult
    ) -> tuple[str, CardOCRRecogResult]:
        """Parse CardOCRRecogResult from OCRTrackingResult.

        Args:
            tracking_result (OCRTrackingResult): The ocr tracking result from
                ocr manager.

        Returns:
            tuple[str, CardOCRRecogResult]: The rule_point uuid & card recog result.
                Set rule_point uuid as card ocr detection_id when the OCRTrackingResult
                is detection result.
        """
        card_id = tracking_result.tracking_id
        # Set rule_point_id as card_id if card_id has not registed.
        rule_point_id = self.id_mapper.get(card_id, card_id)
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
        card_ocr_type = OCRIDChecker.get_ocr_type(card_id)
        origin_recog_texts = []
        # If it's an ID card type, get origin_recog_texts from recog_texts
        if card_ocr_type == OCRInfoType.ID_CARD_OCR_TYPE:
            origin_recog_texts = recog_texts

        origin_keys = tracking_result.keys
        # If origin_keys is not specified, default to ["name", "card_number"]
        if len(tracking_result.keys) <= 0:
            origin_keys.extend(["name", "card_number"])

        card_ocr_recog_result = CardOCRRecogResult(
            ocr_type=card_ocr_type,
            frame=tracking_result.frame,
            time=tracking_result.time_patch,
            bbox=list(filter(None, tracking_result.bbox)) if tracking_result.bbox else [],  # pyright: ignore[reportArgumentType]
            detect_confidence=tracking_result.confidence or 0.0,
            origin_keys=tracking_result.keys,
            origin_texts=origin_texts,
            origin_recog_texts=origin_recog_texts,
            recog_texts=recog_texts,
            recog_confidence=recog_confidences,
        )
        return (rule_point_id, card_ocr_recog_result)
