"""Company people + contract upload + staff confirm (DEV-836, KB/04)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.context import CompanyContext
from app.models import (
    Company,
    Employee,
    Employment,
    EmploymentDocument,
    EmploymentEvent,
    StoredFile,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.services.domain_events import emit_domain_event
from app.storage import build_object_name, get_object_storage, sha256_hex


def require_hr_or_admin(ctx: CompanyContext) -> None:
    if ctx.user.user_type == "BETAXED_STAFF":
        return
    if ctx.membership is None or ctx.membership.role not in {"ADMIN", "HR"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR role required.",
        )


def _current_employment(rows: list[Employment]) -> Employment | None:
    open_rows = [e for e in rows if e.ended_on is None]
    if open_rows:
        return max(open_rows, key=lambda e: e.started_on)
    if not rows:
        return None
    return max(rows, key=lambda e: e.started_on)


def _display_name(crypto, employee: Employee) -> str | None:
    if employee.name_enc is None:
        return None
    try:
        return crypto.decrypt_name(employee.name_enc)
    except Exception:
        return None


async def list_company_people(session: AsyncSession, ctx: CompanyContext) -> list[dict]:
    crypto = await get_or_create_pii_crypto(session, company_id=ctx.company.id)
    employees = (
        (
            await session.execute(
                select(Employee)
                .where(
                    Employee.company_id == ctx.company.id,
                    Employee.deleted_at.is_(None),
                )
                .order_by(Employee.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not employees:
        return []

    ids = [e.id for e in employees]
    employments = (
        (
            await session.execute(
                select(Employment).where(Employment.employee_id.in_(ids))
            )
        )
        .scalars()
        .all()
    )
    by_emp: dict[uuid.UUID, list[Employment]] = {}
    for row in employments:
        by_emp.setdefault(row.employee_id, []).append(row)

    docs = (
        (
            await session.execute(
                select(EmploymentDocument)
                .where(EmploymentDocument.employee_id.in_(ids))
                .order_by(EmploymentDocument.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest_doc: dict[uuid.UUID, EmploymentDocument] = {}
    for doc in docs:
        latest_doc.setdefault(doc.employee_id, doc)

    hide_mismatch = ctx.user.user_type != "BETAXED_STAFF"
    events = (
        (
            await session.execute(
                select(EmploymentEvent)
                .where(
                    EmploymentEvent.employee_id.in_(ids),
                    EmploymentEvent.event_type.in_(
                        ("SOURCE_CONFLICT", "STATUS_OVERRIDE")
                    ),
                )
                .order_by(EmploymentEvent.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest_conflict_kind: dict[uuid.UUID, str] = {}
    for event in events:
        latest_conflict_kind.setdefault(event.employee_id, event.event_type)

    leave_events = (
        (
            await session.execute(
                select(EmploymentEvent)
                .where(
                    EmploymentEvent.employee_id.in_(ids),
                    EmploymentEvent.event_type == "LEAVE_STARTED",
                )
                .order_by(EmploymentEvent.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest_leave: dict[uuid.UUID, str | None] = {}
    for event in leave_events:
        latest_leave.setdefault(event.employee_id, event.leave_type)

    out: list[dict] = []
    for employee in employees:
        current = _current_employment(by_emp.get(employee.id, []))
        doc = latest_doc.get(employee.id)
        review_status = doc.review_status if doc is not None else None
        public_status = review_status
        if hide_mismatch and doc is not None and doc.matches_ss == "MISMATCH":
            public_status = "REVIEWED"
        out.append(
            {
                "id": employee.id,
                "display_name": _display_name(crypto, employee),
                "status": employee.status,
                "status_source": employee.status_source,
                "has_source_conflict": latest_conflict_kind.get(employee.id)
                == "SOURCE_CONFLICT",
                "leave_type": (
                    latest_leave.get(employee.id)
                    if employee.status == "ON_LEAVE"
                    else None
                ),
                "employment_id": current.id if current else None,
                "has_contract": doc is not None,
                "review_status": public_status,
                "document_id": doc.id if doc is not None else None,
            }
        )
    return out


async def upload_employment_contract(
    session: AsyncSession,
    ctx: CompanyContext,
    *,
    employee_id: uuid.UUID,
    filename: str,
    content: bytes,
    mime_type: str | None,
) -> EmploymentDocument:
    require_hr_or_admin(ctx)
    employee = await session.get(Employee, employee_id)
    if (
        employee is None
        or employee.company_id != ctx.company.id
        or employee.deleted_at is not None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    employments = (
        (
            await session.execute(
                select(Employment).where(Employment.employee_id == employee.id)
            )
        )
        .scalars()
        .all()
    )
    current = _current_employment(list(employments))

    storage = get_object_storage()
    object_name = build_object_name(
        company_id=ctx.company.id,
        intake_id=None,
        filename=filename,
    )
    path = storage.put_bytes(
        content,
        object_name=object_name,
        content_type=mime_type,
    )
    stored = StoredFile(
        company_id=ctx.company.id,
        intake_id=None,
        gcs_path=path,
        sha256=sha256_hex(content),
        mime_type=mime_type,
        original_filename=filename,
        kind="EMPLOYMENT_CONTRACT",
        uploaded_by=ctx.user.id,
    )
    session.add(stored)
    await session.flush()

    doc = EmploymentDocument(
        employee_id=employee.id,
        employment_id=current.id if current else None,
        file_id=stored.id,
        matches_ss="UNKNOWN",
        review_status="PENDING",
    )
    session.add(doc)
    await session.flush()

    await emit_domain_event(
        session,
        event_type="CONTRACT_UPLOADED",
        source_entity_type="EMPLOYMENT_DOCUMENT",
        source_entity_id=doc.id,
        actor_id=ctx.user.id,
        company_id=ctx.company.id,
        payload={
            "employment_document_id": str(doc.id),
            "employee_id": str(employee.id),
            "filename": filename,
        },
    )
    return doc


async def list_mismatch_flags(session: AsyncSession) -> list[dict]:
    docs = (
        (
            await session.execute(
                select(EmploymentDocument)
                .where(EmploymentDocument.matches_ss == "MISMATCH")
                .order_by(EmploymentDocument.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out: list[dict] = []
    for doc in docs:
        employee = await session.get(Employee, doc.employee_id)
        if employee is None or employee.company_id is None:
            continue
        company = await session.get(Company, employee.company_id)
        employment = (
            await session.get(Employment, doc.employment_id)
            if doc.employment_id
            else None
        )
        crypto = await get_or_create_pii_crypto(
            session, company_id=employee.company_id
        )
        stored = await session.get(StoredFile, doc.file_id)
        out.append(
            {
                "id": doc.id,
                "company_id": employee.company_id,
                "company_name": company.legal_name if company else None,
                "employee_id": employee.id,
                "display_name": _display_name(crypto, employee),
                "filename": stored.original_filename if stored else None,
                "doc_kind": doc.doc_kind,
                "signed_on": doc.signed_on,
                "term_end_on": doc.term_end_on,
                "ss_modality": employment.contract_modality if employment else None,
                "ss_started_on": employment.started_on if employment else None,
                "ss_ended_on": employment.ended_on if employment else None,
                "ops_confirmed_at": doc.ops_confirmed_at,
                "created_at": doc.created_at,
            }
        )
    return out


def _modality_from_doc_kind(doc_kind: str | None) -> str | None:
    if doc_kind == "SEM_TERMO":
        return "SEM_TERMO"
    if doc_kind == "TERMO":
        return "TERMO_CERTO"
    if doc_kind == "CONVERSION":
        return "SEM_TERMO"
    return None


async def apply_contract_to_employment(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> EmploymentDocument:
    doc = await session.get(EmploymentDocument, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    if doc.review_status != "REVIEWED" or doc.doc_kind is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document has not been reviewed.",
        )
    employment = (
        await session.get(Employment, doc.employment_id)
        if doc.employment_id
        else None
    )
    if employment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No employment to apply.",
        )
    employee = await session.get(Employee, doc.employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found."
        )

    new_modality = _modality_from_doc_kind(doc.doc_kind)
    old_modality = employment.contract_modality
    if new_modality is not None and new_modality != old_modality:
        session.add(
            EmploymentEvent(
                company_id=employee.company_id,
                intake_id=employee.intake_id,
                employee_id=employee.id,
                employment_id=employment.id,
                event_type="MODALITY_CHANGED",
                effective_on=doc.signed_on or employment.started_on,
                source="CONTRACT",
                old_modality=old_modality,
                new_modality=new_modality,
            )
        )
        employment.contract_modality = new_modality
    if doc.signed_on is not None:
        employment.started_on = doc.signed_on
    if doc.doc_kind == "TERMO" and doc.term_end_on is not None:
        employment.ended_on = doc.term_end_on

    doc.ops_confirmed_at = datetime.now(UTC)
    await session.flush()
    return doc
