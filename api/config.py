import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    mongo_uri: str = ""
    mongo_db_name: str = "chronicle_rag"
    mongo_collection_name: str = "documents"
    gemini_api_key: str = ""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
