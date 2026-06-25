from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    All values can be overridden via environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "GenAI RAG Backend"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # ── Database ─────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "rag_user"
    POSTGRES_PASSWORD: str = "rag_password"
    POSTGRES_DB: str = "rag_db"
    DATABASE_URL: str = (
        "postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_db"
    )
    # Sync URL for Alembic (uses psycopg2, not asyncpg)
    SYNC_DATABASE_URL: str = (
        "postgresql+psycopg2://rag_user:rag_password@localhost:5432/rag_db"
    )

    # ── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key — required for embeddings and chat")
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536
    OPENAI_MAX_TOKENS: int = 2048
    OPENAI_TEMPERATURE: float = 0.0

    # ── Ollama (local LLM — free alternative to OpenAI) ──────────────────────
    USE_OLLAMA: bool = False
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"  # host machine from Docker
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"            # pull: ollama pull nomic-embed-text
    OLLAMA_CHAT_MODEL: str = "llama3.2"                         # pull: ollama pull llama3.2
    OLLAMA_EMBEDDING_DIMENSIONS: int = 768                      # nomic-embed-text = 768 dims

    @property
    def embedding_dimensions(self) -> int:
        return self.OLLAMA_EMBEDDING_DIMENSIONS if self.USE_OLLAMA else self.OPENAI_EMBEDDING_DIMENSIONS

    @property
    def chat_model(self) -> str:
        return self.OLLAMA_CHAT_MODEL if self.USE_OLLAMA else self.OPENAI_CHAT_MODEL


    # ── RAG ──────────────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 512          # tokens per chunk
    CHUNK_OVERLAP: int = 50        # token overlap between chunks
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.7

    # ── Security / JWT ────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-must-be-32-chars-min"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # ── Redis Cache ───────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TTL_EMBEDDING: int = 86400    # 24 h — embeddings rarely change
    REDIS_TTL_RAG_QUERY: int = 3600     # 1 h  — query → answer
    REDIS_TTL_DOCUMENT_LIST: int = 300  # 5 min — document listing
    CACHE_ENABLED: bool = True

    # ── File Upload ───────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "pdf,docx,txt"

    # ── Monitoring ────────────────────────────────────────────────────────────
    ENABLE_METRICS: bool = True
    METRICS_PATH: str = "/metrics"

    # ── Dev / Testing ─────────────────────────────────────────────────────────
    MOCK_EMBEDDINGS: bool = False   # Set true to skip OpenAI and use random vectors

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance (singleton)."""
    return Settings()


settings = get_settings()
