"""Package-formation scenarios: run, inspect, export and compare.

A formation runs from saved catalogue + planning data (not raw matrices). It
builds the same (m, n, c, b_ij, b_total, omega) payload the existing Temporal
flow consumes and runs it through SingleAlgorithmWorkflow (one algorithm +
write-back). Provider revenue p_ij and service groups are persisted elsewhere
but are NOT part of the solver input in this iteration.
"""
import asyncio
import csv
import io
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError

from src.operations.db.base import AsyncSessionLocal, get_session
from src.operations.db.models import (
    FormationAssignment,
    FormationIteration,
    FormationScenario,
    FormationSnapshot,
    PlanningCell,
    Provider,
    Service,
    ServiceGroup,
    User,
)
from src.operations.models.algorithm_parametrs import (
    AntColonyParameters,
    CombinedParameters,
    ProbabilisticParameters,
)
from src.operations.models.formation import (
    CompareProviderBreakdown,
    CompareRequest,
    CompareResponse,
    CompareScenario,
    FormationAssignmentRead,
    FormationCreate,
    FormationDetail,
    FormationIterationRead,
    FormationListItem,
    FormationTotals,
)
from src.operations.routers.deps import get_redis, get_temporal_client
from src.operations.security import decode_token, get_current_user
from src.operations.temporal_types import (
    COMBINED_FORMATION_WORKFLOW_NAME,
    SINGLE_ALGORITHM_WORKFLOW_NAME,
    TASK_QUEUE,
    AntColonyParams,
    CombinedParams,
    CombinedSolveInput,
    ProbabilisticParams,
    SingleSolveInput,
)

router = APIRouter(prefix="/formations", tags=["formations"])

_TERMINAL_FAILED = {
    WorkflowExecutionStatus.FAILED,
    WorkflowExecutionStatus.TIMED_OUT,
    WorkflowExecutionStatus.CANCELED,
    WorkflowExecutionStatus.TERMINATED,
}


# ---------------------------------------------------------------------------
# Payload building
# ---------------------------------------------------------------------------

def _build_payload(
    services: list[Service],
    providers: list[Provider],
    cells: list[PlanningCell],
    groups: list[ServiceGroup],
) -> dict:
    """Build the solver payload from saved entities, aggregating service groups
    into "logical units" so the group all-or-nothing rule is enforced without
    touching the Rust solver.

    A unit is either a whole service_group (services share one solver variable
    per provider → all-or-nothing) or a single ungrouped service. Units are
    ordered by their alphabetically-first service name, providers by name.

    Solver subtask A operates on integer prices/resources per the article §5.1;
    NUMERIC storage allows future precision but is truncated at the boundary
    (price → int, resource → int, b_total → int). Discounts and provider revenue
    p stay float (p is a monetary value, used as-is by the solver and metrics).

    Per (unit, provider):
        c_unit     = Σ price_i
        b_unit     = Σ resource_i
        omega_unit = Σ(discount_i·price_i) / c_unit   (price-weighted, 0 if c=0)
    so (1 − omega_unit)·c_unit == Σ(1 − discount_i)·price_i exactly, keeping the
    solver objective consistent with the per-service revenue we report.
    """
    by_pair = {(c.service_id, c.provider_id): c for c in cells}
    service_by_id = {s.id: s for s in services}

    # Per-service planning vectors aligned to provider order (truncated to int).
    service_cells: dict[str, dict] = {}
    for s in services:
        price, resource, discount, prov_rev, min_val = [], [], [], [], []
        for p in providers:
            cell = by_pair.get((s.id, p.id))
            price.append(int(cell.price) if cell else 0)
            resource.append(int(cell.resource) if cell else 0)
            discount.append(float(cell.discount) if cell else 0.0)
            prov_rev.append(float(cell.provider_revenue) if cell else 0.0)
            min_val.append(float(cell.min_value) if cell else 0.0)
        service_cells[str(s.id)] = {
            "name": s.name,
            "price": price,
            "resource": resource,
            "discount": discount,
            "provider_revenue": prov_rev,  # p_ij — combined method
            "min_value": min_val,  # s_ij — combined-method constraint (4)
        }

    # Partition services into units: one per group, one per ungrouped service.
    grouped: set[uuid.UUID] = set()
    units: list[dict] = []
    for g in groups:
        member_ids = [m.id for m in g.members if m.id in service_by_id]
        if not member_ids:
            continue
        grouped.update(member_ids)
        units.append(
            {"unit_id": str(g.id), "display_name": g.name,
             "service_ids": [str(i) for i in member_ids], "is_group": True}
        )
    for s in services:
        if s.id in grouped:
            continue
        units.append(
            {"unit_id": str(s.id), "display_name": s.name,
             "service_ids": [str(s.id)], "is_group": False}
        )

    units.sort(key=lambda u: min(service_cells[sid]["name"] for sid in u["service_ids"]))

    # Aggregate matrices over units. p_ij (Σ provider_revenue) and s_ij (max
    # threshold over the unit — the strictest the provider applies to any
    # service in the bundle) feed constraint (4) for ALL THREE algorithms now.
    # Admissibility is evaluated at the unit (aggregated) level — the unit is the
    # atom — using the aggregated s, p, c and the unit discount, not per member:
    #     s_unit · (1 − r_unit) · c_unit ≤ p_unit
    # so a whole group is admissible-or-not as one, consistent with how its
    # resource/price/discount are aggregated.
    n = len(providers)
    c_matrix: list[list[int]] = []
    b_ij: list[list[int]] = []
    omega: list[list[float]] = []
    p_matrix: list[list[float]] = []
    s_matrix: list[list[float]] = []
    for u in units:
        c_row, b_row, o_row, p_row, s_row = [], [], [], [], []
        for j in range(n):
            c_unit = sum(service_cells[sid]["price"][j] for sid in u["service_ids"])
            b_unit = sum(service_cells[sid]["resource"][j] for sid in u["service_ids"])
            disc_weighted = sum(
                service_cells[sid]["discount"][j] * service_cells[sid]["price"][j]
                for sid in u["service_ids"]
            )
            # p is a monetary value and may be fractional — sum the raw float so
            # the solver sees the SAME p as compute_provider_metrics (no int()).
            p_unit = sum(
                service_cells[sid]["provider_revenue"][j] for sid in u["service_ids"]
            )
            s_unit = max(
                (service_cells[sid]["min_value"][j] for sid in u["service_ids"]),
                default=0.0,
            )
            c_row.append(c_unit)
            b_row.append(b_unit)
            o_row.append(disc_weighted / c_unit if c_unit > 0 else 0.0)
            p_row.append(p_unit)
            s_row.append(s_unit)
        c_matrix.append(c_row)
        b_ij.append(b_row)
        omega.append(o_row)
        p_matrix.append(p_row)
        s_matrix.append(s_row)

    return {
        "m": len(units),
        "n": n,
        "c": c_matrix,
        "b_ij": b_ij,
        "omega": omega,
        "p_ij": p_matrix,
        "s_ij": s_matrix,
        "service_cells": service_cells,
        "unit_order": units,
        "provider_order": [str(p.id) for p in providers],
    }


# ---------------------------------------------------------------------------
# Status reconciliation (Temporal → DB)
# ---------------------------------------------------------------------------

async def _reconcile_status(
    scenario: FormationScenario, client: Client, session: AsyncSession
) -> None:
    """For a pending/running scenario, sync its status from Temporal. Success
    is written by persist_formation_result_activity; here we only surface
    running and failed states."""
    if scenario.status not in ("pending", "running") or not scenario.workflow_id:
        return
    try:
        desc = await client.get_workflow_handle(scenario.workflow_id).describe()
    except RPCError:
        return
    st = desc.status
    if st in _TERMINAL_FAILED:
        scenario.status = "failed"
        scenario.finished_at = datetime.now(timezone.utc)
        if not scenario.error:
            scenario.error = f"Workflow ended with status {st.name}"
        await session.commit()
    elif st == WorkflowExecutionStatus.RUNNING and scenario.status == "pending":
        scenario.status = "running"
        await session.commit()


async def _get_owned(
    scenario_id: uuid.UUID, session: AsyncSession, user: User
) -> FormationScenario:
    result = await session.execute(
        select(FormationScenario).where(
            FormationScenario.id == scenario_id,
            FormationScenario.owner_id == user.id,
        )
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return scenario


# ---------------------------------------------------------------------------
# Detail / totals assembly
# ---------------------------------------------------------------------------

async def _build_detail(
    scenario: FormationScenario, session: AsyncSession
) -> FormationDetail:
    snapshot = await session.get(FormationSnapshot, scenario.id)
    assignments_result = await session.execute(
        select(FormationAssignment).where(FormationAssignment.scenario_id == scenario.id)
    )
    assignments = list(assignments_result.scalars().all())

    # Resolve provider index + per-service resource and group membership from
    # the snapshot. Supports both the unit-aggregated format (service_order is a
    # list of unit dicts + input_payload.service_cells) and the older per-service
    # format (service_order is a list of ids + input_payload.b_ij).
    provider_idx: dict[str, int] = {}
    service_cells: dict | None = None
    group_name_by_service: dict[str, str] = {}
    old_service_idx: dict[str, int] = {}
    old_b_ij: list[list[int]] = []
    if snapshot:
        provider_idx = {pid: j for j, pid in enumerate(snapshot.provider_order)}
        payload = snapshot.input_payload or {}
        service_cells = payload.get("service_cells")
        order = snapshot.service_order or []
        if order and isinstance(order[0], dict):  # unit format
            for unit in order:
                if unit.get("is_group"):
                    for sid in unit["service_ids"]:
                        group_name_by_service[sid] = unit["display_name"]
        else:  # legacy per-service format
            old_service_idx = {sid: i for i, sid in enumerate(order)}
            old_b_ij = payload.get("b_ij", [])

    name_rows = await session.execute(
        select(Service.id, Service.name).where(Service.owner_id == scenario.owner_id)
    )
    service_names = {sid: name for sid, name in name_rows.all()}
    prov_rows = await session.execute(
        select(Provider.id, Provider.name).where(Provider.owner_id == scenario.owner_id)
    )
    provider_names = {pid: name for pid, name in prov_rows.all()}

    def resource_used_for(service_id: str, j: int | None) -> float:
        if j is None:
            return 0.0
        if service_cells is not None:
            res = service_cells.get(service_id, {}).get("resource", [])
            return float(res[j]) if j < len(res) else 0.0
        if old_b_ij:
            i = old_service_idx.get(service_id)
            if i is not None and i < len(old_b_ij) and j < len(old_b_ij[i]):
                return float(old_b_ij[i][j])
        return 0.0

    def provider_revenue_for(service_id: str, j: int | None) -> float | None:
        """Raw p_ij for the pair, from the snapshot. None when unavailable
        (legacy snapshot without per-service provider_revenue)."""
        if j is None or service_cells is None:
            return None
        pr = service_cells.get(service_id, {}).get("provider_revenue", [])
        return float(pr[j]) if j < len(pr) else None

    rows: list[FormationAssignmentRead] = []
    total_revenue = 0.0
    total_resource = 0.0
    for a in assignments:
        j = provider_idx.get(str(a.provider_id))
        resource_used = resource_used_for(str(a.service_id), j)
        eff = float(a.effective_revenue or 0)
        total_revenue += eff
        total_resource += resource_used

        # Per-pair provider metrics, matching compute_provider_metrics term for
        # term: provider revenue is the raw client-side p_ij (no discount); the
        # discount r (final for combined, planning else) only enters the profit.
        price = float(a.price or 0)
        r = float(a.final_discount) if a.final_discount is not None else float(a.discount or 0)
        p_ij = provider_revenue_for(str(a.service_id), j)
        provider_revenue_pair = p_ij if p_ij is not None else None
        provider_profit_pair = p_ij - (1.0 - r) * price if p_ij is not None else None

        rows.append(
            FormationAssignmentRead(
                service_id=a.service_id,
                service_name=service_names.get(a.service_id, str(a.service_id)),
                provider_id=a.provider_id,
                provider_name=provider_names.get(a.provider_id, str(a.provider_id)),
                price=price,
                discount=float(a.discount or 0),
                effective_revenue=eff,
                resource_used=resource_used,
                group_name=group_name_by_service.get(str(a.service_id)),
                final_discount=float(a.final_discount) if a.final_discount is not None else None,
                provider_revenue_pair=provider_revenue_pair,
                provider_profit_pair=provider_profit_pair,
            )
        )

    # Cluster by provider, then by group, then by service name.
    rows.sort(key=lambda r: (r.provider_name, r.group_name or "", r.service_name))
    totals = FormationTotals(
        total_revenue=total_revenue,
        total_resource_used=total_resource,
        provider_count=len({a.provider_id for a in assignments}),
        service_count=len({a.service_id for a in assignments}),
    )
    combined_benefit = (
        float(scenario.value) + float(scenario.provider_value)
        if scenario.value is not None and scenario.provider_value is not None
        else None
    )
    # created_value = F_IT + provider_profit (discount-invariant total value),
    # populated for every algorithm once both are stored.
    created_value = (
        float(scenario.value) + float(scenario.provider_profit)
        if scenario.value is not None and scenario.provider_profit is not None
        else None
    )
    return FormationDetail(
        id=scenario.id,
        name=scenario.name,
        algorithm=scenario.algorithm,
        status=scenario.status,
        value=scenario.value,
        provider_value=scenario.provider_value,
        provider_profit=scenario.provider_profit,
        created_value=created_value,
        combined_source=scenario.combined_source,
        combined_benefit=combined_benefit,
        b_total=float(scenario.b_total),
        params=scenario.params,
        workflow_id=scenario.workflow_id,
        error=scenario.error,
        created_at=scenario.created_at,
        finished_at=scenario.finished_at,
        assignments=rows,
        totals=totals,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=FormationListItem, status_code=status.HTTP_201_CREATED)
async def create_formation(
    body: FormationCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    client: Client = Depends(get_temporal_client),
) -> FormationScenario:
    # Validate params for the chosen algorithm and map UI names → solver names.
    ant = AntColonyParams()
    prob = ProbabilisticParams()
    combined: CombinedParameters | None = None
    if body.algorithm == "ant_colony":
        p = AntColonyParameters(**body.params)
        ant = AntColonyParams(
            num_ants=p.num_ants, kmax=p.Kmax, alpha=p.alpha, beta=p.beta,
            rho=p.p, initial_pheromone=p.tau,
        )
    elif body.algorithm == "probabilistic":
        prob = ProbabilisticParams(kmax=ProbabilisticParameters(**body.params).Kmax)
    elif body.algorithm == "combined":
        combined = CombinedParameters(**body.params)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown algorithm {body.algorithm!r}",
        )

    services = list(
        (await session.execute(
            select(Service).where(Service.owner_id == user.id).order_by(Service.name)
        )).scalars().all()
    )
    providers = list(
        (await session.execute(
            select(Provider).where(Provider.owner_id == user.id).order_by(Provider.name)
        )).scalars().all()
    )
    if not services or not providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one service and one provider are required",
        )
    cells = list(
        (await session.execute(
            select(PlanningCell).where(PlanningCell.owner_id == user.id)
        )).scalars().all()
    )
    groups = list(
        (await session.execute(
            select(ServiceGroup)
            .where(ServiceGroup.owner_id == user.id)
            .options(selectinload(ServiceGroup.members))
            .order_by(ServiceGroup.name)
        )).scalars().all()
    )

    payload = _build_payload(services, providers, cells, groups)
    b_total = int(body.b_total)

    scenario = FormationScenario(
        owner_id=user.id,
        name=body.name,
        b_total=b_total,
        algorithm=body.algorithm,
        params=body.params,
        status="pending",
    )
    session.add(scenario)
    await session.flush()  # assign scenario.id

    workflow_id = f"formation-{scenario.id}"
    redis_channel = f"formation:{workflow_id}"

    # Frozen solver input + per-service vectors for result expansion.
    input_payload = {
        "m": payload["m"],
        "n": payload["n"],
        "c": payload["c"],
        "b_ij": payload["b_ij"],
        "omega": payload["omega"],
        "b_total": b_total,
        "service_cells": payload["service_cells"],
    }

    if combined is not None:
        # omega_max: per-pair planning discount, OR all-0.95 when ignoring the
        # planning upper bound (treat discounts as free in [0, 0.95]).
        omega_max = (
            [[0.95 for _ in row] for row in payload["omega"]]
            if combined.ignore_discounts
            else payload["omega"]
        )
        input_payload.update({
            "p_ij": payload["p_ij"], "s_ij": payload["s_ij"],
            "omega_max": omega_max, "ignore_discounts": combined.ignore_discounts,
        })

    snapshot = FormationSnapshot(
        scenario_id=scenario.id,
        input_payload=input_payload,
        # service_order column now holds the unit partition.
        service_order=payload["unit_order"],
        provider_order=payload["provider_order"],
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(scenario)

    if combined is not None:
        await client.start_workflow(
            COMBINED_FORMATION_WORKFLOW_NAME,
            CombinedSolveInput(
                m=payload["m"], n=payload["n"], c=payload["c"], b_ij=payload["b_ij"],
                p_ij=payload["p_ij"], omega_max=omega_max, s_ij=payload["s_ij"],
                b_total=b_total,
                params=CombinedParams(
                    kmax_subproblem=combined.kmax_subproblem,
                    discount_step=combined.discount_step,
                    local_search_restarts=combined.local_search_restarts,
                ),
                scenario_id=str(scenario.id),
                redis_channel=redis_channel,
            ),
            id=workflow_id,
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(minutes=15),
        )
    else:
        await client.start_workflow(
            SINGLE_ALGORITHM_WORKFLOW_NAME,
            SingleSolveInput(
                m=payload["m"], n=payload["n"], c=payload["c"], b_ij=payload["b_ij"],
                b_total=b_total, omega=payload["omega"],
                algorithm=body.algorithm,
                ant_colony=ant,
                probabilistic=prob,
                # Constraint (4) is now enforced for probabilistic/ant-colony too,
                # at the planning discount (omega). p_ij/s_ij come from the same
                # aggregation as the combined branch (see _build_payload).
                p_ij=payload["p_ij"],
                s_ij=payload["s_ij"],
                scenario_id=str(scenario.id),
                redis_channel=redis_channel,
            ),
            id=workflow_id,
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(minutes=15),
        )

    scenario.workflow_id = workflow_id
    await session.commit()
    await session.refresh(scenario)
    return scenario


@router.get("", response_model=list[FormationListItem])
async def list_formations(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    client: Client = Depends(get_temporal_client),
) -> list[FormationScenario]:
    result = await session.execute(
        select(FormationScenario)
        .where(FormationScenario.owner_id == user.id)
        .order_by(FormationScenario.created_at.desc())
    )
    scenarios = list(result.scalars().all())
    for s in scenarios:
        await _reconcile_status(s, client, session)
    return scenarios


@router.get("/{scenario_id}", response_model=FormationDetail)
async def get_formation(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    client: Client = Depends(get_temporal_client),
) -> FormationDetail:
    scenario = await _get_owned(scenario_id, session, user)
    await _reconcile_status(scenario, client, session)
    return await _build_detail(scenario, session)


@router.get("/{scenario_id}/iterations", response_model=list[FormationIterationRead])
async def get_iterations(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> list[FormationIterationRead]:
    """Convergence history sorted by iteration. While the scenario is still
    running, this is read live from the Redis stream; once it completes the
    persist activity has drained it into Postgres. Empty list is valid."""
    scenario = await _get_owned(scenario_id, session, user)

    if scenario.status in ("completed", "failed"):
        rows = await session.execute(
            select(FormationIteration.iteration, FormationIteration.best_value)
            .where(FormationIteration.scenario_id == scenario.id)
            .order_by(FormationIteration.iteration)
        )
        return [
            FormationIterationRead(iteration=it, best_value=bv) for it, bv in rows.all()
        ]

    # pending / running — read the live stream (best-effort).
    if not scenario.workflow_id:
        return []
    try:
        entries = await redis.xrange(f"formation:{scenario.workflow_id}", min="-", max="+")
    except Exception:
        return []
    by_iter: dict[int, float] = {}
    for _entry_id, fields in entries:
        try:
            data = json.loads(fields["data"])
        except (KeyError, ValueError):
            continue
        if data.get("type") == "iteration":
            by_iter[int(data["iteration"])] = float(data["current_best_value"])
    return [
        FormationIterationRead(iteration=it, best_value=bv)
        for it, bv in sorted(by_iter.items())
    ]


@router.websocket("/{scenario_id}/ws")
async def iterations_ws(websocket: WebSocket, scenario_id: uuid.UUID) -> None:
    """Live convergence stream over WebSocket.

    Authenticates via a ``?token=`` query parameter, because a browser cannot
    set an Authorization header on the WebSocket handshake. The handler replays
    the iterations already buffered in the Redis stream, then tails it for new
    ones, and sends a final ``{"type": "complete"}`` once the scenario reaches a
    terminal state — at which point the full history is durable in Postgres and
    available via ``GET /iterations``.

    Message protocol (server → client, JSON text frames):
      {"type": "iteration", "iteration": int, "best_value": float}
      {"type": "complete"}
    """
    await websocket.accept()
    token = websocket.query_params.get("token")
    user_id = decode_token(token) if token else None
    if user_id is None:
        await websocket.close(code=1008)  # policy violation
        return

    redis: Redis = websocket.app.state.redis

    async def send_iteration(payload: dict) -> None:
        if payload.get("type") == "iteration":
            await websocket.send_json({
                "type": "iteration",
                "iteration": int(payload["iteration"]),
                "best_value": float(payload["current_best_value"]),
            })

    async with AsyncSessionLocal() as session:
        scenario = (
            await session.execute(
                select(FormationScenario).where(
                    FormationScenario.id == scenario_id,
                    FormationScenario.owner_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if scenario is None:
            await websocket.close(code=1008)
            return

        channel = f"formation:{scenario.workflow_id}" if scenario.workflow_id else None

        try:
            # Already finished: stream the persisted history once, then done.
            if scenario.status in ("completed", "failed") or channel is None:
                rows = await session.execute(
                    select(FormationIteration.iteration, FormationIteration.best_value)
                    .where(FormationIteration.scenario_id == scenario.id)
                    .order_by(FormationIteration.iteration)
                )
                for it, bv in rows.all():
                    await websocket.send_json(
                        {"type": "iteration", "iteration": it, "best_value": bv}
                    )
                await websocket.send_json({"type": "complete"})
                return

            # Running: replay what's buffered, then tail the stream live.
            last_id = "0"
            try:
                entries = await redis.xrange(channel, min="-", max="+")
            except Exception:
                entries = []
            for entry_id, fields in entries:
                last_id = entry_id
                try:
                    await send_iteration(json.loads(fields["data"]))
                except (KeyError, ValueError):
                    continue

            while True:
                try:
                    resp = await redis.xread({channel: last_id}, block=1000, count=500)
                except Exception:
                    resp = None
                if resp:
                    for _stream, msgs in resp:
                        for entry_id, fields in msgs:
                            last_id = entry_id
                            try:
                                await send_iteration(json.loads(fields["data"]))
                            except (KeyError, ValueError):
                                continue

                # The persist activity flips status from another process; a fresh
                # scalar read under READ COMMITTED sees its committed value.
                status_val = (
                    await session.execute(
                        select(FormationScenario.status).where(
                            FormationScenario.id == scenario.id
                        )
                    )
                ).scalar_one_or_none()
                await session.commit()  # end the txn so the next poll re-reads
                if status_val in ("completed", "failed"):
                    await websocket.send_json({"type": "complete"})
                    return
        except WebSocketDisconnect:
            return
        finally:
            try:
                await websocket.close()
            except Exception:
                pass


@router.get("/{scenario_id}/export.json")
async def export_json(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    client: Client = Depends(get_temporal_client),
) -> Response:
    scenario = await _get_owned(scenario_id, session, user)
    await _reconcile_status(scenario, client, session)
    detail = await _build_detail(scenario, session)
    return Response(
        content=detail.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="formation-{scenario_id}.json"'
        },
    )


@router.get("/{scenario_id}/export.csv")
async def export_csv(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    client: Client = Depends(get_temporal_client),
) -> Response:
    scenario = await _get_owned(scenario_id, session, user)
    await _reconcile_status(scenario, client, session)
    detail = await _build_detail(scenario, session)

    buf = io.StringIO()
    writer = csv.writer(buf)

    # Scenario-level summary block (totals), then a blank line, then the
    # per-assignment rows. "—" for metrics not yet backfilled on old scenarios.
    def _num(x: float | None) -> str:
        return "" if x is None else f"{x:.4f}"

    writer.writerow(["metric", "value"])
    writer.writerow(["algorithm", detail.algorithm])
    writer.writerow(["f_it", _num(detail.value)])
    writer.writerow(["provider_revenue", _num(detail.provider_value)])
    writer.writerow(["provider_profit", _num(detail.provider_profit)])
    writer.writerow(["created_value", _num(detail.created_value)])
    writer.writerow(["combined_benefit", _num(detail.combined_benefit)])
    writer.writerow([])

    writer.writerow([
        "service", "provider", "price", "discount", "final_discount",
        "effective_revenue", "resource_used",
    ])
    for a in detail.assignments:
        writer.writerow([
            a.service_name, a.provider_name, a.price, a.discount,
            a.final_discount if a.final_discount is not None else a.discount,
            a.effective_revenue, a.resource_used,
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="formation-{scenario_id}.csv"'
        },
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_formations(
    body: CompareRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> CompareResponse:
    scenarios_out: list[CompareScenario] = []
    for sid in body.scenario_ids:
        scenario = await _get_owned(sid, session, user)
        detail = await _build_detail(scenario, session)

        by_provider: dict[uuid.UUID, CompareProviderBreakdown] = {}
        for a in detail.assignments:
            entry = by_provider.get(a.provider_id)
            if entry is None:
                entry = CompareProviderBreakdown(
                    provider_id=a.provider_id,
                    provider_name=a.provider_name,
                    assignment_count=0,
                    services=[],
                )
                by_provider[a.provider_id] = entry
            entry.assignment_count += 1
            entry.services.append(a.service_name)

        scenarios_out.append(
            CompareScenario(
                id=scenario.id,
                name=scenario.name,
                algorithm=scenario.algorithm,
                status=scenario.status,
                value=scenario.value,
                provider_value=scenario.provider_value,
                provider_profit=scenario.provider_profit,
                created_value=detail.created_value,
                combined_benefit=detail.combined_benefit,
                b_total=float(scenario.b_total),
                params=scenario.params,
                total_revenue=detail.totals.total_revenue,
                total_resource_used=detail.totals.total_resource_used,
                per_provider=sorted(by_provider.values(), key=lambda e: e.provider_name),
            )
        )
    return CompareResponse(scenarios=scenarios_out)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_formation(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    scenario = await _get_owned(scenario_id, session, user)
    await session.delete(scenario)
    await session.commit()
