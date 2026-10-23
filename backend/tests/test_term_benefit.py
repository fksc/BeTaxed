"""DEV-877 term-to-permanent clocks. No database."""

from datetime import date
from decimal import Decimal

from app.services.term_benefit import (
    assess_term_benefit,
    classify_hiring_benefit,
    term_length_months,
)


def test_certo_twelve_months_shows_later_caps_when_two_year_window_is_over():
    # Hired 2019-01-01, first term 12 months. One renewal is 2021-01-01.
    # As of Oct 2026 that 60-month window is over. The 3- and 4-year
    # readings still have months, and age on those dates is under 31.
    flag = assess_term_benefit(
        modality="TERMO_CERTO",
        started_on=date(2019, 1, 1),
        dob=date(1995, 1, 1),
        as_of=date(2026, 10, 1),
        term_months=12,
    )
    assert flag is not None
    assert [row.rule for row in flag.readings] == ["years_3", "years_4"]
    assert flag.readings[0].deemed_on == date(2022, 1, 1)
    assert flag.readings[1].deemed_on == date(2023, 1, 1)
    assert flag.early_earliest is None


def test_certo_six_months_renews_once_for_the_same_length():
    assert term_length_months(date(2019, 1, 1), date(2019, 7, 1)) == 6
    flag = assess_term_benefit(
        modality="TERMO_CERTO",
        started_on=date(2019, 1, 1),
        dob=date(1998, 1, 1),
        as_of=date(2020, 6, 1),
        term_months=6,
    )
    assert flag is not None
    rules = {row.rule: row.deemed_on for row in flag.readings}
    assert rules["certo_renewal"] == date(2020, 1, 1)
    assert rules["years_2"] == date(2021, 1, 1)
    assert flag.early_earliest is None


def test_early_window_when_renewal_would_be_age_31():
    # Turns 31 on 2021-06-01. A 12-month certo's renewal (2021-01-01) is
    # still age 30, so this uses an 18-month first term: renewal is
    # 2022-01-01, which is already 31. The 2-year line is still open.
    flag = assess_term_benefit(
        modality="TERMO_CERTO",
        started_on=date(2019, 1, 1),
        dob=date(1990, 6, 1),
        as_of=date(2024, 1, 1),
        term_months=18,
    )
    assert flag is not None
    assert [row.rule for row in flag.readings] == ["years_2"]
    assert flag.readings[0].deemed_on == date(2021, 1, 1)
    assert flag.early_earliest == date(2019, 1, 2)
    assert flag.early_latest == date(2021, 5, 31)
    assert flag.early_suggested == date(2021, 5, 1)


def test_early_window_closed_when_sixty_months_from_the_last_day_are_over():
    assert (
        assess_term_benefit(
            modality="TERMO_CERTO",
            started_on=date(2019, 1, 1),
            dob=date(1990, 6, 1),
            as_of=date(2026, 10, 1),
            term_months=18,
        )
        is None
    )


def test_incerto_is_only_the_four_year_line():
    flag = assess_term_benefit(
        modality="TERMO_INCERTO",
        started_on=date(2024, 1, 1),
        dob=date(2000, 1, 1),
        as_of=date(2026, 10, 1),
        term_months=12,
    )
    assert flag is not None
    assert [(row.rule, row.deemed_on) for row in flag.readings] == [
        ("incerto_4", date(2028, 1, 1))
    ]
    assert flag.early_earliest is None


def test_incerto_early_window_when_four_years_is_already_31():
    flag = assess_term_benefit(
        modality="TERMO_INCERTO",
        started_on=date(2020, 1, 1),
        dob=date(1990, 3, 1),
        as_of=date(2025, 1, 1),
        term_months=None,
    )
    assert flag is not None
    assert flag.readings == ()
    assert flag.early_earliest == date(2020, 1, 2)
    assert flag.early_latest == date(2021, 2, 28)
    assert flag.early_suggested == date(2021, 2, 1)


def test_one_day_after_the_contract_can_be_the_day_before_31():
    flag = assess_term_benefit(
        modality="TERMO_INCERTO",
        started_on=date(2026, 1, 1),
        dob=date(1995, 1, 3),
        as_of=date(2026, 10, 1),
        term_months=None,
    )
    assert flag is not None
    assert flag.early_earliest == date(2026, 1, 2)
    assert flag.early_latest == date(2026, 1, 2)
    assert flag.early_suggested == date(2026, 1, 2)


def test_already_31_on_the_contract_date_is_not_flagged():
    assert (
        assess_term_benefit(
            modality="TERMO_CERTO",
            started_on=date(2019, 1, 1),
            dob=date(1988, 1, 1),
            as_of=date(2019, 6, 1),
            term_months=12,
        )
        is None
    )


def test_outlook_might_covers_an_open_permanent_contract_and_a_flagged_term():
    permanent = classify_hiring_benefit(
        already=False,
        modality="SEM_TERMO",
        started_on=date(2024, 1, 2),
        employment_open=True,
        status="ACTIVE",
        dob=date(1998, 3, 15),
        salary=Decimal("1500"),
        as_of=date(2026, 8, 1),
        term_months=None,
    )
    assert permanent.outlook == "might"
    assert permanent.reason is None
    term = classify_hiring_benefit(
        already=False,
        modality="TERMO_CERTO",
        started_on=date(2019, 1, 1),
        employment_open=True,
        status="ACTIVE",
        dob=date(1995, 1, 1),
        salary=Decimal("1500"),
        as_of=date(2026, 10, 1),
        term_months=12,
    )
    assert term.outlook == "might"
    assert term.reason is None


def test_outlook_never_when_the_window_or_the_age_is_closed():
    assert (
        classify_hiring_benefit(
            already=False,
            modality="SEM_TERMO",
            started_on=date(2019, 1, 1),
            employment_open=True,
            status="ACTIVE",
            dob=date(1995, 1, 1),
            salary=Decimal("1500"),
            as_of=date(2026, 10, 1),
            term_months=None,
        ).reason
        == "window_over"
    )
    assert (
        classify_hiring_benefit(
            already=False,
            modality="TERMO_CERTO",
            started_on=date(2019, 1, 1),
            employment_open=True,
            status="ACTIVE",
            dob=date(1988, 1, 1),
            salary=Decimal("1500"),
            as_of=date(2019, 6, 1),
            term_months=12,
        ).reason
        == "term_no_day"
    )
    assert (
        classify_hiring_benefit(
            already=True,
            modality="SEM_TERMO",
            started_on=date(2019, 1, 1),
            employment_open=True,
            status="ACTIVE",
            dob=date(1995, 1, 1),
            salary=Decimal("1500"),
            as_of=date(2026, 10, 1),
            term_months=None,
        ).outlook
        == "already"
    )


def test_never_reason_names_the_first_closed_path():
    aged = classify_hiring_benefit(
        already=False,
        modality="SEM_TERMO",
        started_on=date(2019, 1, 1),
        employment_open=True,
        status="ACTIVE",
        dob=date(1980, 1, 1),
        salary=Decimal("1500"),
        as_of=date(2020, 1, 1),
        term_months=None,
    )
    assert aged is not None
    assert aged.reason == "age_at_start"
    assert aged.age_on_start == 39

    early = classify_hiring_benefit(
        already=False,
        modality="TERMO_CERTO",
        started_on=date(2019, 1, 1),
        employment_open=True,
        status="ACTIVE",
        dob=date(1990, 6, 1),
        salary=Decimal("1500"),
        as_of=date(2026, 10, 1),
        term_months=18,
    )
    assert early is not None
    assert early.reason == "term_early_over"
    assert early.last_day == date(2021, 5, 31)

    dates = classify_hiring_benefit(
        already=False,
        modality="TERMO_CERTO",
        started_on=date(2019, 1, 1),
        employment_open=True,
        status="ACTIVE",
        dob=date(1995, 1, 1),
        salary=Decimal("1500"),
        as_of=date(2028, 2, 1),
        term_months=12,
    )
    assert dates is not None
    assert dates.reason == "term_dates_over"

    ended = classify_hiring_benefit(
        already=False,
        modality="SEM_TERMO",
        started_on=date(2024, 1, 2),
        employment_open=False,
        status="TERMINATED",
        dob=date(1998, 3, 15),
        salary=Decimal("1500"),
        as_of=date(2026, 8, 1),
        term_months=None,
    )
    assert ended is not None and ended.reason == "employment_ended"

    missing = classify_hiring_benefit(
        already=False,
        modality="SEM_TERMO",
        started_on=None,
        employment_open=True,
        status="ACTIVE",
        dob=date(1998, 3, 15),
        salary=Decimal("1500"),
        as_of=date(2026, 8, 1),
        term_months=None,
    )
    assert missing is not None and missing.reason == "no_start"

    other = classify_hiring_benefit(
        already=False,
        modality="OTHER",
        started_on=date(2024, 1, 2),
        employment_open=True,
        status="ACTIVE",
        dob=date(1998, 3, 15),
        salary=Decimal("1500"),
        as_of=date(2026, 8, 1),
        term_months=None,
    )
    assert other is not None and other.reason == "other_modality"


def test_outlook_stays_unset_without_a_date_of_birth_or_salary():
    assert (
        classify_hiring_benefit(
            already=False,
            modality="SEM_TERMO",
            started_on=date(2024, 1, 2),
            employment_open=True,
            status="ACTIVE",
            dob=None,
            salary=Decimal("1500"),
            as_of=date(2026, 8, 1),
            term_months=None,
        )
        is None
    )
    assert (
        classify_hiring_benefit(
            already=False,
            modality="SEM_TERMO",
            started_on=date(2024, 1, 2),
            employment_open=True,
            status="ACTIVE",
            dob=date(1998, 3, 15),
            salary=None,
            as_of=date(2026, 8, 1),
            term_months=None,
        )
        is None
    )


def test_sem_termo_is_not_this_flag():
    assert (
        assess_term_benefit(
            modality="SEM_TERMO",
            started_on=date(2024, 1, 1),
            dob=date(2000, 1, 1),
            as_of=date(2026, 1, 1),
            term_months=None,
        )
        is None
    )
