# backend/config.py
"""
University DataShield – Production Configuration Management (Phase 11).
Centralized, validated environment configuration with fail-safe defaults for development
and strict security requirements for production deployment.
"""

from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Locate root directory containing .env
_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
_ENV_FILE = _REPO_ROOT / ".env"

if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE)
else:
    load_dotenv()


class Settings:
    # ── General Application Settings ──────────────────────────────────────────
    APP_NAME: str = "University DataShield"
    APP_VERSION: str = "11.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower().strip()
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # ── API & Host ────────────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174,http://localhost:4173,http://127.0.0.1:4173",
        ).split(",")
        if origin.strip()
    ]

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{_REPO_ROOT / 'data' / 'datashield.db'}",
    )

    # ── Authentication & Identity (OAuth2 / OIDC) ─────────────────────────────
    # When false, allows developer demo-mode role switching.
    # In production, AUTH_ENABLED MUST be set to true.
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
    AUTH_ISSUER: str = os.getenv("AUTH_ISSUER", "https://auth.university.edu")
    AUTH_AUDIENCE: str = os.getenv("AUTH_AUDIENCE", "university-datashield")
    AUTH_ALGORITHM: str = os.getenv("AUTH_ALGORITHM", "HS256")
    AUTH_SECRET_KEY: str = os.getenv(
        "AUTH_SECRET_KEY",
        "demo-secret-key-university-datashield-dev-mode-only-do-not-use-in-production-12345",
    )
    TOKEN_EXPIRE_MINUTES: int = int(os.getenv("TOKEN_EXPIRE_MINUTES", "60"))

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "120"))

    # ── Ingestion & File Upload Security ──────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
    MAX_JSON_DEPTH: int = int(os.getenv("MAX_JSON_DEPTH", "10"))
    MAX_RECORDS_INGEST: int = int(os.getenv("MAX_RECORDS_INGEST", "100000"))

    # ── Asynchronous Worker & Queue ───────────────────────────────────────────
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
    WORKER_MAX_QUEUE_SIZE: int = int(os.getenv("WORKER_MAX_QUEUE_SIZE", "1000"))
    WORKER_JOB_TIMEOUT_SECONDS: int = int(os.getenv("WORKER_JOB_TIMEOUT_SECONDS", "300"))

    # ── Audit Integrity ───────────────────────────────────────────────────────
    AUDIT_CHAIN_STRICT: bool = os.getenv("AUDIT_CHAIN_STRICT", "true").lower() in ("true", "1", "yes")

    @classmethod
    def validate_production(cls) -> None:
        """
        Fail-Closed validation for production environment.
        Refuses to start if critical production security controls are missing.
        """
        if cls.ENVIRONMENT == "production":
            errors = []
            if not cls.AUTH_ENABLED:
                errors.append("AUTH_ENABLED must be True in production environment.")
            if "demo-secret-key" in cls.AUTH_SECRET_KEY or len(cls.AUTH_SECRET_KEY) < 32:
                errors.append(
                    "AUTH_SECRET_KEY is using a default or insecure value (<32 chars) in production."
                )
            if cls.DATABASE_URL.startswith("sqlite") and "test" not in cls.DATABASE_URL:
                logger.warning(
                    "Production environment configured with SQLite database. PostgreSQL is recommended for multi-instance deployments."
                )
            if errors:
                error_msg = "FATAL PRODUCTION CONFIGURATION ERROR: " + "; ".join(errors)
                logger.critical(error_msg)
                raise RuntimeError(error_msg)

        logger.info(
            "Configuration loaded successfully [env=%s, auth_enabled=%s, rate_limit=%s]",
            cls.ENVIRONMENT,
            cls.AUTH_ENABLED,
            cls.RATE_LIMIT_ENABLED,
        )


settings = Settings()
settings.validate_production()


def get_settings() -> Settings:
    """Return the global Settings instance."""
    return settings

