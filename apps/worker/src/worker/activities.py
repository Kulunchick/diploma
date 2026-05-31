import asyncio
import json
import logging
import time
from typing import Optional

import numpy as np
from assignment_solver import (
    AntColonyAssignmentSolver,
    CombinedSolver,
    CombinedTask as RustCombinedTask,
    ProbabilisticAssignmentSolver,
    Task as RustTask,
)
from redis.asyncio import Redis
from sqlalchemy import text
from temporalio import activity

from worker.db import AsyncSessionLocal
from worker.types import (
    AntColonyParams,
    CombinedResult,
    CombinedSolveInput,
    PersistCombinedInput,
    PersistFormationInput,
    ProbabilisticParams,
    RunAlgorithmInput,
    RunResult,
)

_redis: Optional[Redis] = None


def set_redis_client(client: Redis) -> None:
    global _redis
    _redis = client


@activity.defn
async def run_algorithm_activity(input: RunAlgorithmInput) -> RunResult:
    return await _run_algorithm_core(input)


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
async def run_combined_method_activity(input: CombinedSolveInput) -> CombinedResult:
    """Runs the combined method (article §4–5) on the aggregated unit×provider
    matrices. Mirrors _run_algorithm_core's off-loop executor + heartbeat +
    Redis iteration-stream wiring; the solver emits current_best_value =
    F_IT + F_prov per accepted move."""
    loop = asyncio.get_running_loop()

    rust_task = RustCombinedTask(
        input.m,
        input.n,
        np.array(input.c, dtype=np.int64),
        np.array(input.b_ij, dtype=np.int64),
        np.array(input.p_ij, dtype=np.int64),
        np.array(input.omega_max, dtype=np.float64),
        np.array(input.s_ij, dtype=np.float64),
        int(input.b_total),
    )

    solver = CombinedSolver(
        kmax_subproblem=input.params.kmax_subproblem,
        discount_step=input.params.discount_step,
        local_search_restarts=input.params.local_search_restarts,
    )

    if input.redis_channel:
        redis = _redis
        channel = input.redis_channel

        def iteration_callback(data: dict) -> None:
            asyncio.run_coroutine_threadsafe(_async_heartbeat(data), loop)
            if redis:
                asyncio.run_coroutine_threadsafe(
                    redis.xadd(
                        channel,
                        {"data": json.dumps({"type": "iteration", "algorithm": "combined", **data})},
                        maxlen=5000,
                        approximate=True,
                    ),
                    loop,
                )

        solver.set_iteration_callback(iteration_callback)

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
            result = executor_task.result()
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

    # CombinedSolver.solve returns a dict of numpy arrays + floats + str.
    return CombinedResult(
        v_final=result["v_final"].tolist(),
        r_final=result["r_final"].tolist(),
        f_it=float(result["f_it"]),
        f_prov=float(result["f_prov"]),
        source=str(result["source"]),
    )


def _maybe_json(value):
    """JSONB columns come back as str from asyncpg over a raw text() query."""
    return json.loads(value) if isinstance(value, str) else value


async def _read_iteration_history(channel: Optional[str]) -> list[tuple[int, float]]:
    """Read the full per-iteration convergence history from the Redis stream.
    Last write per iteration wins. Returns [] if Redis is unavailable or empty."""
    if not channel or _redis is None:
        return []
    entries = await _redis.xrange(channel, min="-", max="+")
    by_iter: dict[int, float] = {}
    for _entry_id, fields in entries:
        try:
            data = json.loads(fields["data"])
        except (KeyError, ValueError):
            continue
        if data.get("type") != "iteration":
            continue
        by_iter[int(data["iteration"])] = float(data["current_best_value"])
    return sorted(by_iter.items())


@activity.defn
async def persist_formation_result_activity(input: PersistFormationInput) -> None:
    """Write a finished formation back to Postgres, expanding the unit-level
    solution into per-service assignment rows.

    The solution matrix has shape (num_units, num_providers). For every selected
    (unit, provider) it writes one row per service in that unit, using the
    service's individual price/discount from the frozen snapshot
    (effective_revenue = price·(1 − discount)). Because group aggregation used a
    price-weighted omega, Σ effective_revenue equals the solver's value — a
    divergence > 1e-6 is logged (not fatal). Idempotent: clears prior rows first.
    """
    async with AsyncSessionLocal() as session:
        snap = (
            await session.execute(
                text(
                    "SELECT input_payload, service_order, provider_order "
                    "FROM formation_snapshots WHERE scenario_id = CAST(:sid AS uuid)"
                ),
                {"sid": input.scenario_id},
            )
        ).one_or_none()
        if snap is None:
            raise RuntimeError(f"Snapshot not found for scenario {input.scenario_id}")

        payload = _maybe_json(snap[0])
        unit_order = _maybe_json(snap[1])
        provider_order = _maybe_json(snap[2])
        service_cells = payload["service_cells"]

        await session.execute(
            text("DELETE FROM formation_assignments WHERE scenario_id = CAST(:sid AS uuid)"),
            {"sid": input.scenario_id},
        )

        total_eff = 0.0
        for u_index, unit in enumerate(unit_order):
            for j, v in enumerate(input.solution[u_index]):
                if v != 1:
                    continue
                for service_id in unit["service_ids"]:
                    sc = service_cells[service_id]
                    price = float(sc["price"][j])
                    discount = float(sc["discount"][j])
                    effective_revenue = (1.0 - discount) * price
                    total_eff += effective_revenue
                    await session.execute(
                        text(
                            "INSERT INTO formation_assignments "
                            "(scenario_id, service_id, provider_id, price, discount, effective_revenue) "
                            "VALUES (CAST(:sid AS uuid), CAST(:svc AS uuid), CAST(:prov AS uuid), "
                            ":price, :discount, :eff)"
                        ),
                        {
                            "sid": input.scenario_id,
                            "svc": service_id,
                            "prov": provider_order[j],
                            "price": price,
                            "discount": discount,
                            "eff": effective_revenue,
                        },
                    )

        if abs(total_eff - input.value) > 1e-6:
            logging.getLogger(__name__).warning(
                "Formation %s: Σ effective_revenue (%.6f) diverges from solver value (%.6f)",
                input.scenario_id, total_eff, input.value,
            )

        # Drain the convergence history (best-effort: Redis problems must not
        # block marking the scenario completed). Idempotent via ON CONFLICT.
        try:
            history = await _read_iteration_history(input.redis_channel)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            history = []
            logging.getLogger(__name__).warning(
                "Formation %s: failed to read iteration history: %s", input.scenario_id, exc
            )
        for iteration, best_value in history:
            await session.execute(
                text(
                    "INSERT INTO formation_iterations (scenario_id, iteration, best_value) "
                    "VALUES (CAST(:sid AS uuid), :it, :bv) "
                    "ON CONFLICT (scenario_id, iteration) DO NOTHING"
                ),
                {"sid": input.scenario_id, "it": iteration, "bv": best_value},
            )

        await session.execute(
            text(
                "UPDATE formation_scenarios "
                "SET status = 'completed', value = :val, finished_at = now() "
                "WHERE id = CAST(:sid AS uuid)"
            ),
            {"val": input.value, "sid": input.scenario_id},
        )
        await session.commit()

        # Free the Redis stream now that history is durable in Postgres.
        if input.redis_channel and _redis is not None:
            try:
                await _redis.delete(input.redis_channel)
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).warning(
                    "Formation %s: failed to delete Redis stream: %s", input.scenario_id, exc
                )


@activity.defn
async def persist_combined_result_activity(input: PersistCombinedInput) -> None:
    """Write a finished combined-method formation back to Postgres.

    Expands the unit-level v_final into per-service rows, using
    r_final[unit][provider] as the negotiated discount for every service in that
    unit (effective_revenue = price · (1 − final_discount)). Persists
    value = F_IT, provider_value = F_prov, combined_source. Σ effective_revenue
    should match F_IT (price-weighted aggregation) — divergence > 1e-6 logged.
    Idempotent: clears prior assignments first.
    """
    async with AsyncSessionLocal() as session:
        snap = (
            await session.execute(
                text(
                    "SELECT input_payload, service_order, provider_order "
                    "FROM formation_snapshots WHERE scenario_id = CAST(:sid AS uuid)"
                ),
                {"sid": input.scenario_id},
            )
        ).one_or_none()
        if snap is None:
            raise RuntimeError(f"Snapshot not found for scenario {input.scenario_id}")

        payload = _maybe_json(snap[0])
        unit_order = _maybe_json(snap[1])
        provider_order = _maybe_json(snap[2])
        service_cells = payload["service_cells"]

        await session.execute(
            text("DELETE FROM formation_assignments WHERE scenario_id = CAST(:sid AS uuid)"),
            {"sid": input.scenario_id},
        )

        total_eff = 0.0
        for u_index, unit in enumerate(unit_order):
            for j, v in enumerate(input.v_final[u_index]):
                if v != 1:
                    continue
                # The negotiated discount applies to the whole unit (group).
                final_discount = float(input.r_final[u_index][j])
                for service_id in unit["service_ids"]:
                    sc = service_cells[service_id]
                    price = float(sc["price"][j])
                    planning_discount = float(sc["discount"][j])
                    effective_revenue = (1.0 - final_discount) * price
                    total_eff += effective_revenue
                    await session.execute(
                        text(
                            "INSERT INTO formation_assignments "
                            "(scenario_id, service_id, provider_id, price, discount, "
                            "effective_revenue, final_discount) "
                            "VALUES (CAST(:sid AS uuid), CAST(:svc AS uuid), CAST(:prov AS uuid), "
                            ":price, :discount, :eff, :final)"
                        ),
                        {
                            "sid": input.scenario_id,
                            "svc": service_id,
                            "prov": provider_order[j],
                            "price": price,
                            # discount keeps the planning r_max for reference;
                            # final_discount is what the heuristic settled on.
                            "discount": planning_discount,
                            "eff": effective_revenue,
                            "final": final_discount,
                        },
                    )

        if abs(total_eff - input.f_it) > 1e-6:
            logging.getLogger(__name__).warning(
                "Combined %s: Σ effective_revenue (%.6f) diverges from F_IT (%.6f)",
                input.scenario_id, total_eff, input.f_it,
            )

        # Drain the convergence history (best-effort), same as the single path.
        try:
            history = await _read_iteration_history(input.redis_channel)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            history = []
            logging.getLogger(__name__).warning(
                "Combined %s: failed to read iteration history: %s", input.scenario_id, exc
            )
        for iteration, best_value in history:
            await session.execute(
                text(
                    "INSERT INTO formation_iterations (scenario_id, iteration, best_value) "
                    "VALUES (CAST(:sid AS uuid), :it, :bv) "
                    "ON CONFLICT (scenario_id, iteration) DO NOTHING"
                ),
                {"sid": input.scenario_id, "it": iteration, "bv": best_value},
            )

        await session.execute(
            text(
                "UPDATE formation_scenarios "
                "SET status = 'completed', value = :val, provider_value = :pval, "
                "combined_source = :src, finished_at = now() "
                "WHERE id = CAST(:sid AS uuid)"
            ),
            {
                "val": input.f_it,
                "pval": input.f_prov,
                "src": input.source,
                "sid": input.scenario_id,
            },
        )
        await session.commit()

        if input.redis_channel and _redis is not None:
            try:
                await _redis.delete(input.redis_channel)
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).warning(
                    "Combined %s: failed to delete Redis stream: %s", input.scenario_id, exc
                )


async def _async_heartbeat(data: dict) -> None:
    activity.heartbeat(data)


async def _periodic_heartbeat() -> None:
    while True:
        await asyncio.sleep(10)
        activity.heartbeat({"status": "running"})
