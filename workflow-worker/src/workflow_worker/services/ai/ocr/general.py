from workflow_worker.shared.config._config import settings
from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.service.ocr import OCRInfo, OCRInfoType, OCRServiceResult, TextBlock
from workflow_worker.domain.entities.proto import ocr_normal_pb2, ocr_normal_pb2_grpc
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.ocr.base import BatchOCRService
from workflow_worker.services.ai.retry import RETRY_UNLIMITED, RetryExhausted, RetryPolicy
from workflow_worker.services.ai.service import timed
from workflow_worker.shared.utils.frame import get_image_bytes

logger = get_logger(__name__)


class GeneralOCRService(BatchOCRService):
    """General OCR service for locating and recognizing text in frames."""

    def __init__(
        self,
        name="general_ocr_service",
        version="v1",
        description="General OCR service",
        retry_policy: RetryPolicy = RETRY_UNLIMITED,
    ):
        super().__init__(settings.GENERAL_OCR.TARGET, ocr_normal_pb2_grpc.OCRServiceStub, name, version, description)
        self.retry_policy = retry_policy

    @timed("predict")
    def predict(self, frame: Frame) -> OCRServiceResult:
        image_bytes = get_image_bytes(frame)
        if image_bytes is None:
            return OCRServiceResult(ocr_infos=[])

        rsp = self._request_with_retry(frame, image_bytes)  # pyright: ignore[reportArgumentType]
        if rsp is None or not rsp.line_text:
            return OCRServiceResult(ocr_infos=[])

        text_blocks = self._parse_text_blocks(rsp)
        if not text_blocks:
            return OCRServiceResult(ocr_infos=[])

        ocr_info = OCRInfo(ocr_type=OCRInfoType.GENERAL_OCR_TYPE, text_blocks=text_blocks, confidence=1.0)
        return OCRServiceResult(ocr_infos=[ocr_info])

    def _request_with_retry(self, frame: Frame, image_bytes: bytes):
        def attempt():
            req = ocr_normal_pb2.OCRSerReq(image_data=image_bytes)
            rsp = self.stub.ReadTextAndLocateChars(req, timeout=10)
            if rsp.base_resp.status_code != 0:
                self._log_grpc_error(rsp.base_resp, "Error from general OCR service", frame.logger)
                raise RuntimeError(f"OCR gRPC error: {rsp.base_resp.status_code}")
            return rsp

        try:
            return self.retry_policy.execute(attempt)
        except RetryExhausted as exc:
            if frame.logger:
                frame.logger.debug(f"msg_id: {frame.msg_id}, OCR retries exhausted: {exc.last_error}")
            return None

    @staticmethod
    def _parse_text_blocks(rsp) -> list[TextBlock]:
        return [
            TextBlock(
                polygon=[rect.x0, rect.y0, rect.x1, rect.y1, rect.x2, rect.y2, rect.x3, rect.y3],
                text=text,
                text_confidence=sum(scores) / len(scores) if scores else 0.0,
                character_confidences=scores,
            )
            for text, scores, rect in zip(rsp.line_text, rsp.char_score, rsp.line_rotated_rect)
            if text
        ]
