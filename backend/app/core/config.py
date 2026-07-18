from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env relative to this file so the server can be started from any directory
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    FIREBASE_PROJECT_ID: str = ""
    # Service-account JSON (full key file contents) for Firebase Admin REST calls —
    # needed to purge under-13 Firebase Auth records created before the age gate
    # and to create managed child credentials from the Family dashboard.
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""
    # Under-13 managed accounts stay off until the jurisdiction's verifiable-consent
    # tier (plan Phase 2) is live; 13+ children can be parent-created regardless.
    ENABLE_MANAGED_CHILDREN: bool = False
    MAX_CHILDREN_PER_PARENT: int = 5
    # Supabase Storage — hero images bucket. Service-role key is required for
    # uploads (bypasses RLS); leave empty to disable image generation entirely.
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Postgres — prefer DATABASE_URL (Supabase pooler); fallback to individual params
    DATABASE_URL: str = ""
    DB_HOST: str = ""
    DB_PORT: int = 5432
    DB_NAME: str = "postgres"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""

    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:3000"

    GEO_DEFAULT_COUNTRY: str = "IN"

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Notification channels — Brevo HTTP API (preferred) or SMTP fallback
    BREVO_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_LOGIN: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@ecalt.app"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"
    NOTIFICATION_SIGNING_SECRET: str = ""
    # Set to false to disable a channel globally (overrides per-user prefs)
    NOTIFICATIONS_EMAIL_ENABLED: bool = True
    NOTIFICATIONS_WHATSAPP_ENABLED: bool = True
    # Exactly ONE instance may run the notification scheduler. A second
    # instance (e.g. local dev against the shared DB) races the daily-cap
    # check and double-sends — keep this false everywhere but production.
    SCHEDULER_ENABLED: bool = True

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


settings = Settings()
