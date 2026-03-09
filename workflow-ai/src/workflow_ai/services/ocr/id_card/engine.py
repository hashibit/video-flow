"""ID card OCR engine.

Detects and extracts structured fields (name, ID number, address, etc.)
from Chinese ID cards and bank cards using PaddleOCR.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class CardType(IntEnum):
    CARD_TYPE_UNKNOWN = 0
    ID_CARD = 1
    BANK_CARD = 2


class Side(IntEnum):
    SIDE_UNKNOWN = 0
    Front = 1
    Back = 2


@dataclass
class ExtractInfo:
    name: str
    confidence: float
    info_corners: list[int] = field(default_factory=list)
    recog_str: str = ""


@dataclass
class CardOCRResult:
    is_detected: bool = False
    side: Side = Side.SIDE_UNKNOWN
    card_corners: list[int] = field(default_factory=list)
    extract_info_list: list[ExtractInfo] = field(default_factory=list)
    cropped_img: bytes = b""
    face_corners: list[int] = field(default_factory=list)


# Simplified field label mapping for Chinese ID cards (front side)
_ID_CARD_FRONT_LABELS = ["姓名", "民族", "出生", "住址", "公民身份号码"]


class IDCardOCREngine:
    """Structured ID/bank card OCR using PaddleOCR."""

    def __init__(self, use_gpu: bool = False) -> None:
        self.use_gpu = use_gpu
        self._ocr: Any = None

    def _load(self) -> None:
        if self._ocr is not None:
            return
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]
            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=self.use_gpu)
            logger.info("IDCardOCR engine loaded")
        except ImportError as exc:
            raise RuntimeError("PaddleOCR is not installed.") from exc

    def recognize(self, img_data: bytes, card_type: int = CardType.ID_CARD) -> CardOCRResult:
        self._load()
        import cv2  # type: ignore[import-untyped]

        arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return CardOCRResult()

        raw = self._ocr.ocr(img, cls=True)
        if not raw or not raw[0]:
            return CardOCRResult()

        extract_infos: list[ExtractInfo] = []
        for line in raw[0]:
            poly, (text, score) = line
            xs = [int(p[0]) for p in poly]
            ys = [int(p[1]) for p in poly]
            corners = [xs[0], ys[0], xs[1], ys[1], xs[2], ys[2], xs[3], ys[3]]

            # Attempt to identify known field labels
            label = self._match_label(text)
            extract_infos.append(ExtractInfo(
                name=label or "text",
                confidence=float(score),
                info_corners=corners,
                recog_str=text,
            ))

        _, encoded = cv2.imencode(".jpg", img)
        return CardOCRResult(
            is_detected=True,
            side=Side.Front,
            extract_info_list=extract_infos,
            cropped_img=encoded.tobytes(),
        )

    @staticmethod
    def _match_label(text: str) -> str | None:
        for label in _ID_CARD_FRONT_LABELS:
            if label in text:
                return label
        return None
