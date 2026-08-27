"""Ops listing and company certificate uploads (DEV-838). Not on company benefit APIs."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.context import CompanyContext
from app.models import (
    BenefitCase,
    Company,
    CompanyCertificate,
    Employee,
    SavingMonth,
    StoredFile,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.services.benefit_engine import (
    _cert_covers,
    add_calendar_months,
    current_regime,
    first_of_month,
)
from app.services.teaser import remaining_benefit_months
from app.storage import build_object_name, get_object_storage, sha256_hex

CERT_KINDS = frozenset({"SS_NO_DEBT", "AT_NO_DEBT"})


def require_admin_or_finance(ctx: CompanyContext) -> None:
    if ctx.user.user_type == "BETAXED_STAFF":
        return
    if ctx.membership is None or ctx.membership.role not in {"ADMIN", "FINANCE"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Finance role required.",
        )


async def list_ops_benefit_cases(
    session: AsyncSession, as_of: date
) -> list[dict]:
    regime = await current_regime(session, as_of)
    cases = (
        (
            await session.execute(
                select(BenefitCase)
                .where(BenefitCase.regime_id == regime.id)
                .order_by(BenefitCase.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if not cases:
        return []
    companies = {
        row.id: row
        for row in (
            await session.execute(
                select(Company).where(Company.id.in_({c.company_id for c in cases}))
            )
        ).scalars().all()
    }
    employees = {
        row.id: row
        for row in (
            await session.execute(
                select(Employee).where(Employee.id.in_({c.employee_id for c in cases}))
            )
        ).scalars().all()
    }
    months = (
        (
            await session.execute(
                select(SavingMonth).where(
                    SavingMonth.benefit_case_id.in_({c.id for c in cases}),
                    SavingMonth.year_month == first_of_month(as_of),
                )
            )
        )
        .scalars()
        .all()
    )
    monthly = {row.benefit_case_id: row.saving_amount for row in months}
    out: list[dict] = []
    cryptos: dict[uuid.UUID, object] = {}
    for case in cases:
        employee = employees.get(case.employee_id)
        name = None
        if employee is not None and employee.name_enc is not None:
            crypto = cryptos.get(case.company_id)
            if crypto is None:
                crypto = await get_or_create_pii_crypto(
                    session, company_id=case.company_id
                )
                cryptos[case.company_id] = crypto
            try:
                name = crypto.decrypt_name(employee.name_enc)
            except Exception:
                name = None
        remaining = None
        if case.sem_termo_on is not None:
            remaining = remaining_benefit_months(case.sem_termo_on, as_of)
        company = companies.get(case.company_id)
        out.append(
            {
                "id": case.id,
                "company_id": case.company_id,
                "company_name": company.legal_name if company else None,
                "employee_id": case.employee_id,
                "display_name": name,
                "state": case.state,
                "ineligibility_code": case.ineligibility_code,
                "sem_termo_on": case.sem_termo_on,
                "window_ends_on": case.window_ends_on,
                "remaining_months": remaining,
                "monthly_saving": monthly.get(case.id),
            }
        )
    return out


async def list_certificates(
    session: AsyncSession, company_id: uuid.UUID
) -> list[CompanyCertificate]:
    return (
        (
            await session.execute(
                select(CompanyCertificate)
                .where(CompanyCertificate.company_id == company_id)
                .order_by(CompanyCertificate.issued_on.desc())
            )
        )
        .scalars()
        .all()
    )


async def latest_certificate(
    session: AsyncSession, company_id: uuid.UUID, kind: str
) -> CompanyCertificate | None:
    return (
        (
            await session.execute(
                select(CompanyCertificate)
                .where(
                    CompanyCertificate.company_id == company_id,
                    CompanyCertificate.kind == kind,
                )
                .order_by(
                    CompanyCertificate.valid_until.desc(),
                    CompanyCertificate.issued_on.desc(),
                )
            )
        )
        .scalars()
        .first()
    )


async def upload_certificate(
    session: AsyncSession,
    ctx: CompanyContext,
    *,
    kind: str,
    issued_on: date,
    filename: str,
    content: bytes,
    mime_type: str | None,
    valid_until: date | None = None,
) -> CompanyCertificate:
    require_admin_or_finance(ctx)
    if kind not in CERT_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="kind must be SS_NO_DEBT or AT_NO_DEBT.",
        )
    regime = await current_regime(session, issued_on)
    until = valid_until or add_calendar_months(issued_on, regime.no_debt_valid_months)
    storage = get_object_storage()
    object_name = build_object_name(
        company_id=ctx.company.id, intake_id=None, filename=filename
    )
    path = storage.put_bytes(content, object_name=object_name, content_type=mime_type)
    stored = StoredFile(
        company_id=ctx.company.id,
        intake_id=None,
        gcs_path=path,
        sha256=sha256_hex(content),
        mime_type=mime_type,
        original_filename=filename,
        kind=kind,
        uploaded_by=ctx.user.id,
    )
    session.add(stored)
    await session.flush()
    cert = CompanyCertificate(
        company_id=ctx.company.id,
        kind=kind,
        file_id=stored.id,
        issued_on=issued_on,
        valid_until=until,
        valid_until_overridden=valid_until is not None,
    )
    session.add(cert)
    await session.flush()
    covering = await _cert_covers(session, ctx.company.id, kind, date.today())
    if kind == "SS_NO_DEBT":
        ctx.company.ss_regularized = covering
    else:
        ctx.company.at_regularized = covering
    await session.flush()
    return cert
