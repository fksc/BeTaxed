"""Pass-1 teaser aggregates (OD-2, DEV-833, KB/10, KB/20).

Working regime parameters stay inside this module. The intake API returns only
four money figures plus currency — never names, rates, remaining months, or
convert-this-contract how-to.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from cryptography.exceptions import InvalidTag
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CompensationPeriod,
    Employee,
    Employment,
    IncentiveRegime,
    Intake,
    SsBatch,
)
from app.security.dek_store import get_or_create_pii_crypto

# KB/20 working values. Do not expose on the teaser API.
_EMPLOYER_TSU_RATE = Decimal("0.2375")
_REDUCTION_FRACTION = Decimal("0.50")
_MONTHLY_SAVING_RATE = _EMPLOYER_TSU_RATE * _REDUCTION_FRACTION
_WINDOW_MONTHS = 60
_MAX_AGE_AT_SEM_TERMO = 30
# Combined sample 34.75, or employer-only 23.75, both mean unused reduction.
_UNUSED_TSU_FLOOR = Decimal("23.75")
_MONEY = Decimal("0.01")
_TERM_MODALITIES = frozenset({"TERMO_CERTO", "TERMO_INCERTO"})


@dataclass(frozen=True)
class TeaserFigures:
    now_monthly: Decimal
    now_window: Decimal
    potential_monthly: Decimal
    potential_window: Decimal


@dataclass(frozen=True)
class VerbosePerson:
    """DEV+VERBOSE row. Not stored; not returned unless flags are on."""

    name: str | None
    age: int | None
    contract: str
    contract_label: str | None
    started_on: date | None
    salary: Decimal | None
    bucket: str
    how_code: str
    remaining_months: int | None
    monthly_eur: Decimal | None
    window_eur: Decimal | None


def age_on(dob: date, on: date) -> int:
    years = on.year - dob.year
    if (on.month, on.day) < (dob.month, dob.day):
        years -= 1
    return years


def calendar_months_elapsed(started_on: date, as_of: date) -> int:
    if as_of < started_on:
        return 0
    return (as_of.year - started_on.year) * 12 + (as_of.month - started_on.month)


def remaining_benefit_months(sem_termo_start: date, as_of: date) -> int:
    elapsed = calendar_months_elapsed(sem_termo_start, as_of)
    return max(0, _WINDOW_MONTHS - elapsed)


def monthly_saving(base_salary: Decimal) -> Decimal:
    return base_salary * _MONTHLY_SAVING_RATE


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _tsu_looks_unused(rate: Decimal | None) -> bool:
    if rate is None:
        return True
    return Decimal(rate) >= _UNUSED_TSU_FLOOR


def _eligible_age(dob: date, at: date) -> bool:
    return age_on(dob, at) <= _MAX_AGE_AT_SEM_TERMO


async def persist_intake_teaser(
    session: AsyncSession,
    intake_id: uuid.UUID,
    as_of: date,
) -> TeaserFigures | None:
    """Write the four figures shown on pass 1. No-op once the intake is decided."""
    intake = await session.get(Intake, intake_id)
    if intake is None or intake.status != "OPEN":
        return None
    figures = await compute_intake_teaser(session, intake_id, as_of)
    intake.teaser_now_monthly = figures.now_monthly
    intake.teaser_now_window = figures.now_window
    intake.teaser_potential_monthly = figures.potential_monthly
    intake.teaser_potential_window = figures.potential_window
    intake.teaser_currency = "EUR"
    intake.teaser_regime_id = await _teaser_regime_id(session, as_of)
    await session.flush()
    return figures


async def _teaser_regime_id(session: AsyncSession, as_of: date) -> uuid.UUID | None:
    row = (
        await session.execute(
            select(IncentiveRegime)
            .where(
                IncentiveRegime.code == "PT_SS_YOUNG_FIRST_PERMANENT",
                IncentiveRegime.valid_from <= as_of,
            )
            .order_by(IncentiveRegime.valid_from.desc())
        )
    ).scalars().first()
    return row.id if row is not None else None


async def persist_intake_teaser_if_missing(
    session: AsyncSession, intake: Intake
) -> None:
    """Convert path: persist once if upload never wrote figures."""
    if intake.status != "OPEN":
        return
    if all(
        value is not None
        for value in (
            intake.teaser_now_monthly,
            intake.teaser_now_window,
            intake.teaser_potential_monthly,
            intake.teaser_potential_window,
        )
    ):
        return
    batch = (
        await session.execute(
            select(SsBatch)
            .where(SsBatch.intake_id == intake.id)
            .order_by(SsBatch.uploaded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if batch is None:
        return
    await persist_intake_teaser(session, intake.id, batch.period_year_month)


async def compute_intake_teaser(
    session: AsyncSession,
    intake_id: uuid.UUID,
    as_of: date,
) -> TeaserFigures:
    now_monthly = Decimal("0")
    now_window = Decimal("0")
    potential_monthly = Decimal("0")
    potential_window = Decimal("0")

    rows = (
        await session.execute(
            select(Employment, Employee, CompensationPeriod)
            .join(Employee, Employee.id == Employment.employee_id)
            .join(
                CompensationPeriod,
                and_(
                    CompensationPeriod.employment_id == Employment.id,
                    CompensationPeriod.period_to.is_(None),
                ),
            )
            .where(
                Employment.intake_id == intake_id,
                Employment.ended_on.is_(None),
                Employee.deleted_at.is_(None),
                Employee.status == "ACTIVE",
            )
        )
    ).all()
    if not rows:
        return TeaserFigures(
            now_monthly=_money(now_monthly),
            now_window=_money(now_window),
            potential_monthly=_money(potential_monthly),
            potential_window=_money(potential_window),
        )

    crypto = await get_or_create_pii_crypto(session, intake_id=intake_id)
    for employment, employee, pay in rows:
        dob = _decrypt_dob(crypto, employee.dob_enc)
        if dob is None:
            continue
        salary = Decimal(pay.base_salary)
        if salary <= 0:
            continue
        person_monthly = monthly_saving(salary)
        modality = employment.contract_modality
        if modality == "SEM_TERMO":
            if not _eligible_age(dob, employment.started_on):
                continue
            if not _tsu_looks_unused(employment.tsu_rate_pct):
                continue
            remaining = remaining_benefit_months(employment.started_on, as_of)
            if remaining == 0:
                continue
            now_monthly += person_monthly
            now_window += person_monthly * remaining
        elif modality in _TERM_MODALITIES:
            if not _eligible_age(dob, as_of):
                continue
            potential_monthly += person_monthly
            potential_window += person_monthly * _WINDOW_MONTHS

    return TeaserFigures(
        now_monthly=_money(now_monthly),
        now_window=_money(now_window),
        potential_monthly=_money(potential_monthly),
        potential_window=_money(potential_window),
    )


async def compute_verbose_people(
    session: AsyncSession,
    intake_id: uuid.UUID,
    as_of: date,
) -> list[VerbosePerson]:
    """Per-person extract rows for local DEV. Never include NISS."""
    rows = (
        await session.execute(
            select(Employment, Employee, CompensationPeriod)
            .join(Employee, Employee.id == Employment.employee_id)
            .outerjoin(
                CompensationPeriod,
                and_(
                    CompensationPeriod.employment_id == Employment.id,
                    CompensationPeriod.period_to.is_(None),
                ),
            )
            .where(
                Employment.intake_id == intake_id,
                Employment.ended_on.is_(None),
                Employee.deleted_at.is_(None),
                Employee.status == "ACTIVE",
            )
        )
    ).all()
    if not rows:
        return []

    crypto = await get_or_create_pii_crypto(session, intake_id=intake_id)
    people: list[VerbosePerson] = []
    for employment, employee, pay in rows:
        dob = _decrypt_dob(crypto, employee.dob_enc)
        name = _decrypt_name(crypto, employee.name_enc)
        salary = Decimal(pay.base_salary) if pay is not None else None
        age = age_on(dob, as_of) if dob is not None else None
        classified = _classify_person(
            dob=dob,
            salary=salary,
            modality=employment.contract_modality,
            started_on=employment.started_on,
            tsu_rate_pct=employment.tsu_rate_pct,
            as_of=as_of,
        )
        people.append(
            VerbosePerson(
                name=name,
                age=age,
                contract=employment.contract_modality,
                contract_label=employment.contract_modality_raw,
                started_on=employment.started_on,
                salary=_money(salary) if salary is not None else None,
                bucket=classified["bucket"],
                how_code=classified["how_code"],
                remaining_months=classified["remaining_months"],
                monthly_eur=classified["monthly_eur"],
                window_eur=classified["window_eur"],
            )
        )
    people.sort(key=lambda row: ((row.name or "").casefold(), row.contract))
    return people


def _classify_person(
    *,
    dob: date | None,
    salary: Decimal | None,
    modality: str,
    started_on: date,
    tsu_rate_pct: Decimal | None,
    as_of: date,
) -> dict:
    empty = {
        "bucket": "none",
        "how_code": "SKIP_NO_PAY",
        "remaining_months": None,
        "monthly_eur": None,
        "window_eur": None,
    }
    if salary is None or salary <= 0:
        empty["how_code"] = "SKIP_NO_PAY"
        return empty
    if dob is None:
        empty["how_code"] = "SKIP_NO_DOB"
        return empty

    person_monthly = _money(monthly_saving(salary))
    if modality == "SEM_TERMO":
        if not _eligible_age(dob, started_on):
            empty["how_code"] = "SKIP_AGE"
            return empty
        if not _tsu_looks_unused(tsu_rate_pct):
            empty["how_code"] = "SKIP_TSU_REDUCED"
            return empty
        remaining = remaining_benefit_months(started_on, as_of)
        if remaining == 0:
            empty["how_code"] = "SKIP_WINDOW"
            return empty
        return {
            "bucket": "now",
            "how_code": "NOW_UNUSED",
            "remaining_months": remaining,
            "monthly_eur": person_monthly,
            "window_eur": _money(person_monthly * remaining),
        }
    if modality in _TERM_MODALITIES:
        if not _eligible_age(dob, as_of):
            empty["how_code"] = "SKIP_AGE"
            return empty
        return {
            "bucket": "potential",
            "how_code": "POTENTIAL_CONVERT",
            "remaining_months": _WINDOW_MONTHS,
            "monthly_eur": person_monthly,
            "window_eur": _money(person_monthly * _WINDOW_MONTHS),
        }
    empty["how_code"] = "SKIP_CONTRACT"
    return empty


def _decrypt_dob(crypto, dob_enc: bytes | None) -> date | None:
    if dob_enc is None:
        return None
    try:
        return crypto.decrypt_dob(dob_enc)
    except (ValueError, UnicodeDecodeError, InvalidTag):
        return None


def _decrypt_name(crypto, name_enc: bytes | None) -> str | None:
    if name_enc is None:
        return None
    try:
        text = crypto.decrypt_name(name_enc).strip()
    except (ValueError, UnicodeDecodeError, InvalidTag):
        return None
    return text or None
