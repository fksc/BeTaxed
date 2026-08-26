"""Remunerações leave ingest apply (DEV-849 / SL-004)."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from sqlalchemy import select

from app.db import AsyncSessionLocal, engine
from app.models import (
    Employee,
    EmploymentEvent,
    Intake,
    StoredFile,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.services.ss_apply import apply_ss_batch, delete_intake_employment_spine
from app.services.ss_ingest import ingest_ss_export
from app.services.ss_parser import SsSourceFile
from app.storage import get_object_storage
from tests.ss_xlsx_fixtures import PERSON_A, combined_workbook, leave_row
from tests.test_ss_apply import _cleanup


@pytest.fixture
def db_session():
    return True


def test_apply_does_not_invent_leave_from_vinculos(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        try:
            async with AsyncSessionLocal() as session:
                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()
                intake_id = intake.id
                ingested = await ingest_ss_export(
                    session,
                    files=[SsSourceFile("ss.xlsx", combined_workbook())],
                    period_year_month=date(2026, 8, 1),
                    intake_id=intake.id,
                )
                applied = await apply_ss_batch(session, ingested.batch.id)
                assert "LEAVE_STARTED" not in applied.event_types
                assert "LEAVE_ENDED" not in applied.event_types
                stored = (
                    await session.execute(
                        select(StoredFile).where(StoredFile.intake_id == intake.id)
                    )
                ).scalars().all()
                storage_paths.extend(row.gcs_path for row in stored)
        finally:
            async with AsyncSessionLocal() as session:
                if intake_id is not None:
                    await _cleanup(session, intake_id)
            storage = get_object_storage()
            for path in storage_paths:
                storage.delete(path)
            await engine.dispose()

    asyncio.run(body())


def test_remuneracoes_emits_leave_start_end_and_user_conflict(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        try:
            async with AsyncSessionLocal() as session:
                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()
                intake_id = intake.id

                async def run(content: bytes, period: date) -> list[str]:
                    ingested = await ingest_ss_export(
                        session,
                        files=[SsSourceFile("ss.xlsx", content)],
                        period_year_month=period,
                        intake_id=intake.id,
                    )
                    applied = await apply_ss_batch(session, ingested.batch.id)
                    stored = (
                        await session.execute(
                            select(StoredFile).where(StoredFile.intake_id == intake.id)
                        )
                    ).scalars().all()
                    storage_paths.extend(row.gcs_path for row in stored)
                    return applied.event_types

                started = await run(
                    combined_workbook(
                        leave_rows=[
                            leave_row(
                                PERSON_A,
                                leave_type="PARENTAL",
                                started=date(2026, 6, 10),
                            )
                        ]
                    ),
                    date(2026, 6, 1),
                )
                assert "HIRED" in started
                assert "LEAVE_STARTED" in started

                crypto = await get_or_create_pii_crypto(session, intake_id=intake.id)
                people = (
                    await session.execute(
                        select(Employee).where(Employee.intake_id == intake.id)
                    )
                ).scalars().all()
                alice = next(
                    row
                    for row in people
                    if crypto.decrypt_niss(row.niss_enc) == PERSON_A
                )
                assert alice.status == "ON_LEAVE"
                assert alice.status_source == "SS"
                leave_event = (
                    await session.execute(
                        select(EmploymentEvent).where(
                            EmploymentEvent.employee_id == alice.id,
                            EmploymentEvent.event_type == "LEAVE_STARTED",
                        )
                    )
                ).scalar_one()
                assert leave_event.source == "SS_DIFF"
                assert leave_event.leave_type == "PARENTAL"

                omitted = await run(combined_workbook(), date(2026, 7, 1))
                assert "LEAVE_ENDED" not in omitted
                await session.refresh(alice)
                assert alice.status == "ON_LEAVE"

                ended = await run(
                    combined_workbook(leave_rows=[]),
                    date(2026, 8, 1),
                )
                assert "LEAVE_ENDED" in ended
                await session.refresh(alice)
                assert alice.status == "ACTIVE"
                assert alice.status_source == "SS"

                alice.status = "ACTIVE"
                alice.status_source = "USER"
                await session.flush()
                conflict = await run(
                    combined_workbook(
                        leave_rows=[
                            leave_row(
                                PERSON_A,
                                leave_type="SICKNESS",
                                started=date(2026, 9, 1),
                            )
                        ]
                    ),
                    date(2026, 9, 1),
                )
                assert "SOURCE_CONFLICT" in conflict
                assert "LEAVE_STARTED" not in conflict
                await session.refresh(alice)
                assert alice.status == "ACTIVE"
                assert alice.status_source == "USER"
        finally:
            async with AsyncSessionLocal() as session:
                if intake_id is not None:
                    await _cleanup(session, intake_id)
            storage = get_object_storage()
            for path in storage_paths:
                storage.delete(path)
            await engine.dispose()

    asyncio.run(body())
