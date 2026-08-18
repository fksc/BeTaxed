"""PII encryption schema and DEK store round-trip (DEV-830)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.db import AsyncSessionLocal, engine
from app.models import Employee, Intake, StoredFile, TenantCryptoKey
from app.security.dek_store import get_or_create_pii_crypto
from app.storage import (
    build_object_name,
    get_object_storage,
    sha256_hex,
)


@pytest.fixture
def db_session():
    return True


def test_encryption_tables_exist(db_session) -> None:
    async def body() -> None:
        try:
            async with AsyncSessionLocal() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'public' "
                            "AND tablename IN ("
                            "'tenant_crypto_key', 'employee', 'stored_file'"
                            ")"
                        )
                    )
                ).fetchall()
                names = {r[0] for r in rows}
                assert names == {
                    "tenant_crypto_key",
                    "employee",
                    "stored_file",
                }
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_employee_pii_roundtrip_via_dek_store(db_session) -> None:
    async def body() -> None:
        try:
            async with AsyncSessionLocal() as session:
                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()

                crypto = await get_or_create_pii_crypto(
                    session, intake_id=intake.id
                )
                niss = "12345678901"
                name = "Test Employee"
                dob = date(1999, 6, 1)

                employee = Employee(
                    intake_id=intake.id,
                    niss_hash=crypto.niss_hash(niss),
                    niss_enc=crypto.encrypt_niss(niss),
                    name_enc=crypto.encrypt_name(name),
                    dob_enc=crypto.encrypt_dob(dob),
                )
                session.add(employee)
                await session.commit()

                loaded_crypto = await get_or_create_pii_crypto(
                    session, intake_id=intake.id
                )
                reloaded = await session.get(Employee, employee.id)
                assert reloaded is not None
                assert loaded_crypto.decrypt_niss(reloaded.niss_enc) == niss
                assert loaded_crypto.decrypt_name(reloaded.name_enc) == name
                assert loaded_crypto.decrypt_dob(reloaded.dob_enc) == dob

                key_count = (
                    await session.execute(
                        text(
                            "SELECT COUNT(*) FROM tenant_crypto_key "
                            "WHERE intake_id = :id"
                        ),
                        {"id": intake.id},
                    )
                ).scalar_one()
                assert key_count == 1

                await session.delete(reloaded)
                await session.flush()
                key_row = (
                    await session.execute(
                        text(
                            "SELECT id FROM tenant_crypto_key "
                            "WHERE intake_id = :id"
                        ),
                        {"id": intake.id},
                    )
                ).scalar_one()
                await session.execute(
                    text("DELETE FROM tenant_crypto_key WHERE id = :id"),
                    {"id": key_row},
                )
                await session.delete(intake)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_local_object_storage_and_stored_file(db_session) -> None:
    async def body() -> None:
        try:
            data = b"fake ss export bytes"
            intake_id = uuid.uuid4()
            object_name = build_object_name(
                intake_id=intake_id,
                company_id=None,
                filename="export.xlsx",
            )
            storage = get_object_storage()
            path = storage.put_bytes(
                data,
                object_name=object_name,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            assert path

            async with AsyncSessionLocal() as session:
                intake = Intake(id=intake_id, status="OPEN")
                session.add(intake)
                await session.flush()

                stored = StoredFile(
                    intake_id=intake.id,
                    gcs_path=path,
                    sha256=sha256_hex(data),
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    original_filename="export.xlsx",
                    kind="SS_EXPORT",
                )
                session.add(stored)
                await session.commit()

                reloaded = await session.get(StoredFile, stored.id)
                assert reloaded is not None
                assert reloaded.sha256 == sha256_hex(data)

                await session.delete(reloaded)
                await session.flush()
                await session.delete(intake)
                await session.commit()

            storage.delete(path)
        finally:
            await engine.dispose()

    asyncio.run(body())
