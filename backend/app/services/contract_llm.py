"""Extract typed fields from an employment-contract PDF (DEV-836)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from app.settings import (
    get_contract_llm_mode,
    get_gemini_model,
    get_google_cloud_project,
    get_vertex_location,
)

logger = logging.getLogger(__name__)

_PROMPT = """You extract facts from a Portuguese employment contract (contrato de trabalho).
Return JSON only with keys:
- doc_kind: SEM_TERMO | TERMO | CONVERSION
  SEM_TERMO = contrato sem termo / permanente / open-ended
  TERMO = contrato a termo certo or incerto (fixed or unfixed term), including 1-year CDD
  CONVERSION = conversão to sem termo
- signed_on: YYYY-MM-DD of signature / start of this contract, or null
- term_end_on: YYYY-MM-DD when the term ends, or null for sem termo
Do not invent names, NISS, salary, or eligibility. If unsure, use TERMO for any end date.
"""


@dataclass(frozen=True)
class ContractExtract:
    doc_kind: str
    signed_on: date | None
    term_end_on: date | None
    leftover: dict


class ContractExtractor(Protocol):
    def extract(
        self, data: bytes, *, mime_type: str | None, filename: str | None
    ) -> ContractExtract: ...


class OffExtractor:
    def extract(
        self, data: bytes, *, mime_type: str | None, filename: str | None
    ) -> ContractExtract:
        raise RuntimeError("CONTRACT_LLM=off")


class StubExtractor:
    """DEV/test: 1-year termo starting 2022-02-01 — the SS-vs-paper worked case."""

    def extract(
        self, data: bytes, *, mime_type: str | None, filename: str | None
    ) -> ContractExtract:
        signed = date(2022, 2, 1)
        return ContractExtract(
            doc_kind="TERMO",
            signed_on=signed,
            term_end_on=signed + timedelta(days=365),
            leftover={"extractor": "stub", "filename": filename},
        )


class GeminiExtractor:
    def extract(
        self, data: bytes, *, mime_type: str | None, filename: str | None
    ) -> ContractExtract:
        from google import genai
        from google.genai import types

        project = get_google_cloud_project()
        if not project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is required for Gemini review")
        mime = mime_type or "application/pdf"
        client = genai.Client(
            vertexai=True,
            project=project,
            location=get_vertex_location(),
        )
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime),
                _PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        text = (response.text or "").strip()
        parsed = json.loads(text)
        kind = _normalize_kind(parsed.get("doc_kind"))
        return ContractExtract(
            doc_kind=kind,
            signed_on=_parse_date(parsed.get("signed_on")),
            term_end_on=_parse_date(parsed.get("term_end_on")),
            leftover={"extractor": "gemini", "raw": parsed},
        )


def get_contract_extractor() -> ContractExtractor:
    mode = get_contract_llm_mode()
    if mode == "off":
        return OffExtractor()
    if mode == "stub":
        return StubExtractor()
    return GeminiExtractor()


def _normalize_kind(raw: object) -> str:
    value = str(raw or "").strip().upper().replace(" ", "_")
    if value in {"SEM_TERMO", "PERMANENT", "OPEN_ENDED"}:
        return "SEM_TERMO"
    if value in {"CONVERSION", "CONVERSAO", "CONVERSÃO"}:
        return "CONVERSION"
    return "TERMO"


def _parse_date(raw: object) -> date | None:
    if raw is None or raw == "":
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None
