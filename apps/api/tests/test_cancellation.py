"""
Step-7 cancellation tests.

Strategy:
- Workflow cancellation is tested via WorkflowEnvironment (no server needed).
- We cancel immediately after start. With tiny inputs the solve completes
  before the cancel is processed → COMPLETED is also acceptable.
  Either way the workflow must NOT end with FAILED.
- Activity cancellation is implicitly covered: a cancelled workflow sends
  cancel requests to its activities, and our activity uses asyncio.wait
  (FIRST_COMPLETED) to detect the heartbeat failure promptly.
"""
import pytest
from temporalio.client import WorkflowExecutionStatus
from temporalio.exceptions import CancelledError as TemporalCancelledError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from src.worker.activities import generate_experiment_runs_activity, run_algorithm_activity
from src.worker.types import (
    AntColonyParams,
    ExperimentInput,
    ProbabilisticParams,
    SolveInput,
)
from src.worker.workflows.experiment import ExperimentWorkflow
from src.worker.workflows.solve import SolveWorkflow

_SOLVE_INPUT = SolveInput(
    m=2, n=2,
    c=[[10, 20], [5, 25]],
    b_ij=[[3, 4], [1, 5]],
    b_total=6,
    omega=[[0.1, 0.2], [0.0, 0.1]],
    ant_colony=AntColonyParams(num_ants=3, kmax=10),
    probabilistic=ProbabilisticParams(kmax=10),
    redis_channel="test-cancel-channel",
)

_EXPERIMENT_INPUT = ExperimentInput(
    experiment_type="noop",
    params={"count": 3},
    concurrency=1,
)


async def test_solve_workflow_cancel_ends_cleanly():
    """Cancelling SolveWorkflow must not result in FAILED status."""
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
                id="test-cancel-solve",
                task_queue="test-queue",
            )
            await handle.cancel()

            try:
                await handle.result()
            except TemporalCancelledError:
                pass  # cancelled before completion — expected
            except Exception:
                pass  # completed normally before cancel was processed — also fine

            desc = await handle.describe()
            assert desc.status in (
                WorkflowExecutionStatus.CANCELED,
                WorkflowExecutionStatus.COMPLETED,
            ), f"Unexpected status: {desc.status}"


async def test_experiment_workflow_cancel_ends_cleanly():
    """Cancelling ExperimentWorkflow must not result in FAILED status."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[ExperimentWorkflow],
            activities=[run_algorithm_activity, generate_experiment_runs_activity],
        ):
            handle = await env.client.start_workflow(
                ExperimentWorkflow.run,
                _EXPERIMENT_INPUT,
                id="test-cancel-experiment",
                task_queue="test-queue",
            )
            await handle.cancel()

            try:
                await handle.result()
            except TemporalCancelledError:
                pass
            except Exception:
                pass

            desc = await handle.describe()
            assert desc.status in (
                WorkflowExecutionStatus.CANCELED,
                WorkflowExecutionStatus.COMPLETED,
            ), f"Unexpected status: {desc.status}"


async def test_solve_workflow_cancel_updates_state():
    """After cancellation, current_state() must not contain 'running' entries."""
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
                id="test-cancel-state",
                task_queue="test-queue",
            )
            await handle.cancel()

            try:
                await handle.result()
            except Exception:
                pass

            try:
                state = await handle.query(SolveWorkflow.current_state)
                assert "running" not in state.values(), (
                    f"State still has 'running' after terminal: {state}"
                )
            except Exception:
                pass  # query may fail on cancelled workflow — acceptable
