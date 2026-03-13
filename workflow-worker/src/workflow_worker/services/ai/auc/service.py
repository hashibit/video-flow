import json
import time
import uuid

import requests  # type: ignore[import-untyped]

from workflow_worker.shared.config._config import settings
from workflow_worker.domain.entities.audio import Audio
from workflow_worker.domain.entities.dialogue import Dialogue
from workflow_worker.domain.entities.service.auc import AUCServiceResult
from workflow_proto import auc_service_pb2, auc_service_pb2_grpc
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.service import GRPCService, require_cache
from workflow_worker.services.ai.auc.postprocess import MistakeCorrectionProcessor, PinyinCorrectionProcessor


class AUCService(GRPCService):
    """Audio Understanding Chain Service for transcribing audio to structured dialogue.

    Submits audio to the AUC gRPC service, polls for completion, then applies
    post-processing corrections (pinyin normalization and error word substitution).
    """

    def __init__(
        self,
        name="auc_service",
        version="v1",
        description="audio understanding chain",
        logger=None,
    ):
        super().__init__(settings.AUC.TARGET, auc_service_pb2_grpc.AucServiceStub, name, version, description)
        self.logger = logger or get_logger(__name__)

    @require_cache
    def predict(self, audio: Audio) -> Dialogue:
        submit_resp = self._submit(audio)
        query_resp = self._poll_until_done(submit_resp.resp.id)
        if query_resp is None:
            return Dialogue(text="")
        return self._parse_dialogue(query_resp)

    @require_cache
    def run(self, audio: Audio) -> AUCServiceResult:  # pyright: ignore[reportIncompatibleMethodOverride]
        pipeline = PinyinCorrectionProcessor() | MistakeCorrectionProcessor()
        dialogue = pipeline.process(self.predict(audio))
        return AUCServiceResult(dialogue=dialogue)

    def _submit(self, audio: Audio):
        app = auc_service_pb2.AucApp(
            appid=settings.AUC.APPID,
            token=settings.AUC.TOKEN,
            params={"asr_appid": settings.AUC.APPID},
        )
        user = auc_service_pb2.AucUser(uid=uuid.uuid1().hex)
        assert audio.meta is not None, "audio meta must not be None"
        auc_audio = auc_service_pb2.AucAudio(
            url=audio.url,
            format=audio.meta.codec,
            rate=audio.meta.sample_rate,
            bits=audio.meta.bits,
            channel=audio.meta.channels,
        )
        req = auc_service_pb2.AucSubmitRequest(app=app, user=user, audio=auc_audio)
        resp = self.stub.Submit(req, timeout=60)
        self.logger.info(f"AUC submit request id: {resp.resp.id}")
        if resp.resp.code != auc_service_pb2.AucCode.SUCCESS:
            raise ValueError(resp.resp.message)
        return resp

    def _poll_until_done(self, req_id: str):
        while True:
            time.sleep(1)
            req = auc_service_pb2.AucQueryRequest(
                id=req_id,
                appid=settings.AUC.APPID,
                token=settings.AUC.TOKEN,
                wait_final_result=True,
            )
            resp = self.stub.Query(req, timeout=60)
            if resp.resp.code == auc_service_pb2.AucCode.SUCCESS:
                return resp
            if resp.resp.code < auc_service_pb2.AucCode.ONGOING:
                self.logger.error(resp)
                return None
            self.logger.info(f"AUC query polling, resp={resp}")

    @staticmethod
    def _parse_dialogue(resp) -> Dialogue:
        if resp.resp.result_url:
            content = requests.get(resp.resp.result_url).content.decode("utf8")
            return Dialogue(**json.loads(content))
        return Dialogue(**{  # pyright: ignore[reportArgumentType,reportCallIssue]
            "id": resp.resp.id,
            "code": resp.resp.code,
            "message": resp.resp.message,
            "result_url": resp.resp.result_url,
            "text": resp.resp.text,
            "utterances": [
                {
                    "text": u.text,
                    "start_time": u.start_time,
                    "end_time": u.end_time,
                    "definite": u.definite,
                    "words": [
                        {
                            "text": w.text,
                            "start_time": w.start_time,
                            "end_time": w.end_time,
                            "blank_duration": w.blank_duration,
                            "pronounce": w.pronounce,
                        }
                        for w in u.words
                    ],
                    "additions": dict(u.additions),
                }
                for u in resp.resp.utterances
            ],
            "additions": dict(resp.resp.additions),
        })
