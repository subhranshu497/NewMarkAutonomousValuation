from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"

    max_retrieval_iterations: int = 3
    max_llm_calls: int = 2

    min_comp_count: int = 5
    min_recent_comp_count: int = 3
    recent_window_months: int = 12

    confidence_threshold: float = 0.6
    review_min_comp_count: int = 3

    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
