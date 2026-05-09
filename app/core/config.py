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

    database_url: str = "sqlite+aiosqlite:///./socialautopost.db"
    secret_key: str = "change-this-to-a-random-string"
    posting_days: str = "tuesday,friday"
    posting_time: str = "10:00"
    timezone: str = "America/Chicago"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
