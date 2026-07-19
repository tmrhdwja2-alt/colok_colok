"""Runtime configuration loaded from environment variables."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_mode: str = os.getenv("APP_MODE", "demo").lower()
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    model_path: str = os.getenv(
        "MODEL_PATH", "models/best_model_xgboost_final.pkl"
    )
    no_call_threshold: float = float(os.getenv("NO_CALL_THRESHOLD", "0.60"))


settings = Settings()
