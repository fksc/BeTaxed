"""Persist parsed SS exports into ss_batch + raw tables (DEV-831)."""

from __future__ import annotations

import base64
import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    SsBatch,
    SsBatchFile,
    SsRawContrato,
    SsRawLeave,
    SsRawVinculo,
    StoredFile,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.security.pii import PiiCrypto
from app.services.ss_headers import fold_header
from app.services.ss_parser import (
    ParsedContrato,
    ParsedLeave,
    ParsedSsExport,
    ParsedVinculo,
    SsParseError,
    SsParseWarning,
    SsSourceFile,
    current_contratos,
    parse_ss_files,
)
from app.storage import build_object_name, get_object_storage, sha256_hex

_XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
_CSV_MIME = "text/csv"
_NISS_RE = re.compile(r"\d{9,11}")


@dataclass(frozen=True)
class SsIngestResult:
    batch: SsBatch
    vinculo_count: int
    contrato_count: int
    leave_count: int
    warnings: list[SsParseWarning]
    current_contrato_ids: list[uuid.UUID]


async def ingest_ss_export(
    session: AsyncSession,
    *,
    files: list[SsSourceFile],
    period_year_month: date,
    company_id: uuid.UUID | None = None,
    intake_id: uuid.UUID | None = None,
    uploaded_by: uuid.UUID | None = None,
) -> SsIngestResult:
    """Parse files and write raw rows. Does not apply to employee tables."""
    if company_id is None and intake_id is None:
        raise ValueError("company_id or intake_id required")
    if company_id is not None and intake_id is not None:
        raise ValueError("only one of company_id or intake_id")
    if period_year_month.day != 1:
        raise ValueError("period_year_month must be the first of the month")

    crypto = await get_or_create_pii_crypto(
        session, company_id=company_id, intake_id=intake_id
    )
    stored_files = _store_files(
        files,
        company_id=company_id,
        intake_id=intake_id,
        uploaded_by=uploaded_by,
    )
    session.add_all(stored_files)
    await session.flush()

    batch = SsBatch(
        company_id=company_id,
        intake_id=intake_id,
        period_year_month=period_year_month,
        uploaded_by=uploaded_by,
        parse_status="PENDING",
    )
    session.add(batch)
    await session.flush()

    try:
        parsed = parse_ss_files(files)
    except SsParseError as exc:
        batch.parse_status = "FAILED"
        batch.parse_error = exc.message
        _add_batch_files(session, batch.id, stored_files, _file_kinds_or_other(files))
        await session.flush()
        return SsIngestResult(
            batch=batch,
            vinculo_count=0,
            contrato_count=0,
            leave_count=0,
            warnings=[],
            current_contrato_ids=[],
        )

    _add_batch_files(session, batch.id, stored_files, list(parsed.file_kinds))

    if parsed.employer_niss:
        batch.employer_niss_hash = crypto.niss_hash(parsed.employer_niss)
        batch.employer_niss_enc = crypto.encrypt_niss(parsed.employer_niss)
    batch.export_label = parsed.export_label or files[0].filename

    vinculo_rows = [
        _to_raw_vinculo(batch.id, row, crypto) for row in parsed.vinculos
    ]
    contrato_rows = [
        _to_raw_contrato(batch.id, row, crypto) for row in parsed.contratos
    ]
    leave_rows = [_to_raw_leave(batch.id, row, crypto) for row in parsed.leaves]
    session.add_all(vinculo_rows)
    session.add_all(contrato_rows)
    session.add_all(leave_rows)
    batch.leave_declared = parsed.leave_declared
    await session.flush()

    current = _current_raw_contratos(contrato_rows, parsed)
    batch.parse_status = "PARSED"
    await session.flush()
    return SsIngestResult(
        batch=batch,
        vinculo_count=len(vinculo_rows),
        contrato_count=len(contrato_rows),
        leave_count=len(leave_rows),
        warnings=parsed.warnings,
        current_contrato_ids=[row.id for row in current],
    )


def _add_batch_files(
    session: AsyncSession,
    batch_id: uuid.UUID,
    stored_files: list[StoredFile],
    kinds: list[str],
) -> None:
    for stored, kind in zip(stored_files, kinds, strict=True):
        session.add(SsBatchFile(batch_id=batch_id, file_id=stored.id, kind=kind))


def _file_kinds_or_other(files: list[SsSourceFile]) -> list[str]:
    """Best-effort kind for ss_batch_file before / without a successful parse."""
    if len(files) == 1:
        return ["COMBINED_XLSX"]
    kinds: list[str] = []
    for item in files:
        folded = item.filename.casefold()
        if "vinculo" in folded:
            kinds.append("VINCULOS")
        elif "contrato" in folded:
            kinds.append("CONTRATOS")
        elif (
            "remunerac" in folded
            or "ausencia" in folded
            or "leave" in folded
        ):
            kinds.append("REMUNERACOES")
        else:
            kinds.append("OTHER")
    return kinds


def _store_files(
    files: list[SsSourceFile],
    *,
    company_id: uuid.UUID | None,
    intake_id: uuid.UUID | None,
    uploaded_by: uuid.UUID | None,
) -> list[StoredFile]:
    storage = get_object_storage()
    stored: list[StoredFile] = []
    for item in files:
        object_name = build_object_name(
            company_id=company_id,
            intake_id=intake_id,
            filename=item.filename,
        )
        path = storage.put_bytes(
            item.content,
            object_name=object_name,
            content_type=_mime_for(item.filename),
        )
        stored.append(
            StoredFile(
                company_id=company_id,
                intake_id=intake_id,
                gcs_path=path,
                sha256=sha256_hex(item.content),
                mime_type=_mime_for(item.filename),
                original_filename=item.filename,
                kind="SS_EXPORT",
                uploaded_by=uploaded_by,
            )
        )
    return stored


def _mime_for(filename: str) -> str:
    if filename.lower().endswith(".csv"):
        return _CSV_MIME
    return _XLSX_MIME


def _to_raw_vinculo(
    batch_id: uuid.UUID, row: ParsedVinculo, crypto: PiiCrypto
) -> SsRawVinculo:
    return SsRawVinculo(
        batch_id=batch_id,
        source_row=row.source_row,
        niss_hash=crypto.niss_hash(row.niss),
        niss_enc=crypto.encrypt_niss(row.niss),
        name_enc=crypto.encrypt_name(row.nome) if row.nome else None,
        dob_enc=crypto.encrypt_dob(row.dob) if row.dob else None,
        vinculo_raw=row.vinculo_raw,
        communicated_on=row.communicated_on,
        started_on=row.started_on,
        ended_on=row.ended_on,
        rate_from=row.rate_from,
        rate_to=row.rate_to,
        taxa_pct=row.taxa_pct,
        workplace_ss_label=row.workplace_ss_label,
        leftover=_leftover_for_storage(row.leftover, crypto),
    )


def _to_raw_contrato(
    batch_id: uuid.UUID, row: ParsedContrato, crypto: PiiCrypto
) -> SsRawContrato:
    return SsRawContrato(
        batch_id=batch_id,
        source_row=row.source_row,
        niss_hash=crypto.niss_hash(row.niss),
        niss_enc=crypto.encrypt_niss(row.niss),
        name_enc=crypto.encrypt_name(row.nome) if row.nome else None,
        modality_raw=row.modality_raw,
        work_mode_raw=row.work_mode_raw,
        contract_started_on=row.contract_started_on,
        contract_ended_on=row.contract_ended_on,
        profession_raw=row.profession_raw,
        percent_work=row.percent_work,
        hours_work=row.hours_work,
        days_work=row.days_work,
        motivo_raw=row.motivo_raw,
        rendimento_from=row.rendimento_from,
        rendimento_to=row.rendimento_to,
        base_salary=row.base_salary,
        leftover=_leftover_for_storage(row.leftover, crypto),
    )


def _to_raw_leave(
    batch_id: uuid.UUID, row: ParsedLeave, crypto: PiiCrypto
) -> SsRawLeave:
    return SsRawLeave(
        batch_id=batch_id,
        source_row=row.source_row,
        niss_hash=crypto.niss_hash(row.niss),
        niss_enc=crypto.encrypt_niss(row.niss),
        leave_type=row.leave_type,
        started_on=row.started_on,
        ended_on=row.ended_on,
        leftover=_leftover_for_storage(row.leftover, crypto),
    )


def _leftover_for_storage(
    leftover: dict[str, Any], crypto: PiiCrypto
) -> dict[str, Any] | None:
    if not leftover:
        return None
    stored: dict[str, Any] = {}
    for key, value in leftover.items():
        if value is None or value == "":
            continue
        if "niss" in fold_header(str(key)):
            matches = _NISS_RE.findall(str(value))
            if matches:
                stored[key] = {
                    "niss_enc": [_enc_b64(crypto, match) for match in matches],
                    "niss_hash": [_hash_hex(crypto, match) for match in matches],
                }
            continue
        stored[key] = value
    return stored or None


def rekey_leftover_niss(
    leftover: dict[str, Any] | None,
    intake_crypto: PiiCrypto,
    company_crypto: PiiCrypto,
) -> dict[str, Any] | None:
    """Decrypt leftover NISS with intake DEK; re-encrypt and re-HMAC for company.

    Hash-only leftovers (pre-DEV-848) cannot be re-HMAC'd and are dropped.
    """
    if not leftover:
        return leftover
    out: dict[str, Any] = {}
    for key, value in leftover.items():
        if not isinstance(value, dict) or (
            "niss_enc" not in value and "niss_hash" not in value
        ):
            out[key] = value
            continue
        encs = value.get("niss_enc") or []
        if not encs:
            continue
        niss_enc: list[str] = []
        niss_hash: list[str] = []
        for blob in encs:
            niss = intake_crypto.decrypt_niss(base64.b64decode(blob))
            niss_enc.append(_enc_b64(company_crypto, niss))
            niss_hash.append(_hash_hex(company_crypto, niss))
        out[key] = {"niss_enc": niss_enc, "niss_hash": niss_hash}
    return out or None


def _enc_b64(crypto: PiiCrypto, niss: str) -> str:
    return base64.b64encode(crypto.encrypt_niss(niss)).decode("ascii")


def _hash_hex(crypto: PiiCrypto, niss: str) -> str:
    return crypto.niss_hash(niss).hex()


def _current_raw_contratos(
    rows: list[SsRawContrato], parsed: ParsedSsExport
) -> list[SsRawContrato]:
    current_keys = {
        (row.niss, row.source_row) for row in current_contratos(parsed.contratos)
    }
    return [
        raw
        for raw, parsed_row in zip(rows, parsed.contratos, strict=True)
        if (parsed_row.niss, parsed_row.source_row) in current_keys
    ]
