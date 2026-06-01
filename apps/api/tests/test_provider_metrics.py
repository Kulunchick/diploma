"""Provider-side metrics: F_prov (gross) and provider_profit (net), computed
and stored for ALL three algorithms.

The discount-invariance identity that anchors the whole feature:

    F_IT + provider_profit == Σ p_ij·v_ij   (total value created)

where F_IT = Σ (1−r)·d. It holds for any discount r, hence for every algorithm
(probabilistic/ant use the planning r; combined uses the negotiated r_final).
"""
import sys
from pathlib import Path

import pytest

_WORKER_SRC = Path(__file__).resolve().parents[3] / "apps" / "worker" / "src"
if str(_WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(_WORKER_SRC))

from worker.metrics import compute_provider_metrics  # noqa: E402


# ---------------------------------------------------------------------------
# Pure unit tests (no DB)
# ---------------------------------------------------------------------------

_SERVICE_CELLS = {
    "s1": {"price": [100, 0], "provider_revenue": [80, 0], "discount": [0.1, 0.0]},
    "s2": {"price": [0, 200], "provider_revenue": [0, 50], "discount": [0.0, 0.25]},
}
_UNIT_ORDER = [{"service_ids": ["s1"]}, {"service_ids": ["s2"]}]
_V = [[1, 0], [0, 1]]  # s1→provider0, s2→provider1


def test_compute_provider_metrics_planning_discount():
    f_prov, profit, total = compute_provider_metrics(_SERVICE_CELLS, _UNIT_ORDER, _V)
    # F_prov is raw Σp·v: 80 + 50
    assert f_prov == pytest.approx(130.0)
    # profit: (80-.9*100) + (50-.75*200) = -10 + -100
    assert profit == pytest.approx(-110.0)
    assert total == pytest.approx(130.0)  # 80 + 50 == F_prov


def test_compute_provider_metrics_final_discount():
    final = [[0.5, 0.0], [0.0, 0.5]]
    f_prov, profit, total = compute_provider_metrics(
        _SERVICE_CELLS, _UNIT_ORDER, _V, final_discount=final
    )
    # F_prov raw Σp·v — unchanged by the discount.
    assert f_prov == pytest.approx(130.0)
    # profit: (80-.5*100) + (50-.5*200) = 30 + -50
    assert profit == pytest.approx(-20.0)
    assert total == pytest.approx(130.0)


def test_discount_affects_profit_not_revenue():
    """F_prov is raw Σp·v → identical regardless of discount. Only provider_profit
    depends on r, so planning vs negotiated discount changes the profit, not F_prov.
    (probabilistic/ant use planning r; combined uses r_final.)"""
    fprov_pl, profit_pl, _ = compute_provider_metrics(_SERVICE_CELLS, _UNIT_ORDER, _V)
    final = [[0.5, 0.0], [0.0, 0.5]]
    fprov_fn, profit_fn, _ = compute_provider_metrics(
        _SERVICE_CELLS, _UNIT_ORDER, _V, final_discount=final
    )
    assert fprov_pl == pytest.approx(fprov_fn)  # F_prov unchanged by r
    assert profit_pl != pytest.approx(profit_fn)  # profit differs with r


@pytest.mark.parametrize(
    "final",
    [None, [[0.3, 0.0], [0.0, 0.4]], [[0.0, 0.0], [0.0, 0.0]], [[0.9, 0.0], [0.0, 0.9]]],
)
def test_discount_invariance_identity(final):
    """F_IT + provider_profit == Σ p·v == F_prov for any discount (all algorithms)."""
    f_prov, profit, total = compute_provider_metrics(
        _SERVICE_CELLS, _UNIT_ORDER, _V, final_discount=final
    )
    # F_IT = Σ (1−r)·d under the same r the metrics used.
    f_it = 0.0
    for u, unit in enumerate(_UNIT_ORDER):
        for j, sel in enumerate(_V[u]):
            if sel != 1:
                continue
            for sid in unit["service_ids"]:
                d = _SERVICE_CELLS[sid]["price"][j]
                r = final[u][j] if final is not None else _SERVICE_CELLS[sid]["discount"][j]
                f_it += (1.0 - r) * d
    assert f_it + profit == pytest.approx(total, abs=1e-9)
    assert f_prov == pytest.approx(total, abs=1e-9)  # F_prov == Σp·v exactly


# ---------------------------------------------------------------------------
# DB-backed: metrics persisted for all algorithms + backfill (mocked Temporal)
# ---------------------------------------------------------------------------

async def _seed(client, h):
    """Two ungrouped services, two providers, provider_revenue set so the
    provider metrics are non-trivial. Anti-correlated d vs p."""
    svc = {n: (await client.post("/api/services", json={"name": n}, headers=h)).json()["id"]
           for n in ["SvcA", "SvcB"]}
    prov = {n: (await client.post("/api/providers", json={"name": n}, headers=h)).json()["id"]
            for n in ["ProvA", "ProvB"]}
    cells = []
    plan = {"SvcA": (500, 200), "SvcB": (300, 600)}  # (price d, provider_revenue p)
    for name, (d, p) in plan.items():
        for pid in prov.values():
            cells.append({
                "service_id": svc[name], "provider_id": pid,
                "price": d, "resource": 400, "provider_revenue": p,
                "discount": 0.2, "min_value": 0.0,
            })
    await client.post("/api/planning/bulk", json={"cells": cells}, headers=h)
    return svc, prov


async def _solve_single(wf_input):
    from worker.activities import run_algorithm_activity
    from worker.types import RunAlgorithmInput

    return await run_algorithm_activity(RunAlgorithmInput(
        m=wf_input.m, n=wf_input.n, c=wf_input.c, b_ij=wf_input.b_ij,
        b_total=wf_input.b_total, omega=wf_input.omega, algorithm=wf_input.algorithm,
        ant_colony_params=wf_input.ant_colony, probabilistic_params=wf_input.probabilistic,
        variant_key="t", redis_channel=None,
    ))


@pytest.mark.parametrize("algorithm,params", [
    ("probabilistic", {"Kmax": 100}),
    ("ant_colony", {"Kmax": 50, "num_ants": 8, "alpha": 1, "beta": 2, "p": 0.1, "tau": 1}),
])
async def test_metrics_populated_for_single_algorithms(
    client, auth_headers, mock_temporal, algorithm, params
):
    import worker.activities as wa
    from worker.types import PersistFormationInput

    wa.set_redis_client(None)
    h = await auth_headers(f"pm-{algorithm}@example.com")
    await _seed(client, h)

    sid = (await client.post("/api/formations", json={
        "name": algorithm, "b_total": 100000, "algorithm": algorithm, "params": params,
    }, headers=h)).json()["id"]
    result = await _solve_single(mock_temporal.calls[-1][0][1])
    await wa.persist_formation_result_activity(PersistFormationInput(
        scenario_id=sid, solution=result.solution, value=result.value,
    ))

    d = (await client.get(f"/api/formations/{sid}", headers=h)).json()
    assert d["provider_value"] is not None
    assert d["provider_profit"] is not None
    assert d["created_value"] is not None
    # API identity: created_value == F_IT + provider_profit
    assert d["created_value"] == pytest.approx(d["value"] + d["provider_profit"], abs=1e-6)

    # Per-pair columns must sum to the scenario-level totals shown in the cards.
    pr_sum = sum(a["provider_revenue_pair"] for a in d["assignments"])
    pp_sum = sum(a["provider_profit_pair"] for a in d["assignments"])
    assert pr_sum == pytest.approx(d["provider_value"], abs=1e-6)
    assert pp_sum == pytest.approx(d["provider_profit"], abs=1e-6)


async def test_backfill_repopulates_from_snapshot(client, auth_headers, mock_temporal):
    """Simulate a pre-migration scenario by NULLing the provider columns, then
    run the 0004 backfill computation (assignment rows + snapshot
    provider_revenue, F_prov = raw Σp·v) and assert it reproduces what persist
    computed."""
    from sqlalchemy import text

    import worker.activities as wa
    from src.operations.db.base import AsyncSessionLocal
    from worker.types import PersistFormationInput

    wa.set_redis_client(None)
    h = await auth_headers("pm-backfill@example.com")
    await _seed(client, h)
    sid = (await client.post("/api/formations", json={
        "name": "bf", "b_total": 100000, "algorithm": "probabilistic", "params": {"Kmax": 100},
    }, headers=h)).json()["id"]
    result = await _solve_single(mock_temporal.calls[-1][0][1])
    await wa.persist_formation_result_activity(PersistFormationInput(
        scenario_id=sid, solution=result.solution, value=result.value,
    ))

    d0 = (await client.get(f"/api/formations/{sid}", headers=h)).json()
    expected_pv, expected_pp = d0["provider_value"], d0["provider_profit"]
    assert expected_pv is not None and expected_pp is not None

    async with AsyncSessionLocal() as s:
        # pre-migration state
        await s.execute(text(
            "UPDATE formation_scenarios SET provider_value = NULL, provider_profit = NULL "
            "WHERE id = CAST(:sid AS uuid)"), {"sid": sid})
        await s.commit()

        # --- mirror the 0003 backfill: assignment rows + snapshot provider_revenue
        snap = (await s.execute(text(
            "SELECT input_payload, provider_order FROM formation_snapshots "
            "WHERE scenario_id = CAST(:sid AS uuid)"), {"sid": sid})).one()
        import json
        payload = json.loads(snap[0]) if isinstance(snap[0], str) else snap[0]
        provider_order = json.loads(snap[1]) if isinstance(snap[1], str) else snap[1]
        cells = payload["service_cells"]
        pidx = {pid: j for j, pid in enumerate(provider_order)}
        rows = (await s.execute(text(
            "SELECT service_id, provider_id, price, discount, final_discount "
            "FROM formation_assignments WHERE scenario_id = CAST(:sid AS uuid)"),
            {"sid": sid})).fetchall()
        f_prov = 0.0
        profit = 0.0
        for service_id, provider_id, price, discount, final_discount in rows:
            j = pidx[str(provider_id)]
            p = float(cells[str(service_id)]["provider_revenue"][j])
            dd = float(price or 0)
            r = float(final_discount if final_discount is not None else (discount or 0))
            f_prov += p  # raw Σp·v (0004), matches persist
            profit += p - (1.0 - r) * dd
        await s.execute(text(
            "UPDATE formation_scenarios SET provider_value = :pv, provider_profit = :pp "
            "WHERE id = CAST(:sid AS uuid)"), {"pv": f_prov, "pp": profit, "sid": sid})
        await s.commit()

    d1 = (await client.get(f"/api/formations/{sid}", headers=h)).json()
    assert d1["provider_value"] == pytest.approx(expected_pv, abs=1e-6)
    assert d1["provider_profit"] == pytest.approx(expected_pp, abs=1e-6)
