from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_id: uuid.UUID
    role: str
    is_active: bool


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    user_type: str
    preferred_language: str
    timezone: str
    is_active: bool
    last_login_at: datetime | None
    memberships: list[MembershipOut]


class CompanyScopeOut(BaseModel):
    company_id: uuid.UUID
    legal_name: str
    role: str | None
    actor: str
    ss_no_debt_valid_until: date | None = None
    at_no_debt_valid_until: date | None = None
    estimate_now_monthly: Decimal | None = None
    estimate_now_window: Decimal | None = None
    estimate_potential_monthly: Decimal | None = None
    estimate_potential_window: Decimal | None = None
    estimate_unconfirmed: bool = True
    contracts_missing: int = 0


class IntakeScopeOut(BaseModel):
    intake_id: uuid.UUID
    status: str
    actor: str
