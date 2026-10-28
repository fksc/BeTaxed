"""Minuta token fill, dates, and snapshot refresh. DEV-882."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.services.minuta_facts import format_date_en, format_date_pt, render_minuta


def test_dates_follow_the_declaration_sample() -> None:
    value = date(2021, 5, 10)
    assert format_date_pt(value) == "10 de maio de 2021"
    assert format_date_en(value) == "May 10, 2021"


def test_unknown_token_stays_blank() -> None:
    body = render_minuta("<p>{{ person_name }} {{ not_a_token }}</p>", {"person_name": "Rita"})
    assert body == "<p>Rita </p>"


def test_refresh_keeps_a_staff_edit() -> None:
    import asyncio

    from sqlalchemy import delete

    from app.db import AsyncSessionLocal
    from app.models import Company, Employee, Employment, RequestCase, TenantCryptoKey, UserBase
    from app.security.dek_store import get_or_create_pii_crypto
    from app.services.minuta_facts import copy_case_facts
    from app.services.request_pipeline import open_request_case

    async def body() -> None:
        company_id = None
        staff_id = None
        try:
            async with AsyncSessionLocal() as session:
                staff = UserBase(
                    firebase_uid=f"staff-{uuid.uuid4().hex}",
                    email=f"s-{uuid.uuid4().hex[:8]}@example.test",
                    user_type="BETAXED_STAFF",
                )
                company = Company(
                    legal_name="Xblend Software, Lda.",
                    registered_address="Rua de Fornelos, 77",
                    signatory_name="Richard Lee Chambers III",
                )
                session.add_all([staff, company])
                await session.flush()
                crypto = await get_or_create_pii_crypto(session, company_id=company.id)
                employee = Employee(
                    company_id=company.id,
                    niss_hash=crypto.niss_hash("11915388869"),
                    niss_enc=crypto.encrypt_niss("11915388869"),
                    nif_enc=crypto.encrypt_nif("251123731"),
                    nif_hash=crypto.nif_hash("251123731"),
                    name_enc=crypto.encrypt_name("Mário Rui Alves Peixoto"),
                    address_enc=crypto.encrypt_address("Alameda Maria da Fonte"),
                )
                session.add(employee)
                await session.flush()
                session.add(
                    Employment(
                        employee_id=employee.id,
                        company_id=company.id,
                        started_on=date(2021, 5, 10),
                        contract_modality="TERMO_CERTO",
                    )
                )
                await session.commit()
                company_id = company.id
                staff_id = staff.id
                employee_id = employee.id

            async with AsyncSessionLocal() as session:
                actor = await session.get(UserBase, staff_id)
                assert actor is not None
                case = await open_request_case(session, employee_id=employee_id, actor=actor)
                assert case.person_name == "Mário Rui Alves Peixoto"
                assert case.company_signatory_name == "Richard Lee Chambers III"
                assert case.contract_started_on == date(2021, 5, 10)
                assert case.person_nif_enc is not None
                case.person_address = "Edited residence"
                company_row = await session.get(Company, company_id)
                assert company_row is not None
                company_row.registered_address = "New seat"
                await copy_case_facts(session, case, only_empty=True)
                assert case.person_address == "Edited residence"
                assert case.company_address == "Rua de Fornelos, 77"
                await session.commit()
        finally:
            if company_id is not None:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        delete(RequestCase).where(RequestCase.company_id == company_id)
                    )
                    await session.execute(
                        delete(Employment).where(Employment.company_id == company_id)
                    )
                    await session.execute(delete(Employee).where(Employee.company_id == company_id))
                    await session.execute(
                        delete(TenantCryptoKey).where(TenantCryptoKey.company_id == company_id)
                    )
                    await session.execute(delete(Company).where(Company.id == company_id))
                    if staff_id is not None:
                        await session.execute(delete(UserBase).where(UserBase.id == staff_id))
                    await session.commit()

        from app.db import engine

        await engine.dispose()

    asyncio.run(body())


def test_extract_fills_empty_profile_and_does_not_replace_the_legal_name() -> None:
    import asyncio

    from sqlalchemy import delete

    from app.db import AsyncSessionLocal
    from app.models import Company, Employee, EmploymentDocument, TenantCryptoKey
    from app.security.dek_store import get_or_create_pii_crypto
    from app.services.contract_llm import ContractExtract
    from app.services.contract_review import remember_minuta_profile

    async def body() -> None:
        company_id = None
        try:
            async with AsyncSessionLocal() as session:
                company = Company(legal_name="Xblend Software, Lda.")
                session.add(company)
                await session.flush()
                crypto = await get_or_create_pii_crypto(session, company_id=company.id)
                employee = Employee(
                    company_id=company.id,
                    niss_hash=crypto.niss_hash("11915388869"),
                    niss_enc=crypto.encrypt_niss("11915388869"),
                    name_enc=crypto.encrypt_name("Mário Rui Alves Peixoto"),
                )
                session.add(employee)
                await session.flush()
                doc = EmploymentDocument(
                    employee_id=employee.id,
                    file_id=employee.id,
                    matches_ss="UNKNOWN",
                    review_status="REVIEWED",
                )
                extract = ContractExtract(
                    doc_kind="CONVERSION",
                    signed_on=date(2022, 5, 11),
                    term_end_on=None,
                    leftover={},
                    employer_legal_name="Some Other Lda",
                    employer_address="Rua de Fornelos, 77",
                    signatory_name="Richard Lee Chambers III",
                    employee_address="Alameda Maria da Fonte",
                    nif="245819363",
                    employer_nif="518273644",
                )
                mismatch = await remember_minuta_profile(
                    session, company, employee, crypto, extract, doc
                )
                assert mismatch is True
                assert company.legal_name == "Xblend Software, Lda."
                assert company.registered_address == "Rua de Fornelos, 77"
                assert company.signatory_name == "Richard Lee Chambers III"
                assert employee.address_enc is not None
                assert crypto.decrypt_address(employee.address_enc) == "Alameda Maria da Fonte"
                assert crypto.decrypt_nif(employee.nif_enc) == "245819363"
                assert crypto.decrypt_nif(company.nif_enc) == "518273644"
                replacement = ContractExtract(
                    doc_kind="CONVERSION",
                    signed_on=date(2022, 5, 11),
                    term_end_on=None,
                    leftover={},
                    nif="263748510",
                    employer_nif="509111217",
                )
                await remember_minuta_profile(
                    session, company, employee, crypto, replacement, doc
                )
                assert crypto.decrypt_nif(employee.nif_enc) == "245819363"
                assert crypto.decrypt_nif(company.nif_enc) == "518273644"
                company_id = company.id
                await session.rollback()
        finally:
            if company_id is not None:
                async with AsyncSessionLocal() as session:
                    await session.execute(delete(Employee).where(Employee.company_id == company_id))
                    await session.execute(
                        delete(TenantCryptoKey).where(TenantCryptoKey.company_id == company_id)
                    )
                    await session.execute(delete(Company).where(Company.id == company_id))
                    await session.commit()
            from app.db import engine

            await engine.dispose()

    asyncio.run(body())
