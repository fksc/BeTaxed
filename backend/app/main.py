"""BeTaxed API — load ``backend/.env`` before imports that read ``os.environ``."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.routers import me_router
from app.settings import get_cors_origins, get_redis_url

app = FastAPI(title="BeTaxed API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness: PostgreSQL; Redis is reserved (REDIS_URL) for a later ping."""
    await db.execute(text("SELECT 1"))
    _ = request
    _ = get_redis_url()
    return {"status": "ok"}
