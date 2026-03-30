"""Configuration management for SAIA V4 backend."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App Configuration
    app_name: str = "SAIA"
    app_version: str = "4.0.0"
    debug: bool = False

    # Database Configuration
    database_url: str = "postgresql+asyncpg://saia:saia_password@localhost:5432/saia_db"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "saia_db"
    db_user: str = "saia"
    db_password: str = "saia_password"

    # JWT Configuration
    jwt_secret: str = "change-this-to-a-random-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 480

    # LLM Configuration
    llm_base_url: str = "http://localhost:8001/v1"
    llm_model: str = "llama-3.1-70b"
    llm_mock_mode: bool = True

    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: Optional[str] = None

    # Embedding Configuration
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768

    # Rate Limiting
    ingest_rate_limit: str = "60/minute"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
