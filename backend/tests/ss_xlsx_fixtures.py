"""Synthetic SS workbooks for parser tests. No real sample PII."""

from __future__ import annotations

import csv
from datetime import date
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook

VINCULO_HEADERS = [
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
]

CONTRATO_HEADERS = [
    "NISS",
    "Nome trabalhador",
    "Modalidade contrato",
    "Prestação trabalho",
    "Data início",
    "Data fim",
    "Profissão",
    "Percentagem trabalho",
    "Horas trabalho",
    "Dias trabalho",
    "Motivo contrato",
    "NISS trabalhador a substituir",
    "Nome trabalhador a substituir",
    "NISS dos trabalhadores a substituir ",
    "Regime jurídico da pluralidade de empregadores",
    "NISS das entidades empregadoras",
    "Data início período rendimento",
    "Data fim período rendimento",
    "Remuneração base(€)",
]

ANALYST_HEADERS = ["Idade", "Vínculo", "Rem Base"]

PERSON_A = "11111111111"
PERSON_B = "22222222222"
EMPLOYER_NISS = "33333333333"
SUBSTITUTE_NISS = "44444444444"


def vinculo_row(
    niss: str,
    *,
    name: str = "Test Person",
    dob: date | None = date(1998, 3, 15),
    started: date = date(2024, 1, 2),
    ended: date | None = None,
    taxa: float = 34.75,
    workplace: str = "1 - R CIDADE DE …",
) -> list[Any]:
    return [
        niss,
        name,
        dob,
        "Trabalhador por Conta de Outrem",
        started,
        started,
        ended,
        started,
        None,
        taxa,
        workplace,
    ]


def contrato_row(
    niss: str,
    *,
    name: str = "Test Person",
    modality: str = "Sem termo, tempo completo",
    started: date = date(2024, 1, 2),
    ended: date | None = None,
    profession: str = "Programador de software",
    rendimento_from: date = date(2025, 1, 1),
    rendimento_to: date | None = None,
    salary: float = 1500,
    substitute_niss: str | None = None,
) -> list[Any]:
    return [
        niss,
        name,
        modality,
        "Presencial",
        started,
        ended,
        profession,
        None,
        40,
        30,
        None,
        substitute_niss,
        None,
        None,
        "Não",
        None,
        rendimento_from,
        rendimento_to,
        salary,
    ]


def build_xlsx(sheets: dict[str, list[list[Any]]]) -> bytes:
    workbook = Workbook()
    first = True
    for name, rows in sheets.items():
        if first:
            sheet = workbook.active
            assert sheet is not None
            sheet.title = name
            first = False
        else:
            sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


LEAVE_HEADERS = [
    "NISS",
    "Tipo de ausência",
    "Início ausência",
    "Fim ausência",
]


def leave_row(
    niss: str,
    *,
    leave_type: str = "PARENTAL",
    started: date = date(2026, 3, 1),
    ended: date | None = None,
) -> list[Any]:
    return [niss, leave_type, started, ended]


def combined_workbook(
    *,
    extra_vinculo_headers: list[str] | None = None,
    extra_vinculo_values: list[Any] | None = None,
    include_closed_pay: bool = True,
    vinculo_headers: list[str] | None = None,
    leave_rows: list[list[Any]] | None = None,
) -> bytes:
    v_headers = list(vinculo_headers or VINCULO_HEADERS)
    if extra_vinculo_headers:
        v_headers.extend(extra_vinculo_headers)
    person_a = vinculo_row(PERSON_A, name="Alice")
    person_b = vinculo_row(PERSON_B, name="Bruno", dob=date(1995, 6, 1))
    if extra_vinculo_values:
        person_a = person_a + extra_vinculo_values
        person_b = person_b + extra_vinculo_values
    contratos = [CONTRATO_HEADERS]
    if include_closed_pay:
        contratos.append(
            contrato_row(
                PERSON_A,
                name="Alice",
                rendimento_from=date(2024, 1, 2),
                rendimento_to=date(2024, 12, 31),
                salary=1000,
            )
        )
    contratos.append(
        contrato_row(
            PERSON_A,
            name="Alice",
            rendimento_from=date(2025, 1, 1),
            rendimento_to=None,
            salary=1500,
            substitute_niss=SUBSTITUTE_NISS,
        )
    )
    contratos.append(
        contrato_row(
            PERSON_B,
            name="Bruno",
            rendimento_from=date(2024, 6, 1),
            rendimento_to=None,
            salary=2000,
        )
    )
    sheets: dict[str, list[list[Any]]] = {
        "Vínculos": [v_headers, person_a, person_b],
        "Contratos": contratos,
    }
    if leave_rows is not None:
        sheets["Remunerações"] = [LEAVE_HEADERS, *leave_rows]
    return build_xlsx(sheets)


def remuneracoes_only_workbook(rows: list[list[Any]] | None = None) -> bytes:
    data = rows if rows is not None else [leave_row(PERSON_A)]
    return build_xlsx({"Ausências": [LEAVE_HEADERS, *data]})


def vinculos_only_workbook() -> bytes:
    return build_xlsx(
        {
            "Vínculos": [
                VINCULO_HEADERS,
                vinculo_row(PERSON_A, name="Alice"),
                vinculo_row(PERSON_B, name="Bruno"),
            ]
        }
    )


def contratos_only_workbook() -> bytes:
    return build_xlsx(
        {
            "Contratos": [
                CONTRATO_HEADERS,
                contrato_row(
                    PERSON_A,
                    name="Alice",
                    rendimento_from=date(2024, 1, 2),
                    rendimento_to=date(2024, 12, 31),
                    salary=1000,
                ),
                contrato_row(
                    PERSON_A,
                    name="Alice",
                    rendimento_from=date(2025, 1, 1),
                    salary=1500,
                ),
                contrato_row(PERSON_B, name="Bruno", salary=2000),
            ]
        }
    )


def unnamed_sheet_workbooks() -> tuple[bytes, bytes]:
    vinculos = build_xlsx(
        {"Sheet1": [VINCULO_HEADERS, vinculo_row(PERSON_A, name="Alice")]}
    )
    contratos = build_xlsx(
        {
            "Sheet1": [
                CONTRATO_HEADERS,
                contrato_row(PERSON_A, name="Alice", salary=1500),
            ]
        }
    )
    return vinculos, contratos


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float):
        return str(value).replace(".", ",")
    return str(value)


def build_csv(
    headers: list[str],
    rows: list[list[Any]],
    *,
    delimiter: str = ";",
    encoding: str = "utf-8",
) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_cell(cell) for cell in row])
    return buffer.getvalue().encode(encoding)


def vinculos_only_csv() -> bytes:
    return build_csv(
        VINCULO_HEADERS,
        [
            vinculo_row(PERSON_A, name="Alice"),
            vinculo_row(PERSON_B, name="Bruno"),
        ],
    )


def contratos_only_csv() -> bytes:
    return build_csv(
        CONTRATO_HEADERS,
        [
            contrato_row(
                PERSON_A,
                name="Alice",
                rendimento_from=date(2024, 1, 2),
                rendimento_to=date(2024, 12, 31),
                salary=1000,
            ),
            contrato_row(
                PERSON_A,
                name="Alice",
                rendimento_from=date(2025, 1, 1),
                salary=1500,
            ),
            contrato_row(PERSON_B, name="Bruno", salary=2000),
        ],
    )
