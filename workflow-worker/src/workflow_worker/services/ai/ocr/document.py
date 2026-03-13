import functools

import cv2  # pyright: ignore[reportMissingImports]
import numpy as np

from workflow_worker.shared.config._config import settings
from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.service.ocr import OCRInfo, OCRInfoType, OCRServiceResult, TextBlock
from workflow_proto import ocr_ehd_warp_pb2, ocr_ehd_warp_pb2_grpc
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.ocr.base import BatchOCRService
from workflow_worker.services.ai.ocr.general import GeneralOCRService
from workflow_worker.shared.utils.frame import decode_image, get_image_bytes

logger = get_logger(__name__)

_PADDING_FACTOR = 0.23


def _adjust_coord(value: float, dimension: float) -> float:
    return value - dimension * _PADDING_FACTOR


def _cmp_text_block(a: TextBlock, b: TextBlock) -> int:
    if a.y != b.y:
        return -1 if a.y < b.y else 1
    if a.character_area != b.character_area:
        return -1 if a.character_area > b.character_area else 1
    return 0


class DocumentOCRService(BatchOCRService):
    """Document OCR service for detecting and recognizing document pages in frames.

    Uses a two-stage pipeline: document detection (OCR EHD Warp) followed by
    general OCR on each detected page after perspective correction.
    """

    def __init__(
        self,
        detect_threshold: float = 0.75,
        name="document_ocr_service",
        version="v1",
        description="Document OCR service",
    ):
        super().__init__(
            settings.DOCUMENT_OCR.OCR_EHD_WARP_TARGET,
            ocr_ehd_warp_pb2_grpc.OcrEHDWarpServiceStub,
            name, version, description,
        )
        self.detect_threshold = detect_threshold
        self.ocr_normal_client = GeneralOCRService()

    def predict(self, frame: Frame) -> OCRServiceResult:
        image_bytes = get_image_bytes(frame)
        if image_bytes is None:
            return OCRServiceResult(ocr_infos=[])

        req = ocr_ehd_warp_pb2.OcrRequest(
            image=image_bytes,
            signature=settings.DOCUMENT_OCR.OCR_EHD_WARP_SIGNATURE,
        )
        rsp = self.stub.OcrWarp(req, timeout=10)
        if rsp.base_resp.status_code != 0:
            self._log_grpc_error(rsp.base_resp, "Error from document OCR service", logger)

        frame_image = decode_image(image_bytes)  # pyright: ignore[reportArgumentType]
        frame_height, frame_width = frame_image.shape[:2]  # pyright: ignore[reportOptionalMemberAccess]

        ocr_infos = [
            self._process_page(page, frame_width, frame_height)
            for page in rsp.pages[:rsp.num_poly]
            if page.poly_prob >= self.detect_threshold
        ]
        return OCRServiceResult(ocr_infos=ocr_infos)

    def _process_page(self, page, width: int, height: int) -> OCRInfo:
        bbox = []
        for pt in page.bounds:
            bbox.extend([_adjust_coord(pt.x, width), _adjust_coord(pt.y, height)])

        polygon = []
        for pt in page.points:
            polygon.extend([_adjust_coord(pt.x, width), _adjust_coord(pt.y, height)])

        image_array = decode_image(page.image_page)
        h, w, _ = image_array.shape  # pyright: ignore[reportOptionalMemberAccess]
        src_corners = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])  # type: ignore[arg-type] # pyright: ignore[reportCallIssue, reportArgumentType]
        dst_corners = np.float32(polygon).reshape(-1, 2)  # type: ignore[arg-type] # pyright: ignore[reportCallIssue, reportArgumentType]
        inverse_mat = cv2.getPerspectiveTransform(src=src_corners, dst=dst_corners)  # type: ignore[call-overload] # pyright: ignore[reportCallIssue, reportArgumentType]

        normal_ocr_result = self.ocr_normal_client.predict(Frame(url="", data=page.image_page))
        text_blocks = normal_ocr_result.ocr_infos[0].text_blocks

        for text_block in text_blocks:
            pts = np.float32(text_block.polygon).reshape(-1, 1, 2)
            text_block.polygon = cv2.perspectiveTransform(src=pts, m=inverse_mat).reshape(-1).tolist()

        text_blocks = sorted(text_blocks, key=functools.cmp_to_key(_cmp_text_block))
        return OCRInfo(
            ocr_type=OCRInfoType.DOC_OCR_TYPE,
            bbox=bbox,
            polygon=polygon,
            confidence=page.poly_prob,
            text_blocks=text_blocks,
        )
