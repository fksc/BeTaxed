"""Emit domain events in the same transaction as the write (KB/08)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DomainEvent


async def emit_domain_event(
    session: AsyncSession,
    *,
    event_type: str,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    company_id: uuid.UUID | None,
    payload: dict,
) -> DomainEvent:
    event = DomainEvent(
        event_type=event_type,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        actor_id=actor_id,
        company_id=company_id,
        payload=payload,
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()
    pending = session.info.setdefault("pending_domain_event_ids", [])
    pending.append(event.id)
    return event
