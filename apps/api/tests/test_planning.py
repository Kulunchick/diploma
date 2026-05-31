async def _setup(client, h):
    s = [
        (await client.post("/api/services", json={"name": n}, headers=h)).json()["id"]
        for n in ["S1", "S2"]
    ]
    p = (await client.post("/api/providers", json={"name": "P1"}, headers=h)).json()["id"]
    return s, p


async def test_bulk_and_single_upsert(client, auth_headers):
    h = await auth_headers("plan@example.com")
    s, p = await _setup(client, h)

    bulk = await client.post(
        "/api/planning/bulk",
        json={
            "cells": [
                {"service_id": s[0], "provider_id": p, "price": 500, "resource": 1000, "discount": 0.1},
                {"service_id": s[1], "provider_id": p, "price": 300, "resource": 800, "discount": 0.2},
            ]
        },
        headers=h,
    )
    assert bulk.status_code == 200
    assert len(bulk.json()) == 2

    # single upsert overwrites the existing (S1, P1) cell — no duplicate row
    single = await client.put(
        "/api/planning/cell",
        json={"service_id": s[0], "provider_id": p, "price": 999, "resource": 1, "discount": 0.5},
        headers=h,
    )
    assert single.status_code == 200
    assert single.json()["price"] == 999

    cells = (await client.get("/api/planning", headers=h)).json()
    assert len(cells) == 2


async def test_discount_validation(client, auth_headers):
    h = await auth_headers("planval@example.com")
    s, p = await _setup(client, h)
    r = await client.put(
        "/api/planning/cell",
        json={"service_id": s[0], "provider_id": p, "discount": 1.0},
        headers=h,
    )
    assert r.status_code == 422


async def test_deleting_service_removes_cells(client, auth_headers):
    h = await auth_headers("plancascade@example.com")
    s, p = await _setup(client, h)
    await client.post(
        "/api/planning/bulk",
        json={"cells": [{"service_id": s[0], "provider_id": p, "price": 1, "resource": 1, "discount": 0}]},
        headers=h,
    )
    assert len((await client.get("/api/planning", headers=h)).json()) == 1

    await client.delete(f"/api/services/{s[0]}", headers=h)
    assert (await client.get("/api/planning", headers=h)).json() == []
