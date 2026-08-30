from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.core.database import get_db
from app.core.redis import get_redis
from app.main import app
from fastapi.testclient import TestClient


class FakeRedis:
    """In-memory stand-in covering the get/set/delete surface we use."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def client(fake_redis: FakeRedis):
    async def _get_redis() -> FakeRedis:
        return fake_redis

    async def _get_db():
        yield AsyncMock()

    app.dependency_overrides[get_redis] = _get_redis
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
