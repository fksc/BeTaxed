from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SsBatchOut(BaseModel):
    """Company-facing batch summary. Counts only — no names, rates, or pay."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_year_month: date
    parse_status: str
    parse_error: str | None
    uploaded_at: datetime
    event_counts: dict[str, int]


class HeadcountMonthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year_month: date
    headcount: int
    source: str
    source_batch_id: uuid.UUID | None


class HeadcountMonthIn(BaseModel):
    year_month: str = Field(min_length=7, max_length=10)
    headcount: int = Field(ge=0)
