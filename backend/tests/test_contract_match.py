"""NIF, then name, then NISS. No database."""

from __future__ import annotations

import uuid

from app.services.contract_match import (
    MatchCandidate,
    match_contract_employee,
    normalize_person_name,
)


def _person(
    *,
    name: str | None,
    nif: bytes | None = None,
    niss: bytes | None = None,
) -> MatchCandidate:
    return MatchCandidate(
        employee_id=uuid.uuid4(),
        nif_hash=nif,
        niss_hash=niss or uuid.uuid4().bytes,
        name_norm=normalize_person_name(name),
    )


def test_normalize_person_name_folds_accents() -> None:
    assert normalize_person_name("  José   Silva ") == "jose silva"


def test_unique_nif_wins_over_a_different_name() -> None:
    alice = _person(name="Alice", nif=b"nif-alice", niss=b"niss-alice")
    bruno = _person(name="Bruno", nif=b"nif-bruno", niss=b"niss-bruno")
    result = match_contract_employee(
        [alice, bruno],
        nif_hash=b"nif-alice",
        name_norm="bruno",
        niss_hash=b"niss-bruno",
    )
    assert result.employee_id == alice.employee_id
    assert result.via == "NIF"


def test_shared_nif_is_paired_with_name() -> None:
    alice = _person(name="Alice", nif=b"same", niss=b"niss-alice")
    bruno = _person(name="Bruno", nif=b"same", niss=b"niss-bruno")
    result = match_contract_employee(
        [alice, bruno],
        nif_hash=b"same",
        name_norm="bruno",
        niss_hash=None,
    )
    assert result.employee_id == bruno.employee_id
    assert result.via == "NAME"


def test_ambiguous_name_uses_niss_inside_that_set() -> None:
    first = _person(name="Alice", niss=b"niss-1")
    second = _person(name="Alice", niss=b"niss-2")
    result = match_contract_employee(
        [first, second],
        nif_hash=None,
        name_norm="alice",
        niss_hash=b"niss-2",
    )
    assert result.employee_id == second.employee_id
    assert result.via == "NISS"


def test_unknown_name_falls_through_to_niss() -> None:
    alice = _person(name="Alice", niss=b"niss-alice")
    result = match_contract_employee(
        [alice],
        nif_hash=b"missing",
        name_norm="nobody",
        niss_hash=b"niss-alice",
    )
    assert result.employee_id == alice.employee_id
    assert result.via == "NISS"


def test_no_unique_hit_stays_unassigned() -> None:
    alice = _person(name="Alice", niss=b"niss-alice")
    bruno = _person(name="Bruno", niss=b"niss-bruno")
    result = match_contract_employee(
        [alice, bruno],
        nif_hash=None,
        name_norm="alice",
        niss_hash=None,
    )
    assert result.via == "NAME"
    result = match_contract_employee(
        [alice, bruno],
        nif_hash=None,
        name_norm=None,
        niss_hash=None,
    )
    assert result.employee_id is None
    assert result.via is None
