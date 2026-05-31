"""Run Alembic migrations programmatically at API startup.

The api image only copies ``src``; the Dockerfile also copies ``alembic.ini``
and ``alembic/`` next to it so this resolves in both the container (/app) and
local dev (apps/api). ``parents[3]`` of this file is the api root in both.
"""
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

_API_ROOT = Path(__file__).resolve().parents[3]


def _run_upgrade() -> None:
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_ROOT / "alembic"))
    command.upgrade(cfg, "head")


async def run_migrations() -> None:
    """Apply migrations up to head. Runs the sync Alembic command in a thread
    so it never blocks the event loop during startup."""
    await asyncio.to_thread(_run_upgrade)
