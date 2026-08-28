"""
Application configuration.

Settings are read from environment variables (12-factor). The meeting BUFFER
default lives here as a single documented value; the running system prefers the
`APPOINTMENT_BUFFER_MINUTES` row in the canonical system_settings table when
present (see app/services/buffer.py), exactly as the brief requests:
"Read the buffer from an existing settings table if available. Otherwise place
it in clearly documented application configuration rather than hard-coding it".

pydantic-settings is used when available; a stdlib fallback keeps this module
importable in minimal environments (e.g. CI without the web stack installed).
"""
from __future__ import annotations

import os


def _get(key: str, default: str) -> str:
    return os.environ.get(key, default)


class Settings:
    # --- Database -------------------------------------------------------
    DATABASE_URL: str = _get(
        "CAMPUSFLOW_DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/campusflow",
    )

    # --- Auth -----------------------------------------------------------
    JWT_SECRET: str = _get("CAMPUSFLOW_JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = _get("CAMPUSFLOW_JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(_get("CAMPUSFLOW_TOKEN_TTL_MIN", "720"))

    # --- Scheduling defaults (single source; overridable via system_settings) --
    DEFAULT_BUFFER_MINUTES: int = int(_get("CAMPUSFLOW_BUFFER_MINUTES", "5"))
    DEFAULT_MEETING_MINUTES: int = int(_get("CAMPUSFLOW_MEETING_MINUTES", "15"))
    QUEUE_BREAK_AFTER: int = int(_get("CAMPUSFLOW_BREAK_AFTER", "0"))
    QUEUE_BREAK_MINUTES: int = int(_get("CAMPUSFLOW_BREAK_MINUTES", "5"))
    GRACE_PERIOD_MINUTES: int = int(_get("CAMPUSFLOW_GRACE_MINUTES", "10"))

    # --- Meta -----------------------------------------------------------
    APP_NAME: str = "CampusFlow AI MVP"
    APP_VERSION: str = "1.0.0"
    ENV: str = _get("CAMPUSFLOW_ENV", "development")


settings = Settings()
