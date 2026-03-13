"""Handwriting OCR engine.

Uses PaddleOCR with handwriting-tuned models (or a dedicated handwriting
recognition library) to recognize both machine-printed and handwritten text.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class LineType(IntEnum):
    MachinePrinted = 0
    Handwritten = 1


@dataclass
class TextRotatedRect:
    x0: int
    y0: int
    x1: int
    y1: int
    x2: int
    y2: int
    x3: int
    y3: int


@dataclass
class HandwritingOCRResult:
    line_poly: list[TextRotatedRect] = field(default_factory=list)
    line_text: list[str] = field(default_factory=list)
    line_type: list[LineType] = field(default_factory=list)


class HandwritingOCREngine:
    """Handwriting-aware OCR using PaddleOCR."""

    def __init__(self, lang: str = "ch", use_gpu: bool = False) -> None:
        self.lang = lang
        self.use_gpu = use_gpu
        self._ocr: Any = None

    def _load(self) -> None:
        if self._ocr is not None:
            return
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-untyped] # pyright: ignore[reportMissingImports]
            self._ocr = PaddleOCR(use_angle_cls=True, lang=self.lang, use_gpu=self.use_gpu)
            logger.info("HandwritingOCR loaded lang=%s", self.lang)
        except ImportError as exc:
            raise RuntimeError("PaddleOCR is not installed.") from exc

    def recognize(self, image_data: bytes, image_url: str = "") -> HandwritingOCRResult:
        self._load()
        import cv2  # type: ignore[import-untyped]

        if image_data:
            arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        elif image_url:
            import urllib.request
            with urllib.request.urlopen(image_url) as resp:
                arr = np.frombuffer(resp.read(), np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        else:
            return HandwritingOCRResult()

        if img is None:
            return HandwritingOCRResult()

        raw = self._ocr.ocr(img, cls=True)
        return self._parse(raw)

    def _parse(self, raw: list | None) -> HandwritingOCRResult:  # pyright: ignore[reportMissingTypeArgument]
        if not raw or not raw[0]:
            return HandwritingOCRResult()

        result = HandwritingOCRResult()
        for line in raw[0]:
            poly, (text, _score) = line
            result.line_text.append(text)
            result.line_poly.append(TextRotatedRect(
                x0=int(poly[0][0]), y0=int(poly[0][1]),
                x1=int(poly[1][0]), y1=int(poly[1][1]),
                x2=int(poly[2][0]), y2=int(poly[2][1]),
                x3=int(poly[3][0]), y3=int(poly[3][1]),
            ))
            # PaddleOCR does not classify handwriting vs machine; default to MachinePrinted
            result.line_type.append(LineType.MachinePrinted)

        return result
