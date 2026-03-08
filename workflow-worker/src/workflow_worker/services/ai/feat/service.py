from typing import Any
from workflow_worker.shared.config._config import settings
from workflow_worker.domain.entities.frame import BatchFrame, Frame
from workflow_worker.domain.entities.proto import face_process_pb2, face_process_pb2_grpc, featurePB_pb2
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.service import GRPCService, require_cache
from workflow_worker.shared.utils.frame import get_batch_image_bytes
from workflow_worker.shared.utils.image_calculator import cal_cosine_distance, calc_iou

logger = get_logger(__name__)


class FeatService(GRPCService):
    """Service for extracting face feature embeddings and computing face similarity.

    Accepts raw frames and face bounding boxes detected by the detection service,
    extracts feature vectors, and compares them using cosine similarity.
    """

    def __init__(
        self,
        threshold: float = 0.7,
        name="feat_service",
        version="v1",
        description="face feature embedding extractor",
    ):
        super().__init__(
            settings.FACE_VERIFICATION.TARGET,
            face_process_pb2_grpc.FaceProcessStub,
            name, version, description,
        )
        self.threshold = threshold

    @require_cache
    def run(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        face_a: Frame,
        face_b: Frame,
        face_a_bbox: list[int] | None,
        face_b_bbox: list[int] | None,
        face_a_feature: list[float | None] | Any = None,
        face_b_feature: list[float | None] | Any = None,
    ) -> bool:
        """Return True when the two faces are similar enough to be the same person."""
        if face_a_feature and face_b_feature:
            similarity = 1.0 - cal_cosine_distance(face_a_feature, face_b_feature)  # pyright: ignore[reportArgumentType]
        else:
            similarity = self._get_similarity(face_a, face_b, face_a_bbox, face_b_bbox)
        return similarity >= self.threshold

    def _get_similarity(
        self,
        face_a: Frame,
        face_b: Frame,
        face_a_bbox: list[int] | None,
        face_b_bbox: list[int] | None,
    ) -> float:
        if face_a_bbox is None or face_b_bbox is None:
            return 0.0
        frames = BatchFrame(frames=[face_a, face_b], batch_size=2)
        features = self.predict(frames, [[face_a_bbox], [face_b_bbox]])
        if len(features) < 2:
            return 0.0
        feat_a = features[0][0] if features[0] else None
        feat_b = features[1][0] if features[1] else None
        if feat_a and feat_b:
            return 1.0 - cal_cosine_distance(feat_a, feat_b)
        return 0.0

    @require_cache
    def predict(self, frames: BatchFrame, detect_face_bboxes: list[list[Any]]) -> list[Any]:  # type: ignore[override]
        """Extract face features for all bounding boxes across a batch of frames."""
        images_index, images_bytes = get_batch_image_bytes(frames)
        logger.info(f"valid frames: {len(images_index)}, total: {frames.batch_size}")

        req = face_process_pb2.ServiceReq()
        req.req_name = "face_feature"
        req.frame_list.extend(images_bytes)
        req.req_type_list.extend(["extract_feature"])
        for bbox_list in detect_face_bboxes:
            for bbox in bbox_list:
                req.bbox.extend(bbox)

        rsp = self.stub.Predict(req, timeout=10)
        if rsp.base_resp.status_code != 0:
            self._log_grpc_error(rsp.base_resp, "Error from face verification service", logger)

        return self._parse_features(rsp, frames.batch_size, images_index, detect_face_bboxes)

    def _parse_features(self, rsp, total_count: int, images_index: list[Any], detect_face_bboxes: list[Any]) -> list[Any]:
        result: list[Any] = [None] * total_count
        for idx, (frame_info, bboxes) in enumerate(zip(rsp.frame_info_list, detect_face_bboxes)):
            features = [self._best_matching_feature(frame_info.obj_info_list, bbox) for bbox in bboxes]
            result[images_index[idx]] = features
        return result

    @staticmethod
    def _best_matching_feature(obj_info_list, target_bbox):
        max_iou, best_feature = 0, None
        for obj_info in obj_info_list:
            iou = calc_iou(obj_info.bbox, target_bbox)
            if iou > max_iou:
                max_iou = iou
                address_book = featurePB_pb2.FaceFeature()
                address_book.ParseFromString(obj_info.feature_pb)
                best_feature = list(address_book.feature)
        return best_feature
