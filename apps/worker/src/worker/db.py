"""Minimal async SQLAlchemy setup for the worker.

Deliberately self-contained — the worker does not import the api package. Only
``persist_formation_result_activity`` uses this; the rest of the worker (solve /
experiment flow) does not touch Postgres.
"""
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://diploma:diploma@localhost:5432/diploma",
)


def _connect_args() -> dict:
    # asyncpg >= 0.31 negotiates SSL by default and raises against a non-TLS
    # server; our Postgres runs without TLS unless DB_SSL is set.
    if os.getenv("DB_SSL", "").lower() in ("require", "true", "1"):
        return {}
    return {"ssl": False}


engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args())

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False, autoflush=False
)
