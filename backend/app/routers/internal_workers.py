"""Cloud Tasks handler for contract association and review (DEV-850)."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from app.db import AsyncSessionLocal
from app.schemas.contracts import ContractWorkerIn
from app.services.cloud_tasks import should_retry_task, worker_authorized
from app.services.contract_inbox import process_contract_inbox
from app.services.contract_review import ContractReviewRetry, review_employment_document

router = APIRouter(prefix="/internal/workers", tags=["internal"])


@router.post("/review-contract")
async def post_review_contract(
    body: ContractWorkerIn,
    authorization: str | None = Header(default=None),
    job_token: str | None = Header(default=None, alias="X-Internal-Job-Token"),
    retry_count_raw: str | None = Header(default=None, alias="X-CloudTasks-TaskRetryCount"),
) -> dict[str, str]:
    if not worker_authorized(authorization, job_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")
    if body.inbox_id is None and body.employment_document_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="inbox_id or employment_document_id is required.",
        )
    retry_count = _retry_count(retry_count_raw)
    try:
        async with AsyncSessionLocal() as db:
            if body.inbox_id is not None:
                await process_contract_inbox(db, body.inbox_id, retry_count=retry_count)
            elif body.employment_document_id is not None:
                await review_employment_document(
                    db,
                    body.employment_document_id,
                    retry=should_retry_task(retry_count),
                )
            await db.commit()
    except ContractReviewRetry:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="retry")
    return {"status": "ok"}


def _retry_count(raw: str | None) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None
