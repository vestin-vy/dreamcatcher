"""Application settings, loaded from environment / .env (SPEC §3, §10)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Project root = directory that contains this `app/` package.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present (no error if missing — env vars still win).
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_db_url(url: str) -> str:
    """Force an explicit driver for Postgres. SQLAlchemy rejects the bare
    'postgres://' scheme that Render hands out, and we use psycopg v3, so map
    'postgres://' and driverless 'postgresql://' to 'postgresql+psycopg://'."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings:
    """Plain settings object read from the environment.

    Kept deliberately simple (no pydantic-settings dependency) — the SPEC pins a
    minimal requirements set.
    """

    def __init__(self) -> None:
        self.BASE_DIR: Path = BASE_DIR
        self.APP_DIR: Path = BASE_DIR / "app"
        self.TEMPLATES_DIR: Path = BASE_DIR / "templates"
        self.STATIC_DIR: Path = BASE_DIR / "static"
        self.UPLOADS_DIR: Path = self.STATIC_DIR / "uploads"
        self.THUMBS_DIR: Path = self.UPLOADS_DIR / "thumbs"

        # Secrets / auth
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-change-me")
        # bcrypt hash of the single admin password. Generate with:
        #   python -m app.security hash "yourpassword"
        self.ADMIN_PASSWORD_HASH: str = os.getenv("ADMIN_PASSWORD_HASH", "")
        self.ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")

        # i18n
        self.DEFAULT_LANG: str = os.getenv("DEFAULT_LANG", "el")

        # Database. Precedence: DB_URL -> Render's DATABASE_URL -> local SQLite default.
        # Dev stays on SQLite; prod sets DB_URL/DATABASE_URL to the Postgres connection.
        default_db = f"sqlite:///{(BASE_DIR / 'data.db').as_posix()}"
        raw_db = os.getenv("DB_URL") or os.getenv("DATABASE_URL") or default_db
        self.DB_URL: str = _normalize_db_url(raw_db)

        # Session
        self.SESSION_COOKIE: str = os.getenv("SESSION_COOKIE", "dc_session")
        # Session lifetime in seconds (default 12h).
        self.SESSION_MAX_AGE: int = int(os.getenv("SESSION_MAX_AGE", str(12 * 3600)))
        # Send the session cookie only over HTTPS. Default: on in production
        # (DEBUG off), off in local dev so http://127.0.0.1 still works.
        self.DEBUG: bool = _as_bool(os.getenv("DEBUG"), default=False)
        self.SESSION_HTTPS_ONLY: bool = _as_bool(
            os.getenv("SESSION_HTTPS_ONLY"), default=not self.DEBUG
        )
        # Seed demo data on startup when the DB is empty (handy on hosts with an
        # ephemeral filesystem like Render's free tier). Off by default locally.
        self.AUTO_SEED: bool = _as_bool(os.getenv("AUTO_SEED"), default=False)
        # One-shot maintenance switch: when true, DROP + recreate + reseed the whole
        # schema on startup (regenerates demo data, e.g. to backfill DB-stored image
        # bytes). DESTRUCTIVE — set it for a single deploy, then remove it. Off by
        # default so a normal restart never wipes data.
        self.FORCE_RESEED: bool = _as_bool(os.getenv("FORCE_RESEED"), default=False)
        # One-shot catalog cleanup: on startup delete ALL products/categories and
        # demo orders (site settings stay). Safe to leave enabled - it runs only
        # until the `catalog_cleared` marker appears in the settings table.
        # Use together with AUTO_SEED=false.
        self.CLEAR_CATALOG: bool = _as_bool(os.getenv("CLEAR_CATALOG"), default=False)

        # Uploads
        self.MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
        self.IMAGE_MAX_SIDE: int = int(os.getenv("IMAGE_MAX_SIDE", "1600"))
        self.THUMB_MAX_SIDE: int = int(os.getenv("THUMB_MAX_SIDE", "400"))

        # --- Payments: Viva (SPEC-BILLING §3) -------------------------------
        # Master switch: when false the checkout pay button renders disabled and
        # POST /checkout refuses to create orders (pre-Viva-contract state).
        # Browsing and the cart keep working; flip to true once Viva is signed.
        self.PAYMENTS_ENABLED: bool = _as_bool(
            os.getenv("PAYMENTS_ENABLED"), default=True
        )
        # VIVA_MODE: "demo" (no keys needed; internal stub flow) or "live".
        self.VIVA_MODE: str = os.getenv("VIVA_MODE", "demo").strip().lower()
        self.VIVA_MERCHANT_ID: str = os.getenv("VIVA_MERCHANT_ID", "")
        self.VIVA_API_KEY: str = os.getenv("VIVA_API_KEY", "")
        self.VIVA_CLIENT_ID: str = os.getenv("VIVA_CLIENT_ID", "")
        self.VIVA_CLIENT_SECRET: str = os.getenv("VIVA_CLIENT_SECRET", "")
        self.VIVA_SOURCE_CODE: str = os.getenv("VIVA_SOURCE_CODE", "")
        self.VIVA_WEBHOOK_SECRET: str = os.getenv("VIVA_WEBHOOK_SECRET", "")
        # Public base URL used to build redirect/callback URLs (live mode).
        self.PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

        # --- Email notifications (SPEC-BILLING §6; optional, off by default) -
        self.NOTIFY_ENABLED: bool = _as_bool(os.getenv("NOTIFY_ENABLED"), default=False)
        self.SMTP_HOST: str = os.getenv("SMTP_HOST", "")
        self.SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USER: str = os.getenv("SMTP_USER", "")
        self.SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    def ensure_dirs(self) -> None:
        """Create runtime directories that must exist before serving."""
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
        (self.STATIC_DIR / "img").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
