"""Configuration management using pydantic-settings"""

from typing import List
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application
    app_name: str = Field(default="YuhHearDem")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/yuhheardem"
    )
    database_pool_size: int = Field(default=20)
    database_max_overflow: int = Field(default=10)

    # Google Gemini API
    google_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.0-flash-exp")
    gemini_temperature: float = Field(default=0.3)

    # Vector Embeddings
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    embedding_dimensions: int = Field(default=384)

    # spaCy
    spacy_model: str = Field(default="en_core_web_trf")

    # Fuzzy Matching
    fuzzy_match_threshold: int = Field(default=85)

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )

    # Cache
    cache_ttl_seconds: int = Field(default=3600)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
