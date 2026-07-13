from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "TravelAI Agent"
    app_version: str = "1.0.0"
    debug: bool = True
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    amadeus_api_key: str | None = None
    amadeus_api_secret: str | None = None
    amadeus_base_url: str = "https://test.api.amadeus.com"
    aviationstack_api_key: str | None = None
    aviationstack_base_url: str = "http://api.aviationstack.com/v1"
    geoapify_api_key: str | None = None

    # Database (persistence layer)
    database_url: str = "sqlite:///./travel_ai.db"

    # RAG / knowledge base
    google_api_key: str | None = None
    google_embedding_model: str = "models/embedding-001"
    knowledge_dir: str = "data/knowledge"
    vectorstore_path: str = "app/vectorstore/index.json"
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100

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