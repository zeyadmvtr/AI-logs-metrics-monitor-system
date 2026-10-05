from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelemetrySettings(BaseSettings):
    """Configuration for Prometheus & Logging telemetry worker."""

    # Prometheus configuration
    PROMETHEUS_URL: str = "http://localhost:9090"
    PROMETHEUS_TIMEOUT_SECONDS: int = 10

    # Loki log store configuration
    LOKI_URL: str = "http://localhost:3100"
    LOKI_TIMEOUT_SECONDS: int = 10

    # Target Kubernetes deployment
    K8S_NAMESPACE: str = "dev"
    APP_NAME: str = "aiops-backend"

    # Ingestion worker tuning
    POLL_INTERVAL_SECONDS: int = 10
    LOOKBACK_MINUTES: int = 5
    SLIDING_WINDOW_SAMPLES: int = 100

    # Output storage
    SNAPSHOT_DIR: str = "data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TELEMETRY_",
        extra="ignore"
    )


@lru_cache()
def get_telemetry_settings() -> TelemetrySettings:
    return TelemetrySettings()
