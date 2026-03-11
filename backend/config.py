from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "SAIA - Secure Artificial Intelligence Auditor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://saia_user:saia_pass@localhost:5432/saia_db"

    # Security
    SECRET_KEY: str = "changeme-use-a-strong-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # AI / ML
    ANOMALY_THRESHOLD: float = 0.65       # score above this triggers an AI alert
    AI_MODE: str = "blended"              # "rules_only" | "ai_only" | "blended"

    # Log ingestion
    MAX_UPLOAD_SIZE_MB: int = 50
    SUPPORTED_LOG_FORMATS: list = ["json", "csv"]

    class Config:
        env_file = ".env"


settings = Settings()
