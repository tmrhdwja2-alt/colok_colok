"""Runtime configuration loaded from environment variables."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_mode: str = os.getenv("APP_MODE", "demo").lower()
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
    gcp_region: str = os.getenv("GCP_REGION", "us-central1")
    gcp_endpoint_id: str = os.getenv("GCP_ENDPOINT_ID", "")
    model_schema_path: str = os.getenv("MODEL_SCHEMA_PATH", "app/model_schema.json")
    gcp_service_account_json_base64: str = os.getenv(
        "GCP_SERVICE_ACCOUNT_JSON_BASE64", ""
    )

    @property
    def vertex_configured(self) -> bool:
        return bool(self.gcp_project_id and self.gcp_endpoint_id)


settings = Settings()
