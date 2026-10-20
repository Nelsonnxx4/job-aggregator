
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
