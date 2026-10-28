"""Compare LLM contract extract to SS employment (DEV-836). Does not rewrite employment."""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Employee, Employment, EmploymentDocument, StoredFile
from app.services.contract_llm import ContractExtract, get_contract_extractor
from app.services.domain_events import emit_domain_event
from app.storage import get_object_storage

logger = logging.getLogger(__name__)


class ContractReviewRetry(Exception):
    """Transient read failure. Cloud Tasks may deliver the job once more."""


def ss_bucket(modality: str) -> str:
    if modality == "SEM_TERMO":
        return "SEM_TERMO"
    if modality in {"TERMO_CERTO", "TERMO_INCERTO"}:
        return "TERMO"
    return "OTHER"


def compute_matches_ss(
    *,
    ss_modality: str,
    ss_started_on,
    ss_ended_on,
    doc_kind: str,
    signed_on,
    term_end_on,
) -> str:
    if ss_bucket(ss_modality) != doc_kind and not (
        doc_kind == "CONVERSION" and ss_bucket(ss_modality) == "SEM_TERMO"
    ):
        return "MISMATCH"
    if signed_on is not None and signed_on != ss_started_on:
        return "MISMATCH"
    if doc_kind == "TERMO" and ss_ended_on is None and term_end_on is not None:
        return "MISMATCH"
    return "MATCH"


def apply_contract_extract(doc: EmploymentDocument, extract, employment) -> str:
    """Write typed columns from one extract. Returns the review event type."""
    doc.doc_kind = extract.doc_kind
    doc.signed_on = extract.signed_on
    doc.term_end_on = extract.term_end_on
    doc.employer_legal_name = extract.employer_legal_name
    doc.employer_address = extract.employer_address
    doc.signatory_name = extract.signatory_name
    doc.term_started_on = extract.term_started_on
    doc.converted_on = extract.converted_on
    doc.declared_on = extract.declared_on
    doc.signing_place = extract.signing_place
    doc.review_leftover = extract.leftover
    doc.review_error = None
    doc.review_status = "REVIEWED"
    if employment is None:
        doc.matches_ss = "UNKNOWN"
    else:
        doc.matches_ss = compute_matches_ss(
            ss_modality=employment.contract_modality,
            ss_started_on=employment.started_on,
            ss_ended_on=employment.ended_on,
            doc_kind=extract.doc_kind,
            signed_on=extract.signed_on,
            term_end_on=extract.term_end_on,
        )
    if doc.matches_ss == "MISMATCH":
        return "CONTRACT_SS_MISMATCH"
    return "CONTRACT_REVIEWED"


async def _reviewed_same_hash(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None,
    sha256: str | None,
    file_id: uuid.UUID,
) -> ContractExtract | None:
    if company_id is None or not sha256:
        return None
    doc = (
        await session.execute(
            select(EmploymentDocument)
            .join(StoredFile, StoredFile.id == EmploymentDocument.file_id)
            .join(Employee, Employee.id == EmploymentDocument.employee_id)
            .where(
                Employee.company_id == company_id,
                StoredFile.sha256 == sha256,
                StoredFile.id != file_id,
                EmploymentDocument.review_status == "REVIEWED",
                EmploymentDocument.doc_kind.is_not(None),
            )
            .order_by(EmploymentDocument.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if doc is None or doc.doc_kind is None:
        return None
    from app.security.dek_store import get_or_create_pii_crypto

    crypto = (
        await get_or_create_pii_crypto(session, company_id=company_id)
        if company_id is not None
        else None
    )
    address = None
    employer_niss = None
    if crypto is not None:
        address = _decrypt_blob(crypto.decrypt_address, doc.employee_address_enc)
        employer_niss = _decrypt_blob(crypto.decrypt_niss, doc.employer_niss_enc)
    return ContractExtract(
        doc_kind=doc.doc_kind,
        signed_on=doc.signed_on,
        term_end_on=doc.term_end_on,
        leftover={"extractor": "sha256"},
        employer_legal_name=doc.employer_legal_name,
        employer_address=doc.employer_address,
        employer_niss=employer_niss,
        signatory_name=doc.signatory_name,
        employee_address=address,
        term_started_on=doc.term_started_on,
        converted_on=doc.converted_on,
        declared_on=doc.declared_on,
        signing_place=doc.signing_place,
    )


def review_event_payload(doc: EmploymentDocument, employee: Employee, employment) -> dict:
    payload = {
        "employment_document_id": str(doc.id),
        "employee_id": str(doc.employee_id),
        "company_id": str(employee.company_id) if employee.company_id else None,
        "doc_kind": doc.doc_kind,
        "signed_on": doc.signed_on.isoformat() if doc.signed_on else None,
        "term_end_on": doc.term_end_on.isoformat() if doc.term_end_on else None,
        "matches_ss": doc.matches_ss,
    }
    if employment is not None:
        payload["ss_modality"] = employment.contract_modality
        payload["ss_started_on"] = employment.started_on.isoformat()
    return payload


async def review_employment_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    *,
    retry: bool = False,
) -> EmploymentDocument | None:
    doc = (
        await session.execute(
            select(EmploymentDocument).where(EmploymentDocument.id == document_id)
        )
    ).scalar_one_or_none()
    if doc is None or doc.review_status != "PENDING":
        return doc

    stored = await session.get(StoredFile, doc.file_id)
    employment = (
        await session.get(Employment, doc.employment_id)
        if doc.employment_id is not None
        else None
    )
    employee = await session.get(Employee, doc.employee_id)
    if stored is None or employee is None:
        doc.review_status = "FAILED"
        doc.review_error = "missing_file_or_employee"
        return doc

    company = (
        await session.get(Company, employee.company_id)
        if employee.company_id is not None
        else None
    )
    # A reused extract does not carry the NIFs. Read the PDF again while either
    # profile NIF is still empty, so the first real read can fill them.
    extract = None
    if employee.nif_enc is not None and company is not None and company.nif_enc is not None:
        extract = await _reviewed_same_hash(
            session,
            company_id=employee.company_id,
            sha256=stored.sha256,
            file_id=stored.id,
        )
    if extract is not None:
        logger.info("contract review reused extract document=%s", document_id)
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
            logger.warning("contract review failed document=%s: %s", document_id, type(exc).__name__)
            if retry:
                raise ContractReviewRetry from exc
            doc.review_status = "FAILED"
            doc.review_error = type(exc).__name__
            await emit_domain_event(
                session,
                event_type="CONTRACT_REVIEW_FAILED",
                source_entity_type="EMPLOYMENT_DOCUMENT",
                source_entity_id=doc.id,
                actor_id=None,
                company_id=employee.company_id,
                payload={"employment_document_id": str(doc.id)},
            )
            return doc

    event_type = apply_contract_extract(doc, extract, employment)
    if company is not None and employee.company_id is not None:
        from app.security.dek_store import get_or_create_pii_crypto

        crypto = await get_or_create_pii_crypto(session, company_id=employee.company_id)
        await remember_minuta_profile(session, company, employee, crypto, extract, doc)
    payload = review_event_payload(doc, employee, employment)
    await emit_domain_event(
        session,
        event_type=event_type,
        source_entity_type="EMPLOYMENT_DOCUMENT",
        source_entity_id=doc.id,
        actor_id=None,
        company_id=employee.company_id,
        payload=payload,
    )
    return doc


def _decrypt_blob(fn, blob: bytes | None) -> str | None:
    if blob is None:
        return None
    try:
        text = fn(blob)
    except Exception:
        return None
    cleaned = str(text).strip() if text else ""
    return cleaned or None


def _same_name(left: str, right: str) -> bool:
    return " ".join(left.lower().split()) == " ".join(right.lower().split())


async def remember_minuta_profile(session, company, employee, crypto, extract: ContractExtract, doc) -> bool:
    """Fill empty profile fields from a contract extract. True when the legal name differs."""
    from sqlalchemy import select

    from app.models import RequestCase
    from app.services.contract_inbox import _digits, _remember_employee_nif
    from app.services.minuta_facts import copy_case_facts

    if employee is not None and extract.employee_address and employee.address_enc is None:
        employee.address_enc = crypto.encrypt_address(extract.employee_address)
    if extract.employee_address and doc is not None:
        doc.employee_address_enc = crypto.encrypt_address(extract.employee_address)
    if (
        employee is not None
        and extract.full_name
        and extract.full_name.strip()
        and employee.name_enc is None
    ):
        employee.name_enc = crypto.encrypt_name(extract.full_name)
    if extract.employer_address and not company.registered_address:
        company.registered_address = extract.employer_address.strip()
    if extract.signatory_name and not company.signatory_name:
        company.signatory_name = extract.signatory_name.strip()
    if _digits(extract.employer_niss) and company.employer_niss_enc is None:
        company.employer_niss_enc = crypto.encrypt_niss(extract.employer_niss)
        if company.employer_niss_hash is None:
            company.employer_niss_hash = crypto.niss_hash(extract.employer_niss)
    if _digits(extract.employer_niss) and doc is not None:
        doc.employer_niss_enc = crypto.encrypt_niss(extract.employer_niss)
    if _digits(extract.employer_nif) and company.nif_enc is None:
        company.nif_enc = crypto.encrypt_nif(extract.employer_nif)
    if employee is not None:
        conflict = await _remember_employee_nif(session, employee, crypto, extract.nif)
        if conflict and doc is not None and hasattr(doc, "review_leftover"):
            leftover = dict(doc.review_leftover or {})
            leftover["nif_conflict"] = True
            doc.review_leftover = leftover
        open_cases = (
            await session.execute(
                select(RequestCase).where(
                    RequestCase.employee_id == employee.id,
                    RequestCase.closed_at.is_(None),
                )
            )
        ).scalars().all()
        for case in open_cases:
            await copy_case_facts(session, case, only_empty=True)
    printed = (extract.employer_legal_name or "").strip()
    return bool(printed and company.legal_name and not _same_name(printed, company.legal_name))
