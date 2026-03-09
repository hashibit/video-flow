"""gRPC servicer for OCRHwService (hw_ocr.proto)."""
from __future__ import annotations

import logging

from workflow_ai.services.ocr.handwriting.engine import HandwritingOCREngine

logger = logging.getLogger(__name__)


class OCRHwServicer:
    """Implements ``OCRHwService.GetGeneralHwOcr``."""

    def __init__(self, engine: HandwritingOCREngine | None = None) -> None:
        self._engine = engine or HandwritingOCREngine()

    def GetGeneralHwOcr(self, request, context):  # noqa: N802
        from workflow_ai.grpc import hw_ocr_pb2  # type: ignore[import]

        result = self._engine.recognize(
            image_data=request.image_data,
            image_url=request.image_url,
        )
        base_resp = hw_ocr_pb2.base.BaseResp(status_code=0, status_message="ok")

        return hw_ocr_pb2.OCRHwRsp(
            image_name=request.image_name,
            line_poly=[
                hw_ocr_pb2.TextRotatedRect(
                    x0=p.x0, y0=p.y0,
                    x1=p.x1, y1=p.y1,
                    x2=p.x2, y2=p.y2,
                    x3=p.x3, y3=p.y3,
                )
                for p in result.line_poly
            ],
            line_text=result.line_text,
            line_type=result.line_type,
            base_resp=base_resp,
        )
