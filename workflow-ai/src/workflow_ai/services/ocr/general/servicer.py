"""gRPC servicer for OCRService (ocr_normal.proto).

Implements ``OCRService.ReadTextAndLocateChars`` and
``OCRService.ReadTextAndLocateCharsBatch`` — the two methods used by the
worker's subtitle and script matching modules.
"""
from __future__ import annotations

import logging

from workflow_ai.services.ocr.general.engine import GeneralOCREngine, TextRect, TextRotatedRect

logger = logging.getLogger(__name__)


class OCRServicer:
    """Implements the OCRService proto contract."""

    def __init__(self, engine: GeneralOCREngine | None = None) -> None:
        self._engine = engine or GeneralOCREngine()

    # ------------------------------------------------------------------
    # Primary RPC used by the worker
    # ------------------------------------------------------------------

    def ReadTextAndLocateChars(self, request, context):  # noqa: N802
        from workflow_ai.grpc import ocr_normal_pb2  # type: ignore[import]

        result = self._engine.recognize(request.image_data)
        base_resp = ocr_normal_pb2.base.BaseResp(status_code=0, status_message="ok")

        return ocr_normal_pb2.CharLocateRsp(
            status="ok",
            line_text=result.line_text,
            line_rect=[self._to_pb_rect(r, ocr_normal_pb2) for r in result.line_rect],
            char_score=result.char_score,
            line_rotated_rect=[self._to_pb_rot_rect(r, ocr_normal_pb2) for r in result.line_rotated_rect],
            base_resp=base_resp,
        )

    # Alias (snake_case variant used by some worker versions)
    Read_text_and_locate_chars = ReadTextAndLocateChars  # noqa: N815

    def ReadScreenImg(self, request, context):  # noqa: N802
        from workflow_ai.grpc import ocr_normal_pb2  # type: ignore[import]

        result = self._engine.recognize(request.image_data)
        text = " ".join(result.line_text)
        base_resp = ocr_normal_pb2.base.BaseResp(status_code=0, status_message="ok")

        return ocr_normal_pb2.OCRSerRsp(status="ok", res=[text], base_resp=base_resp)

    Read_Screen_Img = ReadScreenImg  # noqa: N815

    def ReadTextAndLocateCharsBatch(self, request, context):  # noqa: N802
        from workflow_ai.grpc import ocr_normal_pb2  # type: ignore[import]

        all_line_text, all_line_rect, all_char_score, all_rot_rect = [], [], [], []
        for img_data in request.image_data_batch:
            result = self._engine.recognize(img_data)
            all_line_text.extend(result.line_text)
            all_line_rect.extend([self._to_pb_rect(r, ocr_normal_pb2) for r in result.line_rect])
            all_char_score.extend(result.char_score)
            all_rot_rect.extend([self._to_pb_rot_rect(r, ocr_normal_pb2) for r in result.line_rotated_rect])

        base_resp = ocr_normal_pb2.base.BaseResp(status_code=0, status_message="ok")
        return ocr_normal_pb2.CharLocateBatchRsp(
            line_text=all_line_text,
            line_rect=all_line_rect,
            char_score=all_char_score,
            line_rotated_rect=all_rot_rect,
            base_resp=base_resp,
        )

    def LocateTextAdv(self, request, context):  # noqa: N802
        from workflow_ai.grpc import ocr_normal_pb2  # type: ignore[import]

        result = self._engine.recognize(request.image_data)
        base_resp = ocr_normal_pb2.base.BaseResp(status_code=0, status_message="ok")
        img_rect = result.line_rect[0] if result.line_rect else None
        return ocr_normal_pb2.TextLocateRsp(
            status="ok",
            img_rect=self._to_pb_rect(img_rect, ocr_normal_pb2) if img_rect else None,
            char_score=result.char_score,
            base_resp=base_resp,
        )

    Locate_text_adv = LocateTextAdv  # noqa: N815

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_pb_rect(r: TextRect, pb) -> object:
        return pb.TextRect(x=r.x, y=r.y, width=r.width, height=r.height)

    @staticmethod
    def _to_pb_rot_rect(r: TextRotatedRect, pb) -> object:
        return pb.TextRotatedRect(
            x0=r.x0, y0=r.y0,
            x1=r.x1, y1=r.y1,
            x2=r.x2, y2=r.y2,
            x3=r.x3, y3=r.y3,
        )
