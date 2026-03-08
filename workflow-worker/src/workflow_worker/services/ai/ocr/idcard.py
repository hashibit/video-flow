from workflow_worker.shared.config._config import settings
from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.service.ocr import IDCardOCRInfo, OCRInfoType, OCRServiceResult, TextBlock
from workflow_worker.domain.entities.proto import id_card_ocr_pb2, id_card_ocr_pb2_grpc
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.ocr.base import BatchOCRService
from workflow_worker.shared.utils.frame import get_image_bytes
from workflow_worker.shared.utils.image_calculator import calc_bbox

logger = get_logger(__name__)

_KEY_FIELDS = {"name", "address", "id_card_number"}


class IDCardOCRService(BatchOCRService):
    """ID card OCR service for extracting structured fields from ID card images."""

    def __init__(
        self,
        name="id_card_ocr_service",
        version="v1",
        description="IDCard OCR service",
    ):
        super().__init__(settings.ID_CARD_OCR.TARGET, id_card_ocr_pb2_grpc.CardOCRStub, name, version, description)

    def predict(self, frame: Frame) -> OCRServiceResult:
        image_bytes = get_image_bytes(frame)
        if image_bytes is None:
            return OCRServiceResult(ocr_infos=[])

        req = id_card_ocr_pb2.CardOCRReq(req_name="default", img_data=image_bytes, card_type=1)
        rsp = self.stub.Predict(req, timeout=10)
        if not rsp.is_detected:
            logger.info({
                "status_code": rsp.base_resp.status_code,
                "status_message": rsp.base_resp.status_message,
                "message": "No ID card detected in frame",
            })
            return OCRServiceResult(ocr_infos=[])

        text_blocks, confidence = self._parse_extract_info(rsp.extract_info_list)
        ocr_info = IDCardOCRInfo(
            ocr_type=OCRInfoType.ID_CARD_OCR_TYPE,
            side=rsp.side,
            bbox=list(calc_bbox(list(rsp.card_corners))),
            polygon=list(rsp.card_corners),
            confidence=confidence,
            face_polygon=list(rsp.face_corners),
            text_blocks=text_blocks,
        )
        return OCRServiceResult(ocr_infos=[ocr_info])

    @staticmethod
    def _parse_extract_info(extract_info_list) -> tuple[list[TextBlock], float]:
        text_blocks = []
        confidence_sum = 0
        key_count = 0
        for info in extract_info_list:
            if info.name in _KEY_FIELDS:
                confidence_sum += info.confidence
                key_count += 1
            text_blocks.append(TextBlock(
                name=info.name,
                polygon=list(info.info_corners),
                text=info.recog_str,
                text_confidence=info.confidence,
            ))
        avg_confidence = confidence_sum / key_count if key_count > 0 else 0
        return text_blocks, avg_confidence
