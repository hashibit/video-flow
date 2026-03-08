
import numpy as np
from dataclasses import dataclass

from workflow_worker.shared.config._config import settings
from workflow_worker.domain.entities.common.time_patch import TimePatch
from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.human import Body, Face, Human
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.feat.service import FeatService
from workflow_worker.shared.utils.image_calculator import calc_box_area, calc_iou, calc_piecewise

logger = get_logger(__name__)


@dataclass(frozen=True)
class TrackingConfig:
    """Immutable tracking hyper-parameters, read once from settings."""

    alpha: float
    face_iou_threshold: float
    body_iou_threshold: float
    matched_threshold: float

    @classmethod
    def from_settings(cls) -> TrackingConfig:
        cfg = settings.TRACKING_SEQUENCES
        return cls(
            alpha=cfg.ALPHA,
            face_iou_threshold=cfg.FACE_IOU_THRESHOLD,
            body_iou_threshold=cfg.BODY_IOU_THRESHOLD,
            matched_threshold=cfg.MATCHED_THRESHOLD,
        )


class TrackingSequence:
    alpha: float
    face_iou_threshold: float
    body_iou_threshold: float
    matched_threshold: float
    min_time_interval: int
    node: Human
    stored_frame: Frame
    tracking_id: str
    ttl: float
    length: int
    gap: float
    has_match: bool
    stored_face_bbox: list[int] | None
    stored_face_area: float
    face_score: float
    stored_face_feature: np.ndarray | list[float | None] | None
    last_time: float
    time_patchs: list[TimePatch]

    def __init__(
        self,
        node: Human,
        frame: Frame,
        tracking_id: str,
        ttl: float,
        config: TrackingConfig,
        face_score: float = 0.0,
        length: int = 1,
        gap: float = 1000,
        stored_feature: np.ndarray | list[float | None] | None = None,
        min_time_interval: int = 5000,
    ) -> None:
        self.alpha = config.alpha
        self.face_iou_threshold = config.face_iou_threshold
        self.body_iou_threshold = config.body_iou_threshold
        self.matched_threshold = config.matched_threshold
        self.min_time_interval = min_time_interval

        self.node = node
        self.stored_frame = frame
        self.tracking_id = tracking_id
        self.ttl = ttl
        self.length = length
        self.gap = gap
        self.has_match = True
        self.stored_face_bbox = None
        self.stored_face_area = 0
        if node.face_info:
            self.stored_face_bbox = node.face_info.face_bbox
            self.stored_face_area = calc_box_area(self.stored_face_bbox)
        self.face_score = face_score
        self.stored_face_feature = stored_feature

        frame_time = frame.timestamp
        self.last_time = frame_time
        self.time_patchs = [
            TimePatch(start_time=frame_time, end_time=frame_time, min_time_interval=self.min_time_interval)
        ]

    def __lt__(self, other: TrackingSequence) -> bool:
        return self.length > other.length

    def reverse(self, frame_time: float):
        """Compute the complement (gap) time patches up to *frame_time*."""
        time_patchs = []
        start_time = 0.0
        for tp in self.time_patchs:
            if start_time != tp.start_time:
                gap = TimePatch(start_time=start_time, end_time=start_time, min_time_interval=self.min_time_interval)
                gap.update_end_time(tp.start_time)
                time_patchs.append(gap)
            start_time = tp.end_time
        if start_time < frame_time:
            tail = TimePatch(start_time=start_time, end_time=start_time, min_time_interval=self.min_time_interval)
            tail.update_end_time(frame_time)
            time_patchs.append(tail)
        return time_patchs

    def update(self, human_info: Human, frame: Frame) -> None:
        self.node.update(human_info)
        self.length += 1
        self.time_patchs[-1].update_end_time(frame.timestamp)
        self.has_match = True
        if human_info.face_info:
            new_score = human_info.face_info.score
            new_area = calc_box_area(human_info.face_info.face_bbox)
            if (new_score, new_area) > (self.face_score, self.stored_face_area):
                self.face_score = new_score or 0.0
                self.stored_face_area = new_area
                self.stored_frame = frame
                self.stored_face_bbox = human_info.face_info.face_bbox
                self.stored_face_feature = human_info.face_info.face_feature

    def updata_face(self, other: TrackingSequence) -> None:
        self.face_score = other.face_score
        self.stored_face_area = other.stored_face_area
        self.stored_frame = other.stored_frame
        self.stored_face_bbox = other.stored_face_bbox
        self.stored_face_feature = other.stored_face_feature

    def pub(self) -> Human | None:
        if not self.node:
            return None
        return Human(
            tracking_id=self.tracking_id,
            face_info=self.node.face_info,
            body_info=self.node.body_info,
            tolerance=int(self.ttl),
        )

    def is_alive(self) -> bool:
        return self.ttl >= 0

    def is_match(self, human_info: Human) -> bool:
        return self._calc_matched_score(human_info) >= self.matched_threshold

    def is_better_than(self, other: TrackingSequence) -> bool:
        return (self.face_score, self.stored_face_area) > (other.face_score, other.stored_face_area)

    def check_state(self, frame_time: float) -> None:
        if not self.has_match:
            self.ttl -= frame_time - self.last_time
        self.has_match = False

    def merge(self, other: TrackingSequence) -> None:
        """Merge *other* into this sequence, keeping the better stored face."""
        if not self.is_better_than(other):
            self.updata_face(other)
        self.time_patchs += other.time_patchs
        self._merge_time_patch()

    def filter_time_path(self) -> None:
        """Drop time patches shorter than min_time_interval (burr removal)."""
        self.time_patchs = [tp for tp in self.time_patchs if not tp.is_burr()]

    def _merge_time_patch(self) -> None:
        """Sort and merge overlapping or gap-adjacent time patches in a single pass."""
        self.time_patchs.sort(key=lambda tp: tp.start_time)
        merged: list[TimePatch] = []
        for tp in self.time_patchs:
            if merged and (
                tp.is_overlap(merged[-1].start_time, merged[-1].end_time)
                or tp.start_time - merged[-1].end_time <= self.gap
            ):
                merged[-1].update_end_time(max(merged[-1].end_time, tp.end_time))
            else:
                merged.append(tp)
        self.time_patchs = merged

    def _calc_matched_score(self, human_info: Human) -> float:
        face_score = self._calc_face_matched_score(human_info.face_info)
        body_score = self._calc_body_matched_score(human_info.body_info)
        if not human_info.body_info:
            return face_score
        if not human_info.face_info:
            return body_score
        return self.alpha * face_score + (1 - self.alpha) * body_score

    def _calc_bbox_matched_score(self, bbox_a: list[int] | None, bbox_b: list[int] | None, threshold: float) -> float:
        if bbox_a and bbox_b:
            return calc_piecewise(calc_iou(bbox_a, bbox_b), threshold)
        return 0.0

    def _calc_face_matched_score(self, face_info: Face | None) -> float:
        face_bbox = face_info.face_bbox if face_info else None
        last_bbox = self.node.face_info.face_bbox if self.node.face_info else None
        return self._calc_bbox_matched_score(face_bbox, last_bbox, self.face_iou_threshold)

    def _calc_body_matched_score(self, body_info: Body | None) -> float:
        body_bbox = body_info.body_bbox if body_info else None
        last_bbox = self.node.body_info.body_bbox if self.node.body_info else None
        return self._calc_bbox_matched_score(body_bbox, last_bbox, self.body_iou_threshold)

    def to_dict(self) -> dict[str, object]:
        return {
            "tracking_id": self.tracking_id,
            "face_bbox": self.stored_face_bbox,
            "frame_time": self.stored_frame.timestamp,
            "time_patchs": [
                {"start_time": tp.start_time, "end_time": tp.end_time}
                for tp in self.time_patchs
            ],
        }


class SequenceManager:
    """Maintains a list of TrackingSequence objects and matches incoming humans to them.

    Attributes:
        tolerance: TTL in ms before an unmatched sequence expires.
        gap: Maximum inter-patch gap (ms) that is still merged.
        min_time_interval: Minimum tracking duration (ms) for burr filtering.
        queue: Active tracking sequences, roughly sorted by update frequency.
        id_number: Monotonic counter for generating unique tracking IDs.
        feat: Service for comparing face embeddings.
        config: Frozen hyper-parameters read once from settings.
    """

    tolerance: float
    gap: float
    min_time_interval: int
    config: TrackingConfig
    queue: list[TrackingSequence]
    id_number: int
    feat: FeatService

    def __init__(
        self,
        tolerance_misecond: float = 1000,
        feat: FeatService | None = None,
        min_time_interval: int = 5000,
        config: TrackingConfig | None = None,
    ) -> None:
        self.tolerance = tolerance_misecond
        self.gap = 1000
        self.min_time_interval = min_time_interval
        self.config = config or TrackingConfig.from_settings()
        self.queue = []
        self.id_number = -1
        self.feat = feat or FeatService()

    def pub(self) -> list[Human]:
        return [h for ts in self.queue if (h := ts.pub())]

    def get_tracking_id(self) -> str:
        self.id_number += 1
        return f"v104{self.id_number:05d}"

    def update(self, index: int, human_info: Human, frame: Frame) -> None:
        if index >= len(self.queue):
            logger.error("index out of range: %d/%d", index, len(self.queue))
            raise OverflowError("")
        self.queue[index].update(human_info, frame)

    def _rerank(self, target_index: int, index: int) -> None:
        if target_index == index:
            return
        if target_index > index:
            msg = f"target_index {target_index} must be <= index {index}"
            logger.error(msg)
            raise ValueError(msg)
        matched = self.queue[index]
        while index > target_index:
            self.queue[index] = self.queue[index - 1]
            index -= 1
        self.queue[target_index] = matched

    def _check_face_match(self, frame: Frame, face_info: Face | None) -> tuple[TrackingSequence | None, bool]:
        if not face_info:
            return None, False
        face_bbox, face_feature = face_info.face_bbox, face_info.face_feature
        for ts in self.queue:
            candidates = [(ts.stored_face_bbox, ts.stored_face_feature)]
            if ts.node.face_info:
                candidates.append((ts.node.face_info.face_bbox, ts.node.face_info.face_feature))
            if any(
                self.feat.run(ts.stored_frame, frame, ref_bbox, face_bbox, ref_feat, face_feature)
                for ref_bbox, ref_feat in candidates
            ):
                return ts, True
        return None, False

    def _insert(self, human_info: Human, frame: Frame) -> str:
        frame_time = frame.timestamp
        tracking_sequence, is_pass = self._check_face_match(frame, human_info.face_info)
        if is_pass:
            assert tracking_sequence is not None
            tracking_sequence.ttl = self.tolerance
            last_end = tracking_sequence.time_patchs[-1].end_time
            if frame_time - last_end > self.gap:
                tracking_sequence.time_patchs.append(
                    TimePatch(start_time=frame_time, end_time=frame_time, min_time_interval=self.min_time_interval)
                )
            tracking_sequence.update(human_info, frame)
            return tracking_sequence.tracking_id

        if not human_info.face_info:
            return "v0"

        tracking_id = self.get_tracking_id()
        ts = TrackingSequence(
            human_info, frame, tracking_id, self.tolerance,
            config=self.config,
            face_score=human_info.face_info.score or 0.0,
            stored_feature=human_info.face_info.face_feature,  # type: ignore[arg-type]
            min_time_interval=self.min_time_interval,
        )
        self.queue.append(ts)
        return tracking_id

    def push(self, human_info: Human, frame: Frame) -> str:
        if not self.queue:
            return self._insert(human_info, frame)

        index_head = min(range(len(self.queue)), key=lambda i: self.queue[i].length)

        for i, ts in enumerate(self.queue):
            if not ts.is_alive():
                continue
            if ts.is_match(human_info):
                self.update(i, human_info, frame)
                self._rerank(index_head, i)
                return self.queue[index_head].tracking_id

        return self._insert(human_info, frame)

    def check(self, frame_time: float) -> None:
        for ts in self.queue:
            ts.check_state(frame_time)
            ts.last_time = frame_time

    def merge(self) -> None:
        """Merge duplicate tracking sequences identified by face verification."""
        i = 0
        while i < len(self.queue):
            j = i + 1
            while j < len(self.queue):
                if self.feat.run(
                    self.queue[i].stored_frame, self.queue[j].stored_frame,
                    self.queue[i].stored_face_bbox, self.queue[j].stored_face_bbox,
                    self.queue[i].stored_face_feature, self.queue[j].stored_face_feature,
                ):
                    self.queue[i].merge(self.queue[j])
                    del self.queue[j]
                    j -= 1
                j += 1
            i += 1

    def filter_burr(self) -> None:
        """Remove time patches shorter than min_time_interval; drop empty sequences."""
        for ts in self.queue:
            ts.filter_time_path()
        self.queue = [ts for ts in self.queue if ts.time_patchs]

    def filter_noface_human(self) -> None:
        """Drop sequences that never had a stored face bbox."""
        self.queue = [ts for ts in self.queue if ts.stored_face_bbox]
