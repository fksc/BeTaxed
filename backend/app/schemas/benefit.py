from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BenefitCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str | None = None
    employee_id: uuid.UUID
    display_name: str | None = None
    state: str
    ineligibility_code: str | None
    sem_termo_on: date | None
    window_ends_on: date | None
    remaining_months: int | None = None
    monthly_saving: Decimal | None = None


class CompanyApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    submitted_on: date | None
    decision: str
    headcount_current: int | None
    headcount_trailing_12_avg: Decimal | None
    headcount_test_pass: bool | None
    ss_regularized_at_submit: bool | None
    at_regularized_at_submit: bool | None
    payroll_not_in_arrears_at_submit: bool | None


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    issued_on: date
    valid_until: date
    valid_until_overridden: bool
    created_at: datetime
