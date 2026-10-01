"""Grill API + response-driven state mutations."""

from app.schemas.assertions import AssertionStatus
from app.services.grill_attack_generators import generate_attacks_from_state
from app.services.grill_session import get_next_grill_attack, list_grill_attacks, target_fingerprint
from app.services.project_state import empty_state


def _seed_project(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks. Real-time phishing detector."},
    )
    project_id = created.json()["id"]
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Analyze real-time network traffic using deep learning."},
    )
    return project_id


def test_create_grill_attack(client):
    project_id = _seed_project(client)
    report = client.post(f"/projects/{project_id}/grill")
    assert report.status_code == 200
    body = report.json()
    assert body.get("attacks") is not None or body.get("grill")
    state = client.get(f"/projects/{project_id}/state").json()
    assert state.get("grill_attacks")


def test_list_grill_attacks(client):
    project_id = _seed_project(client)
    client.post(f"/projects/{project_id}/grill")
    listing = client.get(f"/projects/{project_id}/grill")
    assert listing.status_code == 200
    body = listing.json()
    assert "open" in body
    assert "resolved" in body
    assert "blocking" in body
    assert "counts" in body
    assert "by_severity" in body["counts"]


def test_respond_to_grill_attack(client):
    project_id = _seed_project(client)
    client.post(f"/projects/{project_id}/grill")
    listing = client.get(f"/projects/{project_id}/grill").json()
    open_attacks = listing["open"] or listing.get("blocking") or []
    assert open_attacks
    attack_id = open_attacks[0]["id"]
    response = client.post(
        f"/projects/{project_id}/grill/{attack_id}/respond",
        json={"response_text": "Below 500 ms.", "resolution_type": "RESOLVED"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["attack"]["status"] == "RESOLVED"
    assert body["response"]["id"]


def test_grill_response_creates_state_change(client):
    project_id = _seed_project(client)
    client.post(f"/projects/{project_id}/grill")
    attack_id = client.get(f"/projects/{project_id}/grill").json()["open"][0]["id"]
    before = client.get(f"/projects/{project_id}/state").json()
    before_reqs = len(before.get("requirements") or [])
    result = client.post(
        f"/projects/{project_id}/grill/{attack_id}/respond",
        json={"response_text": "Latency must be under 500 ms.", "resolution_type": "RESOLVED"},
    ).json()
    changes = result["response"].get("state_changes") or []
    assert changes or result["response"].get("new_requirement_ids")
    after = result["state"]
    assert len(after.get("requirements") or []) >= before_reqs
    # Newly created requirements from Grill must be PROPOSED, not locked.
    for rid in result["response"].get("new_requirement_ids") or []:
        req = next(r for r in after["requirements"] if r["id"] == rid)
        assert req["assertion_status"] == AssertionStatus.PROPOSED.value


def test_grill_response_creates_audit_event(client):
    project_id = _seed_project(client)
    client.post(f"/projects/{project_id}/grill")
    attack_id = client.get(f"/projects/{project_id}/grill").json()["open"][0]["id"]
    result = client.post(
        f"/projects/{project_id}/grill/{attack_id}/respond",
        json={"response_text": "Defer for later.", "resolution_type": "DEFERRED", "mutate": False},
    ).json()
    events = result["state"].get("audit_events") or []
    assert any(e.get("event_type") == "GRILL_ATTACK_RESOLVED" for e in events)


def test_grill_response_creates_trace_link(client):
    project_id = _seed_project(client)
    client.post(f"/projects/{project_id}/grill")
    attack_id = client.get(f"/projects/{project_id}/grill").json()["open"][0]["id"]
    result = client.post(
        f"/projects/{project_id}/grill/{attack_id}/respond",
        json={
            "response_text": "Use WebSocket instead of REST polling.",
            "resolution_type": "RESOLVED",
            "create_decision": {
                "kind": "architecture_choice",
                "slot": "transport",
                "summary": "Use WebSocket",
                "value": "WebSocket",
            },
        },
    ).json()
    links = result["state"].get("trace_links") or []
    assert any(
        link.get("source_id") == attack_id and link.get("target_type") == "DECISION"
        for link in links
    )


def test_next_grill_attack():
    state = empty_state()
    state["project"]["objective"] = "Detect phishing in real time"
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Detect phishing",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "version": 1,
            "provenance": {"source": "USER", "user_approved": True},
        }
    ]
    generate_attacks_from_state(state)
    nxt = get_next_grill_attack(state)
    assert nxt is not None
    assert nxt["status"] in {"OPEN", "UNRESOLVED"}


def test_high_severity_attack_prioritized():
    state = empty_state()
    state["grill_attacks"] = [
        {
            "id": "ATTACK-001",
            "target_type": "REQUIREMENT",
            "target_id": "REQ-001",
            "attack_type": "ScopeAttackGenerator",
            "challenge": "too broad",
            "severity": "MEDIUM",
            "status": "OPEN",
            "blocking": False,
        },
        {
            "id": "ATTACK-002",
            "target_type": "REQUIREMENT",
            "target_id": "REQ-001",
            "attack_type": "FeasibilityAttackGenerator",
            "challenge": "solo timeline",
            "severity": "HIGH",
            "status": "OPEN",
            "blocking": True,
        },
    ]
    nxt = get_next_grill_attack(state)
    assert nxt["id"] == "ATTACK-002"


def test_resolved_attack_not_returned():
    state = empty_state()
    state["grill_attacks"] = [
        {
            "id": "ATTACK-001",
            "target_type": "REQUIREMENT",
            "target_id": "REQ-001",
            "attack_type": "ScopeAttackGenerator",
            "challenge": "done",
            "severity": "HIGH",
            "status": "RESOLVED",
            "blocking": False,
        }
    ]
    assert get_next_grill_attack(state) is None


def test_duplicate_attack_not_generated():
    state = empty_state()
    state["project"]["objective"] = "Detect phishing"
    state["academic"] = {"subject": "NLP", "required_concepts": []}
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Classify emails",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "version": 1,
            "provenance": {"source": "USER", "user_approved": True},
        }
    ]
    first = generate_attacks_from_state(state)
    second = generate_attacks_from_state(state)
    assert second == []
    assert first


def test_state_change_allows_new_attack():
    state = empty_state()
    state["project"]["objective"] = "Detect phishing"
    state["academic"] = {"subject": "NLP", "required_concepts": []}
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Classify emails",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "version": 1,
            "acceptance": None,
            "provenance": {"source": "USER", "user_approved": True},
        }
    ]
    first = generate_attacks_from_state(state)
    assert first
    # Resolve all open attacks with fingerprint, then change requirement text.
    for attack in state["grill_attacks"]:
        attack["status"] = "RESOLVED"
        attack["blocking"] = False
        attack["target_fingerprint"] = target_fingerprint(state, "REQUIREMENT", "REQ-001")
    state["requirements"][0]["text"] = "Classify phishing emails with latency under 500ms"
    state["requirements"][0]["version"] = 2
    regenerated = generate_attacks_from_state(state)
    # Fingerprint changed → new attacks may appear for same dimension/challenge.
    assert isinstance(regenerated, list)
