import pickle

from workflow_worker.domain.entities.audio import Audio
from workflow_worker.domain.entities.service.auc import AUCServiceResult
from workflow_worker.shared.utils.env import get_env
from workflow_worker.infrastructure.media_stream.s3_hook import S3Hook


class DataLoader(object):
    def __init__(self):
        self.cache_audio_object = {}

    def get_auc_service_result(self, task_id: int) -> AUCServiceResult | None:
        try:
            s3 = S3Hook()
            bucket = get_env().s3_bucket
            s3_obj = s3.get_key(f"task_{task_id}/auc_service_result.pkl", bucket)
            auc_service_result: AUCServiceResult = pickle.loads(s3_obj)
            return auc_service_result
        except Exception:
            import traceback

            from workflow_worker.applications.workflows.task_context import task_context_store
            logger = task_context_store.get_task_logger(task_id)
            logger.error("failed to load auc_service_result from s3, tb: ")
            logger.error(traceback.format_exc())
            return None

    def set_auc_service_result(self, task_id: int, auc_service_result: AUCServiceResult):
        try:
            s3 = S3Hook()
            bucket = get_env().s3_bucket
            data = pickle.dumps(auc_service_result)
            s3.load_bytes(data, f"task_{task_id}/auc_service_result.pkl", bucket, replace=True)
        except Exception:
            import traceback

            from workflow_worker.applications.workflows.task_context import task_context_store
            logger = task_context_store.get_task_logger(task_id)
            logger.error("failed to set auc_service_result to s3, tb: ")
            logger.error(traceback.format_exc())
            return

    def set_audio_object(self, task_uuid: int, audio: Audio):
        self.cache_audio_object[task_uuid] = audio

    def get_audio_object(self, task_uuid: int) -> Audio | None:
        return self.cache_audio_object.get(task_uuid, None)
