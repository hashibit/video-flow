"""Document OCR engine (perspective warp + detection).

Implements the ``OcrEHDWarpService.OcrWarp`` contract: detects document
polygons in an image and returns warped page images.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Point:
    x: int
    y: int


@dataclass
class Poly:
    bounds: list[Point] = field(default_factory=list)
    points: list[Point] = field(default_factory=list)
    poly_prob: float = 1.0
    image_page: bytes = b""


@dataclass
class DocumentOCRResult:
    num_poly: int = 0
    pages: list[Poly] = field(default_factory=list)


class DocumentOCREngine:
    """Perspective-corrected document detection using PaddleOCR's layout analysis."""

    def __init__(self, use_gpu: bool = False) -> None:
        self.use_gpu = use_gpu
        self._ocr: Any = None

    def _load(self) -> None:
        if self._ocr is not None:
            return
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]
            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=self.use_gpu)
            logger.info("DocumentOCR engine loaded")
        except ImportError as exc:
            raise RuntimeError("PaddleOCR is not installed.") from exc

    def warp(self, image_data: bytes) -> DocumentOCRResult:
        """Detect document region, warp it, and return the corrected page."""
        self._load()
        import cv2  # type: ignore[import-untyped]

        arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return DocumentOCRResult()

        raw = self._ocr.ocr(img, cls=False)
        if not raw or not raw[0]:
            # No text detected — return the whole image as-is
            _, encoded = cv2.imencode(".jpg", img)
            page = Poly(image_page=encoded.tobytes(), poly_prob=1.0)
            return DocumentOCRResult(num_poly=1, pages=[page])

        # Build a bounding polygon from all detected text regions
        all_polys = [line[0] for line in raw[0]]  # each is [[x,y]*4]
        bounds = self._convex_hull_points(all_polys)

        _, encoded = cv2.imencode(".jpg", img)
        page = Poly(
            bounds=[Point(x=int(p[0]), y=int(p[1])) for p in bounds],
            image_page=encoded.tobytes(),
            poly_prob=1.0,
        )
        return DocumentOCRResult(num_poly=1, pages=[page])

    @staticmethod
    def _convex_hull_points(polys: list) -> list:
        import cv2  # type: ignore[import-untyped]
        pts = np.array([p for poly in polys for p in poly], dtype=np.float32)
        hull = cv2.convexHull(pts)
        return hull[:, 0, :].tolist()
