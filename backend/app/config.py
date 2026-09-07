from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    anthropic_api_key: str = ""
    # Haiku for the two generation-layer calls (query formulation +
    # valuation synthesis) — both are narrow, structured-output tasks over a
    # bounded evidence bundle, not open-ended reasoning, so the cheaper/
    # faster model is the right default. Override via CLAUDE_MODEL if a
    # harder case ever needs Sonnet's extra reasoning depth.
    claude_model: str = "claude-haiku-4-5-20251001"

    max_retrieval_iterations: int = 3
    max_llm_calls: int = 2

    min_comp_count: int = 5
    min_recent_comp_count: int = 3
    recent_window_months: int = 12

    confidence_threshold: float = 0.6
    review_min_comp_count: int = 3
    top_n_comps: int = 8

    cors_allow_origins: list[str] = [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://auto-val-mktanalysis.netlify.app",
    ]

    voyage_api_key: str = ""
    voyage_model: str = "voyage-3"
    voyage_embedding_dimension: int = 1024

    lancedb_uri: str = "app/data/lancedb"
    lancedb_table_name: str = "evidence_documents"
    ingestion_batch_size: int = 128

    retrieval_top_k: int = 5
    # Calibrated against a live probe (testdata/calibrate_similarity_threshold.py)
    # on voyage-3: unrelated queries scored 0.15-0.25 cosine similarity against
    # the real-estate corpus, genuinely relevant ones scored 0.40-0.66. 0.30
    # sits in that gap with margin on both sides. Re-run the calibration
    # script if the corpus composition changes meaningfully.
    retrieval_min_similarity: float = 0.30


@lru_cache
def get_settings() -> Settings:
    return Settings()
