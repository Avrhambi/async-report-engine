import json
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.models import Event
from app.services.analytics_service import AnalyticsService

pytestmark = pytest.mark.asyncio

@patch("app.services.analytics_service.redis_client")
async def test_get_metrics_cache_hit(mock_redis, db_session):
    """Test that metrics are returned from Redis cache without hitting the DB."""
    # Setup mock Redis to return a cached string
    cached_metrics = {"total_events": 5, "events_by_type": {"login": 5}}
    mock_redis.get = AsyncMock(return_value=json.dumps(cached_metrics))
    
    service = AnalyticsService(db_session)
    result = await service.get_metrics()
    
    assert result == cached_metrics
    mock_redis.get.assert_called_once_with("analytics:metrics")
    # Ensure we didn't try to set the cache if we hit it
    mock_redis.set.assert_not_called()

@patch("app.services.analytics_service.redis_client")
async def test_get_metrics_cache_miss(mock_redis, db_session):
    """Test that on cache miss, metrics are calculated from DB and cached."""
    # Setup mock Redis to simulate empty cache
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    
    # Insert some dummy events into the real test database
    event1 = Event(user_id="u1", event_type="click", payload={})
    event2 = Event(user_id="u2", event_type="click", payload={})
    event3 = Event(user_id="u3", event_type="view", payload={})
    db_session.add_all([event1, event2, event3])
    await db_session.commit()
    
    service = AnalyticsService(db_session)
    result = await service.get_metrics()
    
    assert result["total_events"] == 3
    assert result["events_by_type"]["click"] == 2
    assert result["events_by_type"]["view"] == 1
    
    # Ensure cache was set correctly
    mock_redis.set.assert_called_once()
    args, kwargs = mock_redis.set.call_args
    assert args[0] == "analytics:metrics"
    assert json.loads(args[1]) == result
    assert kwargs["ex"] == 60
