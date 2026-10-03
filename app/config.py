import os
import sys
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None
    test_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/triage_test"
    allowed_origins: str = ""
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_db(self) -> Self:
        # Skip validation during pytest to allow tests to use test_database_url or mocked db
        if "PYTEST_CURRENT_TEST" in os.environ:
            if not self.database_url:
                self.database_url = "sqlite:///:memory:"
            return self

        if not self.database_url:
            print("ERROR: DATABASE_URL is missing in configuration.", file=sys.stderr)
            sys.exit(1)
        if not (self.database_url.startswith("postgres") or self.database_url.startswith("sqlite")):
            print(f"ERROR: DATABASE_URL is malformed. Must be postgresql or sqlite URL. Got: {self.database_url}", file=sys.stderr)
            sys.exit(1)
        return self

settings = Settings()
