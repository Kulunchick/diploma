"""
Step-6 verification: structural correctness of all 4 experiment specs.

For each spec:
  1. generate_experiment_runs_activity → check run count and variant keys
  2. Full ExperimentWorkflow end-to-end → check output shape matches legacy format:
       {variant_key: {ant: {avg_value, avg_time}, prob: {...}, relative_difference}}

Random seeds are NOT controlled — values differ from legacy; only structure is verified.
Experiment4 uses m==n to avoid the preserved omega-shape bug (n, m) vs (m, n).
"""
import json

import pytest
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

import worker.activities as activities
from worker.activities import generate_experiment_runs_activity, run_algorithm_activity
from worker.types import ExperimentInput, ExperimentResult, GenerateRunsInput
from worker.workflows.experiment import ExperimentWorkflow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RANGES = {"min": 1.0, "max": 10.0}
_OMEGA = {"min": 0.0, "max": 0.5}


async def _stored_runs() -> list[dict]:
    """generate_experiment_runs_activity stores the full run list in Redis and
    returns only the count, so read the stored list back to inspect variant keys."""
    keys = await activities._redis.keys("experiment_runs:*")
    assert keys, "no run list was stored in Redis"
    raw = await activities._redis.get(keys[0])
    return json.loads(raw)


def _check_variant_structure(data: dict, variant_keys: list[str]) -> None:
    """Assert each variant key has the correct shape."""
    assert set(data.keys()) == set(variant_keys), (
        f"Expected keys {variant_keys}, got {list(data.keys())}"
    )
    for key in variant_keys:
        v = data[key]
        assert "ant" in v and "prob" in v and "relative_difference" in v, v
        for algo in ("ant", "prob"):
            assert "avg_value" in v[algo], v[algo]
            assert "avg_time" in v[algo], v[algo]
            assert isinstance(v[algo]["avg_value"], float), type(v[algo]["avg_value"])
            assert isinstance(v[algo]["avg_time"], float), type(v[algo]["avg_time"])
        assert isinstance(v["relative_difference"], float)


async def _run_experiment(params: dict, exp_type: str) -> ExperimentResult:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[ExperimentWorkflow],
            activities=[run_algorithm_activity, generate_experiment_runs_activity],
        ):
            return await env.client.execute_workflow(
                ExperimentWorkflow.run,
                ExperimentInput(experiment_type=exp_type, params=params),
                id=f"test-{exp_type}-{id(params)}",
                task_queue="test-queue",
            )


# ---------------------------------------------------------------------------
# Experiment 1 — vary kmax
# ---------------------------------------------------------------------------

async def test_experiment1_generate_runs_count():
    env = ActivityEnvironment()
    count = await env.run(
        generate_experiment_runs_activity,
        GenerateRunsInput(experiment_type="experiment1", params={
            "count": 2, "m": 3, "n": 4,
            "kmaxVariants": [{"kmax": 50}, {"kmax": 100}],
            "l": 5, "p": 0.1, "tau": 1.0, "alpha": 1.0, "beta": 2.0,
            "cRange": _RANGES, "bRange": _RANGES, "omegaRange": _OMEGA,
        }),
    )
    # 2 count × 2 kmax × 2 algos = 8
    assert count == 8
    runs = await _stored_runs()
    assert all(r["variant_key"] in ("50", "100") for r in runs)
    from collections import Counter
    per_key = Counter(r["variant_key"] for r in runs)
    assert per_key["50"] == 4
    assert per_key["100"] == 4


async def test_experiment1_workflow_structure():
    result = await _run_experiment({
        "count": 1, "m": 3, "n": 3,
        "kmaxVariants": [{"kmax": 20}],
        "l": 3, "p": 0.1, "tau": 1.0, "alpha": 1.0, "beta": 2.0,
        "cRange": _RANGES, "bRange": _RANGES, "omegaRange": _OMEGA,
    }, "experiment1")
    _check_variant_structure(result.data, ["20"])


# ---------------------------------------------------------------------------
# Experiment 2 — vary beta
# ---------------------------------------------------------------------------

async def test_experiment2_generate_runs_count():
    env = ActivityEnvironment()
    count = await env.run(
        generate_experiment_runs_activity,
        GenerateRunsInput(experiment_type="experiment2", params={
            "count": 2, "m": 3, "n": 3,
            "betaVariants": [{"beta": 1.0}, {"beta": 2.0}],
            "p": 0.1, "tau": 1.0, "alpha": 1.0, "antKmax": 20, "l": 3,
            "cRange": _RANGES, "bRange": _RANGES, "omegaRange": _OMEGA,
        }),
    )
    assert count == 8  # 2 × 2 × 2
    runs = await _stored_runs()
    assert all(r["variant_key"] in ("1.0", "2.0") for r in runs)


async def test_experiment2_workflow_structure():
    result = await _run_experiment({
        "count": 1, "m": 3, "n": 3,
        "betaVariants": [{"beta": 1.5}],
        "p": 0.1, "tau": 1.0, "alpha": 1.0, "antKmax": 20, "l": 3,
        "cRange": _RANGES, "bRange": _RANGES, "omegaRange": _OMEGA,
    }, "experiment2")
    _check_variant_structure(result.data, ["1.5"])


# ---------------------------------------------------------------------------
# Experiment 3 — vary m×n
# ---------------------------------------------------------------------------

async def test_experiment3_generate_runs_count():
    env = ActivityEnvironment()
    count = await env.run(
        generate_experiment_runs_activity,
        GenerateRunsInput(experiment_type="experiment3", params={
            "count": 2,
            "mnVariants": [{"m": 2, "n": 3}, {"m": 3, "n": 3}],
            "p": 0.1, "tau": 1.0, "antKmax": 20, "probKmax": 20, "l": 3,
            "cRange": _RANGES, "bRange": _RANGES, "omegaRange": _OMEGA,
        }),
    )
    assert count == 8  # 2 × 2 × 2
    runs = await _stored_runs()
    assert all(r["variant_key"] in ("2x3", "3x3") for r in runs)


async def test_experiment3_workflow_structure():
    result = await _run_experiment({
        "count": 1,
        "mnVariants": [{"m": 2, "n": 2}],
        "p": 0.1, "tau": 1.0, "antKmax": 20, "probKmax": 20, "l": 3,
        "cRange": _RANGES, "bRange": _RANGES, "omegaRange": _OMEGA,
    }, "experiment3")
    _check_variant_structure(result.data, ["2x2"])


# ---------------------------------------------------------------------------
# Experiment 4 — vary omega range (use m==n to avoid shape bug)
# ---------------------------------------------------------------------------

async def test_experiment4_generate_runs_count():
    env = ActivityEnvironment()
    count = await env.run(
        generate_experiment_runs_activity,
        GenerateRunsInput(experiment_type="experiment4", params={
            "count": 2, "m": 3, "n": 3,
            "omegaRangeVariants": [{"min": 0.0, "max": 0.3}, {"min": 0.5, "max": 0.9}],
            "p": 0.1, "tau": 1.0, "alpha": 1.0, "beta": 2.0,
            "antKmax": 20, "probKmax": 20, "l": 3,
            "cRange": _RANGES, "bRange": _RANGES,
        }),
    )
    assert count == 8  # 2 × 2 × 2
    runs = await _stored_runs()
    assert all(r["variant_key"] in ("0.0-0.3", "0.5-0.9") for r in runs)


async def test_experiment4_workflow_structure():
    # m==n=3 avoids the omega (n,m) shape bug in legacy code
    result = await _run_experiment({
        "count": 1, "m": 3, "n": 3,
        "omegaRangeVariants": [{"min": 0.0, "max": 0.5}],
        "p": 0.1, "tau": 1.0, "alpha": 1.0, "beta": 2.0,
        "antKmax": 20, "probKmax": 20, "l": 3,
        "cRange": _RANGES, "bRange": _RANGES,
    }, "experiment4")
    _check_variant_structure(result.data, ["0.0-0.5"])
