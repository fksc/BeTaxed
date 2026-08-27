"""Pass-1 teaser: four aggregates, no recipe (OD-2, DEV-833)."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_, select

from app.auth.firebase import FirebaseIdentity
from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import (
    Company,
    CompanyMembership,
    Employee,
    Intake,
    SsBatch,
    StoredFile,
    TenantCryptoKey,
    UserBase,
)
from app.services.ss_apply import (
    apply_ss_batch,
    delete_company_employment_spine,
    delete_intake_employment_spine,
)
from app.services.ss_ingest import ingest_ss_export
from app.services.ss_parser import SsSourceFile
from app.services.teaser import (
    age_on,
    persist_intake_teaser,
    remaining_benefit_months,
)
from app.settings import HEADER_COMPANY_ID, HEADER_INTAKE_SESSION
from app.storage import get_object_storage
from tests.ss_xlsx_fixtures import (
    CONTRATO_HEADERS,
    PERSON_A,
    PERSON_B,
    VINCULO_HEADERS,
    build_xlsx,
    contrato_row,
    vinculo_row,
)

PERSON_C = "55555555555"
PERSON_D = "66666666666"
PERSON_E = "77777777777"
PERSON_F = "88888888888"
PERSON_G = "99999999999"

SAVING_RATE = Decimal("0.2375") * Decimal("0.50")


@pytest.fixture
def db_session():
    return True


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _people_xlsx(people: list[tuple[str, dict]]) -> bytes:
    vinculos = [VINCULO_HEADERS]
    contratos = [CONTRATO_HEADERS]
    for niss, opts in people:
        vinculos.append(
            vinculo_row(
                niss,
                name=opts.get("name", "Test"),
                dob=opts.get("dob", date(1998, 3, 15)),
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
                rendimento_from=opts.get("pay_from", date(2025, 1, 1)),
                salary=opts.get("salary", 1500),
            )
        )
    return build_xlsx({"Vínculos": vinculos, "Contratos": contratos})


def _mixed_teaser_xlsx() -> bytes:
    return _people_xlsx(
        [
            (
                PERSON_A,
                {
                    "name": "Alice",
                    "dob": date(1998, 3, 15),
                    "started": date(2024, 1, 2),
                    "salary": 1500,
                },
            ),
            (
                PERSON_B,
                {
                    "name": "Carla",
                    "dob": date(1999, 6, 1),
                    "started": date(2025, 3, 1),
                    "salary": 1800,
                    "modality": "A termo certo, tempo completo",
                    "pay_from": date(2025, 3, 1),
                },
            ),
            (
                PERSON_C,
                {
                    "name": "Diego",
                    "dob": date(1990, 1, 1),
                    "salary": 2000,
                },
            ),
            (
                PERSON_D,
                {
                    "name": "Eva",
                    "dob": date(1998, 1, 1),
                    "salary": 1600,
                    "taxa": 22.875,
                },
            ),
            (
                PERSON_E,
                {
                    "name": "Fabio",
                    "dob": date(1994, 1, 1),
                    "salary": 1700,
                    "modality": "A termo certo, tempo completo",
                },
            ),
            (
                PERSON_F,
                {
                    "name": "Gina",
                    "dob": None,
                    "salary": 1400,
                },
            ),
            (
                PERSON_G,
                {
                    "name": "Hugo",
                    "dob": date(1998, 1, 1),
                    "started": date(2020, 1, 1),
                    "salary": 1900,
                    "pay_from": date(2020, 1, 1),
                },
            ),
        ]
    )


def test_age_and_remaining_months_helpers() -> None:
    assert age_on(date(1998, 3, 15), date(2024, 1, 2)) == 25
    assert age_on(date(1994, 1, 2), date(2024, 1, 2)) == 30
    assert age_on(date(1993, 1, 2), date(2024, 1, 2)) == 31
    assert remaining_benefit_months(date(2024, 1, 2), date(2026, 8, 1)) == 29
    assert remaining_benefit_months(date(2020, 1, 1), date(2026, 8, 1)) == 0


def test_teaser_persists_now_and_potential_only(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        try:
            async with AsyncSessionLocal() as session:
                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()
                intake_id = intake.id
                result = await ingest_ss_export(
                    session,
                    files=[SsSourceFile("ss.xlsx", _mixed_teaser_xlsx())],
                    period_year_month=date(2026, 8, 1),
                    intake_id=intake.id,
                )
                await apply_ss_batch(session, result.batch.id)
                figures = await persist_intake_teaser(
                    session, intake.id, date(2026, 8, 1)
                )
                await session.commit()
                assert figures is not None
                now_monthly = _money(Decimal("1500") * SAVING_RATE)
                now_window = _money(Decimal("1500") * SAVING_RATE * 29)
                potential_monthly = _money(Decimal("1800") * SAVING_RATE)
                potential_window = _money(Decimal("1800") * SAVING_RATE * 60)
                assert figures.now_monthly == now_monthly
                assert figures.now_window == now_window
                assert figures.potential_monthly == potential_monthly
                assert figures.potential_window == potential_window
                await session.refresh(intake)
                assert intake.teaser_now_monthly == now_monthly
                assert intake.teaser_now_window == now_window
                assert intake.teaser_potential_monthly == potential_monthly
                assert intake.teaser_potential_window == potential_window
                assert intake.teaser_currency == "EUR"
                assert intake.teaser_regime_id is not None

                employees = (
                    await session.execute(
                        select(Employee).where(Employee.intake_id == intake.id)
                    )
                ).scalars().all()
                for employee in employees:
                    employee.first_permanent_elsewhere = "YES"
                await session.flush()
                still = await persist_intake_teaser(
                    session, intake.id, date(2026, 8, 1)
                )
                assert still is not None
                assert still.now_monthly == now_monthly
                assert still.potential_monthly == potential_monthly

                for employee in employees:
                    employee.status = "ON_LEAVE"
                await session.flush()
                left = await persist_intake_teaser(
                    session, intake.id, date(2026, 8, 1)
                )
                assert left is not None
                assert left.now_monthly == Decimal("0.00")
                assert left.potential_monthly == Decimal("0.00")

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


def test_teaser_http_hides_recipe_and_names(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post("/v1/intakes")
                assert created.status_code == 201, created.text
                intake_id = UUID(created.json()["id"])
                session_token = created.json()["session_token"]
                uploaded = await client.post(
                    f"/v1/intakes/{intake_id}/uploads",
                    headers={HEADER_INTAKE_SESSION: session_token},
                    data={"period_year_month": "2026-08"},
                    files={
                        "files": (
                            "ss.xlsx",
                            _mixed_teaser_xlsx(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert uploaded.status_code == 201, uploaded.text
                payload = uploaded.json()
                assert payload.get("verbose_people") is None
                shown = json.dumps(payload)
                assert Decimal(str(payload["teaser_now_monthly"])) == Decimal(
                    "178.13"
                )
                assert Decimal(str(payload["teaser_now_window"])) == Decimal(
                    "5165.63"
                )
                assert Decimal(str(payload["teaser_potential_monthly"])) == Decimal(
                    "213.75"
                )
                assert Decimal(str(payload["teaser_potential_window"])) == Decimal(
                    "12825.00"
                )
                for leak in (
                    "Alice",
                    "Carla",
                    "Diego",
                    PERSON_A,
                    PERSON_B,
                    "23.75",
                    "11.875",
                    "50%",
                    "remaining months",
                    "sem termo",
                    "convert this",
                ):
                    assert leak not in shown
                async with AsyncSessionLocal() as session:
                    stored = (
                        await session.execute(
                            select(StoredFile).where(
                                StoredFile.intake_id == intake_id
                            )
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


def test_teaser_http_verbose_people_when_dev(db_session, monkeypatch) -> None:
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("VERBOSE", "TRUE")

    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post("/v1/intakes")
                assert created.status_code == 201, created.text
                intake_id = UUID(created.json()["id"])
                session_token = created.json()["session_token"]
                uploaded = await client.post(
                    f"/v1/intakes/{intake_id}/uploads",
                    headers={HEADER_INTAKE_SESSION: session_token},
                    data={"period_year_month": "2026-08"},
                    files={
                        "files": (
                            "ss.xlsx",
                            _mixed_teaser_xlsx(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert uploaded.status_code == 201, uploaded.text
                people = uploaded.json()["verbose_people"]
                assert people is not None
                by_name = {row["name"]: row for row in people}
                assert by_name["Alice"]["age"] == 28
                assert by_name["Alice"]["bucket"] == "now"
                assert by_name["Alice"]["how_code"] == "NOW_UNUSED"
                assert by_name["Alice"]["remaining_months"] == 29
                assert by_name["Carla"]["bucket"] == "potential"
                assert by_name["Carla"]["how_code"] == "POTENTIAL_CONVERT"
                assert by_name["Diego"]["how_code"] == "SKIP_AGE"
                assert by_name["Eva"]["how_code"] == "SKIP_TSU_REDUCED"
                assert by_name["Fabio"]["how_code"] == "SKIP_AGE"
                assert by_name["Gina"]["how_code"] == "SKIP_NO_DOB"
                assert by_name["Hugo"]["how_code"] == "SKIP_WINDOW"
                shown = json.dumps(people)
                assert PERSON_A not in shown
                assert PERSON_B not in shown
                async with AsyncSessionLocal() as session:
                    stored = (
                        await session.execute(
                            select(StoredFile).where(
                                StoredFile.intake_id == intake_id
                            )
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


def test_company_scope_exposes_ss_estimate_unconfirmed(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities: dict[str, FirebaseIdentity] = {}

    def fake_verify(token: str) -> FirebaseIdentity:
        if token not in identities:
            raise AssertionError(f"unexpected token {token}")
        return identities[token]

    monkeypatch.setattr("app.deps.auth.verify_id_token", fake_verify)
    token = f"ad-{uuid4().hex[:12]}"
    identities[token] = FirebaseIdentity(
        uid=token, email=f"ad-{uuid4().hex[:8]}@example.test"
    )

    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        company_id = None
        user_id = None
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post("/v1/intakes")
                assert created.status_code == 201, created.text
                intake_id = UUID(created.json()["id"])
                session_token = created.json()["session_token"]
                uploaded = await client.post(
                    f"/v1/intakes/{intake_id}/uploads",
                    headers={HEADER_INTAKE_SESSION: session_token},
                    data={"period_year_month": "2026-08"},
                    files={
                        "files": (
                            "ss.xlsx",
                            _mixed_teaser_xlsx(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert uploaded.status_code == 201, uploaded.text
                now_monthly = uploaded.json()["teaser_now_monthly"]
                now_window = uploaded.json()["teaser_now_window"]
                potential_monthly = uploaded.json()["teaser_potential_monthly"]
                potential_window = uploaded.json()["teaser_potential_window"]
                assert now_monthly is not None

                me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {token}"}
                )
                assert me.status_code == 200, me.text
                user_id = UUID(me.json()["id"])

                converted = await client.post(
                    f"/v1/intakes/{intake_id}/convert",
                    headers={
                        "Authorization": f"Bearer {token}",
                        HEADER_INTAKE_SESSION: session_token,
                    },
                    json={"legal_name": "Estimate Lda"},
                )
                assert converted.status_code == 200, converted.text
                company_id = UUID(converted.json()["company_id"])

                reading = await client.get(
                    "/v1/me/company",
                    headers={
                        "Authorization": f"Bearer {token}",
                        HEADER_COMPANY_ID: str(company_id),
                    },
                )
                assert reading.status_code == 200, reading.text
                portfolio = reading.json()
                assert Decimal(str(portfolio["estimate_now_monthly"])) == Decimal(
                    str(now_monthly)
                )
                assert Decimal(str(portfolio["estimate_now_window"])) == Decimal(
                    str(now_window)
                )
                assert Decimal(str(portfolio["estimate_potential_monthly"])) == Decimal(
                    str(potential_monthly)
                )
                assert Decimal(str(portfolio["estimate_potential_window"])) == Decimal(
                    str(potential_window)
                )
                assert portfolio["estimate_unconfirmed"] is True
                assert portfolio["contracts_missing"] >= 1
                blob = str(portfolio)
                assert "remaining_months" not in blob
                assert PERSON_A not in blob
                async with AsyncSessionLocal() as session:
                    stored = (
                        await session.execute(
                            select(StoredFile).where(
                                or_(
                                    StoredFile.intake_id == intake_id,
                                    StoredFile.company_id == company_id,
                                )
                            )
                        )
                    ).scalars().all()
                    storage_paths.extend(row.gcs_path for row in stored)
        finally:
            async with AsyncSessionLocal() as session:
                if company_id is not None:
                    await session.execute(
                        delete(CompanyMembership).where(
                            CompanyMembership.company_id == company_id
                        )
                    )
                    await delete_company_employment_spine(session, company_id)
                    await session.execute(
                        delete(SsBatch).where(SsBatch.company_id == company_id)
                    )
                    await session.execute(
                        delete(StoredFile).where(
                            or_(
                                StoredFile.company_id == company_id,
                                StoredFile.intake_id == intake_id if intake_id else False,
                            )
                        )
                    )
                    await session.execute(
                        delete(TenantCryptoKey).where(
                            TenantCryptoKey.company_id == company_id
                        )
                    )
                if intake_id is not None:
                    await delete_intake_employment_spine(session, intake_id)
                    await session.execute(
                        delete(SsBatch).where(SsBatch.intake_id == intake_id)
                    )
                    await session.execute(
                        delete(TenantCryptoKey).where(
                            TenantCryptoKey.intake_id == intake_id
                        )
                    )
                    intake = await session.get(Intake, intake_id)
                    if intake is not None:
                        intake.converted_company_id = None
                if company_id is not None:
                    company = await session.get(Company, company_id)
                    if company is not None:
                        company.created_from_intake_id = None
                await session.flush()
                if company_id is not None:
                    company = await session.get(Company, company_id)
                    if company is not None:
                        await session.delete(company)
                if intake_id is not None:
                    intake = await session.get(Intake, intake_id)
                    if intake is not None:
                        await session.delete(intake)
                if user_id is not None:
                    user = await session.get(UserBase, user_id)
                    if user is not None:
                        await session.delete(user)
                await session.commit()
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
