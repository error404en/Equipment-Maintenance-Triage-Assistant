from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Dev defaults — always override via environment variables in production.
    # In Docker, set DATABASE_URL=postgresql+psycopg://user:pass@db:5432/triage
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/triage"
    test_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/triage_test"

    # Comma-separated allowed origins for CORS.
    # Empty string (the default) disables CORS middleware — correct for the
    # single-origin deploy where FastAPI serves the built frontend from the
    # same container. Set this only when the frontend is on a different domain.
    allowed_origins: str = ""

    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
