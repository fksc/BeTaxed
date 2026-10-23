"""Link a contract PDF to one employee: NIF, then name, then NISS (DEV-850)."""

from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class MatchCandidate:
    employee_id: uuid.UUID
    nif_hash: bytes | None
    niss_hash: bytes
    name_norm: str | None


@dataclass(frozen=True)
class MatchResult:
    employee_id: uuid.UUID | None
    via: str | None


def normalize_person_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    folded = unicodedata.normalize("NFKD", raw).casefold()
    stripped = "".join(ch for ch in folded if not unicodedata.combining(ch))
    collapsed = " ".join(stripped.split())
    return collapsed or None


def match_contract_employee(
    candidates: list[MatchCandidate],
    *,
    nif_hash: bytes | None,
    name_norm: str | None,
    niss_hash: bytes | None,
) -> MatchResult:
    """Stop at the first unique hit. NIF, then name, then NISS."""
    nif_hits: list[MatchCandidate] = []
    if nif_hash is not None:
        nif_hits = [row for row in candidates if row.nif_hash == nif_hash]
        if len(nif_hits) == 1:
            return MatchResult(nif_hits[0].employee_id, "NIF")

    if nif_hits:
        name_pool = nif_hits
    else:
        name_pool = candidates

    name_hits: list[MatchCandidate] = []
    if name_norm:
        name_hits = [row for row in name_pool if row.name_norm == name_norm]
        if len(name_hits) == 1:
            return MatchResult(name_hits[0].employee_id, "NAME")

    if niss_hash is None:
        return MatchResult(None, None)

    if len(name_hits) > 1:
        niss_pool = name_hits
    elif len(nif_hits) > 1 and not name_norm:
        niss_pool = nif_hits
    else:
        niss_pool = candidates

    niss_hits = [row for row in niss_pool if row.niss_hash == niss_hash]
    if len(niss_hits) == 1:
        return MatchResult(niss_hits[0].employee_id, "NISS")
    return MatchResult(None, None)
