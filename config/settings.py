"""Runtime settings from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REI_", env_file=".env", extra="ignore")

    # Postgres / PostGIS
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_db: str = "rei"
    pg_user: str = "rei"
    pg_password: str = "change_me"

    # External API credentials (SIRENE key is free; obtained at portail-api.insee.fr)
    insee_sirene_key: str = ""

    # LLM: manual (default), ollama, or openai
    llm_provider: str = "manual"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"
    embed_backend: str = "sentence_transformers"
    embed_model: str = "intfloat/multilingual-e5-base"
    embed_dim: int = 768
    # Optional paid backend (OPENAI_API_KEY read by the client directly)
    openai_chat_model: str = "gpt-4o"
    openai_embed_model: str = "text-embedding-3-small"

    # Runtime
    data_dir: Path = Field(default=Path("data"))   # local folder (Docker overrides to /data/rei)
    http_max_rps: float = 5.0
    log_level: str = "INFO"

    # Storage: postgres (default) or files (Parquet/GeoParquet)
    storage: str = "postgres"
    file_format: str = "parquet"
    also_csv: bool = False

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    @property
    def raw_dir(self) -> Path:
        p = self.data_dir / "raw"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
