"""In-app notification feed and SSE (KB/08, DEV-836)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal, get_db
from app.deps.auth import _upsert_user_from_token, get_current_user
from app.models import DomainEvent, Notification, UserBase
from app.redis_util import get_app_redis, user_notifications_channel
from app.schemas.contracts import NotificationListOut, NotificationOut

router = APIRouter(prefix="/v1", tags=["notifications"])
STREAM_MAX_SECONDS = 50.0


@router.get("/notifications", response_model=NotificationListOut)
async def list_notifications(
    user: UserBase = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListOut:
    rows = (
        (
            await db.execute(
                select(Notification, DomainEvent)
                .join(DomainEvent, DomainEvent.id == Notification.domain_event_id)
                .where(
                    Notification.recipient_id == user.id,
                    Notification.in_app_delivered.is_(True),
                )
                .order_by(Notification.created_at.desc())
                .limit(50)
            )
        )
        .all()
    )
    unread = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_id == user.id,
                Notification.is_read.is_(False),
                Notification.in_app_delivered.is_(True),
            )
        )
    ).scalar_one()
    items = [
        NotificationOut(
            id=note.id,
            event_type=event.event_type,
            payload=_payload_for_user(user, event),
            is_read=note.is_read,
            created_at=note.created_at,
            company_id=event.company_id,
        )
        for note, event in rows
    ]
    return NotificationListOut(items=items, unread_count=int(unread or 0))


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    user: UserBase = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    note = await db.get(Notification, notification_id)
    if note is None or note.recipient_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    note.is_read = True
    note.read_at = datetime.now(UTC)
    await db.commit()
    return {"status": "ok"}


@router.post("/notifications/read-all")
async def mark_all_read(
    user: UserBase = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await db.commit()
    return {"status": "ok"}


@router.get("/notifications/stream")
async def stream_notifications(request: Request) -> StreamingResponse:
    redis = get_app_redis()
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="realtime_unavailable",
        )

    authz = request.headers.get("authorization") or request.headers.get("Authorization")
    if not authz or not authz.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer token required.",
        )
    id_token = authz.split(" ", 1)[1].strip()
    async with AsyncSessionLocal() as session:
        user = await _upsert_user_from_token(session, id_token)
    user_id = user.id
    channel = user_notifications_channel(user_id)

    async def event_gen():
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + STREAM_MAX_SECONDS
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=min(20.0, remaining),
                )
                if msg is None:
                    yield ": ping\n\n"
                    continue
                if msg.get("type") == "message" and msg.get("data") is not None:
                    raw = msg["data"]
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    yield f"data: {raw}\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _payload_for_user(user: UserBase, event: DomainEvent) -> dict:
    payload = dict(event.payload or {})
    if user.user_type != "BETAXED_STAFF":
        payload.pop("ss_modality", None)
        payload.pop("ss_started_on", None)
        payload.pop("doc_kind", None)
        payload.pop("signed_on", None)
        payload.pop("term_end_on", None)
        payload.pop("matches_ss", None)
    return payload
