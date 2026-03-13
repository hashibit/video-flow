"""gRPC servicer for CardOCR (id_card_ocr.proto)."""
from __future__ import annotations

import logging

from workflow_ai.services.ocr.id_card.engine import IDCardOCREngine

logger = logging.getLogger(__name__)


class CardOCRServicer:
    """Implements ``CardOCR.Predict``."""

    def __init__(self, engine: IDCardOCREngine | None = None) -> None:
        self._engine = engine or IDCardOCREngine()

    def Predict(self, request, context):  # noqa: N802
        from workflow_proto import id_card_ocr_pb2  # type: ignore[import]

        result = self._engine.recognize(request.img_data, card_type=request.card_type)
        base_resp = id_card_ocr_pb2.base.BaseResp(status_code=0, status_message="ok")

        extract_info_list = [
            id_card_ocr_pb2.ExtractInfo(
                name=info.name,
                confidence=info.confidence,
                info_corners=info.info_corners,
                recog_str=info.recog_str,
            )
            for info in result.extract_info_list
        ]

        return id_card_ocr_pb2.CardOCRRsp(
            is_detected=result.is_detected,
            side=result.side,
            card_corners=result.card_corners,
            extract_info_list=extract_info_list,
            cropped_img=result.cropped_img,
            face_corners=result.face_corners,
            base_resp=base_resp,
        )
