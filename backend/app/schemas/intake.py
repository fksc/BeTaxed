from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IntakeBatchSummary(BaseModel):
    id: uuid.UUID
    parse_status: str
    parse_error: str | None
    vinculo_count: int
    contrato_count: int
    period_year_month: date


class VerbosePersonOut(BaseModel):
    """Present only when ENV=DEV and VERBOSE is true. Never includes NISS."""

    name: str | None
    age: int | None
    contract: str
    contract_label: str | None
    started_on: date | None
    salary: Decimal | None
    bucket: Literal["now", "potential", "none"]
    how_code: str
    remaining_months: int | None
    monthly_eur: Decimal | None
    window_eur: Decimal | None


class IntakeOut(BaseModel):
    """Pass 1 teaser surface. Recipe rows only when verbose_people is set."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    user_id: uuid.UUID | None
    teaser_now_monthly: Decimal | None
    teaser_now_window: Decimal | None
    teaser_potential_monthly: Decimal | None
    teaser_potential_window: Decimal | None
    teaser_currency: str
    converted_company_id: uuid.UUID | None
    latest_batch: IntakeBatchSummary | None = None
    verbose_people: list[VerbosePersonOut] | None = None


class IntakeCreatedOut(IntakeOut):
    session_token: str | None = None


class ConvertIntakeIn(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trading_name: str | None = Field(default=None, max_length=255)


class ConvertIntakeOut(IntakeOut):
    company_id: uuid.UUID
    membership_role: str | None
