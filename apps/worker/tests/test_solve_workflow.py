"""
Tests for SolveWorkflow using temporalio WorkflowEnvironment (no server needed).
"""
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from worker.activities import run_algorithm_activity, generate_experiment_runs_activity
from worker.types import AntColonyParams, ProbabilisticParams, SolveInput, SolveResult
from worker.workflows.solve import SolveWorkflow

_SOLVE_INPUT = SolveInput(
    m=2,
    n=3,
    c=[[10, 20, 15], [5, 25, 30]],
    b_ij=[[3, 4, 2], [1, 5, 6]],
    b_total=10,
    omega=[[0.1, 0.2, 0.0], [0.0, 0.1, 0.3]],
    ant_colony=AntColonyParams(num_ants=5, kmax=20),
    probabilistic=ProbabilisticParams(kmax=20),
    redis_channel="test-channel",
)


@pytest.mark.asyncio
async def test_solve_workflow_returns_valid_result():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[SolveWorkflow],
            activities=[run_algorithm_activity, generate_experiment_runs_activity],
        ):
            result: SolveResult = await env.client.execute_workflow(
                SolveWorkflow.run,
                _SOLVE_INPUT,
                id="test-solve-1",
                task_queue="test-queue",
            )

    assert isinstance(result, SolveResult)
    assert result.ant_colony.value > 0
    assert result.probabilistic.value > 0
    assert len(result.ant_colony.solution) == 2
    assert len(result.probabilistic.solution) == 2


@pytest.mark.asyncio
async def test_solve_workflow_current_state_query():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[SolveWorkflow],
            activities=[run_algorithm_activity, generate_experiment_runs_activity],
        ):
            handle = await env.client.start_workflow(
                SolveWorkflow.run,
                _SOLVE_INPUT,
                id="test-solve-2",
                task_queue="test-queue",
            )
            result: SolveResult = await handle.result()
            state = await handle.query(SolveWorkflow.current_state)

    assert state["ant_colony"] == "done"
    assert state["probabilistic"] == "done"
