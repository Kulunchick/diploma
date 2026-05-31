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
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://diploma:diploma@localhost:5432/diploma",
)


def connect_args() -> dict:
    """asyncpg >= 0.31 negotiates SSL by default and raises against a non-TLS
    server instead of falling back. Our Postgres (appdb / in-cluster) runs
    without TLS, so disable it unless DB_SSL is explicitly requested. Shared
    with Alembic's env.py so both the runtime engine and migrations agree."""
    if os.getenv("DB_SSL", "").lower() in ("require", "true", "1"):
        return {}
    return {"ssl": False}


class Base(DeclarativeBase):
    pass


# asyncpg connections are event-loop bound. Under pytest-asyncio (a fresh loop
# per test) a pooled connection would be reused across loops and fail, so tests
# set DB_NULLPOOL=1 to open a fresh connection per checkout.
_engine_kwargs: dict = {"pool_pre_ping": True, "connect_args": connect_args()}
if os.getenv("DB_NULLPOOL", "").lower() in ("1", "true"):
    _engine_kwargs = {"poolclass": NullPool, "connect_args": connect_args()}

engine: AsyncEngine = create_async_engine(DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session
