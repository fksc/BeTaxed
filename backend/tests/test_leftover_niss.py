"""Leftover JSONB NISS envelope + re-HMAC on convert (DEV-848). No Postgres."""

from __future__ import annotations

import base64
import json
import uuid

from app.security.crypto import generate_dek, normalize_niss
from app.security.pii import PiiCrypto
from app.services.ss_ingest import _leftover_for_storage, rekey_leftover_niss

_SECRET = b"test-secret-32-bytes-long!!!!!!"
_NISS = "44444444444"


def _crypto() -> PiiCrypto:
    return PiiCrypto(
        dek=generate_dek(),
        tenant_scope=uuid.uuid4(),
        app_secret=_SECRET,
    )


def test_leftover_stores_enc_and_hash_never_plaintext() -> None:
    crypto = _crypto()
    stored = _leftover_for_storage(
        {"NISS substituto": _NISS, "nota": "ok"}, crypto
    )
    assert stored is not None
    dumped = json.dumps(stored)
    assert _NISS not in dumped
    blob = stored["NISS substituto"]
    assert crypto.niss_hash(_NISS).hex() in blob["niss_hash"]
    decoded = base64.b64decode(blob["niss_enc"][0])
    assert crypto.decrypt_niss(decoded) == normalize_niss(_NISS)
    assert stored["nota"] == "ok"


def test_rekey_leftover_uses_company_hmac() -> None:
    intake = _crypto()
    company = _crypto()
    stored = _leftover_for_storage({"extra niss": _NISS}, intake)
    rekeyed = rekey_leftover_niss(stored, intake, company)
    assert rekeyed is not None
    dumped = json.dumps(rekeyed)
    assert _NISS not in dumped
    assert intake.niss_hash(_NISS).hex() not in dumped
    blob = rekeyed["extra niss"]
    assert company.niss_hash(_NISS).hex() in blob["niss_hash"]
    decoded = base64.b64decode(blob["niss_enc"][0])
    assert company.decrypt_niss(decoded) == normalize_niss(_NISS)


def test_legacy_hash_only_leftover_is_dropped() -> None:
    intake = _crypto()
    company = _crypto()
    leftover = {"extra niss": {"niss_hash": ["deadbeef"]}}
    assert rekey_leftover_niss(leftover, intake, company) is None
