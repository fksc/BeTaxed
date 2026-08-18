"""Unit tests for envelope encryption and HMAC (DEV-830)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.security.crypto import (
    decrypt_bytes,
    encrypt_bytes,
    generate_dek,
    hmac_niss,
    normalize_niss,
    unwrap_dek,
    wrap_dek,
)
from app.security.pii import PiiCrypto


def test_normalize_niss_strips_formatting() -> None:
    assert normalize_niss("123 456 789 01") == "12345678901"


def test_hmac_niss_is_tenant_scoped() -> None:
    secret = b"test-secret-32-bytes-long!!!!!!"
    niss = "12345678901"
    company_a = uuid.uuid4()
    company_b = uuid.uuid4()
    h_a = hmac_niss(niss, company_a, secret)
    h_b = hmac_niss(niss, company_b, secret)
    assert h_a != h_b
    assert hmac_niss(niss, company_a, secret) == h_a


def test_envelope_encrypt_roundtrip() -> None:
    dek = generate_dek()
    plaintext = b"sensitive payload"
    blob = encrypt_bytes(plaintext, dek)
    assert decrypt_bytes(blob, dek) == plaintext


def test_wrap_dek_roundtrip() -> None:
    dek = generate_dek()
    wrap_key = generate_dek()
    scope = uuid.uuid4()
    wrapped = wrap_dek(dek, wrap_key, scope)
    assert unwrap_dek(wrapped, wrap_key, scope) == dek


def test_pii_crypto_roundtrip() -> None:
    scope = uuid.uuid4()
    secret = b"test-secret-32-bytes-long!!!!!!"
    dek = generate_dek()
    crypto = PiiCrypto(dek=dek, tenant_scope=scope, app_secret=secret)

    niss = "12345678901"
    assert crypto.decrypt_niss(crypto.encrypt_niss(niss)) == normalize_niss(niss)
    assert crypto.decrypt_name(crypto.encrypt_name("Maria Silva")) == "Maria Silva"
    dob = date(1998, 3, 15)
    assert crypto.decrypt_dob(crypto.encrypt_dob(dob)) == dob
    assert crypto.niss_hash(niss) == hmac_niss(niss, scope, secret)


def test_decrypt_wrong_dek_raises() -> None:
    dek_a = generate_dek()
    dek_b = generate_dek()
    blob = encrypt_bytes(b"data", dek_a)
    with pytest.raises(Exception):
        decrypt_bytes(blob, dek_b)
