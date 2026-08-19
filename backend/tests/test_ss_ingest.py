"""Persist SS raw tables and niss_hash matching (DEV-831)."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text

from app.db import AsyncSessionLocal, engine
from app.models import (
    Intake,
    SsBatch,
    SsBatchFile,
    SsRawContrato,
    SsRawVinculo,
    StoredFile,
    TenantCryptoKey,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.services.ss_ingest import ingest_ss_export
from app.services.ss_parser import SsSourceFile
from app.storage import get_object_storage
from tests.ss_xlsx_fixtures import (
    ANALYST_HEADERS,
    EMPLOYER_NISS,
    PERSON_A,
    PERSON_B,
    SUBSTITUTE_NISS,
    combined_workbook,
    contratos_only_workbook,
    vinculos_only_workbook,
)


@pytest.fixture
def db_session():
    return True


def test_ss_ingest_tables_exist(db_session) -> None:
    async def body() -> None:
        try:
            async with AsyncSessionLocal() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'public' "
                            "AND tablename IN ("
                            "'ss_batch', 'ss_batch_file', "
                            "'ss_raw_vinculo', 'ss_raw_contrato'"
                            ")"
                        )
                    )
                ).fetchall()
                names = {row[0] for row in rows}
                assert names == {
                    "ss_batch",
                    "ss_batch_file",
                    "ss_raw_vinculo",
                    "ss_raw_contrato",
                }
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_ingest_combined_hashes_and_current_pay(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        batch_id = None
        try:
            async with AsyncSessionLocal() as session:
                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()
                intake_id = intake.id

                content = combined_workbook(
                    extra_vinculo_headers=ANALYST_HEADERS,
                    extra_vinculo_values=[30, "Sem termo, tempo completo", 9999],
                )
                filename = f"{EMPLOYER_NISS}_vinculos_2026_08_12.xlsx"
                result = await ingest_ss_export(
                    session,
                    files=[SsSourceFile(filename, content)],
                    period_year_month=date(2026, 8, 1),
                    intake_id=intake.id,
                )
                await session.commit()
                batch_id = result.batch.id

                assert result.batch.parse_status == "PARSED"
                assert result.vinculo_count == 2
                assert result.contrato_count == 3
                assert result.batch.export_label == (
                    f"{EMPLOYER_NISS}_vinculos_2026_08_12"
                )

                crypto = await get_or_create_pii_crypto(
                    session, intake_id=intake.id
                )
                assert result.batch.employer_niss_hash == crypto.niss_hash(
                    EMPLOYER_NISS
                )

                vinculos = (
                    await session.execute(
                        select(SsRawVinculo).where(
                            SsRawVinculo.batch_id == result.batch.id
                        )
                    )
                ).scalars().all()
                contratos = (
                    await session.execute(
                        select(SsRawContrato).where(
                            SsRawContrato.batch_id == result.batch.id
                        )
                    )
                ).scalars().all()

                alice_hash = crypto.niss_hash(PERSON_A)
                bruno_hash = crypto.niss_hash(PERSON_B)
                assert {row.niss_hash for row in vinculos} == {alice_hash, bruno_hash}
                assert {row.niss_hash for row in contratos} == {alice_hash, bruno_hash}

                alice_v = next(row for row in vinculos if row.niss_hash == alice_hash)
                assert crypto.decrypt_niss(alice_v.niss_enc) == PERSON_A
                assert crypto.decrypt_name(alice_v.name_enc) == "Alice"
                assert alice_v.vinculo_raw == "Trabalhador por Conta de Outrem"
                assert alice_v.leftover in (None, {})

                current_ids = set(result.current_contrato_ids)
                current_rows = [row for row in contratos if row.id in current_ids]
                alice_current = next(
                    row for row in current_rows if row.niss_hash == alice_hash
                )
                assert alice_current.base_salary == Decimal("1500.00")
                assert alice_current.rendimento_to is None
                closed = next(
                    row
                    for row in contratos
                    if row.niss_hash == alice_hash and row.rendimento_to is not None
                )
                assert closed.base_salary == Decimal("1000.00")
                assert closed.id not in current_ids

                leftover = alice_current.leftover or {}
                dumped = json.dumps(leftover)
                assert PERSON_A not in dumped
                assert SUBSTITUTE_NISS not in dumped
                assert crypto.niss_hash(SUBSTITUTE_NISS).hex() in dumped

                files = (
                    await session.execute(
                        select(SsBatchFile).where(
                            SsBatchFile.batch_id == result.batch.id
                        )
                    )
                ).scalars().all()
                assert [row.kind for row in files] == ["COMBINED_XLSX"]

                stored = (
                    await session.execute(
                        select(StoredFile).where(
                            StoredFile.id == files[0].file_id
                        )
                    )
                ).scalar_one()
                storage_paths.append(stored.gcs_path)

                vinculo_dump = (
                    await session.execute(
                        text(
                            "SELECT leftover::text, workplace_ss_label, "
                            "vinculo_raw FROM ss_raw_vinculo "
                            "WHERE batch_id = :id"
                        ),
                        {"id": result.batch.id},
                    )
                ).fetchall()
                contrato_dump = (
                    await session.execute(
                        text(
                            "SELECT leftover::text, profession_raw, "
                            "modality_raw, motivo_raw "
                            "FROM ss_raw_contrato "
                            "WHERE batch_id = :id"
                        ),
                        {"id": result.batch.id},
                    )
                ).fetchall()
                blob = " ".join(
                    str(col)
                    for row in (*vinculo_dump, *contrato_dump)
                    for col in row
                    if col is not None
                )
                assert PERSON_A not in blob
                assert PERSON_B not in blob
                assert SUBSTITUTE_NISS not in blob
        finally:
            if batch_id is not None and intake_id is not None:
                async with AsyncSessionLocal() as session:
                    await _cleanup(session, batch_id, intake_id)
            storage = get_object_storage()
            for path in storage_paths:
                storage.delete(path)
            await engine.dispose()

    asyncio.run(body())


def test_ingest_two_files_and_failed_header(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        try:
            async with AsyncSessionLocal() as session:
                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()

                result = await ingest_ss_export(
                    session,
                    files=[
                        SsSourceFile("vinculos.xlsx", vinculos_only_workbook()),
                        SsSourceFile("contratos.xlsx", contratos_only_workbook()),
                    ],
                    period_year_month=date(2026, 8, 1),
                    intake_id=intake.id,
                )
                await session.commit()
                assert result.batch.parse_status == "PARSED"
                assert result.vinculo_count == 2
                kinds = (
                    await session.execute(
                        select(SsBatchFile.kind).where(
                            SsBatchFile.batch_id == result.batch.id
                        )
                    )
                ).scalars().all()
                assert set(kinds) == {"VINCULOS", "CONTRATOS"}
                stored_rows = (
                    await session.execute(
                        select(StoredFile).where(StoredFile.intake_id == intake.id)
                    )
                ).scalars().all()
                storage_paths.extend(row.gcs_path for row in stored_rows)
                await _cleanup(session, result.batch.id, intake.id)

                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()
                from tests.ss_xlsx_fixtures import VINCULO_HEADERS, build_xlsx, vinculo_row

                broken = build_xlsx(
                    {
                        "Vínculos": [
                            [h for h in VINCULO_HEADERS if h != "Local de trabalho"],
                            vinculo_row(PERSON_A)[:-1],
                        ]
                    }
                )
                failed = await ingest_ss_export(
                    session,
                    files=[SsSourceFile("broken.xlsx", broken)],
                    period_year_month=date(2026, 8, 1),
                    intake_id=intake.id,
                )
                await session.commit()
                assert failed.batch.parse_status == "FAILED"
                assert failed.vinculo_count == 0
                assert failed.batch.parse_error is not None
                raw_count = (
                    await session.execute(
                        select(SsRawVinculo).where(
                            SsRawVinculo.batch_id == failed.batch.id
                        )
                    )
                ).scalars().all()
                assert raw_count == []
                stored_rows = (
                    await session.execute(
                        select(StoredFile).where(StoredFile.intake_id == intake.id)
                    )
                ).scalars().all()
                storage_paths.extend(row.gcs_path for row in stored_rows)
                await _cleanup(session, failed.batch.id, intake.id)
        finally:
            storage = get_object_storage()
            for path in storage_paths:
                storage.delete(path)
            await engine.dispose()

    asyncio.run(body())


async def _cleanup(
    session, batch_id, intake_id
) -> None:
    await session.execute(delete(SsBatch).where(SsBatch.id == batch_id))
    await session.execute(delete(StoredFile).where(StoredFile.intake_id == intake_id))
    await session.execute(
        delete(TenantCryptoKey).where(TenantCryptoKey.intake_id == intake_id)
    )
    await session.execute(delete(Intake).where(Intake.id == intake_id))
    await session.commit()
