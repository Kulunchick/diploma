"""Async SQLAlchemy 2.0 setup for the persistent information-system layer.

The legacy /solve + /experiment* flow does not touch the database — only the
new /api/auth, catalogue, planning and formation endpoints depend on it.
"""
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://diploma:diploma@localhost:5432/diploma",
)


class Base(DeclarativeBase):
    pass


engine: AsyncEngine = create_async_engine(DATABASE_URL, pool_pre_ping=True)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session
