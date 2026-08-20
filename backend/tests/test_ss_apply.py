"""Apply SS raw rows onto employee / employment / pay / events (DEV-834)."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, text

from app.db import AsyncSessionLocal, engine
from app.models import (
    CompensationPeriod,
    Employee,
    EmployeeExternalId,
    Employment,
    EmploymentEvent,
    Intake,
    SsBatch,
    StoredFile,
    TenantCryptoKey,
    Workplace,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.services.ss_apply import apply_ss_batch, delete_intake_employment_spine
from app.services.ss_ingest import ingest_ss_export
from app.services.ss_parser import SsSourceFile
from app.storage import get_object_storage
from tests.ss_xlsx_fixtures import (
    CONTRATO_HEADERS,
    EMPLOYER_NISS,
    PERSON_A,
    PERSON_B,
    VINCULO_HEADERS,
    build_xlsx,
    combined_workbook,
    contrato_row,
    vinculo_row,
)

PERSON_C = "55555555555"


@pytest.fixture
def db_session():
    return True


def _people_xlsx(
    people: list[tuple[str, dict]],
) -> bytes:
    vinculos = [VINCULO_HEADERS]
    contratos = [CONTRATO_HEADERS]
    for niss, opts in people:
        vinculos.append(
            vinculo_row(
                niss,
                name=opts.get("name", "Test"),
                started=opts.get("started", date(2024, 1, 2)),
                ended=opts.get("ended"),
                taxa=opts.get("taxa", 34.75),
            )
        )
        contratos.append(
            contrato_row(
                niss,
                name=opts.get("name", "Test"),
                modality=opts.get("modality", "Sem termo, tempo completo"),
                started=opts.get("started", date(2024, 1, 2)),
                ended=opts.get("contract_ended"),
                rendimento_from=opts.get("pay_from", date(2025, 1, 1)),
                rendimento_to=opts.get("pay_to"),
                salary=opts.get("salary", 1500),
            )
        )
    return build_xlsx({"Vínculos": vinculos, "Contratos": contratos})


def test_employment_spine_tables_exist(db_session) -> None:
    async def body() -> None:
        try:
            async with AsyncSessionLocal() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'public' "
                            "AND tablename IN ("
                            "'workplace', 'employment', 'compensation_period', "
                            "'employment_event', 'employee_external_id'"
                            ")"
                        )
                    )
                ).fetchall()
                names = {row[0] for row in rows}
                assert names == {
                    "workplace",
                    "employment",
                    "compensation_period",
                    "employment_event",
                    "employee_external_id",
                }
                cols = (
                    await session.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'employee'"
                        )
                    )
                ).scalars().all()
                assert "first_permanent_source" in cols
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_first_apply_hires_and_current_pay(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        try:
            async with AsyncSessionLocal() as session:
                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()
                intake_id = intake.id
                filename = f"{EMPLOYER_NISS}_vinculos_2026_08_12.xlsx"
                result = await ingest_ss_export(
                    session,
                    files=[SsSourceFile(filename, combined_workbook())],
                    period_year_month=date(2026, 8, 1),
                    intake_id=intake.id,
                )
                applied = await apply_ss_batch(session, result.batch.id)
                await session.commit()
                assert set(applied.event_types) == {"HIRED"}
                assert applied.event_types.count("HIRED") == 2
                assert result.batch.parse_status == "APPLIED"

                employees = (
                    await session.execute(
                        select(Employee).where(Employee.intake_id == intake.id)
                    )
                ).scalars().all()
                assert len(employees) == 2
                assert {row.first_permanent_elsewhere for row in employees} == {"UNKNOWN"}
                assert {row.first_permanent_source for row in employees} == {"UNKNOWN"}
                assert all(row.status == "ACTIVE" for row in employees)

                ext = (
                    await session.execute(select(func.count()).select_from(EmployeeExternalId))
                ).scalar_one()
                assert int(ext) == 0

                employments = (
                    await session.execute(
                        select(Employment).where(Employment.intake_id == intake.id)
                    )
                ).scalars().all()
                assert len(employments) == 2
                assert {row.contract_modality for row in employments} == {"SEM_TERMO"}
                assert all(row.ended_on is None for row in employments)

                pays = (
                    await session.execute(
                        select(CompensationPeriod).where(
                            CompensationPeriod.employment_id.in_(
                                [row.id for row in employments]
                            )
                        )
                    )
                ).scalars().all()
                assert {row.base_salary for row in pays} == {
                    Decimal("1500.00"),
                    Decimal("2000.00"),
                }
                assert all(row.period_to is None for row in pays)

                workplaces = (
                    await session.execute(
                        select(Workplace).where(Workplace.intake_id == intake.id)
                    )
                ).scalars().all()
                assert len(workplaces) >= 1

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


def test_apply_diff_salary_missing_conflict_rehire(db_session) -> None:
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

                month1 = _people_xlsx(
                    [
                        (PERSON_A, {"name": "Alice", "salary": 1500}),
                        (PERSON_B, {"name": "Bruno", "salary": 2000}),
                    ]
                )
                assert (await run(month1, date(2026, 6, 1))).count("HIRED") == 2

                alice = (
                    await session.execute(
                        select(Employee).where(Employee.intake_id == intake.id)
                    )
                ).scalars().all()
                crypto = await get_or_create_pii_crypto(session, intake_id=intake.id)
                alice_emp = next(
                    row
                    for row in alice
                    if crypto.decrypt_niss(row.niss_enc) == PERSON_A
                )
                alice_emp.status = "TERMINATED"
                alice_emp.status_source = "USER"
                await session.flush()

                month2 = _people_xlsx(
                    [
                        (
                            PERSON_A,
                            {
                                "name": "Alice",
                                "salary": 1800,
                                "pay_from": date(2026, 7, 1),
                                "taxa": 23.75,
                                "modality": "A termo certo, tempo completo",
                            },
                        ),
                        (PERSON_C, {"name": "Carla", "salary": 1600}),
                    ]
                )
                types2 = await run(month2, date(2026, 7, 1))
                assert "SALARY_CHANGED" in types2
                assert "MISSING_FROM_DECLARATION" in types2
                assert "HIRED" in types2
                assert "SOURCE_CONFLICT" in types2
                assert "MODALITY_CHANGED" in types2
                assert "TSU_RATE_CHANGED" in types2
                await session.refresh(alice_emp)
                assert alice_emp.status == "TERMINATED"
                assert alice_emp.status_source == "USER"

                pays = (
                    await session.execute(
                        select(CompensationPeriod)
                        .join(Employment, Employment.id == CompensationPeriod.employment_id)
                        .where(Employment.employee_id == alice_emp.id)
                        .order_by(CompensationPeriod.period_from)
                    )
                ).scalars().all()
                assert len(pays) == 2
                assert pays[0].period_to is not None
                assert pays[0].base_salary == Decimal("1500.00")
                assert pays[1].period_to is None
                assert pays[1].base_salary == Decimal("1800.00")
        finally:
            async with AsyncSessionLocal() as session:
                if intake_id is not None:
                    await _cleanup(session, intake_id)
            storage = get_object_storage()
            for path in storage_paths:
                storage.delete(path)
            await engine.dispose()

    asyncio.run(body())


def test_apply_terminated_from_fim_vinculo(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        try:
            async with AsyncSessionLocal() as session:
                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()
                intake_id = intake.id

                first = _people_xlsx(
                    [(PERSON_A, {"name": "Alice", "salary": 1500})]
                )
                ingested = await ingest_ss_export(
                    session,
                    files=[SsSourceFile("a.xlsx", first)],
                    period_year_month=date(2026, 6, 1),
                    intake_id=intake.id,
                )
                await apply_ss_batch(session, ingested.batch.id)

                ended = _people_xlsx(
                    [
                        (
                            PERSON_A,
                            {
                                "name": "Alice",
                                "salary": 1500,
                                "ended": date(2026, 6, 30),
                            },
                        )
                    ]
                )
                ingested2 = await ingest_ss_export(
                    session,
                    files=[SsSourceFile("b.xlsx", ended)],
                    period_year_month=date(2026, 7, 1),
                    intake_id=intake.id,
                )
                types = (await apply_ss_batch(session, ingested2.batch.id)).event_types
                assert "TERMINATED" in types
                emp = (
                    await session.execute(
                        select(Employee).where(Employee.intake_id == intake.id)
                    )
                ).scalar_one()
                assert emp.status == "TERMINATED"
                assert emp.status_source == "SS"
                employment = (
                    await session.execute(
                        select(Employment).where(Employment.employee_id == emp.id)
                    )
                ).scalar_one()
                assert employment.ended_on == date(2026, 6, 30)

                rehired = _people_xlsx(
                    [
                        (
                            PERSON_A,
                            {
                                "name": "Alice",
                                "salary": 1550,
                                "started": date(2026, 8, 3),
                                "pay_from": date(2026, 8, 3),
                            },
                        )
                    ]
                )
                ingested3 = await ingest_ss_export(
                    session,
                    files=[SsSourceFile("c.xlsx", rehired)],
                    period_year_month=date(2026, 8, 1),
                    intake_id=intake.id,
                )
                types3 = (await apply_ss_batch(session, ingested3.batch.id)).event_types
                assert "REHIRED" in types3
                jobs = (
                    await session.execute(
                        select(Employment)
                        .where(Employment.employee_id == emp.id)
                        .order_by(Employment.started_on)
                    )
                ).scalars().all()
                assert len(jobs) == 2
                assert jobs[0].ended_on == date(2026, 6, 30)
                assert jobs[1].ended_on is None
                await session.refresh(emp)
                assert emp.status == "ACTIVE"

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


async def _cleanup(session, intake_id) -> None:
    await delete_intake_employment_spine(session, intake_id)
    await session.execute(delete(SsBatch).where(SsBatch.intake_id == intake_id))
    await session.execute(delete(StoredFile).where(StoredFile.intake_id == intake_id))
    await session.execute(
        delete(TenantCryptoKey).where(TenantCryptoKey.intake_id == intake_id)
    )
    await session.execute(delete(Intake).where(Intake.id == intake_id))
    await session.commit()
