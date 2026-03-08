from typing import Any
from workflow_worker.domain.entities.frame import BatchFrame, Frame
from workflow_worker.domain.entities.human import Body, Face, Human
from workflow_worker.domain.entities.service.human_detection import HumanDetectionServiceResult
from workflow_worker.domain.entities.service.human_tracking import PersonTrackingResult
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.feat.service import FeatService
from workflow_worker.services.ai.service import Service
from workflow_worker.services.ai.track.manager import SequenceManager
from workflow_worker.shared.utils.image_calculator import calc_ioa, calc_iou

logger = get_logger(__name__)


def _serialize_human(h: Human) -> dict[str, Any]:
    d = h.dict()
    if d["face_info"]["face_feature"] is not None:
        d["face_info"]["face_feature"] = None
    return d


class TrackService(Service):
    """Tracks humans across multiple frames by matching face and body detections.

    Pipeline per frame:
      1. Filter out faces that are too small relative to the frame.
      2. Filter out faces whose features cannot be extracted.
      3. Associate each face with the best-matching body (optimal assignment).
      4. Push the assembled Human objects into the SequenceManager for tracking.

    Attributes:
        fps: Frames per second of the source video.
        min_time_interval: Minimum tracking duration in ms.
        localization_threshold: IoA threshold for face-body matching.
        feat_service: Service for extracting and comparing face embeddings.
        sequence_manager: Stateful tracker that maintains tracking sequences.
    """

    def __init__(
        self,
        fps: float = 10,
        min_time_interval: int = 5000,
        verfication_threshold: float = 0.75,
        name="track_service",
        version="v1",
        description="face feature embedding extractor",
    ) -> None:
        super().__init__(name, version, description)
        self.localization_threshold = 0.8
        self.fps = fps
        self.feat_service = FeatService(threshold=verfication_threshold)
        self.min_time_interval = min_time_interval
        self.sequence_manager = SequenceManager(
            2000, self.feat_service, self.min_time_interval
        )

    def _human_localization(
        self, face_infos: list[Face], body_infos: list[Body]
    ) -> list[Human]:
        """Optimally associate faces with bodies using a score-table approach.

        All (face, body) pairs meeting the IoA threshold are scored, then
        assigned greedily by descending score — avoiding the first-come-first-served
        bias of the previous per-face greedy loop.
        """
        candidates = sorted(
            [
                (calc_ioa(f.face_bbox, b.body_bbox), calc_iou(f.face_bbox, b.body_bbox), f, b)
                for f in face_infos
                for b in body_infos
                if calc_ioa(f.face_bbox, b.body_bbox) >= self.localization_threshold
            ],
            key=lambda x: (x[0], x[1]),
            reverse=True,
        )

        assigned_faces: set[int] = set()
        assigned_bodies: set[int] = set()
        face_to_body: dict[int, Body] = {}

        for _ioa, _iou, face, body in candidates:
            fi, bi = id(face), id(body)
            if fi not in assigned_faces and bi not in assigned_bodies:
                face_to_body[fi] = body
                assigned_faces.add(fi)
                assigned_bodies.add(bi)

        humans = [
            Human(face_info=face, body_info=face_to_body.get(id(face)), tolerance=int(self.fps))
            for face in face_infos
        ]
        humans += [
            Human(body_info=body, tolerance=int(self.fps))
            for body in body_infos
            if id(body) not in assigned_bodies
        ]
        return humans

    def _filter_small_face(self, face_infos: list[Face], frame: Frame) -> list[Face]:
        """Remove faces whose bounding box is smaller than 3% of the frame dimensions."""
        def _accept(face: Face) -> bool:
            x_min, y_min, x_max, y_max = face.face_bbox
            if frame.width and frame.height and (x_max - x_min) / frame.width >= 0.03 and (y_max - y_min) / frame.height >= 0.03:
                return True
            logger.warning(
                "face too small at ts=%s, size=%d×%d",
                frame.timestamp, x_max - x_min, y_max - y_min,
            )
            return False

        return [f for f in face_infos if _accept(f)]

    def _filter_illegal_face(self, face_infos: list[Face], frame: Frame) -> list[Face]:
        """Remove faces for which a feature embedding cannot be extracted."""
        if not face_infos:
            return face_infos
        batch_frame = BatchFrame(frames=[frame], batch_size=1)
        face_bboxes: list[list[list[int]]] = [[f.face_bbox for f in face_infos]]
        features = self.feat_service.predict(batch_frame, face_bboxes)  # type: ignore[arg-type]
        if not features:
            return []
        valid = []
        for face, feature in zip(face_infos, features[0]):
            if feature:
                face.face_feature = feature
                valid.append(face)
        return valid

    def predict(self, human_detection_result: HumanDetectionServiceResult, frame: Frame):
        face_infos = self._filter_small_face(human_detection_result.face_infos, frame)
        face_infos = self._filter_illegal_face(face_infos, frame)
        humans = self._human_localization(face_infos, human_detection_result.body_infos)
        for human in humans:
            self.sequence_manager.push(human, frame)
        self.sequence_manager.check(frame.timestamp)
        return self.sequence_manager.pub()

    def run(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        human_detection_results: list[HumanDetectionServiceResult],
        batch_frame: BatchFrame,
    ) -> dict[float, list[dict[str, Any]]]:
        return {
            frame.timestamp: [_serialize_human(h) for h in human_infos]
            for detection_result, frame in zip(human_detection_results, batch_frame.frames)
            if (human_infos := self.predict(detection_result, frame))
        }

    def get_result(self) -> list[PersonTrackingResult]:
        return [
            PersonTrackingResult(
                id=0,
                tracking_id=ts.tracking_id,
                frame=ts.stored_frame,
                time_patchs=ts.time_patchs,
                bbox=ts.stored_face_bbox or [],
            )
            for ts in self.sequence_manager.queue
        ]
