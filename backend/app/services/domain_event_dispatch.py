"""Post-commit drain: fan-out notifications, then contract LLM review (KB/08)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DomainEvent
from app.services.notifications import fanout_domain_event

logger = logging.getLogger(__name__)


async def dispatch_pending_domain_events(session: AsyncSession) -> int:
    pending: list[UUID] = session.info.pop("pending_domain_event_ids", [])
    if not pending:
        return 0

    delivered = 0
    while pending:
        nxt: list[UUID] = []
        for event_id in pending:
            try:
                delivered += await fanout_domain_event(session, event_id)
            except Exception:
                logger.exception("fanout failed event=%s", event_id)
            event = await session.get(DomainEvent, event_id)
            if event is not None and event.event_type == "CONTRACT_UPLOADED":
                from app.services.contract_review import review_employment_document

                try:
                    await review_employment_document(session, event.source_entity_id)
                except Exception:
                    logger.exception(
                        "contract review failed document=%s", event.source_entity_id
                    )
            nxt.extend(session.info.pop("pending_domain_event_ids", []))
        pending = nxt
    return delivered
