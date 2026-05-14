from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    anthropic_api_key: str = ""

    meta_page_access_token: str = ""
    meta_page_id: str = ""
    meta_instagram_account_id: str = ""

    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""

    linkedin_access_token: str = ""
    linkedin_org_id: str = ""

    base_url: str = "http://localhost:8000"

    database_url: str = "sqlite+aiosqlite:///./socialautopost.db"
    secret_key: str = "change-this-to-a-random-string"
    admin_username: str = "admin"
    admin_password: str = "changeme"
    posting_days: str = "tuesday,friday"
    posting_time: str = "10:00"
    timezone: str = "America/Chicago"

    # Email notifications (Resend HTTP API)
    resend_api_key: str = ""
    smtp_from: str = ""
    notification_email: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def async_database_url(self) -> str:
        """Convert DATABASE_URL to async-compatible format.
        Railway gives postgresql://, SQLAlchemy async needs postgresql+asyncpg://
        Local dev uses sqlite+aiosqlite:// which passes through unchanged.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
