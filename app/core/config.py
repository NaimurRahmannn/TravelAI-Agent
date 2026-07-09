from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name:str
    app_version:str
    debug:bool
    gemini_api_key:str
    gemini_model:str
    model_config=SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
settings=Settings()