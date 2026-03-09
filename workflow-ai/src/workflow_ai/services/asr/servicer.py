"""gRPC servicer for the AUC (ASR) service.

Implements the ``AucService`` proto contract defined in ``auc_service.proto``.
The server exposes two RPCs:

* ``Submit`` – accepts an audio URL, triggers the ASR engine, and returns
  a task ID that the caller can use to poll for results.
* ``Query`` – returns the final transcription result for a previously
  submitted task.

Because the workflow-worker uses a Submit → poll → Query pattern, this
implementation runs the ASR engine synchronously on ``Submit`` and stores
the result in memory so ``Query`` can return it immediately.
"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from workflow_ai.services.asr.engine import ASREngine

logger = logging.getLogger(__name__)


class AucServicer:
    """Implements AucService RPC methods.

    Depends on generated ``auc_service_pb2`` / ``auc_service_pb2_grpc``
    modules that are produced by ``grpc/build.sh``.
    """

    def __init__(self, engine: ASREngine | None = None) -> None:
        self._engine = engine or ASREngine()
        self._results: dict[str, Any] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)

    # ------------------------------------------------------------------
    # RPC implementations
    # ------------------------------------------------------------------

    def Submit(self, request, context):  # noqa: N802
        from workflow_ai.grpc import auc_service_pb2  # type: ignore[import]

        task_id = uuid.uuid4().hex
        audio_url = request.audio.url
        audio_format = request.audio.format or "wav"

        logger.info("ASR Submit task_id=%s url=%s", task_id, audio_url)
        self._executor.submit(self._run_asr, task_id, audio_url, audio_format)

        resp = auc_service_pb2.AucSubmitResp(
            code=auc_service_pb2.AucCode.SUCCESS,
            message="submitted",
            id=task_id,
        )
        return auc_service_pb2.AucSubmitResponse(resp=resp)

    def Query(self, request, context):  # noqa: N802
        from workflow_ai.grpc import auc_service_pb2  # type: ignore[import]

        task_id = request.id
        result = self._results.get(task_id)

        if result is None:
            # Still processing
            resp = auc_service_pb2.AucQueryResp(
                id=task_id,
                code=auc_service_pb2.AucCode.ONGOING,
                message="processing",
            )
            return auc_service_pb2.AucQueryResponse(resp=resp)

        if isinstance(result, Exception):
            resp = auc_service_pb2.AucQueryResp(
                id=task_id,
                code=auc_service_pb2.AucCode.ERROR_PROCESSING,
                message=str(result),
            )
            return auc_service_pb2.AucQueryResponse(resp=resp)

        utterances = [
            auc_service_pb2.Utterance(
                text=u.text,
                start_time=u.start_time,
                end_time=u.end_time,
                definite=u.definite,
                words=[
                    auc_service_pb2.Word(
                        text=w.text,
                        start_time=w.start_time,
                        end_time=w.end_time,
                        blank_duration=w.blank_duration,
                        pronounce=w.pronounce,
                    )
                    for w in u.words
                ],
            )
            for u in result.utterances
        ]

        resp = auc_service_pb2.AucQueryResp(
            id=task_id,
            code=auc_service_pb2.AucCode.SUCCESS,
            message="ok",
            text=result.text,
            utterances=utterances,
        )
        return auc_service_pb2.AucQueryResponse(resp=resp)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_asr(self, task_id: str, audio_url: str, audio_format: str) -> None:
        try:
            result = self._engine.transcribe(audio_url, audio_format)
            result.id = task_id
            self._results[task_id] = result
            logger.info("ASR done task_id=%s text_len=%d", task_id, len(result.text))
        except Exception as exc:
            logger.exception("ASR failed task_id=%s", task_id)
            self._results[task_id] = exc
