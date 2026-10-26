"""Request-case pipeline. Operations are assigned to stages. DEV-882, KB/05."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Company,
    Employee,
    Employment,
    MinutaTemplate,
    PipelineOperation,
    PipelineStage,
    PipelineStageOperation,
    RejectionReason,
    RequestCase,
    RequestCaseFile,
    RequestCaseMinuta,
    SsBatch,
    StoredFile,
    UserBase,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.services.teaser import remaining_benefit_months
from app.storage import build_object_name, get_object_storage, sha256_hex

_TOKEN = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
_FIXED = frozenset({"TERMO_CERTO", "TERMO_INCERTO"})
_CLOSE = frozenset({"CLOSE_WON", "CLOSE_LOST"})


def _moves_for_stage(
    links: list[PipelineStageOperation],
    ops: dict[uuid.UUID, str],
    stage_id: uuid.UUID,
) -> list[dict]:
    moves: list[dict] = []
    for link in links:
        if link.stage_id != stage_id:
            continue
        code = ops.get(link.operation_id)
        if not code:
            continue
        if link.next_stage_id is not None:
            moves.append(
                {"operation": code, "stage_id": link.next_stage_id, "outcome": None}
            )
        if link.next_won_stage_id is not None:
            moves.append(
                {
                    "operation": code,
                    "stage_id": link.next_won_stage_id,
                    "outcome": "favorable",
                }
            )
        if link.next_lost_stage_id is not None:
            moves.append(
                {
                    "operation": code,
                    "stage_id": link.next_lost_stage_id,
                    "outcome": "unfavorable",
                }
            )
        if link.next_claim_stage_id is not None:
            moves.append(
                {
                    "operation": code,
                    "stage_id": link.next_claim_stage_id,
                    "outcome": "claim",
                }
            )
    return moves


_OPEN_LINE = ("probation", "ready", "awaiting_decision")
_FIXED_LINE = ("minuta", "signature", "ready", "awaiting_decision")


def earlier_stage_code(path: str, stage_code: str) -> str | None:
    """Previous stage when this case has no visit history yet."""
    if stage_code == "claim":
        return "awaiting_decision"
    if stage_code in {"closed_won", "closed_lost"}:
        return "awaiting_decision"
    line = _OPEN_LINE if path == "OPEN_CONTRACT" else _FIXED_LINE
    if stage_code not in line:
        return None
    index = line.index(stage_code)
    if index == 0:
        return None
    return line[index - 1]


def path_for_modality(modality: str | None) -> str:
    if modality in _FIXED:
        return "FIXED_TERM"
    return "OPEN_CONTRACT"


def render_minuta(body_html: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return values.get(match.group(1), "")

    return _TOKEN.sub(replace, body_html)


def decision_stage_id(
    assignment: PipelineStageOperation,
    outcome: str,
    *,
    blocks_claim: bool,
) -> uuid.UUID:
    if outcome == "favorable":
        if assignment.next_won_stage_id is None:
            raise HTTPException(status_code=400, detail="This stage cannot close won.")
        return assignment.next_won_stage_id
    if outcome == "unfavorable":
        if assignment.next_lost_stage_id is None:
            raise HTTPException(status_code=400, detail="This stage cannot close lost.")
        return assignment.next_lost_stage_id
    if outcome == "claim":
        if blocks_claim or assignment.next_claim_stage_id is None:
            raise HTTPException(status_code=400, detail="A claim is not available.")
        return assignment.next_claim_stage_id
    raise HTTPException(status_code=400, detail="Unknown decision.")


async def list_pipeline(session: AsyncSession) -> list[dict]:
    stages = (
        (
            await session.execute(
                select(PipelineStage)
                .where(PipelineStage.is_active.is_(True))
                .order_by(PipelineStage.position)
            )
        )
        .scalars()
        .all()
    )
    ops = {
        row.id: row
        for row in (await session.execute(select(PipelineOperation))).scalars().all()
    }
    links = (
        (await session.execute(select(PipelineStageOperation))).scalars().all()
    )
    by_stage: dict[uuid.UUID, list[str]] = {}
    for link in links:
        operation = ops.get(link.operation_id)
        if operation is None:
            continue
        by_stage.setdefault(link.stage_id, []).append(operation.code)
    return [
        {
            "id": stage.id,
            "code": stage.code,
            "name": stage.name,
            "stage_type": stage.stage_type,
            "position": stage.position,
            "entry_path": stage.entry_path,
            "operations": by_stage.get(stage.id, []),
        }
        for stage in stages
    ]


async def list_request_cases(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None,
    staff: bool,
) -> list[dict]:
    query = select(RequestCase, PipelineStage, Company, Employee, Employment).join(
        PipelineStage, PipelineStage.id == RequestCase.stage_id
    ).join(Company, Company.id == RequestCase.company_id).join(
        Employee, Employee.id == RequestCase.employee_id
    ).join(Employment, Employment.id == RequestCase.employment_id)
    if company_id is not None:
        query = query.where(RequestCase.company_id == company_id)
    rows = (await session.execute(query.order_by(RequestCase.opened_at.desc()))).all()
    if not rows:
        return []
    company_ids = {case.company_id for case, *_ in rows}
    from app.services.contracts import _display_name

    cryptos = {
        cid: await get_or_create_pii_crypto(session, company_id=cid) for cid in company_ids
    }
    case_ids = [case.id for case, *_ in rows]
    minutas = (
        (
            await session.execute(
                select(RequestCaseMinuta)
                .where(RequestCaseMinuta.request_case_id.in_(case_ids))
                .order_by(RequestCaseMinuta.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest_minuta: dict[uuid.UUID, RequestCaseMinuta] = {}
    for minuta in minutas:
        latest_minuta.setdefault(minuta.request_case_id, minuta)
    notices = (
        (
            await session.execute(
                select(RequestCaseFile)
                .where(
                    RequestCaseFile.request_case_id.in_(case_ids),
                    RequestCaseFile.kind == "UNFAVORABLE_NOTICE",
                )
                .order_by(RequestCaseFile.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    notice_by_case: dict[uuid.UUID, uuid.UUID] = {}
    for notice in notices:
        if notice.request_case_id is not None:
            notice_by_case.setdefault(notice.request_case_id, notice.id)
    links = (
        (await session.execute(select(PipelineStageOperation))).scalars().all()
    )
    ops = {
        row.id: row.code
        for row in (await session.execute(select(PipelineOperation))).scalars().all()
    }
    stages_by_code = {
        row.code: row
        for row in (await session.execute(select(PipelineStage))).scalars().all()
    }
    codes_by_stage: dict[uuid.UUID, list[str]] = {}
    for link in links:
        code = ops.get(link.operation_id)
        if code:
            codes_by_stage.setdefault(link.stage_id, []).append(code)
    as_of_by_company: dict[uuid.UUID, date] = {}
    out: list[dict] = []
    for case, stage, company, employee, employment in rows:
        minuta = latest_minuta.get(case.id)
        item = {
            "id": case.id,
            "company_id": case.company_id,
            "company_name": company.legal_name,
            "employee_id": case.employee_id,
            "display_name": _display_name(cryptos[case.company_id], employee),
            "stage_id": stage.id,
            "stage_code": stage.code,
            "stage_name": stage.name,
            "stage_type": stage.stage_type,
            "path": case.path,
            "applied_on": case.applied_on,
            "benefit_starts_on": case.benefit_starts_on,
            "probation_ends_on": case.probation_ends_on,
            "minuta_sent": bool(minuta and minuta.sent_at),
            "minuta_id": minuta.id if minuta and minuta.sent_at else None,
            "notice_file_id": notice_by_case.get(case.id),
        }
        codes = codes_by_stage.get(stage.id, [])
        if staff:
            item["operations"] = codes
            moves = _moves_for_stage(links, ops, stage.id)
            previous = _previous_stage_id(case, stage, stages_by_code)
            if previous is not None:
                moves.append(
                    {"operation": "REVERT", "stage_id": previous, "outcome": None}
                )
            item["moves"] = moves
            item["can_claim"] = any(
                link.stage_id == stage.id
                and ops.get(link.operation_id) == "RECORD_DECISION"
                and link.next_claim_stage_id is not None
                for link in links
            )
        elif "ATTACH_SIGNED_SCAN" in codes:
            item["can_attach_scan"] = True
        if staff and stage.stage_type == "CLOSE_WON":
            if case.company_id not in as_of_by_company:
                as_of_by_company[case.company_id] = await _as_of(session, case.company_id)
            start = case.benefit_starts_on or employment.started_on
            item["remaining_months"] = remaining_benefit_months(
                start, as_of_by_company[case.company_id]
            )
        out.append(item)
    return out


async def open_request_case(
    session: AsyncSession,
    *,
    employee_id: uuid.UUID,
    actor: UserBase,
) -> RequestCase:
    from app.services.contracts import _current_employment

    employee = await session.get(Employee, employee_id)
    if employee is None or employee.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Employee not found.")
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
    if current is None:
        raise HTTPException(status_code=400, detail="No employment to open a case on.")
    existing = (
        await session.execute(
            select(RequestCase.id).where(
                RequestCase.employment_id == current.id,
                RequestCase.closed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="This person is already in the pipeline.")
    path = path_for_modality(current.contract_modality)
    stage = (
        await session.execute(
            select(PipelineStage).where(
                PipelineStage.entry_path == path,
                PipelineStage.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if stage is None:
        raise HTTPException(status_code=400, detail="No entry stage for this contract.")
    case = RequestCase(
        company_id=employee.company_id,
        employee_id=employee.id,
        employment_id=current.id,
        opened_by=actor.id,
        stage_id=stage.id,
        stage_stack=[stage.id],
        path=path,
        benefit_starts_on=current.started_on,
    )
    session.add(case)
    await session.flush()
    return case


async def run_operation(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    actor: UserBase,
    code: str,
    payload: dict,
) -> RequestCase:
    case = await session.get(RequestCase, case_id)
    if case is None or (case.closed_at is not None and code != "REVERT"):
        raise HTTPException(status_code=404, detail="Case not found.")
    if code == "REVERT":
        await _revert(session, case)
        await session.flush()
        return case
    assignment = await _assignment(session, case.stage_id, code)
    if code == "RECORD_PROBATION":
        if payload.get("no_probation"):
            case.probation_ends_on = None
        else:
            raw = payload.get("probation_ends_on")
            if not raw:
                raise HTTPException(status_code=400, detail="Probation end is required.")
            case.probation_ends_on = date.fromisoformat(raw)
            case.benefit_starts_on = case.probation_ends_on
        _advance(case, assignment.next_stage_id)
    elif code == "GENERATE_MINUTA":
        template_id = payload.get("template_id")
        if not template_id:
            raise HTTPException(status_code=400, detail="Choose a minuta.")
        template = await session.get(MinutaTemplate, uuid.UUID(template_id))
        if template is None or not template.is_active:
            raise HTTPException(status_code=404, detail="Minuta not found.")
        body = payload.get("body_html") or await _filled_body(session, case, template)
        session.add(
            RequestCaseMinuta(
                request_case_id=case.id,
                template_id=template.id,
                body_html=body,
            )
        )
    elif code == "SEND_MINUTA":
        minuta = await _latest_minuta(session, case.id)
        if minuta is None:
            raise HTTPException(status_code=400, detail="Generate a minuta first.")
        if payload.get("body_html"):
            minuta.body_html = payload["body_html"]
        minuta.sent_at = datetime.now(UTC)
        _advance(case, assignment.next_stage_id)
    elif code == "ATTACH_SIGNED_SCAN":
        file_row = await session.get(RequestCaseFile, uuid.UUID(payload["file_id"]))
        if (
            file_row is None
            or file_row.company_id != case.company_id
            or file_row.kind != "SIGNED_MINUTA"
        ):
            raise HTTPException(status_code=404, detail="Signed scan not found.")
        file_row.request_case_id = case.id
        _advance(case, assignment.next_stage_id)
    elif code == "RECORD_FILING":
        raw = payload.get("applied_on") or date.today().isoformat()
        case.applied_on = date.fromisoformat(raw)
        case.applied_by = actor.id
        _advance(case, assignment.next_stage_id)
    elif code == "RECORD_DECISION":
        outcome = payload.get("outcome")
        reason = None
        if outcome in {"unfavorable", "claim"}:
            reason = await session.get(
                RejectionReason, uuid.UUID(payload["rejection_reason_id"])
            )
            if reason is None:
                raise HTTPException(status_code=404, detail="Reason not found.")
            notice = await session.get(
                RequestCaseFile, uuid.UUID(payload["file_id"])
            )
            if notice is None or notice.kind != "UNFAVORABLE_NOTICE":
                raise HTTPException(status_code=400, detail="Attach the notice.")
            notice.request_case_id = case.id
            case.rejection_reason_id = reason.id
        case.decision_on = date.fromisoformat(
            payload.get("decision_on") or date.today().isoformat()
        )
        destination = decision_stage_id(
            assignment,
            outcome,
            blocks_claim=bool(reason and reason.blocks_claim),
        )
        await _move(session, case, destination)
    else:
        raise HTTPException(status_code=400, detail="Unknown operation.")
    await session.flush()
    return case


async def store_request_file(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    actor_id: uuid.UUID,
    kind: str,
    filename: str,
    content: bytes,
    mime_type: str | None,
    request_case_id: uuid.UUID | None = None,
) -> RequestCaseFile:
    if kind not in {"SIGNED_MINUTA", "UNFAVORABLE_NOTICE", "CLAIM_SUPPORT"}:
        raise HTTPException(status_code=400, detail="Unknown file kind.")
    stored = StoredFile(
        company_id=company_id,
        gcs_path="pending",
        sha256=sha256_hex(content),
        mime_type=mime_type,
        original_filename=filename,
        kind="OTHER",
        uploaded_by=actor_id,
    )
    session.add(stored)
    await session.flush()
    path = build_object_name(
        company_id=company_id,
        intake_id=None,
        filename=f"requests/{stored.id}/{filename or 'scan.pdf'}",
    )
    stored.gcs_path = await asyncio.to_thread(
        get_object_storage().put_bytes,
        content,
        object_name=path,
        content_type=mime_type or "application/pdf",
    )
    row = RequestCaseFile(
        company_id=company_id,
        request_case_id=request_case_id,
        kind=kind,
        file_id=stored.id,
        uploaded_by=actor_id,
    )
    session.add(row)
    await session.flush()
    return row


async def company_attach_signed_scan(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    company_id: uuid.UUID,
    actor: UserBase,
    filename: str,
    content: bytes,
    mime_type: str | None,
) -> RequestCase:
    case = await session.get(RequestCase, case_id)
    if case is None or case.company_id != company_id:
        raise HTTPException(status_code=404, detail="Case not found.")
    assignment = await _assignment(session, case.stage_id, "ATTACH_SIGNED_SCAN")
    stored = await store_request_file(
        session,
        company_id=company_id,
        actor_id=actor.id,
        kind="SIGNED_MINUTA",
        filename=filename,
        content=content,
        mime_type=mime_type,
        request_case_id=case.id,
    )
    stored.request_case_id = case.id
    _advance(case, assignment.next_stage_id)
    await session.flush()
    return case


def _push_stage(case: RequestCase, stage_id: uuid.UUID, *, closing: bool) -> None:
    stack = list(case.stage_stack or [])
    if not stack or stack[-1] != stage_id:
        stack.append(stage_id)
    case.stage_stack = stack
    case.stage_id = stage_id
    if closing:
        case.closed_at = datetime.now(UTC)


def _advance(case: RequestCase, stage_id: uuid.UUID | None) -> None:
    if stage_id is None:
        raise HTTPException(status_code=400, detail="This operation does not advance.")
    _push_stage(case, stage_id, closing=False)


async def _move(session: AsyncSession, case: RequestCase, stage_id: uuid.UUID) -> None:
    stage = await session.get(PipelineStage, stage_id)
    if stage is None:
        raise HTTPException(status_code=400, detail="Destination stage is missing.")
    _push_stage(case, stage.id, closing=stage.stage_type in _CLOSE)


def _previous_stage_id(
    case: RequestCase,
    stage: PipelineStage,
    stages_by_code: dict[str, PipelineStage],
) -> uuid.UUID | None:
    stack = list(case.stage_stack or [])
    if len(stack) >= 2 and stack[-1] == case.stage_id:
        return stack[-2]
    code = earlier_stage_code(case.path, stage.code)
    if code is None:
        return None
    earlier = stages_by_code.get(code)
    return None if earlier is None else earlier.id


async def _revert(session: AsyncSession, case: RequestCase) -> None:
    current = await session.get(PipelineStage, case.stage_id)
    if current is None:
        raise HTTPException(status_code=400, detail="This case has no stage.")
    stages = {
        row.code: row
        for row in (await session.execute(select(PipelineStage))).scalars().all()
    }
    target_id = _previous_stage_id(case, current, stages)
    if target_id is None:
        raise HTTPException(status_code=400, detail="This case is already at the start.")
    target = await session.get(PipelineStage, target_id)
    if target is None:
        raise HTTPException(status_code=400, detail="Previous stage is missing.")
    stack = list(case.stage_stack or [])
    if len(stack) >= 2 and stack[-1] == case.stage_id:
        stack = stack[:-1]
    else:
        stack = [target.id]
    case.stage_stack = stack
    case.stage_id = target.id
    if target.stage_type not in _CLOSE:
        case.closed_at = None


async def _assignment(
    session: AsyncSession, stage_id: uuid.UUID, code: str
) -> PipelineStageOperation:
    operation = (
        await session.execute(
            select(PipelineOperation).where(PipelineOperation.code == code)
        )
    ).scalar_one_or_none()
    if operation is None:
        raise HTTPException(status_code=400, detail="Unknown operation.")
    assignment = (
        await session.execute(
            select(PipelineStageOperation).where(
                PipelineStageOperation.stage_id == stage_id,
                PipelineStageOperation.operation_id == operation.id,
            )
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(
            status_code=400, detail="That operation is not on this stage."
        )
    return assignment


async def _latest_minuta(
    session: AsyncSession, case_id: uuid.UUID
) -> RequestCaseMinuta | None:
    return (
        await session.execute(
            select(RequestCaseMinuta)
            .where(RequestCaseMinuta.request_case_id == case_id)
            .order_by(RequestCaseMinuta.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _filled_body(
    session: AsyncSession, case: RequestCase, template: MinutaTemplate
) -> str:
    from app.services.contracts import _display_name

    company = await session.get(Company, case.company_id)
    employee = await session.get(Employee, case.employee_id)
    employment = await session.get(Employment, case.employment_id)
    crypto = await get_or_create_pii_crypto(session, company_id=case.company_id)
    name = _display_name(crypto, employee) if employee is not None else ""
    started = employment.started_on.isoformat() if employment is not None else ""
    benefit = case.benefit_starts_on.isoformat() if case.benefit_starts_on else started
    return render_minuta(
        template.body_html,
        {
            "person_name": name or "",
            "company_name": company.legal_name if company is not None else "",
            "contract_started_on": started,
            "benefit_starts_on": benefit,
        },
    )


async def _as_of(session: AsyncSession, company_id: uuid.UUID | None) -> date:
    if company_id is None:
        return date.today()
    period = (
        await session.execute(
            select(SsBatch.period_year_month)
            .where(
                SsBatch.company_id == company_id,
                SsBatch.parse_status == "APPLIED",
            )
            .order_by(SsBatch.period_year_month.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return period or date.today()


async def sent_minuta_html(
    session: AsyncSession, *, case_id: uuid.UUID, company_id: uuid.UUID
) -> str:
    case = await session.get(RequestCase, case_id)
    if case is None or case.company_id != company_id:
        raise HTTPException(status_code=404, detail="Case not found.")
    minuta = await _latest_minuta(session, case.id)
    if minuta is None or minuta.sent_at is None:
        raise HTTPException(status_code=404, detail="No minuta has been sent.")
    return minuta.body_html


async def read_request_file(
    session: AsyncSession, *, file_row_id: uuid.UUID, company_id: uuid.UUID
) -> tuple[bytes, str, str | None]:
    row = await session.get(RequestCaseFile, file_row_id)
    if row is None or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="File not found.")
    stored = await session.get(StoredFile, row.file_id)
    if stored is None or stored.deleted_at is not None:
        raise HTTPException(status_code=404, detail="File not found.")
    data = await asyncio.to_thread(get_object_storage().get_bytes, stored.gcs_path)
    return data, stored.original_filename or "document", stored.mime_type


async def open_case_stage_names(
    session: AsyncSession, employee_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not employee_ids:
        return {}
    rows = (
        await session.execute(
            select(RequestCase.employee_id, PipelineStage.name)
            .join(PipelineStage, PipelineStage.id == RequestCase.stage_id)
            .where(
                RequestCase.employee_id.in_(employee_ids),
                RequestCase.closed_at.is_(None),
            )
        )
    ).all()
    return {employee_id: name for employee_id, name in rows}

