"""
Central config, loaded from environment / .env. Nothing else in the codebase
should read os.environ directly — that keeps config swaps (e.g. desktop SQLite
path -> web Postgres URL) to this one file.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path.home() / ".stockapp"
APP_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="STOCKAPP_")

    database_url: str = f"sqlite:///{APP_DIR / 'stockapp.db'}"

    # Alerts
    price_move_alert_pct: float = 5.0  # trigger if price moves this % in a day
    alert_check_interval_minutes: int = 30

    # Email notifications
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    alert_email_to: str = ""
    alert_email_from: str = ""

    # Scraping
    request_timeout_seconds: int = 15
    scraper_user_agent: str = "stockapp/0.1 (personal use)"


settings = Settings()
