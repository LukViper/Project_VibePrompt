"""Compiler filtering + compilation report."""

from app.services.assertion_lifecycle import requirement_is_compilable
from app.services.project_state import empty_state
from app.services.prompt_compiler import compilation_gate, _normalize_from_state


def _state_mixed():
    state = empty_state()
    state["project"]["objective"] = "Build a phishing detector"
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Classify phishing emails",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "acceptance": "F1 reported",
            "type": "functional",
            "provenance": {"source": "USER", "user_approved": True},
        },
        {
            "id": "REQ-002",
            "text": "Inferred nice-to-have",
            "status": "active",
            "assertion_status": "INFERRED",
            "type": "functional",
            "provenance": {"source": "INFERRED"},
        },
        {
            "id": "REQ-003",
            "text": "Proposed feature",
            "status": "active",
            "assertion_status": "PROPOSED",
            "type": "functional",
            "provenance": {"source": "USER", "user_approved": False},
        },
        {
            "id": "REQ-004",
            "text": "Old feature",
            "status": "superseded",
            "assertion_status": "SUPERSEDED",
            "superseded_by": "REQ-011",
            "type": "functional",
            "provenance": {"source": "USER"},
        },
        {
            "id": "REQ-005",
            "text": "Rejected feature",
            "status": "removed",
            "assertion_status": "REJECTED",
            "type": "functional",
            "provenance": {"source": "USER"},
        },
    ]
    return state


def test_only_compilable_requirements_enter_specification():
    state = _state_mixed()
    structured = _normalize_from_state(state, {})
    ids = [r["id"] for r in (structured.get("functional") or []) + (structured.get("nonfunctional") or [])]
    assert ids == ["REQ-001"]
    assert "REQ-002" not in ids
    assert "REQ-003" not in ids
    assert "REQ-004" not in ids
    assert "REQ-005" not in ids
    assert requirement_is_compilable(state["requirements"][0])
    assert not requirement_is_compilable(state["requirements"][1])


def test_excluded_requirement_has_reason():
    report = compilation_gate(_state_mixed())
    excluded = {item["id"]: item["reason"] for item in report["excluded_requirements"]}
    assert "REQ-002" in excluded
    assert "INFERRED" in excluded["REQ-002"]
    assert "PROPOSED" in excluded["REQ-003"]
    assert "SUPERSEDED by REQ-011" in excluded["REQ-004"]
    assert "REJECTED" in excluded["REQ-005"]


def test_blocking_grill_attack_prevents_compilation():
    state = _state_mixed()
    state["grill_attacks"] = [
        {
            "id": "ATTACK-017",
            "target_type": "REQUIREMENT",
            "target_id": "REQ-001",
            "attack_type": "FeasibilityAttackGenerator",
            "challenge": "No latency threshold",
            "severity": "HIGH",
            "status": "OPEN",
            "blocking": True,
        }
    ]
    report = compilation_gate(state)
    assert report["can_compile"] is False
    assert any(i["type"] == "UNRESOLVED_GRILL_ATTACK" for i in report["blocking_issues"])


def test_compilation_report_contains_diagnostics():
    report = compilation_gate(_state_mixed())
    assert "included_requirements" in report
    assert "excluded_requirements" in report
    assert "traceability_status" in report
    assert "grill_status" in report
    assert "evidence_status" in report
    assert report["included_requirements"][0]["id"] == "REQ-001"


def test_compilation_report_endpoint(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks. Phishing detector."},
    )
    project_id = created.json()["id"]
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "The system must classify phishing emails."},
    )
    report = client.get(f"/projects/{project_id}/prompt/report")
    assert report.status_code == 200
    body = report.json()
    assert "can_compile" in body
    assert "included_requirements" in body
    assert "excluded_requirements" in body
