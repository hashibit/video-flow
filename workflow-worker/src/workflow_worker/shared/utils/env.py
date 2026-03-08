
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Env(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKFLOW_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    sd_cache_expired_seconds: int = 15

    # Service hosts (WORKFLOW_ prefix automatically applied)
    workflow_manager_host: str = "workflow-manager-grpc.default.svc.cluster.local:80"
    media_manager_host: str = "media-manager.default.svc.cluster.local:80"
    media_worker_host: str = ""
    media_data_source: str = "media_manager"

    # S3 related (no WORKFLOW_ prefix - use validation_alias)
    s3client_name: str = Field(default="", validation_alias="s3client_name")
    s3_ak: str = Field(default="admin", validation_alias="MINIO_ACCESS_KEY")
    s3_sk: str = Field(default="admin", validation_alias="MINIO_SECRET_KEY")
    s3_bucket: str = Field(default="workflow", validation_alias="WORKFLOW_JOB_BUCKET")
    s3_path_style: str = Field(default="false", validation_alias="MINIO_S3_FORCE_PATH_STYLE")
    s3_host: str = Field(default="10.78.118.108:30039", validation_alias="MINIO_SERVICE_ENDPOINT")

    # Other settings (no WORKFLOW_ prefix)
    is_debug: str = Field(default="false", validation_alias="IS_DEBUG")
    is_download_local: str = Field(default="", validation_alias="IS_DOWNLOAD_LOCAL")
    is_use_new_algorithm: str = Field(default="", validation_alias="IS_USE_NEW_ALGORITHM")

    def get_sd_from_cache(self, target: str) -> str | None:
        """
        Resolve service target to ip:port.
        Supports:
        - tcp://ip:port → ip:port
        - k8s service name (svc.cluster.local) → direct use
        - ip:port → ip:port
        """
        # Direct TCP
        if target.startswith("tcp://"):
            return target[6:]

        # K8s service name format
        if ".svc.cluster.local" in target:
            return target

        # Direct ip:port
        return target

    def get_media_manager_host(self):
        resolved = self.get_sd_from_cache(self.media_manager_host)
        return resolved if resolved else self.media_manager_host

    def get_media_worker_host(self):
        resolved = self.get_sd_from_cache(self.media_worker_host)
        return resolved if resolved else self.media_worker_host

    def get_workflow_manager_host(self):
        resolved = self.get_sd_from_cache(self.workflow_manager_host)
        return resolved if resolved else self.workflow_manager_host

    # TODO: The video cloud private platform injects MINIO_SERVICE_ENDPOINT into pods with an http:// prefix.
    # This needs to be handled here by removing the prefix. This logic can be removed after the platform
    # is fixed to inject endpoints without the http:// prefix.
    def get_s3_host(self):
        if self.s3_host.startswith("http://"):
            # print("s3_host has http:// prefix, remove it.")
            self.s3_host = self.s3_host[len("http://") :]
        elif self.s3_host.startswith("https://"):
            # print("s3_host has https:// prefix, remove it.")
            self.s3_host = self.s3_host[len("https://") :]
        return self.s3_host


# Global instance - automatically reads environment variables
global_env = Env()


def get_env() -> Env:
    return global_env


def resolve_service_target(target: str) -> str:
    """Resolve service target (k8s service, tcp://, or direct) to ip:port."""
    env = get_env()
    cached = env.get_sd_from_cache(target)
    return cached if cached else target

