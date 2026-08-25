"""Compare LLM contract extract to SS employment (DEV-836). Does not rewrite employment."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, Employment, EmploymentDocument, StoredFile
from app.services.contract_llm import get_contract_extractor
from app.services.domain_events import emit_domain_event
from app.storage import get_object_storage

logger = logging.getLogger(__name__)


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


async def review_employment_document(
    session: AsyncSession, document_id: uuid.UUID
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

    try:
        data = get_object_storage().get_bytes(stored.gcs_path)
        extract = get_contract_extractor().extract(
            data,
            mime_type=stored.mime_type,
            filename=stored.original_filename,
        )
    except Exception as exc:
        logger.warning("contract review failed document=%s: %s", document_id, exc)
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

    doc.doc_kind = extract.doc_kind
    doc.signed_on = extract.signed_on
    doc.term_end_on = extract.term_end_on
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

    event_type = (
        "CONTRACT_SS_MISMATCH" if doc.matches_ss == "MISMATCH" else "CONTRACT_REVIEWED"
    )
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
