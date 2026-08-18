"""Envelope encryption and HMAC primitives (KB/07).

Never log plaintext NISS — callers must not pass NISS to logging.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from typing import Final

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# AES-GCM nonce length and DEK size.
_NONCE_LEN: Final = 12
_DEK_LEN: Final = 32
_VERSION: Final = 1


def normalize_niss(raw: str) -> str:
    """Strip non-digits so hashes are stable across formatting."""
    return "".join(ch for ch in raw if ch.isdigit())


def _derive_hmac_key(tenant_scope: uuid.UUID, app_secret: bytes) -> bytes:
    """Per-tenant HMAC key — same NISS hashes differently per company/intake."""
    return hashlib.sha256(app_secret + tenant_scope.bytes).digest()


def hmac_niss(niss: str, tenant_scope: uuid.UUID, app_secret: bytes) -> bytes:
    """HMAC-SHA256 of normalized NISS scoped to tenant (company or intake)."""
    normalized = normalize_niss(niss)
    key = _derive_hmac_key(tenant_scope, app_secret)
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).digest()


def generate_dek() -> bytes:
    return os.urandom(_DEK_LEN)


def wrap_dek(dek: bytes, wrapping_key: bytes, tenant_scope: uuid.UUID) -> bytes:
    """Wrap a DEK with AES-GCM; AAD binds wrap to tenant scope."""
    aesgcm = AESGCM(wrapping_key)
    nonce = os.urandom(_NONCE_LEN)
    aad = tenant_scope.bytes
    ciphertext = aesgcm.encrypt(nonce, dek, aad)
    return bytes([_VERSION]) + nonce + ciphertext


def unwrap_dek(
    wrapped: bytes, wrapping_key: bytes, tenant_scope: uuid.UUID
) -> bytes:
    if len(wrapped) < 1 + _NONCE_LEN + _DEK_LEN:
        raise ValueError("wrapped DEK too short")
    version = wrapped[0]
    if version != _VERSION:
        raise ValueError(f"unsupported wrap version {version}")
    nonce = wrapped[1 : 1 + _NONCE_LEN]
    ciphertext = wrapped[1 + _NONCE_LEN :]
    aesgcm = AESGCM(wrapping_key)
    return aesgcm.decrypt(nonce, ciphertext, tenant_scope.bytes)


def encrypt_bytes(plaintext: bytes, dek: bytes) -> bytes:
    """Envelope encrypt with tenant DEK; returns version + nonce + ciphertext."""
    aesgcm = AESGCM(dek)
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return bytes([_VERSION]) + nonce + ciphertext


def decrypt_bytes(blob: bytes, dek: bytes) -> bytes:
    if len(blob) < 1 + _NONCE_LEN:
        raise ValueError("encrypted blob too short")
    version = blob[0]
    if version != _VERSION:
        raise ValueError(f"unsupported encrypt version {version}")
    nonce = blob[1 : 1 + _NONCE_LEN]
    ciphertext = blob[1 + _NONCE_LEN :]
    aesgcm = AESGCM(dek)
    return aesgcm.decrypt(nonce, ciphertext, None)
