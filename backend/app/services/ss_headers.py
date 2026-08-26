"""Official SS export headers (KB/03, KB/20). Analyst columns are ignored."""

from __future__ import annotations

import re
import unicodedata

# Canonical header → dataclass field. First occurrence wins (duplicate
# "Vínculo" on the analyst sheet is the VLOOKUP column and is dropped).
VINCULO_FIELDS: dict[str, str] = {
    "niss": "niss",
    "nome trabalhador": "nome",
    "data nascimento": "dob",
    "vinculo": "vinculo_raw",
    "vinculo comunicado em": "communicated_on",
    "inicio vinculo": "started_on",
    "fim vinculo": "ended_on",
    "inicio aplicacao taxa": "rate_from",
    "fim aplicacao taxa": "rate_to",
    "taxa": "taxa_pct",
    "local de trabalho": "workplace_ss_label",
}

CONTRATO_FIELDS: dict[str, str] = {
    "niss": "niss",
    "nome trabalhador": "nome",
    "modalidade contrato": "modality_raw",
    "prestacao trabalho": "work_mode_raw",
    "data inicio": "contract_started_on",
    "data fim": "contract_ended_on",
    "profissao": "profession_raw",
    "percentagem trabalho": "percent_work",
    "horas trabalho": "hours_work",
    "dias trabalho": "days_work",
    "motivo contrato": "motivo_raw",
    "data inicio periodo rendimento": "rendimento_from",
    "data fim periodo rendimento": "rendimento_to",
    "remuneracao base": "base_salary",
}

VINCULO_REQUIRED = (
    "niss",
    "vinculo",
    "inicio vinculo",
    "taxa",
    "local de trabalho",
)

CONTRATO_REQUIRED = (
    "niss",
    "modalidade contrato",
    "data inicio periodo rendimento",
    "remuneracao base",
)

# BeTaxed remunerações *leave* ingest — not official Segurança Social DR
# headers. Samples only have vínculos + contratos (KB/03, DEV-849). Map
# official remunerações columns here when a sample exists.
LEAVE_FIELDS: dict[str, str] = {
    "niss": "niss",
    "tipo de ausencia": "leave_type",
    "tipo de baixa": "leave_type",
    "leave type": "leave_type",
    "inicio ausencia": "started_on",
    "data inicio ausencia": "started_on",
    "inicio da ausencia": "started_on",
    "started on": "started_on",
    "fim ausencia": "ended_on",
    "data fim ausencia": "ended_on",
    "fim da ausencia": "ended_on",
    "ended on": "ended_on",
}

LEAVE_REQUIRED_FIELDS = frozenset({"niss", "leave_type", "started_on"})

_LEAVE_TYPE_FOLD: dict[str, str] = {
    "parental": "PARENTAL",
    "licenca parental": "PARENTAL",
    "parentalidade": "PARENTAL",
    "doenca": "SICKNESS",
    "sickness": "SICKNESS",
    "baixa": "SICKNESS",
    "baixa medica": "SICKNESS",
    "sick": "SICKNESS",
    "nao remunerada": "UNPAID",
    "unpaid": "UNPAID",
    "sem remuneracao": "UNPAID",
    "other": "OTHER",
    "outra": "OTHER",
    "outro": "OTHER",
    "outros": "OTHER",
}


def map_leave_type(raw: str | None) -> str | None:
    """Map a leave-sheet cell to PARENTAL/SICKNESS/UNPAID/OTHER.

    Official SS remunerações numeric codes are unknown without a sample
    and are not invented here.
    """
    if raw is None or str(raw).strip() == "":
        return None
    folded = fold_header(str(raw))
    return _LEAVE_TYPE_FOLD.get(folded)


# Analyst-only / formula columns on the sample workbook.
_IGNORE_HEADERS = frozenset(
    {
        "idade",
        "rem base",
        "fee",
        "ano",
        "fee/ano",
        "vlookup",
    }
)

_EXPORT_LABEL_RE = re.compile(
    r"(?P<niss>\d{9,11})_(?P<kind>vinculos|contratos)_"
    r"(?P<y>\d{4})_(?P<m>\d{2})_(?P<d>\d{2})",
    re.IGNORECASE,
)


def fold_header(raw: str) -> str:
    """Accent-fold, casefold, collapse whitespace, strip (%)/(€) suffixes."""
    nfkd = unicodedata.normalize("NFKD", raw)
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    collapsed = re.sub(r"\s+", " ", stripped).strip().casefold()
    collapsed = re.sub(r"\s*\(%\)\s*$", "", collapsed)
    collapsed = re.sub(r"\s*\(€\)\s*$", "", collapsed)
    collapsed = re.sub(r"\s*€\s*$", "", collapsed)
    return collapsed.strip()


def is_ignored_header(raw: str) -> bool:
    return fold_header(raw) in _IGNORE_HEADERS


def parse_export_label(filename: str) -> tuple[str | None, str | None]:
    """Return (employer_niss, export_label) from `{niss}_vinculos_{date}`."""
    match = _EXPORT_LABEL_RE.search(filename)
    if match is None:
        return None, None
    return match.group("niss"), match.group(0)
