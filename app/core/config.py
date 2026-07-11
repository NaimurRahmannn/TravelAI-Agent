from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str
    app_version: str
    debug: bool
    groq_api_key: str
    groq_model: str
    amadeus_api_key: str | None = None
    amadeus_api_secret: str | None = None
    amadeus_base_url: str = "https://test.api.amadeus.com"
    aviationstack_api_key: str | None = None
    aviationstack_base_url: str = "http://api.aviationstack.com/v1"
    geoapify_api_key: str | None = None
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True

        return value
settings = Settings()
