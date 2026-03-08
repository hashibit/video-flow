"""Application settings with modern Python 3.13 features."""

import threading
from pathlib import Path
from typing import Self

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Workflow Manager"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = Field(
        default="sqlite:///./workflow_manager.db",
        description="Database connection URL",
    )
    db_echo: bool = False

    # gRPC
    grpc_endpoint: str = "0.0.0.0:50051"
    grpc_enabled: bool = True

    # External API
    external_api_url: str = ""
    external_api_timeout: int = 30

    # Logging
    log_level: str = "INFO"
    enable_curl_log: bool = False
    enable_gorm_log: bool = False

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 5

    @property
    def is_dev(self) -> bool:
        """Check if running in development mode."""
        return self.debug

    @classmethod
    def from_yaml(cls, config_path: Path | None = None) -> Self:
        """Load settings from YAML file with intelligent path resolution.

        Args:
            config_path: Optional path to YAML config file

        Returns:
            Settings instance loaded from YAML or defaults
        """
        import yaml  # type: ignore[import-untyped]

        # Try to find config file if not specified
        if config_path is None:
            config_dir = Path("config")
            for name in ["config.yaml", "config-dev.yaml", "config-prod.yaml"]:
                candidate = config_dir / name
                if candidate.exists():
                    config_path = candidate
                    break

        # Return defaults if no config found
        if config_path is None or not config_path.exists():
            return cls()

        # Load and parse YAML
        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Flatten nested config using pattern matching
        flat_data: dict[str, str | int | bool] = {}

        # Process each config section
        if "db_config" in data:
            flat_data.update(cls._process_db_config(data["db_config"]))

        if "grpc_server_config" in data:
            flat_data.update(cls._process_grpc_config(data["grpc_server_config"]))

        if "external_apiconfig" in data:
            flat_data.update(cls._process_external_api_config(data["external_apiconfig"]))

        if "log_config" in data:
            flat_data.update(cls._process_log_config(data["log_config"]))

        return cls.model_validate(flat_data)

    @staticmethod
    def _process_db_config(db_cfg: dict) -> dict[str, str]:
        """Process database configuration section."""
        result = {}
        if dsn := db_cfg.get("dsn"):
            result["database_url"] = dsn
        return result

    @staticmethod
    def _process_grpc_config(grpc_cfg: dict) -> dict[str, str]:
        """Process gRPC configuration section."""
        result = {}
        if endpoint := grpc_cfg.get("endpoint"):
            result["grpc_endpoint"] = endpoint
        return result

    @staticmethod
    def _process_external_api_config(api_cfg: dict) -> dict[str, str]:
        """Process external API configuration section."""
        result = {}
        if psm := api_cfg.get("psm"):
            result["external_api_url"] = psm
        return result

    @staticmethod
    def _process_log_config(log_cfg: dict) -> dict[str, str | bool]:
        """Process logging configuration section."""
        return {
            "enable_curl_log": log_cfg.get("enable_curl_log", False),
            "enable_gorm_log": log_cfg.get("enable_gorm_log", False),
            "log_level": log_cfg.get("level", "INFO"),
        }


_settings: Settings | None = None
_settings_lock = threading.Lock()


def get_settings(config_path: Path | None = None) -> Settings:
    """Get global settings instance (singleton pattern).

    Args:
        config_path: Optional path to config file

    Returns:
        Global settings instance
    """
    global _settings
    if _settings is None:
        with _settings_lock:
            if _settings is None:
                _settings = Settings.from_yaml(config_path)
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)."""
    global _settings
    _settings = None
