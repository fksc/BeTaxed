from collections.abc import AsyncGenerator
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import get_database_url

logger = logging.getLogger(__name__)

engine = create_async_engine(
    get_database_url(),
    pool_pre_ping=True,
)


class AppAsyncSession(AsyncSession):
    """Commit then drain domain-event fan-out (TJ-shaped, KB/08)."""

    async def commit(self) -> None:
        await super().commit()
        from app.services.domain_event_dispatch import dispatch_pending_domain_events

        try:
            delivered = await dispatch_pending_domain_events(self)
        except Exception:
            logger.exception("domain event dispatch failed")
            return
        if delivered > 0 or self.new or self.dirty or self.deleted:
            await super().commit()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AppAsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
