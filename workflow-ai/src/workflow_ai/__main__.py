"""workflow-ai gRPC server entry point.

Starts one gRPC server per AI service on the configured port.
Each service runs in its own thread pool.

Usage:
    uv run python -m workflow_ai                    # start all services
    uv run python -m workflow_ai --service asr      # start only ASR
    WORKFLOW_AI_IS_DEBUG=true uv run python -m workflow_ai
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from concurrent import futures

import grpc

from workflow_ai.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.is_debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_SERVICES = ["asr", "detection", "face_feature", "ocr_general", "ocr_handwriting", "ocr_document", "ocr_id_card"]


def _add_asr(server: grpc.Server) -> None:
    from workflow_ai.grpc import auc_service_pb2_grpc  # type: ignore[import]
    from workflow_ai.services.asr import AucServicer
    auc_service_pb2_grpc.add_AucServiceServicer_to_server(AucServicer(), server)
    server.add_insecure_port(settings.asr_endpoint)
    logger.info("ASR service listening on %s", settings.asr_endpoint)


def _add_detection(server: grpc.Server) -> None:
    from workflow_ai.grpc import face_body_detection_pb2_grpc  # type: ignore[import]
    from workflow_ai.services.detection import DetectionServicer
    face_body_detection_pb2_grpc.add_DetectionServiceServicer_to_server(DetectionServicer(), server)
    server.add_insecure_port(settings.detection_endpoint)
    logger.info("Detection service listening on %s", settings.detection_endpoint)


def _add_face_feature(server: grpc.Server) -> None:
    from workflow_ai.grpc import face_process_pb2_grpc  # type: ignore[import]
    from workflow_ai.services.face_feature import FaceProcessServicer
    face_process_pb2_grpc.add_FaceProcessServicer_to_server(FaceProcessServicer(), server)
    server.add_insecure_port(settings.face_feature_endpoint)
    logger.info("FaceFeature service listening on %s", settings.face_feature_endpoint)


def _add_ocr_general(server: grpc.Server) -> None:
    from workflow_ai.grpc import ocr_normal_pb2_grpc  # type: ignore[import]
    from workflow_ai.services.ocr.general import OCRServicer
    ocr_normal_pb2_grpc.add_OCRServiceServicer_to_server(OCRServicer(), server)
    server.add_insecure_port(settings.ocr_general_endpoint)
    logger.info("OCR-General service listening on %s", settings.ocr_general_endpoint)


def _add_ocr_handwriting(server: grpc.Server) -> None:
    from workflow_ai.grpc import hw_ocr_pb2_grpc  # type: ignore[import]
    from workflow_ai.services.ocr.handwriting import OCRHwServicer
    hw_ocr_pb2_grpc.add_OCRHwServiceServicer_to_server(OCRHwServicer(), server)
    server.add_insecure_port(settings.ocr_handwriting_endpoint)
    logger.info("OCR-Handwriting service listening on %s", settings.ocr_handwriting_endpoint)


def _add_ocr_document(server: grpc.Server) -> None:
    from workflow_ai.grpc import ocr_ehd_warp_pb2_grpc  # type: ignore[import]
    from workflow_ai.services.ocr.document import OcrEHDWarpServicer
    ocr_ehd_warp_pb2_grpc.add_OcrEHDWarpServiceServicer_to_server(OcrEHDWarpServicer(), server)
    server.add_insecure_port(settings.ocr_document_endpoint)
    logger.info("OCR-Document service listening on %s", settings.ocr_document_endpoint)


def _add_ocr_id_card(server: grpc.Server) -> None:
    from workflow_ai.grpc import id_card_ocr_pb2_grpc  # type: ignore[import]
    from workflow_ai.services.ocr.id_card import CardOCRServicer
    id_card_ocr_pb2_grpc.add_CardOCRServicer_to_server(CardOCRServicer(), server)
    server.add_insecure_port(settings.ocr_id_card_endpoint)
    logger.info("OCR-IDCard service listening on %s", settings.ocr_id_card_endpoint)


_ADDERS = {
    "asr": _add_asr,
    "detection": _add_detection,
    "face_feature": _add_face_feature,
    "ocr_general": _add_ocr_general,
    "ocr_handwriting": _add_ocr_handwriting,
    "ocr_document": _add_ocr_document,
    "ocr_id_card": _add_ocr_id_card,
}


def main(services: list[str] | None = None) -> None:
    services = services or _SERVICES

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=settings.max_workers))

    for svc in services:
        adder = _ADDERS.get(svc)
        if adder is None:
            logger.warning("Unknown service: %s — skipped", svc)
            continue
        adder(server)

    server.start()
    logger.info("workflow-ai started (%d service(s))", len(services))

    def _stop(sig, frame):
        logger.info("Shutting down…")
        server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop(grace=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="workflow-ai gRPC server")
    parser.add_argument(
        "--service",
        nargs="+",
        choices=_SERVICES + ["all"],
        default=["all"],
        help="Which services to start (default: all)",
    )
    args = parser.parse_args()

    selected = _SERVICES if "all" in args.service else args.service
    main(selected)
