"""Combined method (article §4–5) — the canonical proof artifact.

Constraint (4) — corrected formulation. The article writes s_ij ≤ p_ij / b_ij
where b_ij is the provider's cost of offering S_i. We model the provider cost as
the discounted price it pays the IT-company, b_ij = (1 − r_ij)·d_ij, so:

    admissible(i, j, r) ⇔ s_ij · (1 − r_ij) · d_ij ≤ p_ij

Raising the discount lowers the provider's cost → eases admissibility. That is
the lever the stage-3 concessions use.

Invariants (discounts are decision variables in [0, r_max], so the naive
"≤ subtask_X at r_max" bound does NOT hold; the rigorous single-criterion
ceilings are the discount-free Σ value):

  (1) F_IT(combined)   ≤ Σ d_ij                 (since (1−r)·d ≤ d)
  (2) F_prov(combined) ≤ Σ p_ij                 (since (1−r)·p ≤ p)
  (3) F_IT+F_prov(combined) ≥ the same structure's benefit at r_max
      (stage-3 hill climbing only lowers r, which never reduces either term).

The fixture is chosen so unit 0 (IT-heavy: high d, modest p) has a high floor
s=0.70 → it is admissible ONLY when the IT-company concedes a discount
(r ≥ 0.20). This makes the concession lever observable: unit 0 settles at
r_final = 0.20 < r_max = 0.30, a genuine non-trivial concession.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

_WORKER_SRC = Path(__file__).resolve().parents[3] / "apps" / "worker" / "src"
if str(_WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(_WORKER_SRC))

from assignment_solver import CombinedSolver, CombinedTask  # noqa: E402

# --- concession-demonstrating fixture (4 units × 2 providers) ---------------
C = np.array([[1000, 1000], [300, 300], [700, 700], [250, 250]], dtype=np.int64)
P = np.array([[560, 560], [950, 950], [700, 700], [1000, 1000]], dtype=np.int64)
B = np.array([[500, 500], [500, 500], [500, 500], [500, 500]], dtype=np.int64)
S = np.array([[0.70, 0.70], [0.30, 0.30], [0.50, 0.50], [0.30, 0.30]])
R_MAX = 0.30
B_TOTAL = 2000


def _task(omega_max=None) -> CombinedTask:
    om = np.full((4, 2), R_MAX) if omega_max is None else omega_max
    return CombinedTask(4, 2, C, B, P, om, S, B_TOTAL)


def _f(v, value, r):
    return float(sum((1.0 - r[i, j]) * value[i, j]
                     for i in range(v.shape[0]) for j in range(v.shape[1]) if v[i, j] == 1))


def _admissible(i, j, r):  # corrected constraint (4)
    return S[i, j] * (1.0 - r) * C[i, j] <= P[i, j]


def _solve(**params):
    out = CombinedSolver(
        params.get("kmax_subproblem", 400),
        params.get("discount_step", 0.05),
        params.get("local_search_restarts", 3),
    ).solve(_task(params.get("omega_max")))
    return out, np.array(out["v_final"]), np.array(out["r_final"])


def test_return_contract_consistent():
    out, v, r = _solve()
    assert out["f_it"] == pytest.approx(_f(v, C, r), abs=1e-6)
    assert out["f_prov"] == pytest.approx(_f(v, P, r), abs=1e-6)
    assert out["source"] in ("subtask_a_improved", "subtask_b_improved")


def test_invariants_1_2_3():
    out, v, r = _solve()
    # (1) and (2): no objective exceeds its discount-free Σ ceiling.
    assert out["f_it"] <= C.sum() + 1e-6
    assert out["f_prov"] <= P.sum() + 1e-6
    # (3): benefit ≥ the same structure evaluated at r_max (lowering r never hurt).
    benefit = out["f_it"] + out["f_prov"]
    benefit_at_rmax = _f(v, C, np.full((4, 2), R_MAX)) + _f(v, P, np.full((4, 2), R_MAX))
    assert benefit >= benefit_at_rmax - 1e-6
    # resource feasibility
    used = sum(B[i, j] for i in range(4) for j in range(2) if v[i, j] == 1)
    assert used <= B_TOTAL


def test_constraint4_holds_for_every_assignment():
    _out, v, r = _solve()
    for i in range(4):
        for j in range(2):
            if v[i, j] == 1:
                assert _admissible(i, j, r[i, j]), f"constraint (4) violated at ({i},{j}) r={r[i,j]}"


def test_concession_lever_fires():
    """At least one selected pair settles at r_final < r_max — a real concession.
    Unit 0 (s=0.70) is admissible only for r ≥ 0.20, so if selected it must carry
    a non-trivial discount strictly below the r_max=0.30 ceiling."""
    _out, v, r = _solve()
    lowered = [(i, j) for i in range(4) for j in range(2)
               if v[i, j] == 1 and r[i, j] < R_MAX - 1e-9]
    assert lowered, "expected at least one negotiated discount below r_max"
    # and every lowered, selected pair is still admissible (the floor was respected)
    for i, j in lowered:
        assert _admissible(i, j, r[i, j])


def test_ignore_discounts_stays_feasible():
    """ignore_discounts ⇒ omega_max≈0.95 widens the discount range. We do NOT
    assert it yields a higher benefit — the stage-3 search is a greedy local
    optimiser, so a larger feasible region can converge to a different (even
    lower-benefit) local optimum. The contract we DO require: the result stays
    a valid, self-consistent, resource-feasible solution that respects (4)."""
    out, v, r = _solve(omega_max=np.full((4, 2), 0.95))
    assert out["f_it"] == pytest.approx(_f(v, C, r), abs=1e-6)
    assert out["f_prov"] == pytest.approx(_f(v, P, r), abs=1e-6)
    used = sum(B[i, j] for i in range(4) for j in range(2) if v[i, j] == 1)
    assert used <= B_TOTAL
    for i in range(4):
        for j in range(2):
            if v[i, j] == 1:
                assert _admissible(i, j, r[i, j])


# ---------------------------------------------------------------------------
# API + persist integration (mocked Temporal, real solver, real Postgres)
# ---------------------------------------------------------------------------

async def _seed_combined(client, h):
    """2 services in a group + 1 ungrouped; 2 providers; one group service has a
    high relative-value floor so a concession is required."""
    svc = {}
    for n in ["A-Хостинг", "B-DNS", "C-Пошта"]:
        svc[n] = (await client.post("/api/services", json={"name": n}, headers=h)).json()["id"]
    await client.post(
        "/api/service-groups",
        json={"name": "Пакет", "member_ids": [svc["A-Хостинг"], svc["B-DNS"]]},
        headers=h,
    )
    prov = {}
    for n in ["P1", "P2"]:
        prov[n] = (await client.post("/api/providers", json={"name": n}, headers=h)).json()["id"]

    # group services IT-heavy (high d, modest p, high s); ungrouped provider-heavy
    plan = {
        "A-Хостинг": (500, 280, 0.70),
        "B-DNS": (500, 280, 0.70),
        "C-Пошта": (300, 950, 0.30),
    }
    cells = []
    for name, (d, p, s) in plan.items():
        for pid in prov.values():
            cells.append({
                "service_id": svc[name], "provider_id": pid,
                "price": d, "resource": 500, "provider_revenue": p,
                "discount": 0.30, "min_value": s,
            })
    await client.post("/api/planning/bulk", json={"cells": cells}, headers=h)
    return svc, prov


async def _run_combined(wf_input):
    task = CombinedTask(
        wf_input.m, wf_input.n,
        np.array(wf_input.c, dtype=np.int64),
        np.array(wf_input.b_ij, dtype=np.int64),
        np.array(wf_input.p_ij, dtype=np.int64),
        np.array(wf_input.omega_max, dtype=np.float64),
        np.array(wf_input.s_ij, dtype=np.float64),
        int(wf_input.b_total),
    )
    return CombinedSolver(
        wf_input.params.kmax_subproblem,
        wf_input.params.discount_step,
        wf_input.params.local_search_restarts,
    ).solve(task)


async def test_combined_persist_and_read(client, auth_headers, mock_temporal):
    import worker.activities as wa
    from worker.types import PersistCombinedInput

    wa.set_redis_client(None)
    h = await auth_headers("combined@example.com")
    svc, _ = await _seed_combined(client, h)

    created = await client.post(
        "/api/formations",
        json={"name": "C", "b_total": 100000, "algorithm": "combined",
              "params": {"kmax_subproblem": 300, "discount_step": 0.05,
                         "ignore_discounts": False, "local_search_restarts": 3}},
        headers=h,
    )
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    out = await _run_combined(mock_temporal.calls[-1][0][1])

    await wa.persist_combined_result_activity(PersistCombinedInput(
        scenario_id=sid,
        v_final=[list(map(int, row)) for row in out["v_final"]],
        r_final=[list(map(float, row)) for row in out["r_final"]],
        f_it=float(out["f_it"]), f_prov=float(out["f_prov"]), source=str(out["source"]),
    ))

    d = (await client.get(f"/api/formations/{sid}", headers=h)).json()
    assert d["status"] == "completed"
    assert d["provider_value"] is not None
    assert d["combined_source"] in ("subtask_a_improved", "subtask_b_improved")
    assert d["combined_benefit"] == pytest.approx(d["value"] + d["provider_value"], abs=1e-6)
    assert all(a["final_discount"] is not None for a in d["assignments"])
    seff = sum(a["effective_revenue"] for a in d["assignments"])
    assert seff == pytest.approx(d["value"], abs=1e-6)

    # group all-or-nothing per provider
    group_ids = {svc["A-Хостинг"], svc["B-DNS"]}
    per_provider: dict[str, set] = {}
    for a in d["assignments"]:
        if a["service_id"] in group_ids:
            per_provider.setdefault(a["provider_id"], set()).add(a["service_id"])
    for assigned in per_provider.values():
        assert assigned == group_ids
