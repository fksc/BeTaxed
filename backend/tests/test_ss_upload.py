"""SS upload helpers — no database (DEV-835)."""

from datetime import date

import pytest
from fastapi import HTTPException

from app.services.ss_upload import parse_period_year_month


def test_parse_period_accepts_yyyy_mm() -> None:
    assert parse_period_year_month("2026-09") == date(2026, 9, 1)


def test_parse_period_rejects_mid_month() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_period_year_month("2026-09-15")
    assert exc.value.status_code == 400
