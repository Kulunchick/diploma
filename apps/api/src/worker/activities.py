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

    Cancellation:
    - Uses asyncio.wait(FIRST_COMPLETED) to race the executor against the heartbeat
      monitor so that a Temporal cancellation request is detected promptly.
    - When cancellation is detected, the executor future is cancelled.  The Rust
      thread continues to completion in the background (no cancel token yet —
      TODO: propagate via Rust binding when available).
    - Iteration callbacks (redis_channel) fire from a foreign Rust thread →
      asyncio.run_coroutine_threadsafe for both heartbeat and redis.publish.
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
            asyncio.run_coroutine_threadsafe(_async_heartbeat(data), loop)
            if redis:
                asyncio.run_coroutine_threadsafe(
                    redis.publish(
                        channel,
                        json.dumps({"type": "iteration", "algorithm": algo, **data}),
                    ),
                    loop,
                )

        solver.set_iteration_callback(iteration_callback)

    start = time.perf_counter()
    executor_task = asyncio.ensure_future(
        loop.run_in_executor(None, solver.solve, rust_task)
    )
    # Background monitor: heartbeats every 10 s; raises if activity is cancelled.
    heartbeat_task = asyncio.create_task(_periodic_heartbeat())

    try:
        # Race solver vs heartbeat monitor.  FIRST_COMPLETED returns as soon as
        # either finishes — normal solve completion or cancellation signal.
        done, _ = await asyncio.wait(
            {executor_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if executor_task in done:
            # Normal path: solve finished before any cancellation.
            solution, value = executor_task.result()
            elapsed = time.perf_counter() - start
        else:
            # Heartbeat task finished first → cancellation or unexpected error.
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
    """
    Heartbeats Temporal every 10 s for liveness.
    activity.heartbeat() raises temporalio.exceptions.CancelledError when the
    activity has been cancelled — this causes the task to finish with an exception,
    which asyncio.wait(FIRST_COMPLETED) detects promptly.
    """
    while True:
        await asyncio.sleep(10)
        activity.heartbeat({"status": "running"})
