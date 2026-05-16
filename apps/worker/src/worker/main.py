import asyncio
import logging

from redis.asyncio import Redis
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from worker.activities import (
    generate_experiment_runs_activity,
    run_algorithm_activity,
    set_redis_client,
)
from worker.config import REDIS_URL, TASK_QUEUE, TEMPORAL_HOST, TEMPORAL_NAMESPACE
from worker.workflows.experiment import ExperimentWorkflow
from worker.workflows.solve import SolveWorkflow

logger = logging.getLogger(__name__)


async def _connect_temporal() -> Client:
    for attempt in range(1, 31):
        try:
            return await Client.connect(
                TEMPORAL_HOST,
                namespace=TEMPORAL_NAMESPACE,
                data_converter=pydantic_data_converter,
            )
        except Exception as exc:
            if attempt == 30:
                raise
            logger.warning("Temporal not ready (attempt %d/30): %s — retrying in 5s", attempt, exc)
            await asyncio.sleep(5)


async def main() -> None:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    set_redis_client(redis)

    client = await _connect_temporal()

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SolveWorkflow, ExperimentWorkflow],
        activities=[run_algorithm_activity, generate_experiment_runs_activity],
    )

    print(f"Worker started — task queue: {TASK_QUEUE!r}, host: {TEMPORAL_HOST}")
    try:
        await worker.run()
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
