"""
Tests for ExperimentWorkflow + generate_experiment_runs_activity using the noop spec.
No Temporal server required.
"""
import pytest
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from src.worker.activities import (
    generate_experiment_runs_activity,
    run_algorithm_activity,
)
from src.worker.types import (
    ExperimentInput,
    ExperimentResult,
    GenerateRunsInput,
    RunAlgorithmInput,
)
from src.worker.workflows.experiment import ExperimentWorkflow


# ---------------------------------------------------------------------------
# generate_experiment_runs_activity
# ---------------------------------------------------------------------------

async def test_generate_runs_noop_returns_correct_count():
    env = ActivityEnvironment()
    result: list[RunAlgorithmInput] = await env.run(
        generate_experiment_runs_activity,
        GenerateRunsInput(experiment_type="noop", params={"count": 5}),
    )
    assert len(result) == 5
    assert all(r.algorithm == "probabilistic" for r in result)
    assert [r.variant_key for r in result] == ["0", "1", "2", "3", "4"]


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
            activities=[run_algorithm_activity, generate_experiment_runs_activity],
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
            activities=[run_algorithm_activity, generate_experiment_runs_activity],
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
            activities=[run_algorithm_activity, generate_experiment_runs_activity],
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
