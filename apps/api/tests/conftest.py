"""Test fixtures: an in-process Postgres (testcontainers) with a fallback to
TEST_DATABASE_URL, migrations applied once, and a per-test clean schema.

If neither testcontainers (Docker) nor TEST_DATABASE_URL is available, the whole
suite skips with a clear message instead of failing.
"""
import asyncio
import atexit
import os
import re

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DB_SSL", "")  # asyncpg ssl disabled by db.base default
os.environ["DB_NULLPOOL"] = "1"  # avoid cross-event-loop pool reuse under pytest


def _to_asyncpg(url: str) -> str:
    if "+" in url.split("://", 1)[0]:
        return re.sub(r"\+\w+://", "+asyncpg://", url, count=1)
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _resolve_database_url() -> str | None:
    # 1) testcontainers (preferred — fully self-contained)
    try:
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:16")
        container.start()
        atexit.register(container.stop)
        return _to_asyncpg(container.get_connection_url())
    except Exception:
        pass
    # 2) explicit test DB
    if os.getenv("TEST_DATABASE_URL"):
        return _to_asyncpg(os.environ["TEST_DATABASE_URL"])
    return None


_DB_URL = _resolve_database_url()
if _DB_URL:
    os.environ["DATABASE_URL"] = _DB_URL


# Tables truncated between tests (children first is fine with CASCADE).
_TABLES = (
    "formation_snapshots, formation_assignments, formation_scenarios, "
    "planning_cells, service_group_members, service_groups, services, providers, users"
)


def _run_migrations_sync() -> None:
    from src.operations.db.migrations import run_migrations

    asyncio.run(run_migrations())


if _DB_URL:
    _run_migrations_sync()


@pytest.fixture(autouse=True)
def _skip_without_db():
    if not _DB_URL:
        pytest.skip("No test database: install Docker (testcontainers) or set TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
async def _clean_tables():
    from sqlalchemy import text

    from src.operations.db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await session.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
        await session.commit()
    yield


@pytest.fixture
async def client():
    import httpx
    from httpx import ASGITransport

    from src.operations.main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Factory: register (idempotent-ish) + login a user, return Bearer headers."""

    async def _make(email: str = "user@example.com", password: str = "secret123") -> dict:
        await client.post("/api/auth/register", json={"email": email, "password": password})
        res = await client.post(
            "/api/auth/login", data={"username": email, "password": password}
        )
        token = res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


# ---------------------------------------------------------------------------
# Mocked Temporal: capture start_workflow calls instead of running a workflow,
# so formation tests can invoke the persist activities directly. Shared by
# test_formation_flow.py and test_combined_method.py.
# ---------------------------------------------------------------------------

class _MockDesc:
    from temporalio.client import WorkflowExecutionStatus as _S
    status = _S.RUNNING


class _MockHandle:
    async def describe(self):
        return _MockDesc()


class _MockTemporal:
    def __init__(self):
        self.calls = []

    async def start_workflow(self, *args, **kwargs):
        self.calls.append((args, kwargs))

    def get_workflow_handle(self, workflow_id):
        return _MockHandle()


class _ApiFakeRedis:
    """Minimal stand-in for app.state.redis (the /iterations dependency)."""

    async def xrange(self, key, min="-", max="+"):
        return []


@pytest.fixture
def mock_temporal():
    from src.operations.main import app

    mock = _MockTemporal()
    app.state.temporal = mock
    app.state.redis = _ApiFakeRedis()
    return mock
