"""Staff flag: a term contract that can still open the hiring benefit (DEV-877).

Company APIs must not receive this. The flag is a suggestion for staff.
It does not declare anything to Segurança Social.

KB/20. Age is ≤ 30 on the date treated as sem termo (under 31). The 60
months start on that date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.services.teaser import age_on, calendar_months_elapsed, remaining_benefit_months

_MAX_AGE = 30
_TERM = frozenset({"TERMO_CERTO", "TERMO_INCERTO"})


@dataclass(frozen=True)
class TermReading:
    rule: str
    deemed_on: date


@dataclass(frozen=True)
class TermBenefit:
    readings: tuple[TermReading, ...]
    early_earliest: date | None
    early_latest: date | None
    early_suggested: date | None


@dataclass(frozen=True)
class HiringClass:
    outlook: str
    reason: str | None = None
    age_on_start: int | None = None
    last_day: date | None = None


def classify_hiring_benefit(
    *,
    already: bool,
    modality: str | None,
    started_on: date | None,
    employment_open: bool,
    status: str,
    dob: date | None,
    salary: Decimal | None,
    as_of: date,
    term_months: int | None,
) -> HiringClass | None:
    """Staff filter: already, might, or never. None when a fact is missing.

    Might includes a permanent contract that can still open the 60 months,
    and a term contract this module would flag. Never carries the first
    closed path in reason. A missing date of birth or salary, or a term
    contract on leave, is None.
    """
    if already:
        return HiringClass("already")
    if started_on is None:
        return HiringClass("never", "no_start")
    if (
        not employment_open
        or status == "TERMINATED"
        or status not in {"ACTIVE", "ON_LEAVE"}
    ):
        return HiringClass("never", "employment_ended")
    if dob is None or salary is None or salary <= 0:
        return None
    if modality == "SEM_TERMO":
        years = age_on(dob, started_on)
        if years > _MAX_AGE:
            return HiringClass("never", "age_at_start", age_on_start=years)
        if remaining_benefit_months(started_on, as_of) <= 0:
            return HiringClass("never", "window_over")
        return HiringClass("might")
    if modality in _TERM:
        if status != "ACTIVE":
            return None
        closed = _term_closed(modality, started_on, dob, as_of, term_months)
        if closed is None:
            return HiringClass("might")
        reason, last_day = closed
        return HiringClass("never", reason, last_day=last_day)
    if modality is None:
        return None
    return HiringClass("never", "other_modality")


def term_length_months(signed_on: date | None, term_end_on: date | None) -> int | None:
    """Whole calendar months of the first printed term. Not a renewal span."""
    if signed_on is None or term_end_on is None or term_end_on <= signed_on:
        return None
    months = calendar_months_elapsed(signed_on, term_end_on)
    if months <= 0:
        return None
    return months


def assess_term_benefit(
    *,
    modality: str,
    started_on: date,
    dob: date,
    as_of: date,
    term_months: int | None,
) -> TermBenefit | None:
    """Yes-lines for staff, or None when there is nothing to suggest.

    The early window is used only when the primary conversion date would
    already be age 31 or older. Certo's primary date is the first term plus
    one renewal of the same length. Without that length, the early window
    opens only when all three historical caps fail the age test. Incerto's
    primary date is four years after the start.
    """
    plan = _term_plan(modality, started_on, dob, term_months)
    if plan is None:
        return None
    candidates, primary_fails_age = plan

    readings = tuple(
        TermReading(rule, on)
        for rule, on in candidates
        if _age_ok(dob, on) and remaining_benefit_months(on, as_of) > 0
    )
    early = _early_window(dob, started_on, as_of) if primary_fails_age else None
    if not readings and early is None:
        return None
    if early is None:
        return TermBenefit(readings, None, None, None)
    earliest, latest, suggested = early
    return TermBenefit(readings, earliest, latest, suggested)


def _term_plan(
    modality: str,
    started_on: date,
    dob: date,
    term_months: int | None,
) -> tuple[list[tuple[str, date]], bool] | None:
    if modality not in _TERM:
        return None
    candidates: list[tuple[str, date]] = []
    if modality == "TERMO_CERTO":
        if term_months is not None:
            candidates.append(("certo_renewal", shift_months(started_on, term_months * 2)))
        candidates.extend(
            (
                ("years_2", shift_years(started_on, 2)),
                ("years_3", shift_years(started_on, 3)),
                ("years_4", shift_years(started_on, 4)),
            )
        )
        if term_months is not None:
            primary_fails_age = not _age_ok(dob, candidates[0][1])
        else:
            primary_fails_age = all(not _age_ok(dob, on) for _, on in candidates)
    else:
        deemed = shift_years(started_on, 4)
        candidates.append(("incerto_4", deemed))
        primary_fails_age = not _age_ok(dob, deemed)
    return candidates, primary_fails_age


def _term_closed(
    modality: str,
    started_on: date,
    dob: date,
    as_of: date,
    term_months: int | None,
) -> tuple[str, date | None] | None:
    """First closed path for a term contract, or None when it can still be flagged."""
    plan = _term_plan(modality, started_on, dob, term_months)
    if plan is None:
        return ("other_modality", None)
    candidates, primary_fails_age = plan
    open_line = any(
        _age_ok(dob, on) and remaining_benefit_months(on, as_of) > 0
        for _, on in candidates
    )
    if open_line:
        return None
    if not primary_fails_age:
        return ("term_dates_over", None)
    earliest = started_on + timedelta(days=1)
    latest = _birthday(dob, 31) - timedelta(days=1)
    if earliest > latest:
        return ("term_no_day", None)
    if remaining_benefit_months(latest, as_of) <= 0:
        return ("term_early_over", latest)
    return None


def shift_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return date(value.year + years, 2, 28)


def shift_months(value: date, months: int) -> date:
    index = value.month - 1 + months
    year = value.year + index // 12
    month = index % 12 + 1
    if month == 12:
        following = date(year + 1, 1, 1)
    else:
        following = date(year, month + 1, 1)
    last_day = (following - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def _age_ok(dob: date, on: date) -> bool:
    return age_on(dob, on) <= _MAX_AGE


def _birthday(dob: date, years: int) -> date:
    return shift_years(dob, years)


def _early_window(
    dob: date, started_on: date, as_of: date
) -> tuple[date, date, date] | None:
    earliest = started_on + timedelta(days=1)
    latest = _birthday(dob, 31) - timedelta(days=1)
    if earliest > latest:
        return None
    if remaining_benefit_months(latest, as_of) <= 0:
        return None
    suggested = shift_months(_birthday(dob, 31), -1)
    if suggested < earliest:
        suggested = earliest
    if suggested > latest:
        suggested = latest
    return earliest, latest, suggested
