from __future__ import annotations

import functools
from collections.abc import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

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


# --- Sync engine: used only by Celery workers (psycopg) --------------------
# INTENT.md only requires async on the API side; a sync worker avoids the
# event-loop-in-prefork problem entirely. Built lazily so the API and the
# test suite don't need psycopg installed.
@functools.lru_cache(maxsize=1)
def _sync_sessionmaker() -> sessionmaker[Session]:
    sync_engine = create_engine(
        settings.SYNC_DATABASE_URL, echo=False, pool_pre_ping=True
    )
    return sessionmaker(bind=sync_engine, expire_on_commit=False)


def SyncSessionLocal() -> Session:  # noqa: N802 - session-factory naming
    return _sync_sessionmaker()()
