from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

Base = declarative_base()

# --- Async engine: used by the API (asyncpg) ---------------------------------
engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


# --- Sync engine: used by Celery workers (psycopg) --------------------------
# INTENT.md only requires async on the API side; a sync worker avoids the
# event-loop-in-prefork problem entirely.
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL, echo=False, pool_pre_ping=True
)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)
