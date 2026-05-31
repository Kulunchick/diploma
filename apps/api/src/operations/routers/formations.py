"""Package-formation scenarios: run, inspect, export and compare.

A formation runs from saved catalogue + planning data (not raw matrices). It
builds the same (m, n, c, b_ij, b_total, omega) payload the existing Temporal
flow consumes and runs it through SingleAlgorithmWorkflow (one algorithm +
write-back). Provider revenue p_ij and service groups are persisted elsewhere
but are NOT part of the solver input in this iteration.
"""
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.operations.db.base import get_session
from src.operations.db.models import (
    FormationAssignment,
    FormationScenario,
    FormationSnapshot,
    PlanningCell,
    Provider,
    Service,
    User,
)
from src.operations.models.algorithm_parametrs import (
    AntColonyParameters,
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
    FormationListItem,
    FormationTotals,
)
from src.operations.routers.deps import get_temporal_client
from src.operations.security import get_current_user
from src.operations.temporal_types import (
    SINGLE_ALGORITHM_WORKFLOW_NAME,
    TASK_QUEUE,
    AntColonyParams,
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
    services: list[Service], providers: list[Provider], cells: list[PlanningCell]
) -> dict:
    """Build the solver payload from saved entities in a deterministic order
    (services by name ASC, providers by name ASC). Missing cells default to 0.

    Solver subtask A operates on integer prices/resources per the article
    §5.1; NUMERIC storage allows future precision but is truncated at the
    boundary (price → int, resource → int, b_total → int). Discounts (omega)
    stay float.
    """
    by_pair = {(c.service_id, c.provider_id): c for c in cells}
    m, n = len(services), len(providers)

    c_matrix: list[list[int]] = []
    b_ij: list[list[int]] = []
    omega: list[list[float]] = []
    for s in services:
        c_row, b_row, o_row = [], [], []
        for p in providers:
            cell = by_pair.get((s.id, p.id))
            c_row.append(int(cell.price) if cell else 0)
            b_row.append(int(cell.resource) if cell else 0)
            o_row.append(float(cell.discount) if cell else 0.0)
        c_matrix.append(c_row)
        b_ij.append(b_row)
        omega.append(o_row)

    return {
        "m": m,
        "n": n,
        "c": c_matrix,
        "b_ij": b_ij,
        "omega": omega,
        "service_order": [str(s.id) for s in services],
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

    # Resolve names + resource_used (from the frozen snapshot b_ij).
    service_idx: dict[str, int] = {}
    provider_idx: dict[str, int] = {}
    b_ij: list[list[int]] = []
    if snapshot:
        service_idx = {sid: i for i, sid in enumerate(snapshot.service_order)}
        provider_idx = {pid: j for j, pid in enumerate(snapshot.provider_order)}
        b_ij = snapshot.input_payload.get("b_ij", [])

    name_rows = await session.execute(
        select(Service.id, Service.name).where(Service.owner_id == scenario.owner_id)
    )
    service_names = {sid: name for sid, name in name_rows.all()}
    prov_rows = await session.execute(
        select(Provider.id, Provider.name).where(Provider.owner_id == scenario.owner_id)
    )
    provider_names = {pid: name for pid, name in prov_rows.all()}

    rows: list[FormationAssignmentRead] = []
    total_revenue = 0.0
    total_resource = 0.0
    for a in assignments:
        i = service_idx.get(str(a.service_id))
        j = provider_idx.get(str(a.provider_id))
        resource_used = (
            float(b_ij[i][j]) if i is not None and j is not None and b_ij else 0.0
        )
        eff = float(a.effective_revenue or 0)
        total_revenue += eff
        total_resource += resource_used
        rows.append(
            FormationAssignmentRead(
                service_id=a.service_id,
                service_name=service_names.get(a.service_id, str(a.service_id)),
                provider_id=a.provider_id,
                provider_name=provider_names.get(a.provider_id, str(a.provider_id)),
                price=float(a.price or 0),
                discount=float(a.discount or 0),
                effective_revenue=eff,
                resource_used=resource_used,
            )
        )

    rows.sort(key=lambda r: (r.provider_name, r.service_name))
    totals = FormationTotals(
        total_revenue=total_revenue,
        total_resource_used=total_resource,
        provider_count=len({a.provider_id for a in assignments}),
        service_count=len({a.service_id for a in assignments}),
    )
    return FormationDetail(
        id=scenario.id,
        name=scenario.name,
        algorithm=scenario.algorithm,
        status=scenario.status,
        value=scenario.value,
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
    if body.algorithm == "ant_colony":
        p = AntColonyParameters(**body.params)
        ant = AntColonyParams(
            num_ants=p.num_ants, kmax=p.Kmax, alpha=p.alpha, beta=p.beta,
            rho=p.p, initial_pheromone=p.tau,
        )
        prob = ProbabilisticParams()
    else:
        p = ProbabilisticParameters(**body.params)
        prob = ProbabilisticParams(kmax=p.Kmax)
        ant = AntColonyParams()

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

    payload = _build_payload(services, providers, cells)
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

    snapshot = FormationSnapshot(
        scenario_id=scenario.id,
        input_payload={
            "m": payload["m"],
            "n": payload["n"],
            "c": payload["c"],
            "b_ij": payload["b_ij"],
            "omega": payload["omega"],
            "b_total": b_total,
        },
        service_order=payload["service_order"],
        provider_order=payload["provider_order"],
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(scenario)

    workflow_id = f"formation-{scenario.id}"
    await client.start_workflow(
        SINGLE_ALGORITHM_WORKFLOW_NAME,
        SingleSolveInput(
            m=payload["m"],
            n=payload["n"],
            c=payload["c"],
            b_ij=payload["b_ij"],
            b_total=b_total,
            omega=payload["omega"],
            algorithm=body.algorithm,
            ant_colony=ant,
            probabilistic=prob,
            scenario_id=str(scenario.id),
            redis_channel=f"solve:{workflow_id}",
        ),
        id=workflow_id,
        task_queue=TASK_QUEUE,
        execution_timeout=timedelta(minutes=10),
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
    writer.writerow(["service", "provider", "price", "discount", "effective_revenue", "resource_used"])
    for a in detail.assignments:
        writer.writerow(
            [a.service_name, a.provider_name, a.price, a.discount, a.effective_revenue, a.resource_used]
        )
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
