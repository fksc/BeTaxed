from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PersonOut(BaseModel):
    id: uuid.UUID
    display_name: str | None
    status: str
    status_source: str
    has_source_conflict: bool = False
    leave_type: str | None = None
    employment_id: uuid.UUID | None
    has_contract: bool
    review_status: str | None
    document_id: uuid.UUID | None


class StatusOverrideIn(BaseModel):
    status: Literal["ACTIVE", "ON_LEAVE", "TERMINATED"]
    effective_on: date | None = None
    leave_type: Literal["PARENTAL", "SICKNESS", "UNPAID", "OTHER"] | None = Field(
        default=None
    )


class ContractUploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    employment_id: uuid.UUID | None
    review_status: str
    matches_ss: str | None = None


class MismatchFlagOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str | None
    employee_id: uuid.UUID
    display_name: str | None
    filename: str | None
    doc_kind: str | None
    signed_on: date | None
    term_end_on: date | None
    ss_modality: str | None
    ss_started_on: date | None
    ss_ended_on: date | None
    ops_confirmed_at: datetime | None
    created_at: datetime


class NotificationOut(BaseModel):
    id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    is_read: bool
    created_at: datetime
    company_id: uuid.UUID | None


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int
