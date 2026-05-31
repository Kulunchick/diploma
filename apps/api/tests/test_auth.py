async def test_register_login_me_happy_path(client):
    r = await client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "secret123", "full_name": "Alice"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "alice@example.com"
    assert "password" not in body["user"]
    assert body["access_token"]

    login = await client.post(
        "/api/auth/login", data={"username": "alice@example.com", "password": "secret123"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


async def test_duplicate_email_rejected(client):
    await client.post("/api/auth/register", json={"email": "dup@example.com", "password": "secret123"})
    r = await client.post("/api/auth/register", json={"email": "dup@example.com", "password": "secret123"})
    assert r.status_code == 409


async def test_bad_password_rejected(client):
    await client.post("/api/auth/register", json={"email": "bob@example.com", "password": "secret123"})
    r = await client.post(
        "/api/auth/login", data={"username": "bob@example.com", "password": "wrongpass"}
    )
    assert r.status_code == 401


async def test_me_requires_auth(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401
