"""Two-pass intake: create, convert, purge (KB/10, DEV-832)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Company,
    CompanyMembership,
    Employee,
    Intake,
    SsBatch,
    SsRawContrato,
    SsRawVinculo,
    StoredFile,
    TenantCryptoKey,
    UserBase,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.security.pii import PiiCrypto
from app.security.session import (
    hash_session_token,
    new_session_token,
    session_token_matches,
)
from app.services.ss_apply import (
    apply_ss_batch,
    attach_employment_company,
    delete_intake_employment_spine,
    upsert_headcount_for_company_applied_batches,
)
from app.services.teaser import persist_intake_teaser_if_missing
from app.storage import get_object_storage


def session_grants_access(intake: Intake, token: str | None) -> bool:
    if token is None or not token.strip() or intake.session_token_hash is None:
        return False
    return session_token_matches(token.strip(), intake.session_token_hash)


def actor_can_access_intake(
    intake: Intake, user: UserBase | None, session_token: str | None
) -> bool:
    if user is not None and user.user_type == "BETAXED_STAFF":
        return True
    if user is not None and intake.user_id is not None and intake.user_id == user.id:
        return True
    return session_grants_access(intake, session_token)


async def load_intake_or_404(session: AsyncSession, intake_id: uuid.UUID) -> Intake:
    intake = await session.get(Intake, intake_id)
    if intake is None or intake.status == "PURGED":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Intake not found."
        )
    return intake


def require_intake_access(
    intake: Intake, user: UserBase | None, session_token: str | None
) -> None:
    if user is None and (session_token is None or not session_token.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer token or X-Intake-Session required.",
        )
    if actor_can_access_intake(intake, user, session_token):
        return
    if intake.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Intake is not bound to this account.",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not the owner of this intake.",
    )


def require_open(intake: Intake) -> None:
    if intake.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Intake is {intake.status}, not OPEN.",
        )


async def create_intake(
    session: AsyncSession, user: UserBase | None
) -> tuple[Intake, str | None]:
    intake = Intake(status="OPEN")
    plaintext: str | None = None
    if user is not None:
        intake.user_id = user.id
        intake.email = user.email
    else:
        plaintext = new_session_token()
        intake.session_token_hash = hash_session_token(plaintext)
    session.add(intake)
    await session.flush()
    return intake, plaintext


async def convert_intake(
    session: AsyncSession,
    *,
    intake: Intake,
    user: UserBase,
    session_token: str | None,
    legal_name: str,
    trading_name: str | None,
) -> tuple[Intake, Company, str | None]:
    require_open(intake)
    _require_convert_actor(intake, user, session_token)

    name = legal_name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="legal_name is required.",
        )
    trade = trading_name.strip() if trading_name else None

    owner_id = intake.user_id
    if owner_id is None and user.user_type != "BETAXED_STAFF":
        owner_id = user.id
        intake.user_id = user.id
        if intake.email is None:
            intake.email = user.email

    company = Company(
        legal_name=name,
        trading_name=trade or None,
        created_from_intake_id=intake.id,
    )
    session.add(company)
    await session.flush()

    membership_role: str | None = None
    if owner_id is not None:
        session.add(
            CompanyMembership(
                user_id=owner_id, company_id=company.id, role="ADMIN"
            )
        )
        membership_role = "ADMIN"

    batches = (
        await session.execute(select(SsBatch).where(SsBatch.intake_id == intake.id))
    ).scalars().all()
    for batch in batches:
        if batch.parse_status == "PARSED":
            await apply_ss_batch(session, batch.id)
        batch.company_id = company.id
    await persist_intake_teaser_if_missing(session, intake)

    files = (
        await session.execute(
            select(StoredFile).where(StoredFile.intake_id == intake.id)
        )
    ).scalars().all()
    for stored in files:
        stored.company_id = company.id

    await attach_employment_company(session, intake.id, company.id)
    await upsert_headcount_for_company_applied_batches(session, company.id)
    from app.services.benefit_engine import rebuild_company_ledger

    latest = (
        await session.execute(
            select(SsBatch)
            .where(SsBatch.company_id == company.id)
            .order_by(SsBatch.period_year_month.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    as_of = latest.period_year_month if latest is not None else date.today()
    await rebuild_company_ledger(session, company.id, as_of)

    await _rekey_intake_to_company(session, intake.id, company)

    intake.status = "CONVERTED"
    intake.converted_company_id = company.id
    intake.session_token_hash = None
    intake.decided_at = datetime.now(UTC)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employer NISS already registered to another company.",
        ) from exc
    return intake, company, membership_role


def _require_convert_actor(
    intake: Intake, user: UserBase, session_token: str | None
) -> None:
    if user.user_type == "BETAXED_STAFF":
        return
    if intake.user_id is not None and intake.user_id == user.id:
        return
    if intake.user_id is None and session_grants_access(intake, session_token):
        return
    if intake.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Intake is not bound to this account.",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not the owner of this intake.",
    )


async def _rekey_intake_to_company(
    session: AsyncSession, intake_id: uuid.UUID, company: Company
) -> None:
    """Move HMAC/DEK from intake scope to company scope (tenant XOR on keys)."""
    intake_key = (
        await session.execute(
            select(TenantCryptoKey).where(TenantCryptoKey.intake_id == intake_id)
        )
    ).scalar_one_or_none()
    if intake_key is None:
        return

    intake_crypto = await get_or_create_pii_crypto(session, intake_id=intake_id)
    company_crypto = await get_or_create_pii_crypto(
        session, company_id=company.id
    )

    batches = (
        await session.execute(
            select(SsBatch)
            .options(
                selectinload(SsBatch.vinculos),
                selectinload(SsBatch.contratos),
            )
            .where(SsBatch.intake_id == intake_id)
        )
    ).scalars().all()
    for batch in batches:
        _rekey_batch(batch, intake_crypto, company_crypto, company)

    employees = (
        await session.execute(
            select(Employee).where(Employee.intake_id == intake_id)
        )
    ).scalars().all()
    for employee in employees:
        _rekey_employee(employee, intake_crypto, company_crypto)

    await session.flush()
    await session.execute(
        delete(TenantCryptoKey).where(TenantCryptoKey.intake_id == intake_id)
    )
    await session.flush()


def _rekey_batch(
    batch: SsBatch,
    intake_crypto: PiiCrypto,
    company_crypto: PiiCrypto,
    company: Company,
) -> None:
    if batch.employer_niss_enc is not None:
        employer_niss = intake_crypto.decrypt_niss(batch.employer_niss_enc)
        batch.employer_niss_hash = company_crypto.niss_hash(employer_niss)
        batch.employer_niss_enc = company_crypto.encrypt_niss(employer_niss)
        if company.employer_niss_hash is None:
            company.employer_niss_hash = batch.employer_niss_hash
            company.employer_niss_enc = batch.employer_niss_enc
    for row in batch.vinculos:
        _rekey_raw_identity(row, intake_crypto, company_crypto)
        row.leftover = _drop_leftover_niss_hashes(row.leftover)
    for row in batch.contratos:
        _rekey_raw_identity(row, intake_crypto, company_crypto)
        row.leftover = _drop_leftover_niss_hashes(row.leftover)


def _rekey_raw_identity(
    row: SsRawVinculo | SsRawContrato,
    intake_crypto: PiiCrypto,
    company_crypto: PiiCrypto,
) -> None:
    niss = intake_crypto.decrypt_niss(row.niss_enc)
    row.niss_hash = company_crypto.niss_hash(niss)
    row.niss_enc = company_crypto.encrypt_niss(niss)
    if row.name_enc is not None:
        row.name_enc = company_crypto.encrypt_name(
            intake_crypto.decrypt_name(row.name_enc)
        )
    if isinstance(row, SsRawVinculo) and row.dob_enc is not None:
        row.dob_enc = company_crypto.encrypt_dob(
            intake_crypto.decrypt_dob(row.dob_enc)
        )


def _rekey_employee(
    employee: Employee,
    intake_crypto: PiiCrypto,
    company_crypto: PiiCrypto,
) -> None:
    niss = intake_crypto.decrypt_niss(employee.niss_enc)
    employee.niss_hash = company_crypto.niss_hash(niss)
    employee.niss_enc = company_crypto.encrypt_niss(niss)
    if employee.name_enc is not None:
        employee.name_enc = company_crypto.encrypt_name(
            intake_crypto.decrypt_name(employee.name_enc)
        )
    if employee.dob_enc is not None:
        employee.dob_enc = company_crypto.encrypt_dob(
            intake_crypto.decrypt_dob(employee.dob_enc)
        )


def _drop_leftover_niss_hashes(leftover: dict[str, Any] | None) -> dict[str, Any] | None:
    """Intake-scoped leftover hashes cannot be re-HMAC'd without plaintext."""
    if not leftover:
        return leftover
    cleaned = {
        key: value
        for key, value in leftover.items()
        if not (isinstance(value, dict) and "niss_hash" in value)
    }
    return cleaned or None


async def purge_intake(session: AsyncSession, intake: Intake) -> Intake:
    require_open(intake)
    intake.status = "DECLINED"

    stored_files = (
        await session.execute(
            select(StoredFile).where(StoredFile.intake_id == intake.id)
        )
    ).scalars().all()
    storage = get_object_storage()
    for stored in stored_files:
        storage.delete(stored.gcs_path)

    await delete_intake_employment_spine(session, intake.id)
    await session.execute(delete(SsBatch).where(SsBatch.intake_id == intake.id))
    await session.execute(delete(StoredFile).where(StoredFile.intake_id == intake.id))
    await session.execute(
        delete(TenantCryptoKey).where(TenantCryptoKey.intake_id == intake.id)
    )

    now = datetime.now(UTC)
    intake.status = "PURGED"
    intake.purged_at = now
    intake.decided_at = intake.decided_at or now
    intake.user_id = None
    intake.email = None
    intake.session_token_hash = None
    intake.teaser_now_monthly = None
    intake.teaser_now_window = None
    intake.teaser_potential_monthly = None
    intake.teaser_potential_window = None
    intake.teaser_regime_id = None
    intake.converted_company_id = None
    await session.flush()
    return intake


async def latest_batch_summary(
    session: AsyncSession, intake_id: uuid.UUID
) -> tuple[SsBatch, int, int] | None:
    batch = (
        await session.execute(
            select(SsBatch)
            .where(SsBatch.intake_id == intake_id)
            .order_by(SsBatch.uploaded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if batch is None:
        return None
    vinculo_count = (
        await session.execute(
            select(func.count())
            .select_from(SsRawVinculo)
            .where(SsRawVinculo.batch_id == batch.id)
        )
    ).scalar_one()
    contrato_count = (
        await session.execute(
            select(func.count())
            .select_from(SsRawContrato)
            .where(SsRawContrato.batch_id == batch.id)
        )
    ).scalar_one()
    return batch, int(vinculo_count), int(contrato_count)
