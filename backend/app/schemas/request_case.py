"""Request-case API shapes. Company payloads omit the recipe. DEV-882."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PipelineStageOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    stage_type: str
    position: int
    entry_path: str | None = None
    operations: list[str] = Field(default_factory=list)


class RequestMoveOut(BaseModel):
    operation: str
    stage_id: uuid.UUID
    outcome: str | None = None


class RequestCaseOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    employee_id: uuid.UUID
    display_name: str | None
    stage_id: uuid.UUID
    stage_code: str
    stage_name: str
    stage_type: str
    path: str
    applied_on: date | None = None
    benefit_starts_on: date | None = None
    probation_ends_on: date | None = None
    minuta_sent: bool = False
    minuta_id: uuid.UUID | None = None
    notice_file_id: uuid.UUID | None = None
    operations: list[str] | None = None
    moves: list[RequestMoveOut] | None = None
    can_claim: bool | None = None
    can_attach_scan: bool | None = None
    remaining_months: int | None = None
    person_name: str | None = None
    person_address: str | None = None
    person_nif: str | None = None
    person_niss: str | None = None
    company_address: str | None = None
    company_signatory_name: str | None = None
    company_nif: str | None = None
    company_niss: str | None = None
    contract_started_on: date | None = None
    converted_on: date | None = None
    declared_on: date | None = None
    signed_place: str | None = None
    draft_html: str | None = None


class OpenRequestCaseIn(BaseModel):
    employee_id: uuid.UUID


class OperationIn(BaseModel):
    code: str
    payload: dict = Field(default_factory=dict)


class RejectionReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    label: str
    blocks_claim: bool


class MinutaTemplateIn(BaseModel):
    code: str
    title: str
    body_html: str


class MinutaTemplatePatch(BaseModel):
    title: str | None = None
    body_html: str | None = None
    is_active: bool | None = None


class MinutaTokenOut(BaseModel):
    key: str
    group: str


class CaseFactsIn(BaseModel):
    person_name: str | None = None
    person_address: str | None = None
    person_nif: str | None = None
    person_niss: str | None = None
    company_name: str | None = None
    company_address: str | None = None
    company_signatory_name: str | None = None
    company_nif: str | None = None
    company_niss: str | None = None
    contract_started_on: date | None = None
    converted_on: date | None = None
    declared_on: date | None = None
    signed_place: str | None = None


class MinutaDraftIn(BaseModel):
    body_html: str


class MinutaTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    body_html: str
    is_active: bool


class RequestFileOut(BaseModel):
    id: uuid.UUID
    kind: str
    request_case_id: uuid.UUID | None = None
