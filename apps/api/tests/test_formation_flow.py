"""Formation flow with a mocked Temporal client.

Temporal is not run in tests: start_workflow is captured, and the worker's
persist_formation_result_activity is invoked directly to assert that
assignments + snapshot are written and totals reconcile with the solver value.
"""
import sys
from pathlib import Path

import pytest
from temporalio.client import WorkflowExecutionStatus

# The worker package is a sibling app; add its src so the persist activity
# (which shares deps with the api) can be imported and called directly.
_WORKER_SRC = Path(__file__).resolve().parents[3] / "apps" / "worker" / "src"
if str(_WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(_WORKER_SRC))


class _MockDesc:
    status = WorkflowExecutionStatus.RUNNING


class _MockHandle:
    async def describe(self):
        return _MockDesc()


class _MockTemporal:
    def __init__(self):
        self.calls = []

    async def start_workflow(self, *args, **kwargs):
        self.calls.append((args, kwargs))

    def get_workflow_handle(self, workflow_id):
        return _MockHandle()


class _ApiFakeRedis:
    """Minimal stand-in for the API's app.state.redis (the /iterations dep)."""

    async def xrange(self, key, min="-", max="+"):
        return []


@pytest.fixture
def mock_temporal():
    from src.operations.main import app

    mock = _MockTemporal()
    app.state.temporal = mock
    app.state.redis = _ApiFakeRedis()
    return mock


async def _seed(client, h):
    s = [
        (await client.post("/api/services", json={"name": n}, headers=h)).json()["id"]
        for n in ["SvcA", "SvcB"]
    ]
    p = [
        (await client.post("/api/providers", json={"name": n}, headers=h)).json()["id"]
        for n in ["ProvA", "ProvB"]
    ]
    await client.post(
        "/api/planning/bulk",
        json={
            "cells": [
                {"service_id": s[0], "provider_id": p[0], "price": 500, "resource": 1000, "discount": 0.1},
                {"service_id": s[1], "provider_id": p[1], "price": 300, "resource": 800, "discount": 0.2},
            ]
        },
        headers=h,
    )
    return s, p


async def test_create_scenario_and_persist(client, auth_headers, mock_temporal):
    h = await auth_headers("form@example.com")
    await _seed(client, h)

    created = await client.post(
        "/api/formations",
        json={
            "name": "F1",
            "b_total": 5000,
            "algorithm": "ant_colony",
            "params": {"Kmax": 10, "num_ants": 5, "alpha": 1, "beta": 2, "p": 0.1, "tau": 1},
        },
        headers=h,
    )
    assert created.status_code == 201
    sid = created.json()["id"]
    assert created.json()["status"] == "pending"

    # start_workflow was called with the int-truncated payload and scenario id
    assert len(mock_temporal.calls) == 1
    wf_input = mock_temporal.calls[0][0][1]
    assert wf_input.c == [[500, 0], [0, 300]]
    assert wf_input.b_ij == [[1000, 0], [0, 800]]
    assert wf_input.b_total == 5000
    assert wf_input.scenario_id == sid

    # pending detail has no assignments yet
    pending = await client.get(f"/api/formations/{sid}", headers=h)
    assert pending.json()["status"] in ("pending", "running")
    assert pending.json()["assignments"] == []

    # simulate the worker writing back the result (assign SvcA->ProvA, SvcB->ProvB)
    from worker.activities import persist_formation_result_activity
    from worker.types import PersistFormationInput

    await persist_formation_result_activity(
        PersistFormationInput(scenario_id=sid, solution=[[1, 0], [0, 1]], value=690.0)
    )

    detail = (await client.get(f"/api/formations/{sid}", headers=h)).json()
    assert detail["status"] == "completed"
    assert detail["value"] == 690.0
    totals = detail["totals"]
    # F = (1-0.1)*500 + (1-0.2)*300 = 450 + 240 = 690
    assert totals["total_revenue"] == 690.0
    assert totals["total_resource_used"] == 1800.0
    assert totals["provider_count"] == 2
    assert totals["service_count"] == 2
    assert len(detail["assignments"]) == 2


async def test_formation_requires_catalogue(client, auth_headers, mock_temporal):
    h = await auth_headers("empty@example.com")
    r = await client.post(
        "/api/formations",
        json={"name": "X", "b_total": 100, "algorithm": "probabilistic", "params": {"Kmax": 10}},
        headers=h,
    )
    assert r.status_code == 400


async def test_csv_export(client, auth_headers, mock_temporal):
    h = await auth_headers("csv@example.com")
    await _seed(client, h)
    sid = (
        await client.post(
            "/api/formations",
            json={"name": "F", "b_total": 5000, "algorithm": "probabilistic", "params": {"Kmax": 10}},
            headers=h,
        )
    ).json()["id"]

    from worker.activities import persist_formation_result_activity
    from worker.types import PersistFormationInput

    await persist_formation_result_activity(
        PersistFormationInput(scenario_id=sid, solution=[[1, 0], [0, 0]], value=450.0)
    )

    res = await client.get(f"/api/formations/{sid}/export.csv", headers=h)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.strip().splitlines()
    assert lines[0] == "service,provider,price,discount,final_discount,effective_revenue,resource_used"
    assert len(lines) == 2  # header + one assignment


# ---------------------------------------------------------------------------
# Service-group all-or-nothing (runs the REAL Rust solver, then expands)
# ---------------------------------------------------------------------------

async def _solve(wf_input):
    """Run the real solver activity on the captured workflow payload."""
    from worker.activities import run_algorithm_activity
    from worker.types import RunAlgorithmInput

    run_input = RunAlgorithmInput(
        m=wf_input.m, n=wf_input.n, c=wf_input.c, b_ij=wf_input.b_ij,
        b_total=wf_input.b_total, omega=wf_input.omega, algorithm=wf_input.algorithm,
        ant_colony_params=wf_input.ant_colony, probabilistic_params=wf_input.probabilistic,
        variant_key="test", redis_channel=None,
    )
    return await run_algorithm_activity(run_input)


async def _seed_group(client, h, b_total_resource_each):
    """One group {SvcA, SvcB} + ungrouped SvcC; two providers; per-provider
    group resource = b_total_resource_each so callers can size b_total."""
    s = {n: (await client.post("/api/services", json={"name": n}, headers=h)).json()["id"]
         for n in ["SvcA", "SvcB", "SvcC"]}
    await client.post("/api/service-groups",
                      json={"name": "Пакет", "member_ids": [s["SvcA"], s["SvcB"]]}, headers=h)
    p = {n: (await client.post("/api/providers", json={"name": n}, headers=h)).json()["id"]
         for n in ["ProvA", "ProvB"]}
    # group resource per provider = 600 + 400 = 1000; SvcC = 300
    cells = []
    for pid in p.values():
        cells += [
            {"service_id": s["SvcA"], "provider_id": pid, "price": 500, "resource": 600, "discount": 0.1},
            {"service_id": s["SvcB"], "provider_id": pid, "price": 300, "resource": 400, "discount": 0.2},
            {"service_id": s["SvcC"], "provider_id": pid, "price": 250, "resource": 300, "discount": 0.0},
        ]
    await client.post("/api/planning/bulk", json={"cells": cells}, headers=h)
    return s, p


async def test_group_all_or_nothing(client, auth_headers, mock_temporal):
    h = await auth_headers("grp@example.com")
    s, _ = await _seed_group(client, h, 1000)

    created = await client.post(
        "/api/formations",
        json={"name": "G", "b_total": 100000, "algorithm": "probabilistic", "params": {"Kmax": 300}},
        headers=h,
    )
    sid = created.json()["id"]
    wf = mock_temporal.calls[-1][0][1]
    # 2 units: the group + ungrouped SvcC
    assert wf.m == 2
    # group unit aggregates both services: price 800, resource 1000 per provider
    assert [800, 800] in wf.c and [1000, 1000] in wf.b_ij

    result = await _solve(wf)
    from worker.activities import persist_formation_result_activity
    from worker.types import PersistFormationInput
    await persist_formation_result_activity(
        PersistFormationInput(scenario_id=sid, solution=result.solution, value=result.value)
    )

    detail = (await client.get(f"/api/formations/{sid}", headers=h)).json()
    group_svc = {s["SvcA"], s["SvcB"]}
    per_provider: dict[str, set] = {}
    for a in detail["assignments"]:
        if a["service_id"] in group_svc:
            per_provider.setdefault(a["provider_id"], set()).add(a["service_id"])
            assert a["group_name"] == "Пакет"
    # never one alone: each provider has both group services or neither
    assert per_provider, "group should be selected somewhere with b_total this large"
    for assigned in per_provider.values():
        assert assigned == group_svc

    # Σ effective_revenue reconciles with the solver value
    total_eff = sum(a["effective_revenue"] for a in detail["assignments"])
    assert abs(total_eff - detail["value"]) <= 1e-6


async def test_group_excluded_when_too_big(client, auth_headers, mock_temporal):
    h = await auth_headers("grpbig@example.com")
    s, _ = await _seed_group(client, h, 1000)

    # b_total below the group's per-provider resource (1000) but above SvcC (300):
    # the group unit can never be selected, SvcC can.
    created = await client.post(
        "/api/formations",
        json={"name": "GBig", "b_total": 900, "algorithm": "probabilistic", "params": {"Kmax": 300}},
        headers=h,
    )
    sid = created.json()["id"]
    wf = mock_temporal.calls[-1][0][1]
    result = await _solve(wf)
    from worker.activities import persist_formation_result_activity
    from worker.types import PersistFormationInput
    await persist_formation_result_activity(
        PersistFormationInput(scenario_id=sid, solution=result.solution, value=result.value)
    )

    detail = (await client.get(f"/api/formations/{sid}", headers=h)).json()
    group_svc = {s["SvcA"], s["SvcB"]}
    assert all(a["service_id"] not in group_svc for a in detail["assignments"]), \
        "group must not be assigned when it exceeds b_total for every provider"


async def test_one_service_one_group_enforced(client, auth_headers):
    h = await auth_headers("onegrp@example.com")
    a = (await client.post("/api/services", json={"name": "A"}, headers=h)).json()["id"]
    await client.post("/api/service-groups", json={"name": "G1", "member_ids": [a]}, headers=h)
    # adding the same service to a second group is rejected
    r = await client.post("/api/service-groups", json={"name": "G2", "member_ids": [a]}, headers=h)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Per-iteration convergence history
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402


class _FakeWorkerRedis:
    """Stand-in for the worker's Redis stream used by the persist activity."""

    def __init__(self, entries, fail=False):
        self._entries = entries
        self._fail = fail
        self.deleted = []

    async def xrange(self, key, min="-", max="+"):
        if self._fail:
            raise RuntimeError("redis unavailable")
        return self._entries

    async def delete(self, key):
        self.deleted.append(key)


def _iter_entries(n):
    return [
        (f"{i}-0", {"data": _json.dumps(
            {"type": "iteration", "algorithm": "probabilistic",
             "iteration": i, "current_best_value": 1000.0 + i})})
        for i in range(n)
    ]


async def _make_completed_formation(client, h):
    s = [(await client.post("/api/services", json={"name": n}, headers=h)).json()["id"]
         for n in ["SvcA", "SvcB"]]
    p = [(await client.post("/api/providers", json={"name": n}, headers=h)).json()["id"]
         for n in ["ProvA", "ProvB"]]
    await client.post("/api/planning/bulk", json={"cells": [
        {"service_id": s[0], "provider_id": p[0], "price": 500, "resource": 1000, "discount": 0.1},
        {"service_id": s[1], "provider_id": p[1], "price": 300, "resource": 800, "discount": 0.2},
    ]}, headers=h)
    created = await client.post(
        "/api/formations",
        json={"name": "IT", "b_total": 5000, "algorithm": "probabilistic", "params": {"Kmax": 10}},
        headers=h,
    )
    return created.json()["id"]


async def test_iteration_history_persisted_and_idempotent(client, auth_headers, mock_temporal):
    from worker import activities
    from worker.activities import persist_formation_result_activity
    from worker.types import PersistFormationInput

    h = await auth_headers("iters@example.com")
    sid = await _make_completed_formation(client, h)
    fake = _FakeWorkerRedis(_iter_entries(10))
    activities.set_redis_client(fake)
    try:
        payload = PersistFormationInput(
            scenario_id=sid, solution=[[1, 0], [0, 1]], value=690.0,
            redis_channel=f"formation:{sid}",
        )
        await persist_formation_result_activity(payload)
        await persist_formation_result_activity(payload)  # idempotent re-run
    finally:
        activities.set_redis_client(None)

    its = (await client.get(f"/api/formations/{sid}/iterations", headers=h)).json()
    assert [r["iteration"] for r in its] == list(range(10))  # ordered, exactly 10
    assert its[0]["best_value"] == 1000.0 and its[9]["best_value"] == 1009.0
    assert f"formation:{sid}" in fake.deleted  # stream freed after draining


async def test_scenario_completes_when_redis_unavailable(client, auth_headers, mock_temporal):
    from worker import activities
    from worker.activities import persist_formation_result_activity
    from worker.types import PersistFormationInput

    h = await auth_headers("itersdown@example.com")
    sid = await _make_completed_formation(client, h)
    activities.set_redis_client(_FakeWorkerRedis([], fail=True))
    try:
        await persist_formation_result_activity(PersistFormationInput(
            scenario_id=sid, solution=[[1, 0], [0, 1]], value=690.0,
            redis_channel=f"formation:{sid}",
        ))
    finally:
        activities.set_redis_client(None)

    detail = (await client.get(f"/api/formations/{sid}", headers=h)).json()
    assert detail["status"] == "completed"  # result still recorded
    its = (await client.get(f"/api/formations/{sid}/iterations", headers=h)).json()
    assert its == []  # history degraded, but scenario intact
