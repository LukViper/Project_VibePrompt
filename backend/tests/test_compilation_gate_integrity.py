"""Compilation gate respects assertion lifecycle."""

from app.services.prompt_compiler import compilation_gate
from app.services.project_state import empty_state


def test_rejected_requirement_not_compilable():
    state = empty_state()
    state["project"]["objective"] = "Build an app"
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Rejected feature",
            "status": "active",
            "assertion_status": "REJECTED",
            "provenance": {"source": "USER"},
        }
    ]
    trace = __import__("app.services.traceability", fromlist=["validate_traceability"]).validate_traceability(state)
    assert "REQ-001" not in trace["compilable_requirements"]


def test_missing_acceptance_criteria_detected():
    state = empty_state()
    state["project"]["objective"] = "Build an app"
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Feature",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "provenance": {"source": "USER", "user_approved": True},
        }
    ]
    report = __import__("app.services.traceability", fromlist=["validate_traceability"]).validate_traceability(state)
    assert any(w["type"] == "MISSING_ACCEPTANCE_CRITERIA" for w in report["warnings"])
