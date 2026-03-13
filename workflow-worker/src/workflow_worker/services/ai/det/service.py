from typing import Any
from workflow_worker.shared.config._config import settings
from workflow_worker.domain.entities.frame import BatchFrame
from workflow_worker.domain.entities.human import Body, Face
from workflow_worker.domain.entities.service.human_detection import HumanDetectionServiceResult
from workflow_proto import face_body_detection_pb2, face_body_detection_pb2_grpc
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.service import GRPCService, require_cache
from workflow_worker.shared.utils.frame import get_batch_image_bytes

logger = get_logger(__name__)


class DetService(GRPCService):
    """Service for detecting human faces and bodies across a batch of frames.

    Returns bounding boxes sorted by area for each frame, filtered by the
    configured detection thresholds.
    """

    def __init__(
        self,
        face_detection_threshold: float = 0.7,
        body_detection_threshold: float = 0.7,
        name="det_service",
        version="v1",
        description="face and body detection service",
    ):
        super().__init__(
            settings.DETECTION.TARGET,
            face_body_detection_pb2_grpc.DetectionServiceStub,
            name, version, description,
        )
        self.face_detection_threshold = face_detection_threshold
        self.body_detection_threshold = body_detection_threshold

    @require_cache
    def run(self, frames: BatchFrame) -> list[HumanDetectionServiceResult]:  # pyright: ignore[reportIncompatibleMethodOverride]
        images_index, images_bytes = get_batch_image_bytes(frames)
        logger.info(f"valid frames: {len(images_index)}, total: {frames.batch_size}")

        req = face_body_detection_pb2.Request()
        req.imgs.extend(images_bytes)
        rsp = self.stub.Predict(req, timeout=10)
        if rsp.base_resp.status_code != 0:
            self._log_grpc_error(rsp.base_resp, "Error from detection service", logger)

        return self._parse_results(rsp, frames.batch_size, images_index)

    def _parse_results(self, rsp, total_count: int, images_index: list[Any]) -> list[HumanDetectionServiceResult]:
        face_per_frame: list[list[Face] | None] = [None] * total_count
        body_per_frame: list[list[Body] | None] = [None] * total_count

        for idx, frame_objs in enumerate(rsp.result):
            faces, bodies = [], []
            for obj in frame_objs:
                bbox = [obj.box.x1, obj.box.y1, obj.box.x2, obj.box.y2]
                if obj.eng_name == "face" and obj.score >= self.face_detection_threshold:
                    faces.append(Face(face_bbox=bbox, score=obj.score))
                elif obj.eng_name == "body" and obj.score >= self.body_detection_threshold:
                    bodies.append(Body(body_bbox=bbox, confidence=obj.score))
            face_per_frame[images_index[idx]] = faces
            body_per_frame[images_index[idx]] = bodies

        return [
            HumanDetectionServiceResult(face_infos=f or [], body_infos=b or [])
            for f, b in zip(face_per_frame, body_per_frame)
        ]
