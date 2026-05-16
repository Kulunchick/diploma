"""
Tests for ExperimentWorkflow + generate_experiment_runs_activity using the noop spec.
No Temporal server required.
"""
import pytest
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from worker.activities import (
    generate_experiment_runs_activity,
    run_algorithm_activity,
    run_experiment_variant_activity,
    set_redis_client,
)
from worker.types import (
    ExperimentInput,
    ExperimentResult,
    GenerateRunsInput,
)
from worker.workflows.experiment import ExperimentWorkflow


# ---------------------------------------------------------------------------
# In-memory Redis stub — only the methods the activities actually call.
# ---------------------------------------------------------------------------

class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)


@pytest.fixture(autouse=True)
def fake_redis():
    fake = FakeRedis()
    set_redis_client(fake)  # type: ignore[arg-type]
    yield fake
    set_redis_client(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# generate_experiment_runs_activity
# ---------------------------------------------------------------------------

async def test_generate_runs_noop_returns_count(fake_redis):
    env = ActivityEnvironment()
    count: int = await env.run(
        generate_experiment_runs_activity,
        GenerateRunsInput(experiment_type="noop", params={"count": 5}),
    )
    assert count == 5
    # Activity stored the runs in Redis under the workflow's key.
    assert any(k.startswith("experiment_runs:") for k in fake_redis.store)


async def test_generate_runs_unknown_type_raises():
    env = ActivityEnvironment()
    with pytest.raises(ValueError, match="Unknown experiment type"):
        await env.run(
            generate_experiment_runs_activity,
            GenerateRunsInput(experiment_type="does_not_exist", params={}),
        )


# ---------------------------------------------------------------------------
# ExperimentWorkflow end-to-end with noop spec
# ---------------------------------------------------------------------------

async def test_experiment_workflow_noop_result():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[ExperimentWorkflow],
            activities=[
                run_algorithm_activity,
                run_experiment_variant_activity,
                generate_experiment_runs_activity,
            ],
        ):
            result: ExperimentResult = await env.client.execute_workflow(
                ExperimentWorkflow.run,
                ExperimentInput(experiment_type="noop", params={"count": 3}),
                id="test-exp-noop-1",
                task_queue="test-queue",
            )

    assert isinstance(result, ExperimentResult)
    assert result.data["total_runs"] == 3


async def test_experiment_workflow_progress_query():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[ExperimentWorkflow],
            activities=[
                run_algorithm_activity,
                run_experiment_variant_activity,
                generate_experiment_runs_activity,
            ],
        ):
            handle = await env.client.start_workflow(
                ExperimentWorkflow.run,
                ExperimentInput(experiment_type="noop", params={"count": 4}),
                id="test-exp-noop-2",
                task_queue="test-queue",
            )
            await handle.result()
            prog = await handle.query(ExperimentWorkflow.progress)

    assert prog["completed"] == 4
    assert prog["total"] == 4


async def test_experiment_workflow_concurrency_one():
    """With concurrency=1 (default), all runs execute sequentially."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[ExperimentWorkflow],
            activities=[
                run_algorithm_activity,
                run_experiment_variant_activity,
                generate_experiment_runs_activity,
            ],
        ):
            result: ExperimentResult = await env.client.execute_workflow(
                ExperimentWorkflow.run,
                ExperimentInput(
                    experiment_type="noop",
                    params={"count": 3},
                    concurrency=1,
                ),
                id="test-exp-noop-3",
                task_queue="test-queue",
            )

    assert result.data["total_runs"] == 3
