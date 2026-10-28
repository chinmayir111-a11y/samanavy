"""All configuration comes from the environment (.env). Nothing secret or
personal is hard-coded here: email addresses and SMTP keys are read at
start-up."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND = Path(__file__).resolve().parent.parent   # backend/ locally, /app in the container
ROOT = BACKEND.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", BACKEND / ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://samanvay:samanvay@localhost:5432/samanvay"

    jwt_secret: str = "change-me-in-env"
    jwt_expire_minutes: int = 720

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_password: str = ""  # accepted as an alias of SMTP_PASS
    smtp_from: str = ""
    smtp_starttls: bool = True
    test_alert_email: str = ""
    # HTTPS email API (for hosts that block SMTP, such as Render's free tier). Set it and SMTP is not used.
    brevo_api_key: str = ""

    public_web_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://localhost:4180,http://127.0.0.1:5173"
    upload_dir: str = str(BACKEND / "uploads")
    max_upload_mb: int = 5

    scheduler_enabled: bool = True
    demo_mode: bool = True             # one-tap demo sign-in and the demo clock
    demo_password: str = "samanvay-demo-2026"
    app_env: str = "development"       # "production" on the host: never log links
    cookie_secure: bool = False        # true on https hosts
    cookie_samesite: str = "lax"       # the web host proxies /api, so the cookie stays first-party
    sms_provider: str = ""             # empty = not configured (see app/services/sms.py)
    login_rate_limit: int = 5
    login_rate_window_s: int = 300
    signup_rate_limit: int = 10        # sign-ups per IP per window

    def model_post_init(self, _ctx) -> None:
        for prefix in ("postgres://", "postgresql://"):
            if self.database_url.startswith(prefix):
                self.database_url = "postgresql+psycopg://" + self.database_url[len(prefix):]

    @property
    def smtp_secret(self) -> str:
        return self.smtp_pass or self.smtp_password

    @property
    def email_provider(self) -> str:
        return "brevo" if self.brevo_api_key else "smtp"

    @property
    def email_configured(self) -> bool:
        if self.brevo_api_key:
            return bool(self.smtp_from or self.smtp_user)
        return bool(self.smtp_host and self.smtp_user and self.smtp_secret)


settings = Settings()
