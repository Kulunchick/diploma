async def test_service_crud(client, auth_headers):
    h = await auth_headers("svc@example.com")

    created = await client.post("/api/services", json={"name": "DNS", "description": "d"}, headers=h)
    assert created.status_code == 201
    sid = created.json()["id"]

    listed = await client.get("/api/services", headers=h)
    assert [s["name"] for s in listed.json()] == ["DNS"]

    got = await client.get(f"/api/services/{sid}", headers=h)
    assert got.status_code == 200

    updated = await client.put(
        f"/api/services/{sid}", json={"name": "DNS+", "description": None}, headers=h
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "DNS+"

    deleted = await client.delete(f"/api/services/{sid}", headers=h)
    assert deleted.status_code == 204
    assert (await client.get("/api/services", headers=h)).json() == []


async def test_duplicate_name_rejected(client, auth_headers):
    h = await auth_headers("dupsvc@example.com")
    await client.post("/api/services", json={"name": "VPN"}, headers=h)
    r = await client.post("/api/services", json={"name": "VPN"}, headers=h)
    assert r.status_code == 409


async def test_user_isolation(client, auth_headers):
    h1 = await auth_headers("owner1@example.com")
    h2 = await auth_headers("owner2@example.com")

    created = await client.post("/api/services", json={"name": "Hosting"}, headers=h1)
    sid = created.json()["id"]

    # user2 sees an empty catalogue and cannot read user1's service
    assert (await client.get("/api/services", headers=h2)).json() == []
    assert (await client.get(f"/api/services/{sid}", headers=h2)).status_code == 404
    assert (await client.delete(f"/api/services/{sid}", headers=h2)).status_code == 404
