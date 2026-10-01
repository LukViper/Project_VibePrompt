"""Runtime configuration. Secrets come from the environment, never the client."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VibePrompt"
    database_url: str = "postgresql+psycopg://vibeprompt:vibeprompt@localhost:5432/vibeprompt"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_fast_model: str = "gemini-2.0-flash"
    gemini_reasoning_model: str = "gemini-2.0-flash"
    gemini_research_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    llm_provider: str = "auto"  # auto | gemini | openai
    environment: str = "development"  # development | production
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    nli_model: str = "typeform/distilbert-base-uncased-mnli"
    embedding_dimension: int = 384
    cors_origins: str = "*"
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    auto_create_tables: bool = True
    enable_multi_perspective: bool = False
    auth_secret: str = "dev-insecure-auth-secret-change-me"
    auth_token_ttl_hours: float = 72.0
    artifact_dir: str = str(BACKEND_ROOT / "app" / "nlp" / "artifacts")
    dataset_dir: str = str(REPO_ROOT / "datasets")

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def llm_configured(self) -> bool:
        return self.gemini_configured or self.openai_configured

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def auth_secret_is_insecure(self) -> bool:
        secret = self.auth_secret.strip()
        return (not secret) or secret.startswith("dev-insecure") or secret == "change-me-in-production"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
