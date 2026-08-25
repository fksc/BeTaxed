"""Notification fan-out: Postgres rows + Redis wake-up (KB/08)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanyMembership, DomainEvent, Notification, UserBase
from app.redis_util import get_app_redis, publish_user_notification

logger = logging.getLogger(__name__)

STAFF_ONLY = frozenset(
    {"CONTRACT_REVIEWED", "CONTRACT_SS_MISMATCH", "CONTRACT_REVIEW_FAILED"}
)
COMPANY_AND_STAFF = frozenset({"CONTRACT_UPLOADED"})


async def fanout_domain_event(session: AsyncSession, event_id: uuid.UUID) -> int:
    event = await session.get(DomainEvent, event_id)
    if event is None:
        return 0
    recipients = await _recipients(session, event)
    if not recipients:
        return 0

    rows = [
        {
            "recipient_id": rid,
            "domain_event_id": event.id,
            "is_read": False,
            "in_app_delivered": True,
            "created_at": datetime.now(UTC),
        }
        for rid in recipients
    ]
    stmt = (
        insert(Notification)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_notification_event_recipient")
        .returning(Notification.id, Notification.recipient_id)
    )
    created = (await session.execute(stmt)).all()
    await session.flush()

    redis = get_app_redis()
    if redis is not None:
        ping = json.dumps(
            {
                "type": "notification_created",
                "domain_event_id": str(event.id),
                "event_type": event.event_type,
            }
        )
        for _nid, recipient_id in created:
            try:
                await publish_user_notification(redis, recipient_id, ping)
            except Exception:
                logger.warning(
                    "redis publish failed recipient=%s event=%s",
                    recipient_id,
                    event.id,
                    exc_info=True,
                )
    return len(created)


async def _recipients(session: AsyncSession, event: DomainEvent) -> set[uuid.UUID]:
    staff = await _staff_ids(session)
    if event.event_type in STAFF_ONLY:
        return staff
    if event.event_type in COMPANY_AND_STAFF:
        company = set()
        if event.company_id is not None:
            company = await _company_hr_admin_ids(session, event.company_id)
        return staff | company
    return staff


async def _staff_ids(session: AsyncSession) -> set[uuid.UUID]:
    rows = (
        await session.execute(
            select(UserBase.id).where(
                UserBase.user_type == "BETAXED_STAFF",
                UserBase.is_active.is_(True),
            )
        )
    ).scalars().all()
    return set(rows)


async def _company_hr_admin_ids(
    session: AsyncSession, company_id: uuid.UUID
) -> set[uuid.UUID]:
    rows = (
        await session.execute(
            select(CompanyMembership.user_id).where(
                CompanyMembership.company_id == company_id,
                CompanyMembership.is_active.is_(True),
                CompanyMembership.role.in_(("ADMIN", "HR")),
            )
        )
    ).scalars().all()
    return set(rows)
