import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.core.database import Base, get_db
from app.main import app

# Spin up a Postgres container for the duration of the test session
postgres = PostgresContainer("postgres:16-alpine")

@pytest.fixture(scope="session", autouse=True)
def setup_postgres():
    """Starts the Testcontainer at the beginning of the test session and stops it at the end."""
    postgres.start()
    yield
    postgres.stop()

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Creates the SQLAlchemy async engine connected to the Testcontainer."""
    # Testcontainers returns a sync driver string (psycopg2). 
    # We replace it to use the async driver (asyncpg) required by our app.
    connection_url = postgres.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )
    
    engine = create_async_engine(connection_url, echo=False)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(autouse=True)
async def setup_database(test_engine):
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provides an active asynchronous database session for tests."""
    TestingSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture
async def client(db_session):
    """Provides an AsyncClient for FastAPI endpoint testing."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()
