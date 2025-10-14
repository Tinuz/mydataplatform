from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Environment
    env: str = "development"
    
    # API
    api_title: str = "Investigations API"
    api_version: str = "1.0.0"
    api_description: str = "API for managing strafrechtelijke onderzoeken"
    
    # Database
    database_url: str = "postgresql+asyncpg://superset:superset@postgres:5432/investigations"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    
    # MinIO / S3
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio123"
    minio_bucket: str = "investigations"
    minio_use_ssl: bool = False
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5000"
    ]
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
