"""gRPC servicer for the DetectionService (face_body_detection.proto)."""
from __future__ import annotations

import logging

from workflow_ai.services.detection.engine import DetectionEngine

logger = logging.getLogger(__name__)


class DetectionServicer:
    """Implements ``DetectionService.Predict`` RPC."""

    def __init__(self, engine: DetectionEngine | None = None) -> None:
        self._engine = engine or DetectionEngine()

    def Predict(self, request, context):  # noqa: N802
        from workflow_ai.grpc import face_body_detection_pb2  # type: ignore[import]

        images = list(request.imgs)
        logger.info("Detection batch size=%d", len(images))
        results = self._engine.predict(images)

        grpc_objects = []
        for det_result in results:
            frame_objects = []
            for obj in det_result.objects:
                box = face_body_detection_pb2.Box(
                    x1=obj.x1, y1=obj.y1, x2=obj.x2, y2=obj.y2,
                )
                frame_objects.append(face_body_detection_pb2.Object(
                    eng_name=obj.eng_name,
                    chn_name=obj.chn_name,
                    box=box,
                    score=obj.score,
                ))
            grpc_objects.extend(frame_objects)

        base_resp = face_body_detection_pb2.base.BaseResp(status_code=0, status_message="ok")
        return face_body_detection_pb2.Response(result=grpc_objects, base_resp=base_resp)
