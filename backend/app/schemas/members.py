from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SalesCompanyIn(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trading_name: str | None = Field(default=None, max_length=255)
    locale: str = Field(default="pt", max_length=10)
    nif: str | None = Field(default=None, max_length=32)
    admin_email: str = Field(min_length=3, max_length=255)
    admin_role: str = "ADMIN"


class CompanyPatchIn(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    trading_name: str | None = Field(default=None, max_length=255)
    locale: str | None = Field(default=None, max_length=10)
    max_members: int | None = Field(default=None, ge=1, le=500)


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


class PublicInviteOut(BaseModel):
    company_name: str
    email: str
    role: str
    status: str
    needs_password: bool
    expires_at: datetime


class SalesCompanyOut(OpsCompanyDetailOut):
    invite_url: str | None = None
