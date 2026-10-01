"""Phase 9 — guest + login authentication and project isolation."""

from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_roundtrip():
    encoded = hash_password("correct horse battery")
    assert verify_password("correct horse battery", encoded)
    assert not verify_password("wrong password", encoded)


def test_token_roundtrip():
    token = create_access_token(user_id="11111111-1111-1111-1111-111111111111", is_guest=True)
    payload = decode_access_token(token)
    assert payload["guest"] is True
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"


def test_guest_continue(client):
    guest = client.post("/auth/guest")
    assert guest.status_code == 200
    body = guest.json()
    assert body["access_token"]
    assert body["user"]["is_guest"] is True
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["is_guest"] is True


def test_register_login_and_isolation(client):
    registered = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "password123", "display_name": "Alice"},
    )
    assert registered.status_code == 200
    token_a = registered.json()["access_token"]
    assert registered.json()["user"]["is_guest"] is False

    other = client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "password123"},
    )
    token_b = other.json()["access_token"]

    created = client.post(
        "/projects",
        json={"title": "Alice Project", "description": "I need a project for NLP."},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]
    assert created.json()["is_ephemeral"] is False
    assert created.json()["user_id"]

    # Owner can read
    ok = client.get(f"/projects/{project_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert ok.status_code == 200

    # Other user forbidden
    denied = client.get(f"/projects/{project_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert denied.status_code == 403

    # Unauthenticated cannot read owned project
    anon = client.get(f"/projects/{project_id}")
    assert anon.status_code == 401

    listed = client.get("/projects", headers={"Authorization": f"Bearer {token_a}"})
    assert listed.status_code == 200
    assert any(item["id"] == project_id for item in listed.json())

    login = client.post("/auth/login", json={"email": "alice@example.com", "password": "password123"})
    assert login.status_code == 200
    assert login.json()["user"]["email"] == "alice@example.com"


def test_guest_project_is_ephemeral(client):
    guest = client.post("/auth/guest").json()
    token = guest["access_token"]
    created = client.post(
        "/projects",
        json={"title": "Temp"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 200
    assert created.json()["is_ephemeral"] is True
    assert created.json()["user_id"] == guest["user"]["id"]


def test_anonymous_legacy_project_still_works(client):
    """Existing test style: create without auth remains allowed for anonymous rows."""
    created = client.post("/projects", json={"description": "I need a project for NLP."})
    assert created.status_code == 200
    assert created.json()["user_id"] is None
    project_id = created.json()["id"]
    state = client.get(f"/projects/{project_id}/state")
    assert state.status_code == 200


def test_claim_anonymous_project(client):
    created = client.post("/projects", json={"title": "Orphan"})
    project_id = created.json()["id"]
    registered = client.post(
        "/auth/register",
        json={"email": "claim@example.com", "password": "password123"},
    )
    token = registered.json()["access_token"]
    claimed = client.post(f"/projects/{project_id}/claim", headers={"Authorization": f"Bearer {token}"})
    assert claimed.status_code == 200
    assert claimed.json()["user_id"] == registered.json()["user"]["id"]
    assert claimed.json()["is_ephemeral"] is False


def test_duplicate_register_rejected(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    again = client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert again.status_code == 409
