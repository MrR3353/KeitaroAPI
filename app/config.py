from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    keitaro_base_url: str
    keitaro_api_key: str

    database_url: str = "sqlite:///./app.db"

    keitaro_default_domain_id: int | None = None
    google_redirect_url: str = "https://www.google.com"
    http_timeout_seconds: float = 5.0

    @field_validator("keitaro_default_domain_id", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
