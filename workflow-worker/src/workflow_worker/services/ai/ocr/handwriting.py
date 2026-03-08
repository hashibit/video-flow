from workflow_worker.shared.config._config import settings
from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.service.ocr import OCRInfo, OCRInfoType, OCRServiceResult, TextBlock
from workflow_worker.domain.entities.proto import base_pb2, hw_ocr_pb2, hw_ocr_pb2_grpc
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.ocr.base import BatchOCRService
from workflow_worker.shared.utils.frame import get_image_bytes

logger = get_logger(__name__)


class HandwritingOCRService(BatchOCRService):
    """Handwriting OCR service for recognizing handwritten text in frames."""

    def __init__(
        self,
        name="handwriting_ocr_service",
        version="v1",
        description="Handwriting OCR service",
    ):
        super().__init__(settings.HANDWRITING_OCR.TARGET, hw_ocr_pb2_grpc.OCRHwServiceStub, name, version, description)

    def predict(self, frame: Frame) -> OCRServiceResult:
        image_bytes = get_image_bytes(frame)
        if image_bytes is None:
            return OCRServiceResult(ocr_infos=[])

        req = hw_ocr_pb2.HwReq(image_data=image_bytes, base=base_pb2.Base(caller="test"))
        rsp = self.stub.GetGeneralHwOcr(req, timeout=10)
        if rsp.base_resp.status_code != 0:
            self._log_grpc_error(rsp.base_resp, "Error from handwriting OCR service", logger)

        text_blocks = self._parse_text_blocks(rsp)
        if not text_blocks:
            return OCRServiceResult(ocr_infos=[])

        ocr_info = OCRInfo(ocr_type=OCRInfoType.HANDWRITING_OCR_TYPE, text_blocks=text_blocks, confidence=1.0)
        return OCRServiceResult(ocr_infos=[ocr_info])

    @staticmethod
    def _parse_text_blocks(rsp) -> list[TextBlock]:
        num = len(rsp.line_poly)
        if num != len(rsp.line_text) or num != len(rsp.line_type):
            return []
        return [
            TextBlock(
                polygon=[rect.x0, rect.y0, rect.x1, rect.y1, rect.x2, rect.y2, rect.x3, rect.y3],
                text=rsp.line_text[i],
                text_confidence=1,
            )
            for i, rect in enumerate(rsp.line_poly)
            if rsp.line_type[i] == 1
        ]
