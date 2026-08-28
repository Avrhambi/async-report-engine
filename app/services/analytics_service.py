import json
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.domain.models import Event

logger = structlog.get_logger()

class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_metrics(self) -> dict[str, Any]:
        cache_key = "analytics:metrics"
        
        # Cache-Aside: Check Redis first
        try:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                return dict(json.loads(cached_data))
        except Exception as e:  # noqa: BLE001
            # Fallback to DB if Redis is down
            logger.warning("Redis cache read failed, falling back to database", error=str(e))
        
        # Fallback to PostgreSQL Database
        total_events = await self.session.scalar(select(func.count(Event.id)))
        
        stmt = select(Event.event_type, func.count(Event.id)).group_by(Event.event_type)
        result = await self.session.execute(stmt)
        events_by_type = {row[0]: row[1] for row in result.all()}
        
        metrics = {
            "total_events": total_events or 0,
            "events_by_type": events_by_type
        }
        
        # Save to Redis with a TTL of 60 seconds
        try:
            await redis_client.set(cache_key, json.dumps(metrics), ex=60)
        except Exception as e:  # noqa: BLE001
            # Ignore cache write errors if Redis is down
            logger.warning("Redis cache write failed", error=str(e))
            
        return metrics
