"""gRPC servicer for FaceProcess (face_process.proto).

Implements ``FaceProcess.Predict`` used by the worker's ``FeatService`` client
to extract ArcFace embeddings for face bounding boxes.
"""
from __future__ import annotations

import logging

from workflow_ai.services.face_feature.engine import FaceFeatureEngine

logger = logging.getLogger(__name__)


class FaceProcessServicer:
    """Implements ``FaceProcess.Predict`` and ``FaceProcess.GetSupportType``."""

    def __init__(self, engine: FaceFeatureEngine | None = None) -> None:
        self._engine = engine or FaceFeatureEngine()

    def Predict(self, request, context):  # noqa: N802
        from workflow_ai.grpc import face_process_pb2  # type: ignore[import]

        images = list(request.frame_list)
        # bbox is a flat list: [x1,y1,x2,y2, x1,y1,x2,y2, ...]
        raw_bboxes = list(request.bbox)
        bboxes_per_image = self._split_bboxes(raw_bboxes, len(images))

        logger.info("FaceFeature batch size=%d bboxes=%d", len(images), len(raw_bboxes) // 4)
        results = self._engine.extract(images, bboxes_per_image)

        frame_info_list = []
        for res in results:
            obj_info_list = [
                face_process_pb2.ObjInfo(
                    bbox=obj.bbox,
                    keypoint=obj.keypoint,
                    feature_pb=obj.feature_pb,
                    face_id=obj.face_id,
                )
                for obj in res.obj_info_list
            ]
            frame_info_list.append(face_process_pb2.FrameInfo(
                obj_info_list=obj_info_list,
                img_height=res.img_height,
                img_width=res.img_width,
            ))

        base_resp = face_process_pb2.base.BaseResp(status_code=0, status_message="ok")
        return face_process_pb2.ServiceRsp(
            frame_info_list=frame_info_list,
            base_resp=base_resp,
        )

    def GetSupportType(self, request, context):  # noqa: N802
        from workflow_ai.grpc import face_process_pb2  # type: ignore[import]
        base_resp = face_process_pb2.base.BaseResp(status_code=0, status_message="ok")
        return face_process_pb2.SupportTypeRsp(
            support_type_list=["extract_feature"],
            base_resp=base_resp,
        )

    @staticmethod
    def _split_bboxes(flat: list[int], num_images: int) -> list[list[list[int]]]:
        """Split flat bbox list into per-image groups of [x1,y1,x2,y2]."""
        quads = [flat[i:i + 4] for i in range(0, len(flat), 4)]
        # Distribute quads evenly across images (each image gets the same count)
        per_img = len(quads) // num_images if num_images else 0
        result = []
        for i in range(num_images):
            result.append(quads[i * per_img:(i + 1) * per_img])
        return result
