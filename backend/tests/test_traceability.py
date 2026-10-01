"""Trace links and validation."""

from app.services.project_state import empty_state
from app.services.traceability import add_trace_link, validate_traceability
from app.schemas.traceability import TraceEntityType, TraceRelationship


def test_requirement_trace():
    state = empty_state()
    add_trace_link(
        state,
        source_type=TraceEntityType.REQUIREMENT,
        source_id="REQ-001",
        target_type=TraceEntityType.CLAIM,
        target_id="CLAIM-001",
        relationship=TraceRelationship.DERIVED_FROM,
    )
    assert len(state["trace_links"]) == 1


def test_broken_trace_detection_warns_missing_acceptance():
    state = empty_state()
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Real-time response",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "provenance": {"source": "USER"},
        }
    ]
    report = validate_traceability(state)
    assert any(w["type"] == "MISSING_ACCEPTANCE_CRITERIA" for w in report["warnings"])
