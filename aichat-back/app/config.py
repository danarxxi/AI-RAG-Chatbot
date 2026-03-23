from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "HR-RAG-Chatbot"
    environment: str = "development"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    ssl_cert_path: str | None = None  # Optional: only for local dev with HTTPS
    ssl_key_path: str | None = None   # Optional: only for local dev with HTTPS

    # Admin credentials (environment variable-based authentication)
    admin_user_id: str = "admin"
    admin_password: str = "password"

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Bedrock
    bedrock_knowledge_base_id: str = ""
    work_guide_knowledge_base_id: str = ""
    bedrock_model_id: str = "us.amazon.nova-lite-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v1"

    # RAG Display Settings
    rag_display_threshold: float = 0.4  # Sources below this score are hidden from UI

    # CloudWatch
    cloudwatch_log_group: str = "/aws/my-rag-chatbot"
    cloudwatch_log_stream: str = "chatbot-logs"

    # Session
    session_expire_minutes: int = 60
    max_conversation_turns: int = 10

    # CORS
    frontend_url: str = "https://localhost:3000"

    # PostgreSQL Database (Glossary)
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "postgres"
    pg_user: str = "ai-chat"
    pg_password: str = "ai-chat"

    # Glossary Feature Settings
    # Uses same model as main chatbot by default; override in .env if needed
    glossary_model_id: str = ""  # Empty = use bedrock_model_id
    glossary_search_limit: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]