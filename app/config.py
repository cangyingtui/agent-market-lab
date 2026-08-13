from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Product Market Simulation Platform", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    enable_debug_api: bool = Field(default=True, alias="ENABLE_DEBUG_API")

    database_url: str = Field(alias="DATABASE_URL")
    db_pool_pre_ping: bool = Field(default=True, alias="DB_POOL_PRE_PING")
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    redis_url: str = Field(default="redis://:123456@127.0.0.1:6379/0", alias="REDIS_URL")
    redis_task_queue: str = Field(default="simulation:queue", alias="REDIS_TASK_QUEUE")
    redis_pro_queue: str = Field(default="simulation:queue:pro", alias="REDIS_PRO_QUEUE")
    redis_basic_queue: str = Field(default="simulation:queue:basic", alias="REDIS_BASIC_QUEUE")
    redis_export_queue: str = Field(default="simulation:queue:exports", alias="REDIS_EXPORT_QUEUE")
    redis_progress_expire_seconds: int = Field(default=7200, alias="REDIS_PROGRESS_EXPIRE_SECONDS")
    redis_heartbeat_ttl_seconds: int = Field(default=15, alias="REDIS_HEARTBEAT_TTL_SECONDS")
    heavy_resource_lock_ttl_seconds: int = Field(default=7200, alias="HEAVY_RESOURCE_LOCK_TTL_SECONDS")
    pdf_export_lock_ttl_seconds: int = Field(default=900, alias="PDF_EXPORT_LOCK_TTL_SECONDS")

    custom_competitor_backfill_enabled: bool = Field(default=True, alias="CUSTOM_COMPETITOR_BACKFILL_ENABLED")
    custom_competitor_brand_similarity_threshold: float = Field(
        default=0.85,
        alias="CUSTOM_COMPETITOR_BRAND_SIMILARITY_THRESHOLD",
    )
    custom_competitor_price_rel_tolerance: float = Field(
        default=0.15,
        alias="CUSTOM_COMPETITOR_PRICE_REL_TOLERANCE",
    )
    custom_competitor_price_abs_tolerance_cny: float = Field(
        default=50.0,
        alias="CUSTOM_COMPETITOR_PRICE_ABS_TOLERANCE_CNY",
    )
    custom_competitor_backfill_stale_seconds: int = Field(
        default=900,
        alias="CUSTOM_COMPETITOR_BACKFILL_STALE_SECONDS",
    )
    custom_competitor_backfill_max_retries: int = Field(
        default=3,
        alias="CUSTOM_COMPETITOR_BACKFILL_MAX_RETRIES",
    )
    custom_competitor_backfill_poll_seconds: int = Field(
        default=60,
        alias="CUSTOM_COMPETITOR_BACKFILL_POLL_SECONDS",
    )

    jwt_secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    llm_provider: str = Field(default="deepseek", alias="LLM_PROVIDER")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_api_base: str = Field(default="https://api.deepseek.com/v1", alias="LLM_API_BASE")
    llm_model: str = Field(default="deepseek-chat", alias="LLM_MODEL")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    llm_max_retry: int = Field(default=2, alias="LLM_MAX_RETRY")

    enable_rag: bool = Field(default=True, alias="ENABLE_RAG")
    rag_mode: str = Field(default="faiss_ann", alias="RAG_MODE")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    faiss_index_path: str = Field(default="knowledge_model/knowledge_base/faiss_index", alias="FAISS_INDEX_PATH")
    faiss_metadata_path: str = Field(default="knowledge_model/knowledge_base/faiss_metadata.pkl", alias="FAISS_METADATA_PATH")

    embedding_provider: str = Field(default="openai_compatible", alias="EMBEDDING_PROVIDER")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_api_base: str = Field(default="", alias="EMBEDDING_API_BASE")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=384, alias="EMBEDDING_DIM")
    embedding_timeout_seconds: int = Field(default=30, alias="EMBEDDING_TIMEOUT_SECONDS")
    embedding_use_dimensions_param: bool = Field(default=True, alias="EMBEDDING_USE_DIMENSIONS_PARAM")

    enable_data_enrichment: bool = Field(default=False, alias="ENABLE_DATA_ENRICHMENT")
    enrichment_provider: str = Field(default="tavily", alias="ENRICHMENT_PROVIDER")
    enrichment_api_key: str = Field(default="", alias="ENRICHMENT_API_KEY")
    enrichment_api_base: str = Field(default="https://api.tavily.com/search", alias="ENRICHMENT_API_BASE")
    enrichment_cache_ttl_hours: int = Field(default=72, alias="ENRICHMENT_CACHE_TTL_HOURS")
    enrichment_max_items_per_run: int = Field(default=3, alias="ENRICHMENT_MAX_ITEMS_PER_RUN")

    public_evidence_enabled: bool = Field(default=False, alias="PUBLIC_EVIDENCE_ENABLED")
    public_evidence_provider: str = Field(default="bailian", alias="PUBLIC_EVIDENCE_PROVIDER")
    public_evidence_api_key: str = Field(default="", alias="PUBLIC_EVIDENCE_API_KEY")
    public_evidence_api_base: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="PUBLIC_EVIDENCE_API_BASE",
    )
    public_evidence_model: str = Field(default="qwen-plus", alias="PUBLIC_EVIDENCE_MODEL")
    public_evidence_timeout_seconds: int = Field(default=12, alias="PUBLIC_EVIDENCE_TIMEOUT_SECONDS")
    public_evidence_total_timeout_seconds: int = Field(default=30, alias="PUBLIC_EVIDENCE_TOTAL_TIMEOUT_SECONDS")
    public_evidence_cache_ttl_hours: int = Field(default=72, alias="PUBLIC_EVIDENCE_CACHE_TTL_HOURS")
    public_evidence_basic_query_limit: int = Field(default=2, alias="PUBLIC_EVIDENCE_BASIC_QUERY_LIMIT")
    public_evidence_pro_query_limit: int = Field(default=6, alias="PUBLIC_EVIDENCE_PRO_QUERY_LIMIT")

    price_enrichment_enabled: bool = Field(default=False, alias="PRICE_ENRICHMENT_ENABLED")
    price_enrichment_write_master: bool = Field(default=False, alias="PRICE_ENRICHMENT_WRITE_MASTER")
    price_enrichment_api_key: str = Field(default="", alias="PRICE_ENRICHMENT_API_KEY")
    price_enrichment_api_base: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="PRICE_ENRICHMENT_API_BASE",
    )
    price_enrichment_model: str = Field(default="qwen-plus", alias="PRICE_ENRICHMENT_MODEL")
    price_enrichment_max_items_per_request: int = Field(default=4, alias="PRICE_ENRICHMENT_MAX_ITEMS_PER_REQUEST")
    price_enrichment_min_confidence: float = Field(default=0.65, alias="PRICE_ENRICHMENT_MIN_CONFIDENCE")
    price_enrichment_timeout_seconds: int = Field(default=20, alias="PRICE_ENRICHMENT_TIMEOUT_SECONDS")

    enable_distill_check: bool = Field(default=False, alias="ENABLE_DISTILL_CHECK")
    distill_model_path: str = Field(default="knowledge_model/sentiment", alias="DISTILL_MODEL_PATH")
    distill_api_base: str = Field(default="", alias="DISTILL_API_BASE")
    distill_api_key: str = Field(default="", alias="DISTILL_API_KEY")
    distill_timeout_seconds: int = Field(default=10, alias="DISTILL_TIMEOUT_SECONDS")
    distill_batch_size: int = Field(default=16, alias="DISTILL_BATCH_SIZE")
    distill_consistency_path: str = Field(default="/v1/consistency-check", alias="DISTILL_CONSISTENCY_PATH")
    distill_model_version: str = Field(default="sentiment_student_v2_balanced600", alias="DISTILL_MODEL_VERSION")
    student_base_model: str = Field(default="bert-base-chinese", alias="STUDENT_BASE_MODEL")

    social_network_enabled: bool = Field(default=True, alias="SOCIAL_NETWORK_ENABLED")
    social_network_k: int = Field(default=4, alias="SOCIAL_NETWORK_K")
    social_network_rewire_probability: float = Field(default=0.3, alias="SOCIAL_NETWORK_REWIRE_PROBABILITY")
    social_network_max_rounds: int = Field(default=3, alias="SOCIAL_NETWORK_MAX_ROUNDS")
    social_network_convergence_threshold: float = Field(default=0.02, alias="SOCIAL_NETWORK_CONVERGENCE_THRESHOLD")
    social_trust_sensitivity_min: float = Field(default=0.5, alias="SOCIAL_TRUST_SENSITIVITY_MIN")
    social_trust_sensitivity_max: float = Field(default=1.0, alias="SOCIAL_TRUST_SENSITIVITY_MAX")
    social_representative_ratio: float = Field(default=0.03, alias="SOCIAL_REPRESENTATIVE_RATIO")
    social_representative_min: int = Field(default=60, alias="SOCIAL_REPRESENTATIVE_MIN")
    social_representative_max: int = Field(default=300, alias="SOCIAL_REPRESENTATIVE_MAX")
    social_llm_sample_size: int = Field(default=12, alias="SOCIAL_LLM_SAMPLE_SIZE")

    task_timeout_seconds: int = Field(default=7200, alias="TASK_TIMEOUT_SECONDS")
    max_retry_times: int = Field(default=2, alias="MAX_RETRY_TIMES")
    heartbeat_interval_seconds: int = Field(default=5, alias="HEARTBEAT_INTERVAL_SECONDS")
    basic_report_min_seconds: int = Field(default=600, alias="BASIC_REPORT_MIN_SECONDS")
    basic_report_max_seconds: int = Field(default=1800, alias="BASIC_REPORT_MAX_SECONDS")
    pro_report_min_seconds: int = Field(default=900, alias="PRO_REPORT_MIN_SECONDS")
    pro_report_max_seconds: int = Field(default=3600, alias="PRO_REPORT_MAX_SECONDS")
    basic_task_estimate_seconds: int = Field(default=1200, alias="BASIC_TASK_ESTIMATE_SECONDS")
    pro_task_estimate_seconds: int = Field(default=2100, alias="PRO_TASK_ESTIMATE_SECONDS")
    share_token_salt: str = Field(default="change-me", alias="SHARE_TOKEN_SALT")
    export_dir: str = Field(default="logs/exports", alias="EXPORT_DIR")
    public_base_url: str = Field(default="http://127.0.0.1:8000", alias="PUBLIC_BASE_URL")
    frontend_base_url: str = Field(default="http://127.0.0.1:5173", alias="FRONTEND_BASE_URL")
    playwright_browsers_path: str = Field(default=".playwright-browsers", alias="PLAYWRIGHT_BROWSERS_PATH")

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return ROOT_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
