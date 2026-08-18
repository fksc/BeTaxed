"""Core schema round-trip against local Postgres (DEV-828)."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db import AsyncSessionLocal
from app.models import Company, CompanyMembership, Intake, UserBase


@pytest.fixture
def db_session():
    """Marks tests that need Postgres. Session is opened inside the test."""
    return True


def test_core_spine_tables_and_roundtrip(db_session) -> None:
    async def body() -> None:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public' "
                        "AND tablename IN "
                        "('user_base', 'company', 'company_membership', 'intake')"
                    )
                )
            ).fetchall()
            names = {r[0] for r in rows}
            assert names == {
                "user_base",
                "company",
                "company_membership",
                "intake",
            }

            intake_cols = (
                await session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'intake'"
                    )
                )
            ).scalars().all()
            assert "teaser_now_monthly" in intake_cols
            assert "teaser_now_window" in intake_cols
            assert "teaser_potential_monthly" in intake_cols
            assert "teaser_potential_window" in intake_cols
            assert "teaser_amount" not in intake_cols
            assert "reason" not in intake_cols

            company_cols = (
                await session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'company'"
                    )
                )
            ).scalars().all()
            assert "certified_vendor_name" in company_cols

            user = UserBase(
                firebase_uid=f"fb-{uuid.uuid4()}",
                email=f"ops-{uuid.uuid4().hex[:8]}@example.com",
                user_type="COMPANY_STAFF",
            )
            session.add(user)
            await session.flush()

            intake = Intake(
                user_id=None,
                status="OPEN",
                teaser_now_monthly=Decimal("1200.00"),
                teaser_now_window=Decimal("72000.00"),
                teaser_potential_monthly=Decimal("400.00"),
                teaser_potential_window=Decimal("24000.00"),
            )
            session.add(intake)
            await session.flush()
            await session.refresh(intake)
            assert intake.user_id is None
            assert intake.teaser_currency == "EUR"

            company = Company(
                legal_name="Acme Lda",
                created_from_intake_id=intake.id,
                certified_vendor_name=None,
            )
            session.add(company)
            await session.flush()

            intake.status = "CONVERTED"
            intake.converted_company_id = company.id
            intake.user_id = user.id

            membership = CompanyMembership(
                user_id=user.id,
                company_id=company.id,
                role="ADMIN",
            )
            session.add(membership)
            await session.commit()

            loaded = await session.get(Company, company.id)
            assert loaded is not None
            assert loaded.created_from_intake_id == intake.id
            assert loaded.certified_vendor_name is None
            assert loaded.invoicing_method is None

            reloaded_intake = await session.get(Intake, intake.id)
            assert reloaded_intake is not None
            assert reloaded_intake.converted_company_id == company.id
            assert reloaded_intake.teaser_now_monthly == Decimal("1200.00")

            await session.delete(membership)
            await session.flush()
            reloaded_intake.converted_company_id = None
            loaded.created_from_intake_id = None
            await session.flush()
            await session.delete(loaded)
            await session.delete(reloaded_intake)
            await session.delete(user)
            await session.commit()

    asyncio.run(body())
