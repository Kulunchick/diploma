import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from src.worker.activities import (
    generate_experiment_runs_activity,
    run_algorithm_activity,
)
from src.worker.config import TASK_QUEUE, TEMPORAL_HOST, TEMPORAL_NAMESPACE
from src.worker.workflows.experiment import ExperimentWorkflow
from src.worker.workflows.solve import SolveWorkflow


async def main() -> None:
    client = await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
        data_converter=pydantic_data_converter,
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SolveWorkflow, ExperimentWorkflow],
        activities=[run_algorithm_activity, generate_experiment_runs_activity],
    )

    print(f"Worker started — task queue: {TASK_QUEUE!r}, host: {TEMPORAL_HOST}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
