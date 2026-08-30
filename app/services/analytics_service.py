"""Cache-Aside analytics for the dashboard-facing metrics endpoint."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from redis.asyncio import Redis

from app.repositories.order_repo import OrderRepository

ANALYTICS_CACHE_KEY = "analytics:metrics:24h"
ANALYTICS_CACHE_TTL_SECONDS = 30

# Single-flight guard: on a cache miss, exactly one request holds this lock
# and recomputes; concurrent misses wait briefly and re-read the cache instead
# of stampeding the aggregation query. A soft-TTL / serve-stale design would
# also work and never block a reader, but it is a larger pattern -- this is the
# minimal lock-on-miss version.
ANALYTICS_LOCK_KEY = "analytics:metrics:24h:lock"
ANALYTICS_LOCK_TTL_SECONDS = 10
_LOSER_RETRIES = 5
_LOSER_SLEEP_SECONDS = 0.25


class AnalyticsService:
    def __init__(self, order_repo: OrderRepository, redis_client: Redis) -> None:
        self.order_repo = order_repo
        self.redis_client = redis_client

    async def get_metrics(self) -> dict[str, Any]:
        cached = await self.redis_client.get(ANALYTICS_CACHE_KEY)
        if cached is not None:
            return json.loads(cached)

        got_lock = await self.redis_client.set(
            ANALYTICS_LOCK_KEY, "1", ex=ANALYTICS_LOCK_TTL_SECONDS, nx=True
        )
        if not got_lock:
            # Someone else is already recomputing. Wait for them to populate
            # the cache; fall through to computing ourselves if they don't.
            for _ in range(_LOSER_RETRIES):
                await asyncio.sleep(_LOSER_SLEEP_SECONDS)
                cached = await self.redis_client.get(ANALYTICS_CACHE_KEY)
                if cached is not None:
                    return json.loads(cached)

        try:
            metrics = await self.order_repo.rolling_metrics(window_hours=24)
            await self.redis_client.set(
                ANALYTICS_CACHE_KEY,
                json.dumps(metrics),
                ex=ANALYTICS_CACHE_TTL_SECONDS,
            )
            return metrics
        finally:
            if got_lock:
                # Release even on failure, or a broken query blocks recompute
                # for the full lock TTL.
                await self.redis_client.delete(ANALYTICS_LOCK_KEY)
