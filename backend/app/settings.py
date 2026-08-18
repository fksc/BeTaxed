from __future__ import annotations

import os
from functools import lru_cache


_DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://betaxed:betaxed_dev@localhost:5432/betaxed"
)

HEADER_COMPANY_ID = "X-Company-Id"
HEADER_INTAKE_ID = "X-Intake-Id"


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


_DEMO_FIREBASE_PROJECT_ID = "demo-betaxed"


def _normalize_emulator_host(raw: str) -> str:
    host = raw.strip()
    if host.startswith("http://"):
        host = host[len("http://") :]
    elif host.startswith("https://"):
        host = host[len("https://") :]
    return host.rstrip("/")


@lru_cache
def get_firebase_auth_emulator_host() -> str | None:
    """host:port for the Auth emulator. Empty env value disables it."""
    raw = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "").strip()
    if not raw:
        return None
    host = _normalize_emulator_host(raw)
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = host
    return host


@lru_cache
def get_firebase_project_id() -> str | None:
    raw = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
    if raw:
        return raw
    if get_firebase_auth_emulator_host():
        return _DEMO_FIREBASE_PROJECT_ID
    return None
