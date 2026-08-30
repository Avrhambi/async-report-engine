import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.core.redis import get_redis

# Mock Redis
async def mock_get_redis():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    return mock_redis

# Mock Database session
async def mock_get_db():
    mock_session = AsyncMock()
    yield mock_session

@pytest.fixture
def client():
    app.dependency_overrides[get_redis] = mock_get_redis
    app.dependency_overrides[get_db] = mock_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}
