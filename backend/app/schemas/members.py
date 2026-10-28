from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class SalesCompanyIn(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trading_name: str | None = Field(default=None, max_length=255)
    locale: str = Field(default="pt", max_length=10)
    nif: str | None = Field(default=None, max_length=32)
    admin_email: str = Field(min_length=3, max_length=255)
    admin_given_name: str = Field(min_length=1, max_length=100)
    admin_family_name: str = Field(min_length=1, max_length=100)
    admin_role: str = "ADMIN"


class CompanyPatchIn(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    trading_name: str | None = Field(default=None, max_length=255)
    locale: str | None = Field(default=None, max_length=10)
    max_members: int | None = Field(default=None, ge=1, le=500)
    registered_address: str | None = None
    signatory_name: str | None = Field(default=None, max_length=255)
    ss_subconta_username: str | None = Field(default=None, max_length=255)
    ss_subconta_password: str | None = Field(default=None, max_length=255)
    ss_subconta_available_on: date | None = None
    clear_ss_subconta: bool = False


class MemberInviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = "HR"


class InviteAcceptIn(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    needs_password: bool
    expires_at: datetime
    sent_at: datetime | None
    last_error: str | None
    created_at: datetime
    invite_url: str | None = None

    model_config = {"from_attributes": True}


class MembersBundleOut(BaseModel):
    max_members: int
    seats_used: int
    members: list[MemberOut]
    invites: list[InviteOut]


class OpsCompanyListOut(BaseModel):
    id: uuid.UUID
    legal_name: str
    trading_name: str | None
    locale: str
    status: str
    max_members: int
    seats_used: int
    has_nif: bool
    created_from_intake_id: uuid.UUID | None
    created_at: datetime


class OpsCompanyDetailOut(OpsCompanyListOut):
    members: list[MemberOut]
    invites: list[InviteOut]
    registered_address: str | None = None
    signatory_name: str | None = None
    ss_subconta_username: str | None = None
    has_ss_subconta_password: bool = False
    ss_subconta_available_on: date | None = None


class SsSubcontaRevealOut(BaseModel):
    username: str | None = None
    password: str | None = None


class PublicInviteOut(BaseModel):
    company_name: str
    email: str
    given_name: str | None = None
    family_name: str | None = None
    role: str
    status: str
    needs_password: bool
    expires_at: datetime


class SalesCompanyOut(OpsCompanyDetailOut):
    invite_url: str | None = None
