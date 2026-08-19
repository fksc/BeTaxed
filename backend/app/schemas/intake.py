from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IntakeBatchSummary(BaseModel):
    id: uuid.UUID
    parse_status: str
    parse_error: str | None
    vinculo_count: int
    contrato_count: int
    period_year_month: date


class IntakeOut(BaseModel):
    """Pass 1 teaser surface. Never include names, rates, or remaining months."""

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


class IntakeCreatedOut(IntakeOut):
    session_token: str | None = None


class ConvertIntakeIn(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trading_name: str | None = Field(default=None, max_length=255)


class ConvertIntakeOut(IntakeOut):
    company_id: uuid.UUID
    membership_role: str | None
