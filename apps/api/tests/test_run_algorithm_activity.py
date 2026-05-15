"""
Tests for run_algorithm_activity using ActivityEnvironment
(no Temporal server required).
"""
import asyncio
import pytest
from temporalio.testing import ActivityEnvironment

from worker.activities import run_algorithm_activity
from worker.types import AntColonyParams, ProbabilisticParams, RunAlgorithmInput, RunResult

# Minimal 2×3 task fixture
TASK_KWARGS = dict(
    m=2,
    n=3,
    c=[[10, 20, 15], [5, 25, 30]],
    b_ij=[[3, 4, 2], [1, 5, 6]],
    b_total=10,
    omega=[[0.1, 0.2, 0.0], [0.0, 0.1, 0.3]],
)


@pytest.mark.asyncio
async def test_ant_colony_returns_valid_result():
    env = ActivityEnvironment()
    inp = RunAlgorithmInput(
        **TASK_KWARGS,
        algorithm="ant_colony",
        ant_colony_params=AntColonyParams(num_ants=5, kmax=20),
        variant_key="test",
    )
    result: RunResult = await env.run(run_algorithm_activity, inp)

    assert isinstance(result, RunResult)
    assert result.algorithm == "ant_colony"
    assert result.variant_key == "test"
    assert result.value > 0
    assert result.time_seconds >= 0
    assert len(result.solution) == 2
    assert len(result.solution[0]) == 3


@pytest.mark.asyncio
async def test_probabilistic_returns_valid_result():
    env = ActivityEnvironment()
    inp = RunAlgorithmInput(
        **TASK_KWARGS,
        algorithm="probabilistic",
        probabilistic_params=ProbabilisticParams(kmax=50),
        variant_key="test",
    )
    result: RunResult = await env.run(run_algorithm_activity, inp)

    assert isinstance(result, RunResult)
    assert result.algorithm == "probabilistic"
    assert result.value > 0
    assert len(result.solution) == 2


@pytest.mark.asyncio
async def test_unknown_algorithm_raises():
    env = ActivityEnvironment()
    inp = RunAlgorithmInput(
        **TASK_KWARGS,
        algorithm="unknown",
        variant_key="test",
    )
    with pytest.raises(ValueError, match="Unknown algorithm"):
        await env.run(run_algorithm_activity, inp)


@pytest.mark.asyncio
async def test_iteration_callback_fires_without_redis():
    """Callback is set but redis_channel is given with no Redis client — should not crash."""
    env = ActivityEnvironment()
    inp = RunAlgorithmInput(
        **TASK_KWARGS,
        algorithm="ant_colony",
        ant_colony_params=AntColonyParams(num_ants=3, kmax=5),
        variant_key="test",
        redis_channel="test-channel",  # no Redis client set → publish is skipped
    )
    result: RunResult = await env.run(run_algorithm_activity, inp)
    assert result.value > 0
