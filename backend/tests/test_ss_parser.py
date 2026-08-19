"""Unit tests for the SS vínculos/contratos parser (DEV-831)."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.ss_parser import (
    SsParseError,
    SsSourceFile,
    current_contratos,
    parse_ss_files,
)
from tests.ss_xlsx_fixtures import (
    ANALYST_HEADERS,
    PERSON_A,
    PERSON_B,
    SUBSTITUTE_NISS,
    combined_workbook,
    contratos_only_workbook,
    unnamed_sheet_workbooks,
    vinculos_only_workbook,
)


def test_combined_workbook_parses_official_headers_only() -> None:
    content = combined_workbook(
        extra_vinculo_headers=ANALYST_HEADERS,
        extra_vinculo_values=[30, "Sem termo, tempo completo", 9999],
    )
    parsed = parse_ss_files(
        [SsSourceFile("11122233344_vinculos_2026_08_12.xlsx", content)]
    )

    assert parsed.file_kinds == ["COMBINED_XLSX"]
    assert parsed.employer_niss == "11122233344"
    assert parsed.export_label == "11122233344_vinculos_2026_08_12"
    assert len(parsed.vinculos) == 2
    assert len(parsed.contratos) == 3

    alice = next(row for row in parsed.vinculos if row.niss == PERSON_A)
    assert alice.vinculo_raw == "Trabalhador por Conta de Outrem"
    assert alice.workplace_ss_label == "1 - R CIDADE DE …"
    assert alice.taxa_pct is not None
    assert float(alice.taxa_pct) == 34.75
    assert "Idade" not in alice.leftover
    assert "Rem Base" not in alice.leftover
    assert 9999 not in alice.leftover.values()


def test_current_pay_is_open_rendimento_not_first_row() -> None:
    parsed = parse_ss_files(
        [SsSourceFile("combined.xlsx", combined_workbook())]
    )
    alice_rows = [row for row in parsed.contratos if row.niss == PERSON_A]
    assert alice_rows[0].base_salary == 1000
    assert alice_rows[0].rendimento_to == date(2024, 12, 31)

    current = current_contratos(parsed.contratos)
    current_alice = [row for row in current if row.niss == PERSON_A]
    assert len(current_alice) == 1
    assert current_alice[0].base_salary == 1500
    assert current_alice[0].rendimento_to is None
    assert current_alice[0].source_row != alice_rows[0].source_row


def test_two_files_merge_into_one_export() -> None:
    parsed = parse_ss_files(
        [
            SsSourceFile("vinculos.xlsx", vinculos_only_workbook()),
            SsSourceFile("contratos.xlsx", contratos_only_workbook()),
        ]
    )
    assert set(parsed.file_kinds) == {"VINCULOS", "CONTRATOS"}
    assert {row.niss for row in parsed.vinculos} == {PERSON_A, PERSON_B}
    assert len(parsed.contratos) == 3


def test_unnamed_sheets_classified_by_headers() -> None:
    vinculos, contratos = unnamed_sheet_workbooks()
    parsed = parse_ss_files(
        [
            SsSourceFile("a.xlsx", vinculos),
            SsSourceFile("b.xlsx", contratos),
        ]
    )
    assert len(parsed.vinculos) == 1
    assert len(parsed.contratos) == 1


def test_missing_required_header_fails() -> None:
    from tests.ss_xlsx_fixtures import (
        CONTRATO_HEADERS,
        contrato_row,
        vinculo_row,
        build_xlsx,
    )

    broken = list(CONTRATO_HEADERS)
    broken[broken.index("Remuneração base(€)")] = "Something else"
    content = build_xlsx(
        {
            "Vínculos": [
                [
                    "NISS",
                    "Nome trabalhador",
                    "Data nascimento",
                    "Vínculo",
                    "Vínculo comunicado em",
                    "Início vínculo",
                    "Fim vínculo",
                    "Início aplicação taxa",
                    "Fim aplicação taxa",
                    "Taxa (%)",
                    "Local de trabalho",
                ],
                vinculo_row(PERSON_A),
            ],
            "Contratos": [broken, contrato_row(PERSON_A)],
        }
    )
    with pytest.raises(SsParseError, match="Remuneração base|remuneracao base"):
        parse_ss_files([SsSourceFile("bad.xlsx", content)])


def test_official_extra_niss_stays_in_parser_leftover() -> None:
    parsed = parse_ss_files(
        [SsSourceFile("combined.xlsx", combined_workbook())]
    )
    alice_current = next(
        row for row in current_contratos(parsed.contratos) if row.niss == PERSON_A
    )
    leftover_values = " ".join(str(value) for value in alice_current.leftover.values())
    assert SUBSTITUTE_NISS in leftover_values


def test_same_person_present_on_both_sheets() -> None:
    parsed = parse_ss_files(
        [SsSourceFile("combined.xlsx", combined_workbook())]
    )
    assert {row.niss for row in parsed.vinculos} == {
        row.niss for row in parsed.contratos
    }
