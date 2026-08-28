import redis.asyncio as redis

from app.core.config import settings

# Create an async redis client using our config
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
