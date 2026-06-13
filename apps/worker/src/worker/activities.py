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
)
from redis.asyncio import Redis
from sqlalchemy import text
from temporalio import activity

from worker.db import AsyncSessionLocal
from worker.metrics import compute_provider_metrics
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

    # All three algorithms now share CombinedTask so constraint (4) (relative
    # value s_ij) is enforced uniformly. probabilistic/ant-colony evaluate (4) at
    # the planning discount (omega). p_ij/s_ij default to zeros when absent →
    # s = 0 → every pair admissible (identical to the pre-(4) behaviour).
    m, n = input.m, input.n
    p_ij = (
        np.array(input.p_ij, dtype=np.float64)
        if input.p_ij is not None
        else np.zeros((m, n), dtype=np.float64)
    )
    s_ij = (
        np.array(input.s_ij, dtype=np.float64)
        if input.s_ij is not None
        else np.zeros((m, n), dtype=np.float64)
    )
    rust_task = RustCombinedTask(
        m,
        n,
        np.array(input.c, dtype=np.int64),
        np.array(input.b_ij, dtype=np.int64),
        p_ij,
        np.array(input.omega, dtype=np.float64),
        s_ij,
        int(input.b_total),
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

    # Convergence points buffered in-thread (callback only appends — Redis-free,
    # non-blocking, race-free). A background flusher streams them to Redis live.
    iteration_history: list[tuple[int, float]] = []

    if input.redis_channel:
        def iteration_callback(data: dict) -> None:
            asyncio.run_coroutine_threadsafe(_async_heartbeat(data), loop)
            iteration_history.append(
                (int(data["iteration"]), float(data["current_best_value"]))
            )

        solver.set_iteration_callback(iteration_callback)

    stop_flush = asyncio.Event()
    flusher_task: Optional[asyncio.Task] = (
        asyncio.create_task(
            _live_flush_loop(input.redis_channel, input.algorithm, iteration_history, stop_flush)
        )
        if input.redis_channel
        else None
    )

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
            # Solve done → stop the live flusher; it performs a final drain so the
            # stream holds the COMPLETE history before the persist activity reads.
            if flusher_task is not None:
                stop_flush.set()
                await flusher_task
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
        # Failure paths: tear down the flusher without a final drain (no curve
        # needed for a failed run). On success it is already awaited above.
        if flusher_task is not None and not flusher_task.done():
            flusher_task.cancel()
            await asyncio.gather(flusher_task, return_exceptions=True)

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
        np.array(input.p_ij, dtype=np.float64),
        np.array(input.omega_max, dtype=np.float64),
        np.array(input.s_ij, dtype=np.float64),
        int(input.b_total),
    )

    solver = CombinedSolver(
        kmax_subproblem=input.params.kmax_subproblem,
        discount_step=input.params.discount_step,
        local_search_restarts=input.params.local_search_restarts,
        subtask_solver=input.params.subtask_solver,
    )

    # See _run_algorithm_core: callback only appends; a background flusher streams
    # the buffer to Redis live, with a final drain after solve for completeness.
    iteration_history: list[tuple[int, float]] = []

    if input.redis_channel:
        def iteration_callback(data: dict) -> None:
            asyncio.run_coroutine_threadsafe(_async_heartbeat(data), loop)
            iteration_history.append(
                (int(data["iteration"]), float(data["current_best_value"]))
            )

        solver.set_iteration_callback(iteration_callback)

    stop_flush = asyncio.Event()
    flusher_task: Optional[asyncio.Task] = (
        asyncio.create_task(
            _live_flush_loop(input.redis_channel, "combined", iteration_history, stop_flush)
        )
        if input.redis_channel
        else None
    )

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
            if flusher_task is not None:
                stop_flush.set()
                await flusher_task
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
        if flusher_task is not None and not flusher_task.done():
            flusher_task.cancel()
            await asyncio.gather(flusher_task, return_exceptions=True)

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


async def _xadd_iteration_batch(
    channel: Optional[str], algorithm: str, points: list[tuple[int, float]]
) -> None:
    """Write a batch of convergence points to the Redis stream in ONE pipeline.

    The solver fires its callback from a worker thread; it only appends to a
    plain list (thread-safe under the GIL). Writes to Redis are funnelled through
    this single batched call so they never run concurrently on the shared
    connection — scheduling one fire-and-forget ``xadd`` per iteration drives many
    concurrent writes that mostly error out and are silently lost (observed: only
    ~100 of N landing, sometimes 0). maxlen is generous (50000 ≫ any realistic
    run, incl. combined-method restarts) so the cap never silently truncates."""
    if not channel or _redis is None or not points:
        return
    # Sub-batch each flush so a single pipeline never grows unbounded (a flush
    # that accumulated hundreds of thousands of points would otherwise time out
    # the connection). Each chunk is one awaited pipeline — still a single
    # serialised writer, so no concurrent-connection race.
    CHUNK = 5000
    for base in range(0, len(points), CHUNK):
        pipe = _redis.pipeline()
        for iteration, value in points[base:base + CHUNK]:
            pipe.xadd(
                channel,
                {"data": json.dumps(
                    {"type": "iteration", "algorithm": algorithm,
                     "iteration": iteration, "current_best_value": value}
                )},
                maxlen=50000,
                approximate=True,
            )
        await pipe.execute()


async def _live_flush_loop(
    channel: Optional[str],
    algorithm: str,
    history: list[tuple[int, float]],
    stop_event: asyncio.Event,
) -> None:
    """Single-writer flusher: drain newly-buffered convergence points to Redis in
    batched pipelines at a bounded cadence, so the chart fills progressively
    while the solver runs — then a final guaranteed drain once stopped.

    One writer task → writes are inherently serialised → no concurrent-connection
    race. The solver thread only appends to ``history`` (never touches Redis), so
    it is never throttled on Redis round-trips. A ``flushed`` index makes every
    point reach the stream exactly once; the flush cadence changes only WHEN
    points appear, never WHICH points or their order, so the final persisted
    curve is identical to a single batch flush."""
    if not channel or _redis is None:
        return
    flushed = 0
    while True:
        n = len(history)  # atomic read; appends happen on the solver thread
        if n > flushed:
            await _xadd_iteration_batch(channel, algorithm, history[flushed:n])
            flushed = n
        if stop_event.is_set():
            # Solve has finished before stop is set, so history is now final —
            # re-read to drain any tail appended since the snapshot above.
            n = len(history)
            if n > flushed:
                await _xadd_iteration_batch(channel, algorithm, history[flushed:n])
            return
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=0.3)
        except asyncio.TimeoutError:
            pass


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

        # Provider-side metrics for the non-optimised side. probabilistic and
        # ant-colony never move the discount, so use the planning discount frozen
        # in the snapshot (final_discount=None → per-service planning r).
        f_prov, provider_profit, total_value = compute_provider_metrics(
            service_cells, unit_order, input.solution, final_discount=None
        )
        if abs((input.value + provider_profit) - total_value) > 1e-6:
            logging.getLogger(__name__).warning(
                "Formation %s: identity F_IT+profit (%.6f) ≠ Σp·v (%.6f)",
                input.scenario_id, input.value + provider_profit, total_value,
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
                "SET status = 'completed', value = :val, provider_value = :pval, "
                "provider_profit = :pprofit, finished_at = now() "
                "WHERE id = CAST(:sid AS uuid)"
            ),
            {
                "val": input.value,
                "pval": f_prov,
                "pprofit": provider_profit,
                "sid": input.scenario_id,
            },
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

        # Provider metrics from the snapshot using the negotiated discount r_final
        # (the lever the combined method actually moved). f_prov recomputed here
        # should match the solver's F_prov; a divergence flags an aggregation bug.
        f_prov, provider_profit, total_value = compute_provider_metrics(
            service_cells, unit_order, input.v_final, final_discount=input.r_final
        )
        if abs(f_prov - input.f_prov) > 1e-6:
            logging.getLogger(__name__).warning(
                "Combined %s: recomputed F_prov (%.6f) diverges from solver F_prov (%.6f)",
                input.scenario_id, f_prov, input.f_prov,
            )
        if abs((input.f_it + provider_profit) - total_value) > 1e-6:
            logging.getLogger(__name__).warning(
                "Combined %s: identity F_IT+profit (%.6f) ≠ Σp·v (%.6f)",
                input.scenario_id, input.f_it + provider_profit, total_value,
            )

        # Drain the convergence history (best-effort), same as the single path.
        try:
            history = await _read_iteration_history(input.redis_channel)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            history = []
            logging.getLogger(__name__).warning(
                "Combined %s: failed to read iteration history: %s", input.scenario_id, exc
            )
        # The solver now emits a clean best-so-far series on a single contiguous
        # tick counter (running max over all passes/stages) — no stitching or
        # running-max needed here. The only residual concern is the flush race:
        # the iteration callback fires xadd fire-and-forget from the solver
        # thread, so the final tick(s) may not land before the solver returns and
        # we drain. Append a guaranteed terminal point equal to the canonical
        # F_IT + F_prov so the chart always ends exactly at the value shown on the
        # result cards. Because the series is already best-so-far, this only ever
        # tops up a missing tail — it never reorders or smooths.
        combined_benefit = input.f_it + input.f_prov
        if history:
            running = history[-1][1]
            if combined_benefit > running:
                history.append((history[-1][0] + 1, combined_benefit))
        else:
            history = [(1, combined_benefit)]

        # Warn-only regression guard: the chart's final point must equal the
        # combined benefit on the totals cards. Catches any re-introduction of the
        # stitching bug (where the series' max/final ≠ stored benefit).
        if abs(history[-1][1] - combined_benefit) > 1e-6:
            logging.getLogger(__name__).warning(
                "Combined %s: final iteration best_value (%.6f) ≠ combined benefit (%.6f)",
                input.scenario_id, history[-1][1], combined_benefit,
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
                "provider_profit = :pprofit, combined_source = :src, finished_at = now() "
                "WHERE id = CAST(:sid AS uuid)"
            ),
            {
                "val": input.f_it,
                "pval": f_prov,
                "pprofit": provider_profit,
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
