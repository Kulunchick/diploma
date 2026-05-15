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

from src.worker.types import (
    AntColonyParams,
    GenerateRunsInput,
    ProbabilisticParams,
    RunAlgorithmInput,
    RunResult,
)

# Module-level Redis client, set once at worker startup via set_redis_client().
_redis: Optional[Redis] = None


def set_redis_client(client: Redis) -> None:
    global _redis
    _redis = client


@activity.defn
async def run_algorithm_activity(input: RunAlgorithmInput) -> RunResult:
    """
    Atomic unit: one run of one algorithm on one task.

    - Runs the Rust solver in a thread-pool executor (blocking call).
    - Heartbeats Temporal every 10 s via a background task for liveness.
    - If input.redis_channel is set, also heartbeats and publishes per-iteration
      events to Redis (used by /solve for real-time streaming).
    - The Rust callback fires from a foreign thread → asyncio.run_coroutine_threadsafe.
    """
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
            # Heartbeat Temporal for liveness on each iteration.
            asyncio.run_coroutine_threadsafe(_async_heartbeat(data), loop)
            # Publish iteration event to Redis for WS clients.
            if redis:
                asyncio.run_coroutine_threadsafe(
                    redis.publish(
                        channel,
                        json.dumps({"type": "iteration", "algorithm": algo, **data}),
                    ),
                    loop,
                )

        solver.set_iteration_callback(iteration_callback)

    # Background heartbeat for experiments (no iteration callback) and as a
    # fallback for /solve between iterations.
    heartbeat_task = asyncio.create_task(_periodic_heartbeat())
    try:
        start = time.perf_counter()
        solution, value = await loop.run_in_executor(None, solver.solve, rust_task)
        elapsed = time.perf_counter() - start
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
async def generate_experiment_runs_activity(
    input: GenerateRunsInput,
) -> list[RunAlgorithmInput]:
    """
    Generates the full list of RunAlgorithmInput for an experiment.
    Runs as an activity (not in workflow) because TaskGenerator uses random.
    Looks up the spec in EXPERIMENT_REGISTRY and delegates to spec.generate_runs().
    """
    from src.experiments.registry import EXPERIMENT_REGISTRY

    spec = EXPERIMENT_REGISTRY.get(input.experiment_type)
    if spec is None:
        raise ValueError(f"Unknown experiment type: {input.experiment_type!r}")

    validated_input = spec.input_model.model_validate(input.params)
    return spec.generate_runs(validated_input)


async def _async_heartbeat(data: dict) -> None:
    """Wraps synchronous activity.heartbeat() as a coroutine for run_coroutine_threadsafe."""
    activity.heartbeat(data)


async def _periodic_heartbeat() -> None:
    """Sends a Temporal heartbeat every 10 s during long solver runs."""
    while True:
        await asyncio.sleep(10)
        activity.heartbeat({"status": "running"})
