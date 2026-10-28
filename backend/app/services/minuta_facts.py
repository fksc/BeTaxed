"""Minuta token catalogue and the request-case snapshot. DEV-882, KB/05."""

from __future__ import annotations

import re
import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Employee, Employment, EmploymentDocument, RequestCase
from app.security.dek_store import get_or_create_pii_crypto
from app.security.pii import PiiCrypto

_TOKEN = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

_PT_MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
_EN_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

# key, group. Date keys also publish `_pt` and `_en` at fill time.
CATALOGUE: tuple[tuple[str, str], ...] = (
    ("company_name", "company"),
    ("company_address", "company"),
    ("company_nif", "company"),
    ("company_niss", "company"),
    ("company_signatory_name", "company"),
    ("person_name", "person"),
    ("person_address", "person"),
    ("person_nif", "person"),
    ("person_niss", "person"),
    ("contract_started_on", "case"),
    ("converted_on", "case"),
    ("declared_on", "case"),
    ("signed_place", "case"),
)
DATE_KEYS = frozenset({"contract_started_on", "converted_on", "declared_on"})
TEXT_FACTS = (
    "person_name",
    "person_address",
    "company_name",
    "company_address",
    "company_signatory_name",
    "signed_place",
)
SECRET_FACTS = {
    "person_nif": "person_nif_enc",
    "person_niss": "person_niss_enc",
    "company_nif": "company_nif_enc",
    "company_niss": "company_niss_enc",
}


def catalogue() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, group in CATALOGUE:
        rows.append({"key": key, "group": group})
        if key in DATE_KEYS:
            rows.append({"key": f"{key}_pt", "group": "date"})
            rows.append({"key": f"{key}_en", "group": "date"})
    return rows


def format_date_pt(value: date) -> str:
    return f"{value.day} de {_PT_MONTHS[value.month - 1]} de {value.year}"


def format_date_en(value: date) -> str:
    return f"{_EN_MONTHS[value.month - 1]} {value.day}, {value.year}"


def render_minuta(body_html: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return values.get(match.group(1), "")

    return _TOKEN.sub(replace, body_html)


def fact_values(case: RequestCase, crypto: PiiCrypto) -> dict[str, str]:
    values = {
        "company_name": case.company_name or "",
        "company_address": case.company_address or "",
        "company_nif": _decrypt(crypto.decrypt_nif, case.company_nif_enc),
        "company_niss": _decrypt(crypto.decrypt_niss, case.company_niss_enc),
        "company_signatory_name": case.company_signatory_name or "",
        "person_name": case.person_name or "",
        "person_address": case.person_address or "",
        "person_nif": _decrypt(crypto.decrypt_nif, case.person_nif_enc),
        "person_niss": _decrypt(crypto.decrypt_niss, case.person_niss_enc),
        "signed_place": case.signed_place or "",
    }
    for key in DATE_KEYS:
        raw = getattr(case, key)
        values[key] = raw.isoformat() if isinstance(raw, date) else ""
        values[f"{key}_pt"] = format_date_pt(raw) if isinstance(raw, date) else ""
        values[f"{key}_en"] = format_date_en(raw) if isinstance(raw, date) else ""
    return values


def _decrypt(fn, blob: bytes | None) -> str:
    if blob is None:
        return ""
    try:
        return fn(blob) or ""
    except Exception:
        return ""


def _set_text(case: RequestCase, attr: str, value: str | None, *, only_empty: bool) -> None:
    current = getattr(case, attr)
    if only_empty and current:
        return
    if value is None:
        return
    cleaned = value.strip()
    if not cleaned and only_empty:
        return
    setattr(case, attr, cleaned or None)


def _set_blob(case: RequestCase, attr: str, value: bytes | None, *, only_empty: bool) -> None:
    if only_empty and getattr(case, attr) is not None:
        return
    if value is None and only_empty:
        return
    if value is not None or not only_empty:
        if value is not None:
            setattr(case, attr, value)


def _set_date(case: RequestCase, attr: str, value: date | None, *, only_empty: bool) -> None:
    if only_empty and getattr(case, attr) is not None:
        return
    if value is None and only_empty:
        return
    if value is not None:
        setattr(case, attr, value)


async def copy_case_facts(
    session: AsyncSession, case: RequestCase, *, only_empty: bool
) -> None:
    company = await session.get(Company, case.company_id)
    employee = await session.get(Employee, case.employee_id)
    employment = await session.get(Employment, case.employment_id)
    if company is None or employee is None:
        raise HTTPException(status_code=404, detail="Case profile not found.")
    crypto = await get_or_create_pii_crypto(session, company_id=case.company_id)
    term_started, converted, declared, place = await _paper_dates(
        session, employee.id, employment, case
    )
    _set_text(case, "person_name", _decrypt(crypto.decrypt_name, employee.name_enc), only_empty=only_empty)
    _set_text(
        case,
        "person_address",
        _decrypt(crypto.decrypt_address, employee.address_enc),
        only_empty=only_empty,
    )
    _set_blob(case, "person_nif_enc", employee.nif_enc, only_empty=only_empty)
    _set_blob(case, "person_niss_enc", employee.niss_enc, only_empty=only_empty)
    _set_text(case, "company_name", company.legal_name, only_empty=only_empty)
    _set_text(case, "company_address", company.registered_address, only_empty=only_empty)
    _set_text(case, "company_signatory_name", company.signatory_name, only_empty=only_empty)
    _set_blob(case, "company_nif_enc", company.nif_enc, only_empty=only_empty)
    _set_blob(case, "company_niss_enc", company.employer_niss_enc, only_empty=only_empty)
    _set_date(case, "contract_started_on", term_started, only_empty=only_empty)
    _set_date(case, "converted_on", converted, only_empty=only_empty)
    _set_date(case, "declared_on", declared, only_empty=only_empty)
    _set_text(case, "signed_place", place, only_empty=only_empty)


async def _paper_dates(
    session: AsyncSession,
    employee_id: uuid.UUID,
    employment: Employment | None,
    case: RequestCase,
) -> tuple[date | None, date | None, date | None, str | None]:
    docs = (
        (
            await session.execute(
                select(EmploymentDocument)
                .where(EmploymentDocument.employee_id == employee_id)
                .order_by(EmploymentDocument.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    term_started = None
    converted = None
    declared = None
    place = None
    for doc in docs:
        if term_started is None:
            term_started = doc.term_started_on or (
                doc.signed_on if doc.doc_kind == "TERMO" else None
            )
        if converted is None:
            converted = doc.converted_on or (
                doc.signed_on if doc.doc_kind in {"CONVERSION", "SEM_TERMO"} else None
            )
        if declared is None:
            declared = doc.declared_on
        if place is None:
            place = doc.signing_place
    if term_started is None and employment is not None:
        term_started = employment.started_on
    if converted is None:
        converted = case.benefit_starts_on
    return term_started, converted, declared, place


async def update_case_facts(
    session: AsyncSession, case: RequestCase, fields: dict
) -> None:
    crypto = await get_or_create_pii_crypto(session, company_id=case.company_id)
    for key in TEXT_FACTS:
        if key not in fields:
            continue
        raw = fields.get(key)
        case_attr = key
        if raw is None or str(raw).strip() == "":
            setattr(case, case_attr, None)
        else:
            setattr(case, case_attr, str(raw).strip())
    for key in DATE_KEYS:
        if key not in fields:
            continue
        raw = fields.get(key)
        if raw is None or str(raw).strip() == "":
            setattr(case, key, None)
        else:
            setattr(case, key, date.fromisoformat(str(raw)[:10]))
    secret_fns = {
        "person_nif": crypto.encrypt_nif,
        "person_niss": crypto.encrypt_niss,
        "company_nif": crypto.encrypt_nif,
        "company_niss": crypto.encrypt_niss,
    }
    for key, column in SECRET_FACTS.items():
        if key not in fields:
            continue
        raw = fields.get(key)
        if raw is None or str(raw).strip() == "":
            setattr(case, column, None)
        else:
            setattr(case, column, secret_fns[key](str(raw)))


def staff_fact_fields(case: RequestCase, crypto: PiiCrypto) -> dict:
    values = fact_values(case, crypto)
    return {
        "company_name": case.company_name,
        "person_name": case.person_name,
        "person_address": case.person_address,
        "person_nif": values["person_nif"] or None,
        "person_niss": values["person_niss"] or None,
        "company_address": case.company_address,
        "company_signatory_name": case.company_signatory_name,
        "company_nif": values["company_nif"] or None,
        "company_niss": values["company_niss"] or None,
        "contract_started_on": case.contract_started_on,
        "converted_on": case.converted_on,
        "declared_on": case.declared_on,
        "signed_place": case.signed_place,
    }
