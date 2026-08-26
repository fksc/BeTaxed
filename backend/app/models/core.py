"""Spine tables: user_base, company, company_membership, intake (KB/01, DEV-828)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserBase(Base):
    __tablename__ = "user_base"
    __table_args__ = (
        CheckConstraint(
            "user_type IN ('BETAXED_STAFF', 'COMPANY_STAFF')",
            name="ck_user_base_user_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    user_type: Mapped[str] = mapped_column(String(20), nullable=False)
    preferred_language: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'pt'"), default="pt"
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'Europe/Lisbon'"),
        default="Europe/Lisbon",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE"), default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    memberships: Mapped[list[CompanyMembership]] = relationship(
        back_populates="user"
    )
    intakes: Mapped[list[Intake]] = relationship(back_populates="user")


class Company(Base):
    __tablename__ = "company"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'CHURNED')",
            name="ck_company_status",
        ),
        CheckConstraint(
            "invoicing_method IS NULL OR invoicing_method IN "
            "('STRIPE_SEPA', 'CERTIFIED_SOFTWARE')",
            name="ck_company_invoicing_method",
        ),
        CheckConstraint("max_members >= 1", name="ck_company_max_members"),
        Index(
            "idx_company_employer_niss_hash",
            "employer_niss_hash",
            unique=True,
            postgresql_where=text(
                "employer_niss_hash IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nif_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    employer_niss_hash: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    employer_niss_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ACTIVE'")
    )
    locale: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'pt'")
    )
    ss_regularized: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    at_regularized: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payroll_not_in_arrears: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invoicing_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    certified_vendor_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    max_members: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3"), default=3
    )
    created_from_intake_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intake.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    memberships: Mapped[list[CompanyMembership]] = relationship(
        back_populates="company"
    )
    invites: Mapped[list[CompanyInvite]] = relationship(
        back_populates="company"
    )
    created_from_intake: Mapped[Intake | None] = relationship(
        foreign_keys=[created_from_intake_id],
        back_populates="created_companies",
    )
    converted_intakes: Mapped[list[Intake]] = relationship(
        foreign_keys="Intake.converted_company_id",
        back_populates="converted_company",
    )


class CompanyMembership(Base):
    __tablename__ = "company_membership"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'HR', 'FINANCE')",
            name="ck_company_membership_role",
        ),
        UniqueConstraint("user_id", "company_id", name="uq_company_membership_user_company"),
        Index("idx_membership_company", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_base.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE"), default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[UserBase] = relationship(back_populates="memberships")
    company: Mapped[Company] = relationship(back_populates="memberships")
    invites: Mapped[list[CompanyInvite]] = relationship(
        back_populates="membership"
    )


class CompanyInvite(Base):
    __tablename__ = "company_invite"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'HR', 'FINANCE')",
            name="ck_company_invite_role",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'EXPIRED', 'FAILED', 'CANCELLED')",
            name="ck_company_invite_status",
        ),
        UniqueConstraint("token_hash", name="uq_company_invite_token_hash"),
        Index("idx_company_invite_company", "company_id"),
        Index("idx_company_invite_email", "company_id", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    given_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_base.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_base.id"), nullable=True
    )
    membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_membership.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDING'")
    )
    needs_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE"), default=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="invites")
    membership: Mapped[CompanyMembership | None] = relationship(
        back_populates="invites"
    )


class Intake(Base):
    __tablename__ = "intake"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'CONVERTED', 'DECLINED', 'PURGED')",
            name="ck_intake_status",
        ),
        Index("idx_intake_user", "user_id"),
        Index("idx_intake_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_base.id"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_token_hash: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'OPEN'")
    )
    teaser_now_monthly: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    teaser_now_window: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    teaser_potential_monthly: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    teaser_potential_window: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    teaser_currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'EUR'")
    )
    teaser_regime_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incentive_regime.id"), nullable=True
    )
    converted_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[UserBase | None] = relationship(back_populates="intakes")
    converted_company: Mapped[Company | None] = relationship(
        foreign_keys=[converted_company_id],
        back_populates="converted_intakes",
    )
    created_companies: Mapped[list[Company]] = relationship(
        foreign_keys="Company.created_from_intake_id",
        back_populates="created_from_intake",
    )
