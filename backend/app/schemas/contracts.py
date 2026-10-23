from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TermReadingOut(BaseModel):
    rule: Literal["certo_renewal", "years_2", "years_3", "years_4", "incerto_4"]
    deemed_on: date
    can_benefit: bool = True


class TermBenefitOut(BaseModel):
    """Staff-only. Omitted for company users."""

    flagged: bool
    readings: list[TermReadingOut] = Field(default_factory=list)
    early_earliest: date | None = None
    early_latest: date | None = None
    early_suggested: date | None = None


class BenefitBlockOut(BaseModel):
    """Staff-only. Why this person cannot open the hiring benefit."""

    reason: Literal[
        "no_start",
        "employment_ended",
        "age_at_start",
        "window_over",
        "term_no_day",
        "term_early_over",
        "term_dates_over",
        "other_modality",
    ]
    contract_started_on: date | None = None
    age_on_start: int | None = None
    counted_to: date | None = None
    last_day: date | None = None


class PersonOut(BaseModel):
    id: uuid.UUID
    display_name: str | None
    status: str
    status_source: str
    has_source_conflict: bool = False
    leave_type: str | None = None
    employment_id: uuid.UUID | None
    contract_modality: str | None = None
    has_contract: bool
    review_status: str | None
    document_id: uuid.UUID | None
    already_on_ss_reduction: bool = False
    age: int | None = None
    contract_started_on: date | None = None
    benefit_outlook: Literal["already", "might", "never"] | None = None
    benefit_block: BenefitBlockOut | None = None
    term_benefit: TermBenefitOut | None = None


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


class ContractBatchItemOut(BaseModel):
    inbox_id: uuid.UUID
    filename: str | None
    status: str
    match_via: str | None = None
    employee_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None


class ContractBatchOut(BaseModel):
    items: list[ContractBatchItemOut]


class ContractWorkerIn(BaseModel):
    inbox_id: uuid.UUID | None = None
    employment_document_id: uuid.UUID | None = None


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
