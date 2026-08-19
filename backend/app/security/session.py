"""Anonymous intake session tokens (OD-1 upload-first)."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def session_token_matches(token: str, stored_hash: bytes) -> bool:
    digest = hash_session_token(token)
    if len(digest) != len(stored_hash):
        return False
    return hmac.compare_digest(digest, stored_hash)
