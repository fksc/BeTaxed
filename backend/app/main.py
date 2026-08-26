"""BeTaxed API — load ``backend/.env`` before imports that read ``os.environ``."""

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.redis_util import ping as redis_ping, set_app_redis
from app.routers import (
    certificates_router,
    intakes_router,
    me_router,
    notifications_router,
    ops_router,
    people_router,
    ss_batches_router,
)
from app.settings import get_cors_origins, get_redis_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = get_redis_url()
    if url:
        from redis.asyncio import Redis

        app.state.redis = Redis.from_url(url, decode_responses=True)
    else:
        app.state.redis = None
    set_app_redis(app.state.redis)
    yield
    redis = getattr(app.state, "redis", None)
    if redis is not None:
        await redis.aclose()
    set_app_redis(None)


app = FastAPI(title="BeTaxed API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me_router)
app.include_router(intakes_router)
app.include_router(people_router)
app.include_router(ss_batches_router)
app.include_router(certificates_router)
app.include_router(notifications_router)
app.include_router(ops_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        ok = await redis_ping(redis)
        if not ok:
            raise HTTPException(status_code=503, detail="redis_unavailable")
    return {"status": "ok"}
