"""Tenant DEK lifecycle: generate, wrap, persist, load (DEV-830)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crypto import TenantCryptoKey
from app.security.crypto import generate_dek, unwrap_dek, wrap_dek
from app.security.pii import PiiCrypto
from app.settings import get_encryption_master_key, get_niss_hmac_secret


async def get_or_create_pii_crypto(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None = None,
    intake_id: uuid.UUID | None = None,
) -> PiiCrypto:
    """Load or create a tenant DEK and return a PiiCrypto helper."""
    if company_id is None and intake_id is None:
        raise ValueError("company_id or intake_id required")
    if company_id is not None and intake_id is not None:
        raise ValueError("only one of company_id or intake_id")

    tenant_scope = company_id if company_id is not None else intake_id
    assert tenant_scope is not None

    master_key = get_encryption_master_key()
    app_secret = get_niss_hmac_secret()

    stmt = select(TenantCryptoKey).where(
        TenantCryptoKey.company_id == company_id,
        TenantCryptoKey.intake_id == intake_id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()

    if row is None:
        dek = generate_dek()
        wrapped = wrap_dek(dek, master_key, tenant_scope)
        row = TenantCryptoKey(
            company_id=company_id,
            intake_id=intake_id,
            wrapped_dek=wrapped,
            key_version=1,
        )
        session.add(row)
        await session.flush()
    else:
        dek = unwrap_dek(row.wrapped_dek, master_key, tenant_scope)

    return PiiCrypto(dek=dek, tenant_scope=tenant_scope, app_secret=app_secret)
