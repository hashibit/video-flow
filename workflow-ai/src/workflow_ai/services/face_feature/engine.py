"""Face feature extraction engine.

Uses InsightFace ArcFace model to extract 512-dim embeddings for face crops,
serialised using the ``featurePB`` protobuf format consumed by the worker.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FaceFeatureResult:
    """Feature extraction result for one frame."""
    obj_info_list: list["ObjInfo"]
    img_height: int
    img_width: int


@dataclass
class ObjInfo:
    bbox: list[int]          # [x1, y1, x2, y2]
    keypoint: list[int]
    feature_pb: bytes        # serialised featurePB.FaceFeature protobuf
    face_id: int = 0


class FaceFeatureEngine:
    """ArcFace-based face feature extractor.

    Parameters
    ----------
    model_path:
        Root directory for InsightFace model download cache.
    device:
        ``"cpu"`` or ``"cuda"``.
    """

    def __init__(self, model_path: str = "models/face_feature", device: str = "cpu") -> None:
        self.model_path = model_path
        self.device = device
        self._app: Any = None

    def _load(self) -> None:
        if self._app is not None:
            return
        try:
            import insightface  # type: ignore[import-untyped] # pyright: ignore[reportMissingImports]
            app = insightface.app.FaceAnalysis(
                name="buffalo_l",
                root=self.model_path,
                providers=["CPUExecutionProvider"] if self.device == "cpu" else ["CUDAExecutionProvider"],
            )
            app.prepare(ctx_id=0 if self.device == "cpu" else 1, det_size=(640, 640))
            self._app = app
            logger.info("Face feature model loaded from %s", self.model_path)
        except ImportError as exc:
            raise RuntimeError(
                "insightface is not installed. Install with: pip install insightface onnxruntime"
            ) from exc

    def extract(self, images: list[bytes], bboxes_per_image: list[list[list[int]]]) -> list[FaceFeatureResult]:
        """Extract features for given bounding boxes across a batch of images.

        Parameters
        ----------
        images:
            Raw image bytes (JPEG or PNG), one per frame.
        bboxes_per_image:
            For each image, a list of ``[x1, y1, x2, y2]`` boxes whose
            features should be extracted.

        Returns
        -------
        list[FaceFeatureResult]
            One result per input image.
        """
        self._load()
        import cv2  # type: ignore[import-untyped]

        results: list[FaceFeatureResult] = []

        for img_bytes, bboxes in zip(images, bboxes_per_image):
            arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                results.append(FaceFeatureResult(obj_info_list=[], img_height=0, img_width=0))
                continue

            h, w = img.shape[:2]
            faces = self._app.get(img)
            face_map = {tuple(f.bbox.astype(int).tolist()): f for f in faces}

            obj_infos: list[ObjInfo] = []
            for bbox in bboxes:
                feature = self._best_feature(face_map, bbox)
                obj_infos.append(ObjInfo(
                    bbox=bbox,
                    keypoint=[],
                    feature_pb=self._serialize_feature(feature),
                ))

            results.append(FaceFeatureResult(obj_info_list=obj_infos, img_height=h, img_width=w))

        return results

    def _best_feature(self, face_map: dict, target_bbox: list[int]) -> list[float] | None:  # pyright: ignore[reportMissingTypeArgument]
        """Find the detected face that best overlaps *target_bbox* and return its embedding."""
        best_iou, best_embedding = 0.0, None
        for face_bbox, face in face_map.items():
            iou = self._iou(list(face_bbox), target_bbox)
            if iou > best_iou:
                best_iou = iou
                best_embedding = face.embedding.tolist() if face.embedding is not None else None
        return best_embedding

    @staticmethod
    def _iou(a: list[int], b: list[int]) -> float:
        ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
        ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0:
            return 0.0
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        return inter / (area_a + area_b - inter)

    @staticmethod
    def _serialize_feature(feature: list[float] | None) -> bytes:
        """Serialize a feature vector using the featurePB protobuf schema."""
        if not feature:
            return b""
        try:
            from workflow_proto import featurePB_pb2  # type: ignore[import]
            proto = featurePB_pb2.FaceFeature()
            proto.feature.extend(feature)
            return proto.SerializeToString()
        except ImportError:
            # featurePB_pb2 not yet generated; return raw float bytes as fallback
            import struct
            return struct.pack(f"{len(feature)}f", *feature)
