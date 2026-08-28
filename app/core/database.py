from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 1. Create the async engine to connect to PostgreSQL
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# 2. Create a session factory for generating new database sessions
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 3. Create a Base class that our models will inherit from
class Base(DeclarativeBase):
    pass



# 4. A helper function (FastAPI Dependency) to hand out sessions to our API routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
