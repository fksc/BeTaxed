"""Employment and document models with encrypted PII (KB/02, KB/04, DEV-830)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Employee(Base):
    __tablename__ = "employee"
    __table_args__ = (
        CheckConstraint(
            "company_id IS NOT NULL OR intake_id IS NOT NULL",
            name="ck_employee_scope",
        ),
        CheckConstraint(
            "first_permanent_elsewhere IN ('UNKNOWN', 'NO', 'YES')",
            name="ck_employee_first_permanent",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'ON_LEAVE', 'TERMINATED')",
            name="ck_employee_status",
        ),
        CheckConstraint(
            "status_source IN ('SS', 'USER', 'HRMS', 'ADMIN')",
            name="ck_employee_status_source",
        ),
        Index(
            "idx_employee_company_niss",
            "company_id",
            "niss_hash",
            unique=True,
            postgresql_where=text(
                "company_id IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        Index(
            "idx_employee_intake_niss",
            "intake_id",
            "niss_hash",
            unique=True,
            postgresql_where=text(
                "intake_id IS NOT NULL AND company_id IS NULL AND deleted_at IS NULL"
            ),
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
    niss_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    niss_enc: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    name_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    dob_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    first_permanent_elsewhere: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'UNKNOWN'")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )
    status_source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'SS'")
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class StoredFile(Base):
    __tablename__ = "stored_file"
    __table_args__ = (
        CheckConstraint(
            "company_id IS NOT NULL OR intake_id IS NOT NULL",
            name="ck_stored_file_scope",
        ),
        CheckConstraint(
            "kind IN ("
            "'SS_EXPORT', 'EMPLOYMENT_CONTRACT', 'CONVERSION_DECLARATION', "
            "'AT_NO_DEBT', 'INVOICE_PDF', 'PROFORMA', 'OTHER'"
            ")",
            name="ck_stored_file_kind",
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
    gcs_path: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_base.id"),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
