import asyncio

from redis.asyncio import Redis
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from worker.activities import (
    persist_combined_result_activity,
    persist_formation_result_activity,
    run_algorithm_activity,
    run_combined_method_activity,
    set_redis_client,
)
from worker.config import REDIS_URL, TASK_QUEUE, TEMPORAL_HOST, TEMPORAL_NAMESPACE
from worker.workflows.combined import CombinedFormationWorkflow
from worker.workflows.single import SingleAlgorithmWorkflow


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
        workflows=[SingleAlgorithmWorkflow, CombinedFormationWorkflow],
        activities=[
            run_algorithm_activity,
            persist_formation_result_activity,
            run_combined_method_activity,
            persist_combined_result_activity,
        ],
    )

    print(f"Worker started — task queue: {TASK_QUEUE!r}, host: {TEMPORAL_HOST}")
    try:
        await worker.run()
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
