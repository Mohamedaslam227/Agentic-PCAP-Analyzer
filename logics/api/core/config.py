from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import Field
 
 
class Settings(BaseSettings):
    # ── API ───────────────────────────────────────────────────────────────────
    app_name: str = "PCAP Analyzer API"
    app_version: str = "1.0.0"
    max_request_size: int = 500 * 1024 * 1024  # 500 MB
 
    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit: int = 60          # requests per minute
    rate_limit_window: int = 60   # seconds
 
    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = "@redis_password@"
    redis_decode_responses: bool = True
    redis_max_connections: int = 10
    redis_socket_timeout: int = 5
    redis_connect_timeout: int = 5
    redis_retry_on_timeout: bool = True
 
    # ── Auth / JWT ───────────────────────────────────────────────────────────
    secret_key: str = "changeme-use-a-real-secret-in-env"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440    # 24 h
    refresh_token_expire_minutes: int = 10080  # 7 days

    # ── Storage ───────────────────────────────────────────────────────────────
    upload_dir: str = "C:\\Users\\Mohamed Aslam\\Learnings\\PCAP ANALYZER\\code\\logics\\data\\pcaps"
    temp_dir: str = "C:\\Users\\Mohamed Aslam\\Learnings\\PCAP ANALYZER\\code\\logics\\data\\temp"
 
    # ── TShark / processing ───────────────────────────────────────────────────
    tshark_path: str = "C:\\Program Files\\Wireshark\\tshark.exe"
    capinfos_path: str = "C:\\Program Files\\Wireshark\\capinfos.exe"
    chunk_size: int = 50_000         # packets per extraction chunk
    database_url: str = Field(...)

    # ── LLM / OpenAI ─────────────────────────────────────────────────────────
    # Primary backend: OpenAI (used when PCAP_OPENAI_API_KEY is set)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 2000

    # ── LLM / Internal fallback ───────────────────────────────────────────────
    # Used automatically when openai_api_key is NOT set.
    # Bifrost proxy — OpenAI-compatible, model must be "chat" or "code".
    internal_llm_base_url: Optional[str] = "https://llm.ccc.embedur.com/v1"
    internal_llm_model: str = "chat"      # Bifrost accepts: "chat" or "code"
    internal_llm_api_key: str = "dummy"   # placeholder — server ignores auth

    # ── Embedding microservice ────────────────────────────────────────────────
    # The chat service always POSTs embeddings to this URL.
    # Default targets the standalone embedding server (server.py / docker).
    # Override with PCAP_EMBEDDING_SERVICE_URL in .env for docker networking.
    # Example: http://embedding-svc:8001  (docker-compose service name)
    embedding_service_url: Optional[str] = "http://localhost:8001"

    # ── Chat settings ─────────────────────────────────────────────────────────
    chat_cache_ttl: int = 300          # seconds — Redis answer cache TTL
    chat_history_turns: int = 6        # prior conversation turns to include

    # ── Session data retention in Redis ──────────────────────────────────────
    # Applied to session:* keys (stats + related working keys) to prevent
    # unbounded growth with many concurrent users.
    session_data_ttl_seconds: int = 7 * 24 * 60 * 60
 
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PCAP_",case_sensitive=False)
 
 
settings = Settings()