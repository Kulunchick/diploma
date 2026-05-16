import asyncio
import json
import time
from typing import Optional

import numpy as np
from assignment_solver import (
    AntColonyAssignmentSolver,
    ProbabilisticAssignmentSolver,
    Task as RustTask,
)
from redis.asyncio import Redis
from temporalio import activity

from worker.types import (
    AntColonyParams,
    ExperimentVariantInput,
    GenerateRunsInput,
    ProbabilisticParams,
    RunAlgorithmInput,
    RunResult,
)


def _experiment_runs_key(workflow_id: str) -> str:
    return f"experiment_runs:{workflow_id}"

_redis: Optional[Redis] = None


def set_redis_client(client: Redis) -> None:
    global _redis
    _redis = client


@activity.defn
async def run_algorithm_activity(input: RunAlgorithmInput) -> RunResult:
    return await _run_algorithm_core(input)


@activity.defn
async def run_experiment_variant_activity(input: ExperimentVariantInput) -> RunResult:
    """
    Fetches the variant for this index from Redis (written by
    generate_experiment_runs_activity) and runs it. Keeps the activity
    input small so the Temporal payload limit is never approached even
    for experiments with hundreds of variants.
    """
    if _redis is None:
        raise RuntimeError("Redis client is not initialized")
    key = _experiment_runs_key(activity.info().workflow_id)
    raw = await _redis.get(key)
    if raw is None:
        raise RuntimeError(f"Experiment runs not found in Redis: {key}")
    runs_data = json.loads(raw)
    run_input = RunAlgorithmInput.model_validate(runs_data[input.index])
    return await _run_algorithm_core(run_input)


async def _run_algorithm_core(input: RunAlgorithmInput) -> RunResult:
    loop = asyncio.get_running_loop()

    rust_task = RustTask(
        input.m,
        input.n,
        np.array(input.c, dtype=np.int64),
        np.array(input.b_ij, dtype=np.int64),
        int(input.b_total),
        np.array(input.omega, dtype=np.float64),
    )

    if input.algorithm == "ant_colony":
        params = input.ant_colony_params or AntColonyParams()
        solver = AntColonyAssignmentSolver(
            num_ants=params.num_ants,
            kmax=params.kmax,
            alpha=params.alpha,
            beta=params.beta,
            rho=params.rho,
            initial_pheromone=params.initial_pheromone,
        )
    elif input.algorithm == "probabilistic":
        params = input.probabilistic_params or ProbabilisticParams()
        solver = ProbabilisticAssignmentSolver(kmax=params.kmax)
    else:
        raise ValueError(f"Unknown algorithm: {input.algorithm!r}")

    if input.redis_channel:
        redis = _redis
        channel = input.redis_channel
        algo = input.algorithm

        def iteration_callback(data: dict) -> None:
            asyncio.run_coroutine_threadsafe(_async_heartbeat(data), loop)
            if redis:
                # XADD instead of PUBLISH so late WS subscribers can replay
                # iterations from the start. maxlen caps memory growth.
                asyncio.run_coroutine_threadsafe(
                    redis.xadd(
                        channel,
                        {"data": json.dumps({"type": "iteration", "algorithm": algo, **data})},
                        maxlen=5000,
                        approximate=True,
                    ),
                    loop,
                )

        solver.set_iteration_callback(iteration_callback)

    start = time.perf_counter()
    executor_task = asyncio.ensure_future(
        loop.run_in_executor(None, solver.solve, rust_task)
    )
    heartbeat_task = asyncio.create_task(_periodic_heartbeat())

    try:
        done, _ = await asyncio.wait(
            {executor_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if executor_task in done:
            solution, value = executor_task.result()
            elapsed = time.perf_counter() - start
        else:
            exc = (
                heartbeat_task.exception()
                if not heartbeat_task.cancelled()
                else asyncio.CancelledError()
            )
            executor_task.cancel()
            await asyncio.gather(executor_task, return_exceptions=True)
            raise exc  # type: ignore[misc]

    except asyncio.CancelledError:
        executor_task.cancel()
        await asyncio.gather(executor_task, return_exceptions=True)
        raise
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)

    return RunResult(
        variant_key=input.variant_key,
        algorithm=input.algorithm,
        value=float(value),
        time_seconds=elapsed,
        solution=solution.tolist(),
    )


@activity.defn
async def generate_experiment_runs_activity(input: GenerateRunsInput) -> int:
    """
    Generates the variant list, stores it in Redis as a single JSON blob
    keyed by workflow_id, and returns the count. Keeps the Temporal
    workflow history payload tiny no matter how many variants there are.
    """
    from experiments.registry import EXPERIMENT_REGISTRY

    spec = EXPERIMENT_REGISTRY.get(input.experiment_type)
    if spec is None:
        raise ValueError(f"Unknown experiment type: {input.experiment_type!r}")

    validated_input = spec.input_model.model_validate(input.params)
    runs = spec.generate_runs(validated_input)

    if _redis is None:
        raise RuntimeError("Redis client is not initialized")
    key = _experiment_runs_key(activity.info().workflow_id)
    # 24h TTL — enough for any running experiment to finish and replay.
    await _redis.set(key, json.dumps([r.model_dump() for r in runs]), ex=86400)

    return len(runs)


async def _async_heartbeat(data: dict) -> None:
    activity.heartbeat(data)


async def _periodic_heartbeat() -> None:
    while True:
        await asyncio.sleep(10)
        activity.heartbeat({"status": "running"})
