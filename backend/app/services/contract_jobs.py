"""After commit: enqueue contract jobs, or run them inline when Cloud Tasks is unset."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cloud_tasks import (
    contract_tasks_configured,
    enqueue_contract_inbox,
    enqueue_contract_review,
)
from app.services.contract_inbox import process_contract_inbox
from app.services.contract_review import review_employment_document

logger = logging.getLogger(__name__)


async def drain_contract_jobs(session: AsyncSession) -> int:
    inbox_ids = list(session.info.pop("pending_contract_inbox_ids", []))
    review_ids = list(session.info.pop("pending_contract_review_ids", []))
    handled = 0
    if contract_tasks_configured():
        for inbox_id in inbox_ids:
            try:
                enqueue_contract_inbox(inbox_id)
            except Exception:
                logger.exception("contract inbox enqueue failed inbox=%s", inbox_id)
                await process_contract_inbox(session, inbox_id, retry_count=None)
                handled += 1
        for document_id in review_ids:
            try:
                enqueue_contract_review(document_id)
            except Exception:
                logger.exception("contract review enqueue failed document=%s", document_id)
                await review_employment_document(session, document_id)
                handled += 1
        return handled

    for inbox_id in inbox_ids:
        try:
            await process_contract_inbox(session, inbox_id, retry_count=None)
            handled += 1
        except Exception:
            logger.exception("contract inbox failed inbox=%s", inbox_id)
    for document_id in review_ids:
        try:
            await review_employment_document(session, document_id)
            handled += 1
        except Exception:
            logger.exception("contract review failed document=%s", document_id)
    return handled
