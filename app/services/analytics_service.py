"""Cache-Aside analytics for the dashboard-facing metrics endpoint."""
from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.repositories.order_repo import OrderRepository

ANALYTICS_CACHE_KEY = "analytics:metrics:24h"
ANALYTICS_CACHE_TTL_SECONDS = 30


class AnalyticsService:
    def __init__(self, order_repo: OrderRepository, redis_client: Redis) -> None:
        self.order_repo = order_repo
        self.redis_client = redis_client

    async def get_metrics(self) -> dict[str, Any]:
        cached = await self.redis_client.get(ANALYTICS_CACHE_KEY)
        if cached is not None:
            return json.loads(cached)

        metrics = await self.order_repo.rolling_metrics(window_hours=24)
        await self.redis_client.set(
            ANALYTICS_CACHE_KEY,
            json.dumps(metrics),
            ex=ANALYTICS_CACHE_TTL_SECONDS,
        )
        return metrics
