from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    ANTHROPIC_API_KEY: str = ""
    # Hard cap on every Claude SDK call so a single slow upstream request
    # cannot pin a worker thread (SDK default is 600s with 2 retries).
    AI_REQUEST_TIMEOUT_SECONDS: float = 120.0
    AI_MAX_RETRIES: int = 2

    STORAGE_PATH: str = "./storage"
    ENVIRONMENT: str = "development"

    CORS_ORIGINS: str = '["http://localhost:3000"]'

    # Default admin credentials (used if users.json is empty)
    DEFAULT_ADMIN_EMAIL: str = "admin@br-food.com"
    DEFAULT_ADMIN_PASSWORD: str = "changeme123"

    # Confidence threshold for AI extraction
    EXTRACTION_CONFIDENCE_THRESHOLD: float = 0.90

    # Tolerances
    CURRENCY_TOLERANCE: float = 0.005
    WEIGHT_AVG_TOLERANCE_PCT: float = 0.15
    PRICE_CHANGE_NO_CHANGE_THRESHOLD: float = 0.005

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
