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


@pytest.fixture
def mock_temporal():
    from src.operations.main import app

    mock = _MockTemporal()
    app.state.temporal = mock
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
    assert lines[0] == "service,provider,price,discount,effective_revenue,resource_used"
    assert len(lines) == 2  # header + one assignment
