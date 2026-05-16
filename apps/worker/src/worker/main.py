import asyncio

from redis.asyncio import Redis
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from worker.activities import (
    generate_experiment_runs_activity,
    run_algorithm_activity,
    run_experiment_variant_activity,
    set_redis_client,
)
from worker.config import REDIS_URL, TASK_QUEUE, TEMPORAL_HOST, TEMPORAL_NAMESPACE
from worker.workflows.experiment import ExperimentWorkflow
from worker.workflows.solve import SolveWorkflow


async def main() -> None:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    set_redis_client(redis)

    client = await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
        data_converter=pydantic_data_converter,
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SolveWorkflow, ExperimentWorkflow],
        activities=[
            run_algorithm_activity,
            run_experiment_variant_activity,
            generate_experiment_runs_activity,
        ],
    )

    print(f"Worker started — task queue: {TASK_QUEUE!r}, host: {TEMPORAL_HOST}")
    try:
        await worker.run()
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
