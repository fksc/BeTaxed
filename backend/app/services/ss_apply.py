"""Apply a PARSED SS batch onto canonical employment (KB/02, KB/03, DEV-834).

Writes company_headcount_month when the batch is company-scoped (DEV-835).
Does not invent leave from the current extract (SL-004 / DEV-849).
Never sets first_permanent_* from SS.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    CompanyHeadcountMonth,
    CompensationPeriod,
    Employee,
    EmployeeExternalId,
    Employment,
    EmploymentDocument,
    EmploymentEvent,
    SsBatch,
    SsRawContrato,
    SsRawVinculo,
    Workplace,
)
from app.services.ss_headers import fold_header

_USER_OWNED = frozenset({"USER", "ADMIN"})


@dataclass(frozen=True)
class _PersonSnap:
    niss_hash: bytes
    niss_enc: bytes
    name_enc: bytes | None
    dob_enc: bytes | None
    vinculo: SsRawVinculo
    contrato: SsRawContrato | None

    @property
    def is_active(self) -> bool:
        return self.vinculo.ended_on is None


@dataclass
class SsApplyResult:
    batch: SsBatch
    event_types: list[str]


async def apply_ss_batch(session: AsyncSession, batch_id: uuid.UUID) -> SsApplyResult:
    """Match niss_hash, upsert employment/pay, insert events, mark APPLIED."""
    batch = (
        await session.execute(
            select(SsBatch)
            .options(
                selectinload(SsBatch.vinculos),
                selectinload(SsBatch.contratos),
            )
            .where(SsBatch.id == batch_id)
        )
    ).scalar_one_or_none()
    if batch is None:
        raise ValueError("ss_batch not found")
    if batch.parse_status == "APPLIED":
        return SsApplyResult(batch=batch, event_types=[])
    if batch.parse_status != "PARSED":
        raise ValueError(f"ss_batch is {batch.parse_status}, not PARSED")

    current = _snaps_from_raw(batch.vinculos, batch.contratos)
    previous_batch = await _previous_applied(session, batch)
    previous = _snaps_from_raw(
        previous_batch.vinculos if previous_batch else [],
        previous_batch.contratos if previous_batch else [],
    )

    event_types: list[str] = []
    for niss_hash, snap in current.items():
        event_types.extend(
            await _apply_person(session, batch, snap, previous.get(niss_hash))
        )

    for niss_hash, snap in previous.items():
        if niss_hash in current or not snap.is_active:
            continue
        event_types.extend(await _apply_missing(session, batch, snap))

    batch.parse_status = "APPLIED"
    await upsert_ss_batch_headcount(session, batch)
    if batch.company_id is not None:
        from app.services.benefit_engine import rebuild_company_ledger

        await rebuild_company_ledger(
            session, batch.company_id, batch.period_year_month
        )
    await session.flush()
    return SsApplyResult(batch=batch, event_types=event_types)


async def delete_intake_employment_spine(
    session: AsyncSession, intake_id: uuid.UUID
) -> None:
    """Hard-delete canonical intake employment so purge/tests can drop employees."""
    emp_ids = select(Employee.id).where(Employee.intake_id == intake_id)
    empl_ids = select(Employment.id).where(Employment.intake_id == intake_id)
    await session.execute(
        delete(EmploymentDocument).where(EmploymentDocument.employee_id.in_(emp_ids))
    )
    await session.execute(
        delete(EmploymentEvent).where(EmploymentEvent.intake_id == intake_id)
    )
    await session.execute(
        delete(CompensationPeriod).where(CompensationPeriod.employment_id.in_(empl_ids))
    )
    await session.execute(
        delete(EmployeeExternalId).where(EmployeeExternalId.employee_id.in_(emp_ids))
    )
    await session.execute(delete(Employment).where(Employment.intake_id == intake_id))
    await session.execute(delete(Employee).where(Employee.intake_id == intake_id))
    await session.execute(delete(Workplace).where(Workplace.intake_id == intake_id))


async def delete_company_employment_spine(
    session: AsyncSession, company_id: uuid.UUID
) -> None:
    emp_ids = select(Employee.id).where(Employee.company_id == company_id)
    empl_ids = select(Employment.id).where(Employment.company_id == company_id)
    from app.services.billing import delete_company_billing_spine
    from app.services.benefit_engine import delete_company_benefit_spine

    await delete_company_billing_spine(session, company_id)
    await delete_company_benefit_spine(session, company_id)
    await session.execute(
        delete(CompanyHeadcountMonth).where(
            CompanyHeadcountMonth.company_id == company_id
        )
    )
    await session.execute(
        delete(EmploymentDocument).where(EmploymentDocument.employee_id.in_(emp_ids))
    )
    await session.execute(
        delete(EmploymentEvent).where(EmploymentEvent.company_id == company_id)
    )
    await session.execute(
        delete(CompensationPeriod).where(CompensationPeriod.employment_id.in_(empl_ids))
    )
    await session.execute(
        delete(EmployeeExternalId).where(EmployeeExternalId.employee_id.in_(emp_ids))
    )
    await session.execute(delete(Employment).where(Employment.company_id == company_id))
    await session.execute(delete(Employee).where(Employee.company_id == company_id))
    await session.execute(delete(Workplace).where(Workplace.company_id == company_id))


async def attach_employment_company(
    session: AsyncSession, intake_id: uuid.UUID, company_id: uuid.UUID
) -> None:
    for model in (Workplace, Employment, EmploymentEvent, Employee):
        rows = (
            await session.execute(select(model).where(model.intake_id == intake_id))
        ).scalars().all()
        for row in rows:
            row.company_id = company_id


async def upsert_ss_batch_headcount(session: AsyncSession, batch: SsBatch) -> None:
    """Count distinct active vínculos and upsert source=SS_BATCH for the month."""
    if batch.company_id is None:
        return
    count = (
        await session.execute(
            select(func.count(func.distinct(SsRawVinculo.niss_hash))).where(
                SsRawVinculo.batch_id == batch.id,
                SsRawVinculo.ended_on.is_(None),
            )
        )
    ).scalar_one()
    existing = (
        await session.execute(
            select(CompanyHeadcountMonth).where(
                CompanyHeadcountMonth.company_id == batch.company_id,
                CompanyHeadcountMonth.year_month == batch.period_year_month,
                CompanyHeadcountMonth.source == "SS_BATCH",
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            CompanyHeadcountMonth(
                company_id=batch.company_id,
                year_month=batch.period_year_month,
                headcount=int(count),
                source="SS_BATCH",
                source_batch_id=batch.id,
            )
        )
    else:
        existing.headcount = int(count)
        existing.source_batch_id = batch.id
    await session.flush()


async def upsert_headcount_for_company_applied_batches(
    session: AsyncSession, company_id: uuid.UUID
) -> None:
    """Backfill SS_BATCH headcount after convert attaches company_id."""
    batches = (
        await session.execute(
            select(SsBatch).where(
                SsBatch.company_id == company_id,
                SsBatch.parse_status == "APPLIED",
            )
        )
    ).scalars().all()
    for batch in batches:
        await upsert_ss_batch_headcount(session, batch)


async def upsert_user_headcount(
    session: AsyncSession,
    company_id: uuid.UUID,
    year_month: date,
    headcount: int,
) -> CompanyHeadcountMonth:
    existing = (
        await session.execute(
            select(CompanyHeadcountMonth).where(
                CompanyHeadcountMonth.company_id == company_id,
                CompanyHeadcountMonth.year_month == year_month,
                CompanyHeadcountMonth.source == "USER",
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = CompanyHeadcountMonth(
            company_id=company_id,
            year_month=year_month,
            headcount=headcount,
            source="USER",
            source_batch_id=None,
        )
        session.add(existing)
    else:
        existing.headcount = headcount
    await session.flush()
    return existing


async def _previous_applied(session: AsyncSession, batch: SsBatch) -> SsBatch | None:
    stmt = (
        select(SsBatch)
        .options(
            selectinload(SsBatch.vinculos),
            selectinload(SsBatch.contratos),
        )
        .where(
            SsBatch.parse_status == "APPLIED",
            SsBatch.id != batch.id,
            or_(
                SsBatch.period_year_month < batch.period_year_month,
                and_(
                    SsBatch.period_year_month == batch.period_year_month,
                    SsBatch.uploaded_at < batch.uploaded_at,
                ),
            ),
        )
        .order_by(SsBatch.period_year_month.desc(), SsBatch.uploaded_at.desc())
        .limit(1)
    )
    if batch.company_id is not None:
        stmt = stmt.where(SsBatch.company_id == batch.company_id)
    else:
        stmt = stmt.where(SsBatch.intake_id == batch.intake_id)
    return (await session.execute(stmt)).scalar_one_or_none()


def _snaps_from_raw(
    vinculos: list[SsRawVinculo], contratos: list[SsRawContrato]
) -> dict[bytes, _PersonSnap]:
    by_v: dict[bytes, list[SsRawVinculo]] = {}
    for row in vinculos:
        by_v.setdefault(row.niss_hash, []).append(row)
    by_c: dict[bytes, list[SsRawContrato]] = {}
    for row in contratos:
        by_c.setdefault(row.niss_hash, []).append(row)
    snaps: dict[bytes, _PersonSnap] = {}
    for niss_hash, v_rows in by_v.items():
        vinculo = _pick_vinculo(v_rows)
        contrato = _pick_contrato(by_c.get(niss_hash, []))
        snaps[niss_hash] = _PersonSnap(
            niss_hash=niss_hash,
            niss_enc=vinculo.niss_enc,
            name_enc=vinculo.name_enc or (contrato.name_enc if contrato else None),
            dob_enc=vinculo.dob_enc,
            vinculo=vinculo,
            contrato=contrato,
        )
    return snaps


def _pick_vinculo(rows: list[SsRawVinculo]) -> SsRawVinculo:
    open_rows = [row for row in rows if row.ended_on is None]
    pool = open_rows or rows
    return max(pool, key=lambda row: (row.started_on or date.min, row.source_row))


def _pick_contrato(rows: list[SsRawContrato]) -> SsRawContrato | None:
    open_rows = [row for row in rows if row.rendimento_to is None]
    if not open_rows:
        return None
    return max(
        open_rows, key=lambda row: (row.rendimento_from or date.min, row.source_row)
    )


async def _apply_person(
    session: AsyncSession,
    batch: SsBatch,
    snap: _PersonSnap,
    previous: _PersonSnap | None,
) -> list[str]:
    employee = await _find_employee(session, batch, snap.niss_hash)
    created = employee is None
    if employee is None:
        employee = Employee(
            company_id=batch.company_id,
            intake_id=batch.intake_id,
            niss_hash=snap.niss_hash,
            niss_enc=snap.niss_enc,
            name_enc=snap.name_enc,
            dob_enc=snap.dob_enc,
            first_permanent_elsewhere="UNKNOWN",
            first_permanent_source="UNKNOWN",
            status="ACTIVE",
            status_source="SS",
        )
        session.add(employee)
        await session.flush()
    elif snap.name_enc is not None:
        employee.name_enc = snap.name_enc
    if snap.dob_enc is not None:
        employee.dob_enc = snap.dob_enc

    workplace_id = await _workplace_id(session, batch, snap.vinculo.workplace_ss_label)
    events: list[str] = []
    protected = employee.status_source in _USER_OWNED

    if created:
        employment = await _insert_employment(session, batch, employee, snap, workplace_id)
        await _sync_pay(session, batch, employee, employment, snap, emit=False)
        events.append(
            _emit(
                session,
                batch,
                employee,
                employment,
                "HIRED",
                snap.vinculo.started_on or batch.period_year_month,
            )
        )
        return events

    open_emp = await _open_employment(session, employee.id)
    prev_active = previous is not None and previous.is_active

    if snap.is_active and not prev_active and open_emp is None:
        employment = await _insert_employment(
            session, batch, employee, snap, workplace_id
        )
        await _sync_pay(session, batch, employee, employment, snap, emit=False)
        events.append(
            _emit(
                session,
                batch,
                employee,
                employment,
                "REHIRED",
                snap.vinculo.started_on or batch.period_year_month,
            )
        )
        if protected and employee.status == "TERMINATED":
            events.append(
                _conflict(session, batch, employee, employment, "TERMINATED", "ACTIVE")
            )
        elif not protected:
            _set_ss_status(employee, "ACTIVE")
        return events

    if open_emp is None:
        open_emp = await _insert_employment(
            session, batch, employee, snap, workplace_id
        )

    if snap.is_active:
        events.extend(
            await _diff_open(session, batch, employee, open_emp, snap, previous)
        )
        if protected and employee.status == "TERMINATED":
            events.append(
                _conflict(session, batch, employee, open_emp, "TERMINATED", "ACTIVE")
            )
        elif not protected:
            _set_ss_status(employee, "ACTIVE")
        return events

    end_on = snap.vinculo.ended_on or batch.period_year_month
    if open_emp.ended_on is None:
        open_emp.ended_on = end_on
    if protected and employee.status in ("ACTIVE", "ON_LEAVE"):
        events.append(
            _conflict(session, batch, employee, open_emp, employee.status, "TERMINATED")
        )
    else:
        _set_ss_status(employee, "TERMINATED")
        events.append(_emit(session, batch, employee, open_emp, "TERMINATED", end_on))
    return events


async def _apply_missing(
    session: AsyncSession, batch: SsBatch, snap: _PersonSnap
) -> list[str]:
    employee = await _find_employee(session, batch, snap.niss_hash)
    if employee is None:
        return []
    open_emp = await _open_employment(session, employee.id)
    return [
        _emit(
            session,
            batch,
            employee,
            open_emp,
            "MISSING_FROM_DECLARATION",
            batch.period_year_month,
        )
    ]


async def _diff_open(
    session: AsyncSession,
    batch: SsBatch,
    employee: Employee,
    employment: Employment,
    snap: _PersonSnap,
    previous: _PersonSnap | None,
) -> list[str]:
    events: list[str] = []
    _fill_employment(employment, snap)
    new_mod = map_modality(snap.contrato.modality_raw if snap.contrato else None)
    if previous and previous.contrato is not None:
        old_mod = map_modality(previous.contrato.modality_raw)
        if old_mod != new_mod:
            events.append(
                _emit(
                    session,
                    batch,
                    employee,
                    employment,
                    "MODALITY_CHANGED",
                    batch.period_year_month,
                    old_modality=old_mod,
                    new_modality=new_mod,
                )
            )
    employment.contract_modality = new_mod
    new_rate = snap.vinculo.taxa_pct
    if previous and previous.vinculo.taxa_pct != new_rate:
        events.append(
            _emit(
                session,
                batch,
                employee,
                employment,
                "TSU_RATE_CHANGED",
                snap.vinculo.rate_from or batch.period_year_month,
                old_rate_pct=previous.vinculo.taxa_pct,
                new_rate_pct=new_rate,
            )
        )
    employment.tsu_rate_pct = new_rate
    pay = await _sync_pay(session, batch, employee, employment, snap, emit=True)
    if pay:
        events.append(pay)
    return events


async def _insert_employment(
    session: AsyncSession,
    batch: SsBatch,
    employee: Employee,
    snap: _PersonSnap,
    workplace_id: uuid.UUID | None,
) -> Employment:
    started = snap.vinculo.started_on or batch.period_year_month
    row = Employment(
        employee_id=employee.id,
        company_id=batch.company_id,
        intake_id=batch.intake_id,
        started_on=started,
        ended_on=snap.vinculo.ended_on if not snap.is_active else None,
        workplace_id=workplace_id,
        contract_modality=map_modality(
            snap.contrato.modality_raw if snap.contrato else None
        ),
    )
    _fill_employment(row, snap)
    session.add(row)
    await session.flush()
    return row


def _fill_employment(row: Employment, snap: _PersonSnap) -> None:
    vinculo = snap.vinculo
    contrato = snap.contrato
    row.actor_type_raw = vinculo.vinculo_raw
    row.actor_type = map_actor(vinculo.vinculo_raw)
    row.ss_communicated_on = vinculo.communicated_on
    row.rate_applied_from = vinculo.rate_from
    row.rate_applied_to = vinculo.rate_to
    row.tsu_rate_pct = vinculo.taxa_pct
    if contrato is None:
        return
    row.contract_modality = map_modality(contrato.modality_raw)
    row.contract_modality_raw = contrato.modality_raw
    row.work_mode = map_work_mode(contrato.work_mode_raw)
    row.work_mode_raw = contrato.work_mode_raw
    row.hours_per_week = contrato.hours_work
    row.days_per_month = contrato.days_work
    row.percent_work = contrato.percent_work
    row.profession_raw = contrato.profession_raw


async def _sync_pay(
    session: AsyncSession,
    batch: SsBatch,
    employee: Employee,
    employment: Employment,
    snap: _PersonSnap,
    *,
    emit: bool,
) -> str | None:
    if snap.contrato is None or snap.contrato.base_salary is None:
        return None
    new_salary = snap.contrato.base_salary
    new_from = snap.contrato.rendimento_from or batch.period_year_month
    open_row = (
        await session.execute(
            select(CompensationPeriod).where(
                CompensationPeriod.employment_id == employment.id,
                CompensationPeriod.period_to.is_(None),
            )
        )
    ).scalar_one_or_none()
    if open_row is None:
        session.add(
            CompensationPeriod(
                employment_id=employment.id,
                period_from=new_from,
                period_to=None,
                base_salary=new_salary,
            )
        )
        await session.flush()
        return None
    if open_row.base_salary == new_salary:
        return None
    if not emit:
        open_row.base_salary = new_salary
        return None
    old = open_row.base_salary
    close_on = new_from - timedelta(days=1)
    if close_on < open_row.period_from:
        close_on = open_row.period_from
    open_row.period_to = close_on
    session.add(
        CompensationPeriod(
            employment_id=employment.id,
            period_from=new_from,
            period_to=None,
            base_salary=new_salary,
        )
    )
    await session.flush()
    return _emit(
        session,
        batch,
        employee,
        employment,
        "SALARY_CHANGED",
        new_from,
        old_salary=old,
        new_salary=new_salary,
    )


async def _find_employee(
    session: AsyncSession, batch: SsBatch, niss_hash: bytes
) -> Employee | None:
    stmt = select(Employee).where(
        Employee.niss_hash == niss_hash, Employee.deleted_at.is_(None)
    )
    if batch.company_id is not None:
        stmt = stmt.where(Employee.company_id == batch.company_id)
    else:
        stmt = stmt.where(
            Employee.intake_id == batch.intake_id, Employee.company_id.is_(None)
        )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _open_employment(
    session: AsyncSession, employee_id: uuid.UUID
) -> Employment | None:
    rows = (
        await session.execute(
            select(Employment)
            .where(Employment.employee_id == employee_id, Employment.ended_on.is_(None))
            .order_by(Employment.started_on.desc())
        )
    ).scalars().all()
    return rows[0] if rows else None


async def _workplace_id(
    session: AsyncSession, batch: SsBatch, label: str | None
) -> uuid.UUID | None:
    if not label:
        return None
    stmt = select(Workplace).where(Workplace.ss_label == label)
    if batch.company_id is not None:
        stmt = stmt.where(Workplace.company_id == batch.company_id)
    else:
        stmt = stmt.where(
            Workplace.intake_id == batch.intake_id, Workplace.company_id.is_(None)
        )
    row = (await session.execute(stmt)).scalars().first()
    if row is not None:
        return row.id
    row = Workplace(
        company_id=batch.company_id, intake_id=batch.intake_id, ss_label=label
    )
    session.add(row)
    await session.flush()
    return row.id


def _set_ss_status(employee: Employee, status: str) -> None:
    employee.status = status
    employee.status_source = "SS"


def _emit(
    session: AsyncSession,
    batch: SsBatch,
    employee: Employee,
    employment: Employment | None,
    event_type: str,
    effective_on: date,
    **extra: object,
) -> str:
    row = EmploymentEvent(
        company_id=batch.company_id,
        intake_id=batch.intake_id,
        employee_id=employee.id,
        employment_id=employment.id if employment is not None else None,
        event_type=event_type,
        effective_on=effective_on,
        source="SS_DIFF",
        ss_batch_id=batch.id,
        old_salary=extra.get("old_salary"),  # type: ignore[arg-type]
        new_salary=extra.get("new_salary"),  # type: ignore[arg-type]
        old_modality=extra.get("old_modality"),  # type: ignore[arg-type]
        new_modality=extra.get("new_modality"),  # type: ignore[arg-type]
        old_rate_pct=extra.get("old_rate_pct"),  # type: ignore[arg-type]
        new_rate_pct=extra.get("new_rate_pct"),  # type: ignore[arg-type]
        old_status=extra.get("old_status"),  # type: ignore[arg-type]
        new_status=extra.get("new_status"),  # type: ignore[arg-type]
    )
    session.add(row)
    return event_type


def _conflict(
    session: AsyncSession,
    batch: SsBatch,
    employee: Employee,
    employment: Employment | None,
    old_status: str,
    new_status: str,
) -> str:
    return _emit(
        session,
        batch,
        employee,
        employment,
        "SOURCE_CONFLICT",
        batch.period_year_month,
        old_status=old_status,
        new_status=new_status,
    )


def map_modality(raw: str | None) -> str:
    if not raw:
        return "OTHER"
    folded = fold_header(raw)
    if "sem termo" in folded:
        return "SEM_TERMO"
    if "incerto" in folded:
        return "TERMO_INCERTO"
    if "termo certo" in folded or folded.startswith("a termo"):
        return "TERMO_CERTO"
    return "OTHER"


def map_actor(raw: str | None) -> str:
    if raw and "conta de outrem" in fold_header(raw):
        return "TCO"
    return "TCO"


def map_work_mode(raw: str | None) -> str | None:
    if not raw:
        return None
    folded = fold_header(raw)
    if "presencial" in folded:
        return "PRESENCIAL"
    if "tele" in folded:
        return "TELETRABALHO"
    return "OTHER"
