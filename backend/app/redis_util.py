"""Redis helpers: pub/sub wake-up for in-app notifications (KB/08, DEV-836)."""

from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis

_app_redis: Redis | None = None


def set_app_redis(redis: Redis | None) -> None:
    global _app_redis
    _app_redis = redis


def get_app_redis() -> Redis | None:
    return _app_redis


def user_notifications_channel(user_id: UUID) -> str:
    return f"user:{user_id}:notifications"


async def publish_user_notification(redis: Redis, user_id: UUID, message: str) -> int:
    return await redis.publish(user_notifications_channel(user_id), message)


async def ping(redis: Redis) -> bool:
    return bool(await redis.ping())
