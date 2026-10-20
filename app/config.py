
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Remote Job Aggregator API"
    app_version: str = "0.2.0"

    database_url: str
    hiring_cafe_feed_url: str | None = None
    dover_feed_url: str | None = None
    wellfound_feed_url: str | None = None
    jobberman_feed_url: str | None = None
    jobtogether_feed_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    ingestion_interval_seconds: int = Field(default=21600, ge=60)
    ingestion_freshness_days: int = Field(default=30, ge=1, le=365)
    ingestion_retry_attempts: int = Field(default=2, ge=0, le=5)
    ingestion_retry_backoff_seconds: float = Field(
        default=0.5, gt=0, le=30
    )
    telegram_retry_attempts: int = Field(default=3, ge=1, le=5)
    telegram_retry_backoff_seconds: float = Field(
        default=2.0, gt=0, le=300
    )
    telegram_min_relevance_score: int = Field(default=50, ge=0, le=100)
    telegram_include_country_restricted: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
