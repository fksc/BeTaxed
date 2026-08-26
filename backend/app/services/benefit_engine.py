"""Internal benefit cases and saving_month (KB/05, KB/20, DEV-838).

Company APIs never return these rows. Leave months are not billable (OD-4).
Clawback only when initiator/reason are already set (SL-006 / DEV-851 stays parked).
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BenefitCase,
    Company,
    CompanyApplication,
    CompanyCertificate,
    CompanyHeadcountMonth,
    CompensationPeriod,
    Employee,
    Employment,
    EmploymentEvent,
    IncentiveRegime,
    SavingMonth,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.services.teaser import (
    _decrypt_dob,
    _tsu_looks_unused,
    age_on,
    remaining_benefit_months,
)
from app.settings import get_default_fee_percent

_MONEY = Decimal("0.01")
_TERM = frozenset({"TERMO_CERTO", "TERMO_INCERTO"})
_CLAWBACK_REASONS = frozenset(
    {"NO_FAIR_MOTIVE", "COLLECTIVE", "JOB_EXTINCTION", "UNSUITABILITY"}
)
_LOCKED_STATES = frozenset({"SUBMITTED", "GRANTED", "REJECTED", "CEASED", "CLAWBACK"})
REGIME_CODE = "PT_SS_YOUNG_FIRST_PERMANENT"


def first_of_month(value: date) -> date:
    return date(value.year, value.month, 1)


def add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def add_calendar_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(value.day, last))


def month_iter(start: date, end: date) -> list[date]:
    cursor = first_of_month(start)
    last = first_of_month(end)
    out: list[date] = []
    while cursor <= last:
        out.append(cursor)
        cursor = add_months(cursor, 1)
    return out


def fee_percent() -> Decimal:
    raw = get_default_fee_percent()
    if not raw:
        return Decimal("0")
    return Decimal(raw)


def leave_covers_month(intervals: list[tuple[date, date | None]], month: date) -> bool:
    start = first_of_month(month)
    end = add_months(start, 1) - timedelta(days=1)
    for left, right in intervals:
        close = right or date.max
        if left <= end and close >= start:
            return True
    return False


def build_leave_intervals(events: list[EmploymentEvent]) -> list[tuple[date, date | None]]:
    ordered = sorted(events, key=lambda row: (row.effective_on, row.created_at))
    open_start: date | None = None
    intervals: list[tuple[date, date | None]] = []
    for event in ordered:
        if event.event_type == "LEAVE_STARTED":
            open_start = event.effective_on
        elif event.event_type == "LEAVE_ENDED" and open_start is not None:
            intervals.append((open_start, event.effective_on))
            open_start = None
    if open_start is not None:
        intervals.append((open_start, None))
    return intervals


def headcount_for_month(
    rows: list[CompanyHeadcountMonth], month: date
) -> int | None:
    ss = next((row for row in rows if row.year_month == month and row.source == "SS_BATCH"), None)
    if ss is not None:
        return ss.headcount
    user = next((row for row in rows if row.year_month == month and row.source == "USER"), None)
    return user.headcount if user is not None else None


def trailing_12_average(
    rows: list[CompanyHeadcountMonth], as_of: date
) -> tuple[int | None, Decimal | None, bool]:
    current_month = first_of_month(as_of)
    current = headcount_for_month(rows, current_month)
    previous: list[int] = []
    for offset in range(1, 13):
        value = headcount_for_month(rows, add_months(current_month, -offset))
        if value is not None:
            previous.append(value)
    if current is None or not previous:
        return current, None, False
    avg = (Decimal(sum(previous)) / Decimal(len(previous))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return current, avg, current > avg


def money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


async def current_regime(session: AsyncSession, as_of: date) -> IncentiveRegime:
    row = (
        await session.execute(
            select(IncentiveRegime)
            .where(
                IncentiveRegime.code == REGIME_CODE,
                IncentiveRegime.valid_from <= as_of,
            )
            .order_by(IncentiveRegime.valid_from.desc())
        )
    ).scalars().first()
    if row is None:
        raise RuntimeError("incentive_regime seed missing")
    return row


async def rebuild_company_ledger(
    session: AsyncSession, company_id: uuid.UUID, as_of: date
) -> int:
    """Upsert DETECTED / NEEDS_CONVERSION / EXPIRED cases and unlocked saving months."""
    company = await session.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        return 0
    regime = await current_regime(session, as_of)
    employees = (
        (
            await session.execute(
                select(Employee).where(
                    Employee.company_id == company_id,
                    Employee.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not employees:
        return 0
    crypto = await get_or_create_pii_crypto(session, company_id=company_id)
    count = 0
    for employee in employees:
        count += await _rebuild_employee(
            session, company, regime, employee, crypto, as_of
        )
    return count


async def _dob_pay_events(
    session: AsyncSession,
    employee: Employee,
    current: Employment,
    crypto,
) -> tuple[date | None, Decimal, list[EmploymentEvent]]:
    dob = _decrypt_dob(crypto, employee.dob_enc)
    pay = (
        await session.execute(
            select(CompensationPeriod).where(
                CompensationPeriod.employment_id == current.id,
                CompensationPeriod.period_to.is_(None),
            )
        )
    ).scalar_one_or_none()
    salary = Decimal(pay.base_salary) if pay is not None else Decimal("0")
    events = (
        (
            await session.execute(
                select(EmploymentEvent)
                .where(EmploymentEvent.employee_id == employee.id)
                .order_by(EmploymentEvent.effective_on, EmploymentEvent.created_at)
            )
        )
        .scalars()
        .all()
    )
    return dob, salary, events


async def _rebuild_employee(
    session: AsyncSession,
    company: Company,
    regime: IncentiveRegime,
    employee: Employee,
    crypto,
    as_of: date,
) -> int:
    employments = (
        (
            await session.execute(
                select(Employment)
                .where(Employment.employee_id == employee.id)
                .order_by(Employment.started_on.desc())
            )
        )
        .scalars()
        .all()
    )
    if not employments:
        return 0
    current = next((row for row in employments if row.ended_on is None), employments[0])
    existing = (
        await session.execute(
            select(BenefitCase).where(
                BenefitCase.employee_id == employee.id,
                BenefitCase.regime_id == regime.id,
                BenefitCase.employment_id == current.id,
            )
        )
    ).scalar_one_or_none()
    dob, salary, events = await _dob_pay_events(
        session, employee, current, crypto
    )
    state, code, sem_termo_on = _classify(
        employee=employee,
        employment=current,
        dob=dob,
        salary=salary,
        as_of=as_of,
        regime=regime,
        events=events,
    )
    if existing is not None and existing.state in _LOCKED_STATES:
        if existing.state in {"SUBMITTED", "GRANTED"} and state in {"CEASED", "CLAWBACK"}:
            existing.state = state
            existing.ineligibility_code = code
        await _refresh_unlocked_months(session, existing, employee, current, regime, as_of)
        return 0
    age_value = None
    window_ends = None
    starts = None
    if sem_termo_on is not None and dob is not None:
        age_value = Decimal(age_on(dob, sem_termo_on))
        window_ends = add_months(first_of_month(sem_termo_on), regime.window_months) - timedelta(
            days=1
        )
        starts = first_of_month(sem_termo_on)
        if (as_of - sem_termo_on).days > regime.apply_within_days:
            starts = add_months(first_of_month(as_of), 1)
    previous_state = existing.state if existing is not None else None
    if existing is None:
        existing = BenefitCase(
            company_id=company.id,
            employee_id=employee.id,
            employment_id=current.id,
            regime_id=regime.id,
            state=state,
        )
        session.add(existing)
    existing.state = state
    existing.ineligibility_code = code
    existing.sem_termo_on = sem_termo_on
    existing.window_ends_on = window_ends
    existing.benefit_starts_on = starts
    existing.age_at_sem_termo = age_value
    await session.flush()
    keep_months = previous_state in {
        "DETECTED",
        "READY",
        "SUBMITTED",
        "GRANTED",
        "CEASED",
        "CLAWBACK",
    }
    if state in {"DETECTED", "READY"} and starts is not None and window_ends is not None:
        await _sync_months(
            session,
            existing,
            employee,
            current,
            regime,
            salary=salary if salary > 0 else Decimal("0"),
            as_of=as_of,
        )
    elif state in {"CEASED", "CLAWBACK"} and keep_months:
        await _sync_months(
            session,
            existing,
            employee,
            current,
            regime,
            salary=salary if salary > 0 else Decimal("0"),
            as_of=as_of,
        )
    else:
        await _delete_unlocked_months(session, existing.id)
    return 1


def _classify(
    *,
    employee: Employee,
    employment: Employment,
    dob: date | None,
    salary: Decimal,
    as_of: date,
    regime: IncentiveRegime,
    events: list[EmploymentEvent],
) -> tuple[str, str | None, date | None]:
    if salary <= 0:
        return "EXPIRED", "SKIP_NO_PAY", None
    if dob is None:
        return "EXPIRED", "SKIP_NO_DOB", None
    if employment.contract_modality in _TERM:
        if age_on(dob, as_of) > regime.max_age_inclusive:
            return "EXPIRED", "SKIP_AGE", None
        return "NEEDS_CONVERSION", None, None
    if employment.contract_modality != "SEM_TERMO":
        return "EXPIRED", "SKIP_CONTRACT", None
    sem = employment.started_on
    if age_on(dob, sem) > regime.max_age_inclusive:
        return "EXPIRED", "SKIP_AGE", sem
    if not _tsu_looks_unused(employment.tsu_rate_pct):
        return "EXPIRED", "SKIP_TSU_REDUCED", sem
    remaining = remaining_benefit_months(sem, as_of)
    if remaining == 0:
        return "EXPIRED", "SKIP_WINDOW", sem
    if _should_clawback(events):
        return "CLAWBACK", "CLAWBACK_TERMINATION", sem
    if employee.status == "TERMINATED":
        return "CEASED", "TERMINATED", sem
    return "DETECTED", None, sem


def _should_clawback(events: list[EmploymentEvent]) -> bool:
    for event in events:
        if event.event_type not in {"TERMINATED", "STATUS_OVERRIDE"}:
            continue
        if event.initiator == "EMPLOYER" and event.reason in _CLAWBACK_REASONS:
            return True
    return False


async def _sync_months(
    session: AsyncSession,
    case: BenefitCase,
    employee: Employee,
    employment: Employment,
    regime: IncentiveRegime,
    *,
    salary: Decimal,
    as_of: date,
) -> None:
    assert case.benefit_starts_on is not None
    assert case.window_ends_on is not None
    events = (
        (
            await session.execute(
                select(EmploymentEvent)
                .where(EmploymentEvent.employee_id == employee.id)
                .order_by(EmploymentEvent.effective_on, EmploymentEvent.created_at)
            )
        )
        .scalars()
        .all()
    )
    intervals = build_leave_intervals(events)
    if employee.status == "ON_LEAVE" and not any(right is None for _left, right in intervals):
        intervals.append((as_of, None))
    rate = regime.employer_rate * regime.reduction_factor
    percent = fee_percent()
    months = month_iter(case.benefit_starts_on, case.window_ends_on)
    existing = (
        (
            await session.execute(
                select(SavingMonth).where(SavingMonth.benefit_case_id == case.id)
            )
        )
        .scalars()
        .all()
    )
    by_month = {row.year_month: row for row in existing}
    wanted = set(months)
    for month in months:
        row = by_month.get(month)
        on_leave = leave_covers_month(intervals, month)
        terminated = employee.status == "TERMINATED" and (
            employment.ended_on is None or first_of_month(employment.ended_on) <= month
        )
        billable = not on_leave and not terminated and case.state not in {"CLAWBACK", "CEASED"}
        saving = money(salary * rate)
        fee = money(saving * percent)
        if row is None:
            session.add(
                SavingMonth(
                    company_id=case.company_id,
                    benefit_case_id=case.id,
                    employee_id=employee.id,
                    year_month=month,
                    base_salary=salary,
                    saving_amount=saving,
                    fee_percent=percent,
                    fee_amount=fee,
                    billable=billable,
                )
            )
            continue
        if row.locked_at is not None:
            continue
        row.base_salary = salary
        row.saving_amount = saving
        row.fee_percent = percent
        row.fee_amount = fee
        row.billable = billable
    for month, row in by_month.items():
        if month not in wanted and row.locked_at is None:
            await session.delete(row)
    await session.flush()


async def _refresh_unlocked_months(
    session: AsyncSession,
    case: BenefitCase,
    employee: Employee,
    employment: Employment,
    regime: IncentiveRegime,
    as_of: date,
) -> None:
    if case.benefit_starts_on is None or case.window_ends_on is None:
        return
    pay = (
        await session.execute(
            select(CompensationPeriod).where(
                CompensationPeriod.employment_id == employment.id,
                CompensationPeriod.period_to.is_(None),
            )
        )
    ).scalar_one_or_none()
    salary = Decimal(pay.base_salary) if pay is not None else Decimal("0")
    await _sync_months(
        session, case, employee, employment, regime, salary=salary, as_of=as_of
    )


async def _delete_unlocked_months(session: AsyncSession, case_id: uuid.UUID) -> None:
    await session.execute(
        delete(SavingMonth).where(
            SavingMonth.benefit_case_id == case_id,
            SavingMonth.locked_at.is_(None),
        )
    )


async def delete_company_benefit_spine(session: AsyncSession, company_id: uuid.UUID) -> None:
    await session.execute(delete(SavingMonth).where(SavingMonth.company_id == company_id))
    await session.execute(delete(BenefitCase).where(BenefitCase.company_id == company_id))
    await session.execute(
        delete(CompanyCertificate).where(CompanyCertificate.company_id == company_id)
    )
    await session.execute(
        delete(CompanyApplication).where(CompanyApplication.company_id == company_id)
    )


async def submit_company_application(
    session: AsyncSession, company_id: uuid.UUID, as_of: date
) -> CompanyApplication:
    company = await session.get(Company, company_id)
    if company is None:
        raise ValueError("company not found")
    regime = await current_regime(session, as_of)
    rows = (
        (
            await session.execute(
                select(CompanyHeadcountMonth).where(
                    CompanyHeadcountMonth.company_id == company_id
                )
            )
        )
        .scalars()
        .all()
    )
    current, avg, passed = trailing_12_average(rows, as_of)
    today = as_of
    ss_ok = await _cert_covers(session, company_id, "SS_NO_DEBT", today)
    at_ok = await _cert_covers(session, company_id, "AT_NO_DEBT", today)
    cases = (
        (
            await session.execute(
                select(BenefitCase).where(
                    BenefitCase.company_id == company_id,
                    BenefitCase.regime_id == regime.id,
                    BenefitCase.state.in_(("DETECTED", "READY")),
                )
            )
        )
        .scalars()
        .all()
    )
    if not cases:
        existing = (
            (
                await session.execute(
                    select(CompanyApplication)
                    .where(
                        CompanyApplication.company_id == company_id,
                        CompanyApplication.regime_id == regime.id,
                    )
                    .order_by(
                        CompanyApplication.submitted_on.desc(),
                        CompanyApplication.created_at.desc(),
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            return existing
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No DETECTED benefit cases to submit.",
        )
    app = CompanyApplication(
        company_id=company_id,
        regime_id=regime.id,
        submitted_on=today,
        decision="SUBMITTED",
        decision_on=today,
        headcount_current=current,
        headcount_trailing_12_avg=avg,
        headcount_test_pass=passed,
        ss_regularized_at_submit=ss_ok,
        at_regularized_at_submit=at_ok,
        payroll_not_in_arrears_at_submit=company.payroll_not_in_arrears,
    )
    session.add(app)
    await session.flush()
    for case in cases:
        employee = await session.get(Employee, case.employee_id)
        case.application_id = app.id
        case.applied_on = today
        case.state = "SUBMITTED"
        if employee is not None:
            case.first_permanent_elsewhere_at_submit = employee.first_permanent_elsewhere
    company.ss_regularized = ss_ok
    company.at_regularized = at_ok
    await session.flush()
    return app


async def _cert_covers(
    session: AsyncSession, company_id: uuid.UUID, kind: str, today: date
) -> bool:
    row = (
        await session.execute(
            select(CompanyCertificate).where(
                CompanyCertificate.company_id == company_id,
                CompanyCertificate.kind == kind,
                CompanyCertificate.issued_on <= today,
                CompanyCertificate.valid_until >= today,
            )
        )
    ).scalars().first()
    return row is not None
