from __future__ import annotations

import os
from functools import lru_cache

_DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://betaxed:betaxed_dev@localhost:5432/betaxed"
)


@lru_cache
def get_public_app_url() -> str:
    return os.environ.get("PUBLIC_APP_URL", "http://localhost:3000").strip().rstrip("/")


@lru_cache
def get_cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000").strip()
    return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL).strip()


@lru_cache
def get_redis_url() -> str | None:
    raw = os.environ.get("REDIS_URL", "").strip()
    return raw or None


@lru_cache
def get_default_fee_percent() -> str | None:
    """Platform default success-fee fraction. Empty until billing sets it; commercial_terms overrides per client."""
    raw = os.environ.get("DEFAULT_FEE_PERCENT", "").strip()
    return raw or None
