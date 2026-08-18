from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache
from pathlib import Path


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


def _decode_key32(env_name: str, default_dev: bytes) -> bytes:
    raw = os.environ.get(env_name, "").strip()
    if raw:
        decoded = base64.b64decode(raw, validate=True)
        if len(decoded) != 32:
            raise ValueError(f"{env_name} must decode to 32 bytes")
        return decoded
    return default_dev


# Fixed DEV-only keys — never use in staging/prod (set env vars there).
_DEV_MASTER_KEY = hashlib.sha256(b"betaxed-dev-encryption-master-v1").digest()
_DEV_HMAC_SECRET = hashlib.sha256(b"betaxed-dev-niss-hmac-v1").digest()


@lru_cache
def get_encryption_master_key() -> bytes:
    """AES-256 key wrapping tenant DEKs. Set ENCRYPTION_MASTER_KEY in prod."""
    return _decode_key32("ENCRYPTION_MASTER_KEY", _DEV_MASTER_KEY)


@lru_cache
def get_niss_hmac_secret() -> bytes:
    """App secret for per-tenant NISS HMAC. Set NISS_HMAC_SECRET in prod."""
    return _decode_key32("NISS_HMAC_SECRET", _DEV_HMAC_SECRET)


@lru_cache
def get_gcs_bucket() -> str | None:
    raw = os.environ.get("GCS_BUCKET", "").strip()
    return raw or None


@lru_cache
def get_gcs_kms_key_name() -> str | None:
    """Full KMS key resource for GCS CMEK, e.g. projects/P/locations/L/keyRings/R/cryptoKeys/K."""
    raw = os.environ.get("GCS_KMS_KEY_NAME", "").strip()
    return raw or None


@lru_cache
def get_local_storage_dir() -> Path:
    raw = os.environ.get("LOCAL_STORAGE_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent / ".local_storage"
