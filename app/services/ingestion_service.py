"""Orchestration for order-event ingestion."""
from __future__ import annotations

from typing import Any

from redis.asyncio import Redis

from app.repositories.order_repo import OrderRepository
from app.services.analytics_service import ANALYTICS_CACHE_KEY

_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


class IngestionService:
    def __init__(self, order_repo: OrderRepository, redis_client: Redis) -> None:
        self.order_repo = order_repo
        self.redis_client = redis_client

    async def ingest_batch(
        self, idempotency_key: str, events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        marker = f"idempotency:events:{idempotency_key}"
        # A full replay of the same batch is a no-op.
        if await self.redis_client.get(marker):
            return {"status": "accepted", "ingested": 0, "duplicates": len(events)}

        inserted = await self.order_repo.bulk_insert_ignore_duplicates(events)

        await self.redis_client.set(marker, "1", ex=_IDEMPOTENCY_TTL_SECONDS)
        # New data invalidates the analytics cache.
        await self.redis_client.delete(ANALYTICS_CACHE_KEY)

        return {
            "status": "accepted",
            "ingested": inserted,
            "duplicates": len(events) - inserted,
        }
