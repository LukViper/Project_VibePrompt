"""Traceability lineage and integrity endpoints."""

from app.schemas.traceability import TraceEntityType, TraceRelationship
from app.services.project_state import empty_state
from app.services.traceability import add_trace_link, get_requirement_lineage, validate_traceability


def test_requirement_lineage():
    state = empty_state()
    state["requirements"] = [
        {"id": "REQ-009", "text": "latency <= 500ms", "status": "active", "assertion_status": "CONFIRMED"}
    ]
    add_trace_link(
        state,
        source_type=TraceEntityType.REQUIREMENT,
        source_id="REQ-009",
        target_type=TraceEntityType.CLAIM,
        target_id="CLAIM-003",
        relationship=TraceRelationship.DERIVED_FROM,
    )
    add_trace_link(
        state,
        source_type=TraceEntityType.CLAIM,
        source_id="CLAIM-003",
        target_type=TraceEntityType.EVIDENCE,
        target_id="EVIDENCE-004",
        relationship=TraceRelationship.SUPPORTED_BY,
    )
    add_trace_link(
        state,
        source_type=TraceEntityType.ATTACK,
        source_id="ATTACK-017",
        target_type=TraceEntityType.REQUIREMENT,
        target_id="REQ-009",
        relationship=TraceRelationship.CHALLENGES,
    )
    add_trace_link(
        state,
        source_type=TraceEntityType.ATTACK,
        source_id="ATTACK-017",
        target_type=TraceEntityType.DECISION,
        target_id="DEC-012",
        relationship=TraceRelationship.RESOLVES,
    )
    lineage = get_requirement_lineage(state, "REQ-009")
    assert lineage["requirement_id"] == "REQ-009"
    assert lineage["chains"]
    entity_ids = {step["entity_id"] for chain in lineage["chains"] for step in chain}
    assert "CLAIM-003" in entity_ids
    assert "EVIDENCE-004" in entity_ids or "ATTACK-017" in entity_ids


def test_attack_to_decision_trace():
    state = empty_state()
    add_trace_link(
        state,
        source_type=TraceEntityType.ATTACK,
        source_id="ATTACK-021",
        target_type=TraceEntityType.DECISION,
        target_id="DEC-012",
        relationship=TraceRelationship.RESOLVES,
    )
    add_trace_link(
        state,
        source_type=TraceEntityType.DECISION,
        source_id="DEC-012",
        target_type=TraceEntityType.REQUIREMENT,
        target_id="REQ-009",
        relationship=TraceRelationship.AFFECTS,
    )
    lineage = get_requirement_lineage(state, "REQ-009")
    ids = {step["entity_id"] for chain in lineage["chains"] for step in chain}
    assert "DEC-012" in ids
    assert "ATTACK-021" in ids


def test_evidence_to_claim_trace():
    state = empty_state()
    add_trace_link(
        state,
        source_type=TraceEntityType.CLAIM,
        source_id="CLAIM-001",
        target_type=TraceEntityType.EVIDENCE,
        target_id="EVIDENCE-001",
        relationship=TraceRelationship.SUPPORTED_BY,
    )
    assert any(link["relationship"] == "SUPPORTED_BY" for link in state["trace_links"])


def test_broken_traceability_detected():
    state = empty_state()
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Needs acceptance",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "provenance": {"source": "USER"},
        }
    ]
    report = validate_traceability(state)
    assert any(w["type"] == "MISSING_ACCEPTANCE_CRITERIA" for w in report["warnings"])


def test_integrity_endpoint(client):
    created = client.post("/projects", json={"description": "NLP phishing detector"})
    project_id = created.json()["id"]
    result = client.get(f"/projects/{project_id}/integrity")
    assert result.status_code == 200
    body = result.json()
    for key in (
        "requirements",
        "decisions",
        "assumptions",
        "evidence",
        "grill",
        "traceability",
        "verification",
        "compilation",
    ):
        assert key in body
    assert "score" not in body


def test_integrity_changes_after_grill_resolution(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks. Phishing detector."},
    )
    project_id = created.json()["id"]
    client.post(f"/projects/{project_id}/messages", json={"content": "Detect phishing emails in real time."})
    client.post(f"/projects/{project_id}/grill")
    before = client.get(f"/projects/{project_id}/integrity").json()
    open_before = before["grill"]["open"]
    listing = client.get(f"/projects/{project_id}/grill").json()
    if listing["open"]:
        attack_id = listing["open"][0]["id"]
        client.post(
            f"/projects/{project_id}/grill/{attack_id}/respond",
            json={"response_text": "Defer for now.", "resolution_type": "DEFERRED", "mutate": False},
        )
        after = client.get(f"/projects/{project_id}/integrity").json()
        assert after["grill"]["deferred"] >= 1 or after["grill"]["open"] <= open_before


def test_integrity_changes_after_requirement_confirmation(client):
    created = client.post("/projects", json={"title": "Confirm"})
    project_id = created.json()["id"]
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "I need an NLP phishing classifier requirement: classify emails."},
    )
    state = client.get(f"/projects/{project_id}/state").json()
    req = state["requirements"][0]
    before = client.get(f"/projects/{project_id}/integrity").json()["requirements"]["confirmed"]
    if req.get("assertion_status") == "PROPOSED":
        client.post(f"/projects/{project_id}/assertions/{req['id']}/confirm")
        after = client.get(f"/projects/{project_id}/integrity").json()["requirements"]["confirmed"]
        assert after >= before
    elif req.get("assertion_status") in {"CONFIRMED", "LOCKED"}:
        assert before >= 1


def test_lineage_endpoint(client):
    created = client.post("/projects", json={"description": "NLP phishing"})
    project_id = created.json()["id"]
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "The system must classify phishing emails."},
    )
    state = client.get(f"/projects/{project_id}/state").json()
    req_id = state["requirements"][0]["id"]
    result = client.get(f"/projects/{project_id}/requirements/{req_id}/lineage")
    assert result.status_code == 200
    assert result.json()["requirement_id"] == req_id
