"""Shared worker-test fixtures.

The experiment activities stash their generated run-list in Redis
(``generate_experiment_runs_activity`` → ``_redis.set``; the variant activity
reads it back), so any test that exercises them needs a Redis client. Provide
an in-memory fake so the suite has no external dependency.
"""
import pytest
from fakeredis import FakeAsyncRedis

from worker.activities import set_redis_client


@pytest.fixture(autouse=True)
def fake_redis():
    set_redis_client(FakeAsyncRedis(decode_responses=True))
    yield
    set_redis_client(None)
