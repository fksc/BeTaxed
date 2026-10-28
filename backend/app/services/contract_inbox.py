"""Batch contract PDFs: store, infer, then link NIF → name → NISS (DEV-850)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.context import CompanyContext
from app.models import Company, ContractInbox, Employee, Employment, EmploymentDocument, StoredFile
from app.security.crypto import normalize_niss
from app.security.dek_store import get_or_create_pii_crypto
from app.services.contract_llm import ContractExtract, get_contract_extractor
from app.services.contract_match import (
    MatchCandidate,
    match_contract_employee,
    normalize_person_name,
)
from app.services.contract_review import (
    ContractReviewRetry,
    apply_contract_extract,
    review_event_payload,
)
from app.services.contracts import _current_employment, require_hr_or_admin
from app.services.domain_events import emit_domain_event
from app.storage import build_contract_object_name, get_object_storage, sha256_hex

logger = logging.getLogger(__name__)

_MAX_FILES = 100


async def upload_contract_batch(
    session: AsyncSession,
    ctx: CompanyContext,
    files: list[tuple[str, bytes, str | None]],
) -> list[ContractInbox]:
    require_hr_or_admin(ctx)
    if not files:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload at least one PDF.")
    if len(files) > _MAX_FILES:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload at most {_MAX_FILES} PDFs at once.",
        )

    storage = get_object_storage()
    pending = session.info.setdefault("pending_contract_inbox_ids", [])
    created: list[ContractInbox] = []
    for filename, content, mime_type in files:
        file_id = uuid.uuid4()
        object_name = build_contract_object_name(
            company_id=ctx.company.id,
            file_id=file_id,
            filename=filename,
        )
        path = await asyncio.to_thread(
            storage.put_bytes,
            content,
            object_name=object_name,
            content_type=mime_type,
        )
        stored = StoredFile(
            id=file_id,
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
        inbox = ContractInbox(
            company_id=ctx.company.id,
            file_id=stored.id,
            uploaded_by=ctx.user.id,
            status="PENDING",
        )
        session.add(inbox)
        await session.flush()
        pending.append(inbox.id)
        created.append(inbox)
    return created


async def process_contract_inbox(
    session: AsyncSession,
    inbox_id: uuid.UUID,
    *,
    retry_count: int | None,
) -> ContractInbox | None:
    from app.services.cloud_tasks import should_retry_task

    inbox = (
        await session.execute(
            select(ContractInbox).where(ContractInbox.id == inbox_id).with_for_update()
        )
    ).scalar_one_or_none()
    if inbox is None or inbox.status != "PENDING":
        return inbox

    stored = await session.get(StoredFile, inbox.file_id)
    company = await session.get(Company, inbox.company_id)
    if stored is None or company is None:
        _fail(inbox, "missing_file_or_company")
        return inbox

    crypto = await get_or_create_pii_crypto(session, company_id=company.id)
    reused = None
    if company.nif_enc is not None:
        reused = await _cached_extract(
            session,
            crypto,
            company_id=company.id,
            sha256=stored.sha256,
            file_id=stored.id,
        )
    if reused is not None:
        extract = reused.extract
        logger.info("contract inbox reused extract inbox=%s", inbox_id)
    else:
        try:
            storage = get_object_storage()
            data = await asyncio.to_thread(storage.get_bytes, stored.gcs_path)
            extract = await asyncio.to_thread(
                get_contract_extractor().extract,
                data,
                mime_type=stored.mime_type,
                filename=stored.original_filename,
            )
        except Exception as exc:
            logger.warning("contract inbox read failed inbox=%s: %s", inbox_id, type(exc).__name__)
            if should_retry_task(retry_count):
                raise ContractReviewRetry from exc
            _fail(inbox, type(exc).__name__)
            return inbox

    _remember_extract(inbox, crypto, extract)
    if reused is not None and extract.employer_nif is None:
        inbox.employer_nif_mismatch = reused.employer_nif_mismatch
    else:
        inbox.employer_nif_mismatch = _employer_nif_mismatch(company, crypto, extract.employer_nif)

    employees = (
        (
            await session.execute(
                select(Employee).where(
                    Employee.company_id == company.id,
                    Employee.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    candidates = [_candidate(crypto, row) for row in employees]
    nif_hash = crypto.nif_hash(extract.nif) if _digits(extract.nif) else None
    niss_hash = crypto.niss_hash(extract.niss) if _digits(extract.niss) else None
    result = match_contract_employee(
        candidates,
        nif_hash=nif_hash,
        name_norm=normalize_person_name(extract.full_name),
        niss_hash=niss_hash,
    )
    if result.employee_id is None or result.via is None:
        from app.services.contract_review import remember_minuta_profile

        inbox.legal_name_mismatch = await remember_minuta_profile(
            session, company, None, crypto, extract, inbox
        )
        inbox.status = "UNMATCHED"
        inbox.processed_at = datetime.now(UTC)
        logger.info("contract inbox unmatched inbox=%s", inbox_id)
        return inbox

    employee = await session.get(Employee, result.employee_id)
    if employee is None or employee.company_id != company.id:
        inbox.status = "UNMATCHED"
        inbox.processed_at = datetime.now(UTC)
        return inbox

    inbox.nif_conflict = await _remember_employee_nif(session, employee, crypto, extract.nif)
    from app.services.contract_review import remember_minuta_profile

    inbox.legal_name_mismatch = await remember_minuta_profile(
        session, company, employee, crypto, extract, inbox
    )
    existing = await _document_for_hash(session, employee.id, stored.sha256)
    if existing is not None:
        inbox.status = "MATCHED"
        inbox.match_via = result.via
        inbox.employee_id = employee.id
        inbox.employment_document_id = existing.id
        inbox.processed_at = datetime.now(UTC)
        inbox.error = None
        logger.info("contract inbox reused document inbox=%s", inbox_id)
        return inbox

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
        actor_id=inbox.uploaded_by,
        company_id=company.id,
        payload={
            "employment_document_id": str(doc.id),
            "employee_id": str(employee.id),
            "filename": stored.original_filename,
        },
    )
    event_type = apply_contract_extract(doc, extract, current)
    await remember_minuta_profile(session, company, employee, crypto, extract, doc)
    leftover = dict(doc.review_leftover or {})
    leftover["match_via"] = result.via
    if inbox.nif_conflict:
        leftover["nif_conflict"] = True
    if inbox.employer_nif_mismatch is not None:
        leftover["employer_nif_mismatch"] = inbox.employer_nif_mismatch
    doc.review_leftover = leftover
    await emit_domain_event(
        session,
        event_type=event_type,
        source_entity_type="EMPLOYMENT_DOCUMENT",
        source_entity_id=doc.id,
        actor_id=None,
        company_id=company.id,
        payload=review_event_payload(doc, employee, current),
    )

    inbox.status = "MATCHED"
    inbox.match_via = result.via
    inbox.employee_id = employee.id
    inbox.employment_document_id = doc.id
    inbox.processed_at = datetime.now(UTC)
    inbox.error = None
    logger.info("contract inbox matched inbox=%s via=%s", inbox_id, result.via)
    return inbox


def _digits(raw: str | None) -> str:
    return normalize_niss(raw or "")


def _store_extract(inbox: ContractInbox, crypto, extract) -> None:
    if _digits(extract.nif):
        inbox.nif_enc = crypto.encrypt_nif(extract.nif)
    if extract.full_name and extract.full_name.strip():
        inbox.name_enc = crypto.encrypt_name(extract.full_name)
    if _digits(extract.niss):
        inbox.niss_enc = crypto.encrypt_niss(extract.niss)
    if extract.employee_address:
        inbox.employee_address_enc = crypto.encrypt_address(extract.employee_address)
    if _digits(extract.employer_niss):
        inbox.employer_niss_enc = crypto.encrypt_niss(extract.employer_niss)
    inbox.employer_legal_name = extract.employer_legal_name
    inbox.employer_address = extract.employer_address
    inbox.signatory_name = extract.signatory_name
    inbox.term_started_on = extract.term_started_on
    inbox.converted_on = extract.converted_on
    inbox.declared_on = extract.declared_on
    inbox.signing_place = extract.signing_place


def _remember_extract(inbox: ContractInbox, crypto, extract) -> None:
    _store_extract(inbox, crypto, extract)
    inbox.doc_kind = extract.doc_kind
    inbox.signed_on = extract.signed_on
    inbox.term_end_on = extract.term_end_on


def _decrypt(fn, blob: bytes | None) -> str | None:
    if blob is None:
        return None
    try:
        text = fn(blob)
    except Exception:
        return None
    cleaned = str(text).strip() if text else ""
    return cleaned or None


class _CachedExtract:
    def __init__(self, extract: ContractExtract, employer_nif_mismatch: bool | None) -> None:
        self.extract = extract
        self.employer_nif_mismatch = employer_nif_mismatch


async def _cached_extract(
    session,
    crypto,
    *,
    company_id: uuid.UUID,
    sha256: str | None,
    file_id: uuid.UUID,
) -> _CachedExtract | None:
    if not sha256:
        return None
    found = (
        await session.execute(
            select(ContractInbox, EmploymentDocument)
            .join(StoredFile, StoredFile.id == ContractInbox.file_id)
            .outerjoin(
                EmploymentDocument,
                EmploymentDocument.id == ContractInbox.employment_document_id,
            )
            .where(
                ContractInbox.company_id == company_id,
                StoredFile.sha256 == sha256,
                StoredFile.id != file_id,
                ContractInbox.status.in_(("MATCHED", "UNMATCHED")),
            )
            .order_by(ContractInbox.processed_at.desc())
            .limit(1)
        )
    ).first()
    if found is None:
        return None
    prior, doc = found
    name = _decrypt(crypto.decrypt_name, prior.name_enc)
    nif = _decrypt(crypto.decrypt_nif, prior.nif_enc)
    niss = _decrypt(crypto.decrypt_niss, prior.niss_enc)
    kind = prior.doc_kind or (doc.doc_kind if doc is not None else None)
    signed = prior.signed_on if prior.signed_on is not None else (doc.signed_on if doc else None)
    term_end = (
        prior.term_end_on if prior.term_end_on is not None else (doc.term_end_on if doc else None)
    )
    if kind is None or not any((name, nif, niss)):
        return None
    return _CachedExtract(
        ContractExtract(
            doc_kind=kind,
            signed_on=signed,
            term_end_on=term_end,
            leftover={"extractor": "sha256"},
            full_name=name,
            nif=nif,
            niss=niss,
            employer_legal_name=prior.employer_legal_name,
            employer_address=prior.employer_address,
            employer_niss=_decrypt(crypto.decrypt_niss, prior.employer_niss_enc),
            signatory_name=prior.signatory_name,
            employee_address=_decrypt(crypto.decrypt_address, prior.employee_address_enc),
            term_started_on=prior.term_started_on,
            converted_on=prior.converted_on,
            declared_on=prior.declared_on,
            signing_place=prior.signing_place,
        ),
        prior.employer_nif_mismatch,
    )


async def _document_for_hash(
    session,
    employee_id: uuid.UUID,
    sha256: str | None,
) -> EmploymentDocument | None:
    if not sha256:
        return None
    return (
        await session.execute(
            select(EmploymentDocument)
            .join(StoredFile, StoredFile.id == EmploymentDocument.file_id)
            .where(
                EmploymentDocument.employee_id == employee_id,
                StoredFile.sha256 == sha256,
                EmploymentDocument.review_status == "REVIEWED",
            )
            .order_by(EmploymentDocument.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _candidate(crypto, employee: Employee) -> MatchCandidate:
    name = None
    if employee.name_enc is not None:
        try:
            name = normalize_person_name(crypto.decrypt_name(employee.name_enc))
        except Exception:
            name = None
    return MatchCandidate(
        employee_id=employee.id,
        nif_hash=employee.nif_hash,
        niss_hash=employee.niss_hash,
        name_norm=name,
    )


def _employer_nif_mismatch(company: Company, crypto, employer_nif: str | None) -> bool | None:
    extracted = _digits(employer_nif)
    if not extracted or company.nif_enc is None:
        return None
    try:
        stored = _digits(crypto.decrypt_nif(company.nif_enc))
    except Exception:
        return None
    if not stored:
        return None
    return stored != extracted


async def _remember_employee_nif(session, employee: Employee, crypto, nif: str | None) -> bool:
    """Store the PDF NIF when the employee has none. True when it conflicts."""
    if not _digits(nif):
        return False
    digest = crypto.nif_hash(nif or "")
    if employee.nif_hash == digest:
        return False
    if employee.nif_hash is not None:
        return True
    other = (
        await session.execute(
            select(Employee.id).where(
                Employee.company_id == employee.company_id,
                Employee.nif_hash == digest,
                Employee.deleted_at.is_(None),
                Employee.id != employee.id,
            )
        )
    ).scalar_one_or_none()
    if other is not None:
        return True
    employee.nif_enc = crypto.encrypt_nif(nif or "")
    employee.nif_hash = digest
    return False


def _fail(inbox: ContractInbox, error: str) -> None:
    inbox.status = "FAILED"
    inbox.error = error
    inbox.processed_at = datetime.now(UTC)
