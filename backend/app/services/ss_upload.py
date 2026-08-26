"""Shared SS upload helpers for intake and company routes (DEV-835)."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, UploadFile, status

from app.services.ss_parser import SsSourceFile


async def read_ss_upload_files(files: list[UploadFile]) -> list[SsSourceFile]:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one SS export file is required.",
        )
    sources: list[SsSourceFile] = []
    for item in files:
        content = await item.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        sources.append(SsSourceFile(item.filename or "upload.xlsx", content))
    return sources


def parse_period_year_month(raw: str) -> date:
    value = raw.strip()
    try:
        if len(value) == 7 and value[4] == "-":
            parsed = date(int(value[:4]), int(value[5:7]), 1)
        else:
            parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_year_month must be YYYY-MM or YYYY-MM-DD.",
        ) from exc
    if parsed.day != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_year_month must be the first of the month.",
        )
    return parsed
