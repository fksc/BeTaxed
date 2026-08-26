"""Headcount and leave helpers for DEV-838 (no database)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.benefit_engine import (
    _should_clawback,
    add_calendar_months,
    add_months,
    build_leave_intervals,
    leave_covers_month,
    trailing_12_average,
)


def test_add_months_year_wrap() -> None:
    assert add_months(date(2026, 11, 1), 2) == date(2027, 1, 1)


def test_add_calendar_months_keeps_day_and_clamps() -> None:
    assert add_calendar_months(date(2026, 1, 15), 4) == date(2026, 5, 15)
    assert add_calendar_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_clawback_only_employer_listed_reasons() -> None:
    assert (
        _should_clawback(
            [
                SimpleNamespace(
                    event_type="STATUS_OVERRIDE",
                    initiator="EMPLOYER",
                    reason="NO_FAIR_MOTIVE",
                )
            ]
        )
        is True
    )
    assert (
        _should_clawback(
            [
                SimpleNamespace(
                    event_type="TERMINATED",
                    initiator="EMPLOYEE",
                    reason="NO_FAIR_MOTIVE",
                )
            ]
        )
        is False
    )


def test_leave_interval_covers_month() -> None:
    events = [
        SimpleNamespace(
            event_type="LEAVE_STARTED",
            effective_on=date(2026, 3, 10),
            created_at=date(2026, 3, 10),
        ),
        SimpleNamespace(
            event_type="LEAVE_ENDED",
            effective_on=date(2026, 5, 2),
            created_at=date(2026, 5, 2),
        ),
    ]
    intervals = build_leave_intervals(events)
    assert leave_covers_month(intervals, date(2026, 4, 1)) is True
    assert leave_covers_month(intervals, date(2026, 6, 1)) is False


def test_trailing_12_uses_ss_over_user_and_requires_history() -> None:
    rows = [
        SimpleNamespace(year_month=date(2026, 8, 1), source="SS_BATCH", headcount=12),
        SimpleNamespace(year_month=date(2026, 8, 1), source="USER", headcount=99),
        SimpleNamespace(year_month=date(2026, 7, 1), source="SS_BATCH", headcount=10),
        SimpleNamespace(year_month=date(2026, 6, 1), source="USER", headcount=10),
    ]
    current, avg, passed = trailing_12_average(rows, date(2026, 8, 15))
    assert current == 12
    assert avg == Decimal("10.00")
    assert passed is True
    empty_current, empty_avg, empty_pass = trailing_12_average([], date(2026, 8, 1))
    assert empty_current is None
    assert empty_avg is None
    assert empty_pass is False
