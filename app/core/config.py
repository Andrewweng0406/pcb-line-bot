import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PCB Quote Bot"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Web session signing key — set a real random value via env var in production
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Shared code required to self-register a web login account
    INVITE_CODE: str = os.getenv("INVITE_CODE", "dev-invite-change-me")

    # Quote data foundation
    DEFAULT_CURRENCY: str = os.getenv("DEFAULT_CURRENCY", "")
    PRICING_VERSION: str = os.getenv("PRICING_VERSION", "v1")

    # LINE Bot
    LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET: str = os.getenv("LINE_CHANNEL_SECRET", "")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Database - PostgreSQL
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/pcb_bot"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "False").lower() == "true"
    LOGIN_RATE_LIMIT: int = 10
    REGISTER_RATE_LIMIT: int = 5
    AI_RATE_LIMIT: int = 10

    # AWS S3
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_BUCKET: str = os.getenv("AWS_S3_BUCKET", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ENABLED: bool = os.getenv("AWS_ENABLED", "False").lower() == "true"

    # Base URLs
    PUBLIC_BASE_URL: str = os.getenv(
        "PUBLIC_BASE_URL",
        "http://localhost:8000"
    )

    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    PERSISTENT_DIR: str = os.getenv("PERSISTENT_DIR", ".")
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        os.path.join(PERSISTENT_DIR, "data", "uploads"),
    )
    EXPORT_DIR: str = os.getenv(
        "EXPORT_DIR",
        os.path.join(PERSISTENT_DIR, "exports"),
    )
    LOG_DIR: str = os.getenv(
        "LOG_DIR",
        os.path.join(PERSISTENT_DIR, "logs"),
    )

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
