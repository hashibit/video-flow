"""gRPC servicer for OcrEHDWarpService (ocr_ehd_warp.proto)."""
from __future__ import annotations

import logging

from workflow_ai.services.ocr.document.engine import DocumentOCREngine

logger = logging.getLogger(__name__)


class OcrEHDWarpServicer:
    """Implements ``OcrEHDWarpService.OcrWarp``."""

    def __init__(self, engine: DocumentOCREngine | None = None) -> None:
        self._engine = engine or DocumentOCREngine()

    def OcrWarp(self, request, context):  # noqa: N802
        from workflow_proto import ocr_ehd_warp_pb2  # type: ignore[import]

        result = self._engine.warp(request.image)
        base_resp = ocr_ehd_warp_pb2.base.BaseResp(status_code=0, status_message="ok")

        pages = [
            ocr_ehd_warp_pb2.Poly(
                bounds=[ocr_ehd_warp_pb2.Point(x=p.x, y=p.y) for p in poly.bounds],
                points=[ocr_ehd_warp_pb2.Point(x=p.x, y=p.y) for p in poly.points],
                poly_prob=poly.poly_prob,
                image_page=poly.image_page,
            )
            for poly in result.pages
        ]

        return ocr_ehd_warp_pb2.OcrResponse(
            num_poly=result.num_poly,
            pages=pages,
            base_resp=base_resp,
        )
