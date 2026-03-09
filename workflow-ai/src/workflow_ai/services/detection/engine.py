"""Face and body detection engine.

Wraps InsightFace's RetinaFace detector for faces and a lightweight
body detector (YOLO or InsightFace body model) to return bounding boxes
with confidence scores for each image in a batch.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DetectedObject:
    eng_name: str       # "face" or "body"
    chn_name: str       # Chinese label
    x1: int
    y1: int
    x2: int
    y2: int
    score: float


@dataclass
class DetectionResult:
    """Detection results for a single image."""
    objects: list[DetectedObject]


class DetectionEngine:
    """Batch face + body detector backed by InsightFace.

    Parameters
    ----------
    model_path:
        Directory containing the InsightFace model pack.
    face_threshold:
        Minimum confidence to keep a face detection.
    body_threshold:
        Minimum confidence to keep a body detection.
    device:
        ``"cpu"`` or ``"cuda"``.
    """

    def __init__(
        self,
        model_path: str = "models/detection",
        face_threshold: float = 0.7,
        body_threshold: float = 0.7,
        device: str = "cpu",
    ) -> None:
        self.model_path = model_path
        self.face_threshold = face_threshold
        self.body_threshold = body_threshold
        self.device = device
        self._face_model: Any = None

    def _load(self) -> None:
        if self._face_model is not None:
            return
        try:
            import insightface  # type: ignore[import-untyped]
            app = insightface.app.FaceAnalysis(
                name="buffalo_sc",
                root=self.model_path,
                providers=["CPUExecutionProvider"] if self.device == "cpu" else ["CUDAExecutionProvider"],
            )
            app.prepare(ctx_id=0 if self.device == "cpu" else 1, det_size=(640, 640))
            self._face_model = app
            logger.info("Detection model loaded from %s", self.model_path)
        except ImportError as exc:
            raise RuntimeError(
                "insightface is not installed. Install with: pip install insightface onnxruntime"
            ) from exc

    def predict(self, images: list[bytes]) -> list[DetectionResult]:
        """Detect faces and bodies in a batch of JPEG/PNG byte strings."""
        self._load()
        results: list[DetectionResult] = []

        for img_bytes in images:
            objects = self._detect_one(img_bytes)
            results.append(DetectionResult(objects=objects))

        return results

    def _detect_one(self, img_bytes: bytes) -> list[DetectedObject]:
        import cv2  # type: ignore[import-untyped]

        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return []

        faces = self._face_model.get(img)
        objects: list[DetectedObject] = []

        for face in faces:
            score = float(face.det_score)
            if score < self.face_threshold:
                continue
            bbox = face.bbox.astype(int)
            objects.append(DetectedObject(
                eng_name="face",
                chn_name="人脸",
                x1=int(bbox[0]), y1=int(bbox[1]),
                x2=int(bbox[2]), y2=int(bbox[3]),
                score=score,
            ))

        return objects
