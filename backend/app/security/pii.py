"""High-level PII encrypt/decrypt using tenant DEKs (DEV-830)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from enum import Enum

from app.security.crypto import (
    decrypt_bytes,
    encrypt_bytes,
    hmac_niss,
    normalize_niss,
)


class PiiField(str, Enum):
    NISS = "niss"
    NAME = "name"
    DOB = "dob"
    NIF = "nif"


@dataclass(frozen=True)
class PiiCrypto:
    """Encrypt/decrypt identity fields and compute niss_hash for joins."""

    dek: bytes
    tenant_scope: uuid.UUID
    app_secret: bytes

    def niss_hash(self, niss: str) -> bytes:
        return hmac_niss(niss, self.tenant_scope, self.app_secret)

    def encrypt_niss(self, niss: str) -> bytes:
        normalized = normalize_niss(niss)
        return encrypt_bytes(normalized.encode("utf-8"), self.dek)

    def decrypt_niss(self, niss_enc: bytes) -> str:
        return decrypt_bytes(niss_enc, self.dek).decode("utf-8")

    def encrypt_name(self, name: str) -> bytes:
        return encrypt_bytes(name.strip().encode("utf-8"), self.dek)

    def decrypt_name(self, name_enc: bytes) -> str:
        return decrypt_bytes(name_enc, self.dek).decode("utf-8")

    def encrypt_dob(self, dob: date) -> bytes:
        return encrypt_bytes(dob.isoformat().encode("utf-8"), self.dek)

    def decrypt_dob(self, dob_enc: bytes) -> date:
        raw = decrypt_bytes(dob_enc, self.dek).decode("utf-8")
        return date.fromisoformat(raw)

    def encrypt_nif(self, nif: str) -> bytes:
        normalized = normalize_niss(nif)
        return encrypt_bytes(normalized.encode("utf-8"), self.dek)

    def decrypt_nif(self, nif_enc: bytes) -> str:
        return decrypt_bytes(nif_enc, self.dek).decode("utf-8")
