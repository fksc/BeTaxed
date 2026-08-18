"""Tenant DEK storage — one wrapped key per company or intake (KB/07)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, func, text
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TenantCryptoKey(Base):
    __tablename__ = "tenant_crypto_key"
    __table_args__ = (
        CheckConstraint(
            "(company_id IS NOT NULL AND intake_id IS NULL) OR "
            "(company_id IS NULL AND intake_id IS NOT NULL)",
            name="ck_tenant_crypto_key_scope",
        ),
        Index(
            "idx_tenant_crypto_key_company",
            "company_id",
            unique=True,
            postgresql_where=text("company_id IS NOT NULL"),
        ),
        Index(
            "idx_tenant_crypto_key_intake",
            "intake_id",
            unique=True,
            postgresql_where=text("intake_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("company.id"),
        nullable=True,
    )
    intake_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intake.id"),
        nullable=True,
    )
    wrapped_dek: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    key_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
