"""General OCR engine backed by PaddleOCR."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TextRect:
    x: int
    y: int
    width: int
    height: int


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
class OCRResult:
    line_text: list[str] = field(default_factory=list)
    line_rect: list[TextRect] = field(default_factory=list)
    char_rect: list[TextRect] = field(default_factory=list)
    char_score: list[float] = field(default_factory=list)
    line_rotated_rect: list[TextRotatedRect] = field(default_factory=list)


class GeneralOCREngine:
    """PaddleOCR-based text recognition engine.

    Parameters
    ----------
    lang:
        OCR language, e.g. ``"ch"``, ``"en"``.
    use_gpu:
        Whether to use GPU.
    """

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
            logger.info("PaddleOCR loaded lang=%s gpu=%s", self.lang, self.use_gpu)
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR is not installed. Install with: pip install paddlepaddle paddleocr"
            ) from exc

    def recognize(self, image_data: bytes) -> OCRResult:
        """Run OCR on raw image bytes and return structured result."""
        self._load()
        import cv2  # type: ignore[import-untyped]

        arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return OCRResult()

        raw = self._ocr.ocr(img, cls=True)
        return self._parse(raw)

    def _parse(self, raw: list | None) -> OCRResult:  # pyright: ignore[reportMissingTypeArgument]
        if not raw or not raw[0]:
            return OCRResult()

        result = OCRResult()
        for line in raw[0]:
            poly, (text, score) = line  # poly: [[x,y], [x,y], [x,y], [x,y]]
            xs = [int(p[0]) for p in poly]
            ys = [int(p[1]) for p in poly]
            x, y = min(xs), min(ys)
            w, h = max(xs) - x, max(ys) - y

            result.line_text.append(text)
            result.line_rect.append(TextRect(x=x, y=y, width=w, height=h))
            result.char_score.append(float(score))

            # Rotated rect from polygon corners
            result.line_rotated_rect.append(TextRotatedRect(
                x0=int(poly[0][0]), y0=int(poly[0][1]),
                x1=int(poly[1][0]), y1=int(poly[1][1]),
                x2=int(poly[2][0]), y2=int(poly[2][1]),
                x3=int(poly[3][0]), y3=int(poly[3][1]),
            ))

        return result
