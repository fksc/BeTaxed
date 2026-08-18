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
