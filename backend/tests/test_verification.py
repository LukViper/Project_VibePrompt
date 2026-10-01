"""Requirement verification records."""

from datetime import datetime, timezone

from app.schemas.agent_verification import RequirementVerification, VerificationResultStatus
from app.services.project_state import empty_state


def test_requirement_verification_record():
    state = empty_state()
    record = RequirementVerification(
        id="VER-001",
        requirement_id="REQ-009",
        agent_run_id="RUN-001",
        status=VerificationResultStatus.PASS,
        evidence=["benchmark.json"],
        confidence=0.91,
        verified_at=datetime.now(timezone.utc).isoformat(),
    ).as_dict()
    state.setdefault("requirement_verifications", []).append(record)
    assert state["requirement_verifications"][0]["status"] == "PASS"


def test_partial_verification():
    record = RequirementVerification(
        id="VER-002",
        requirement_id="REQ-010",
        status=VerificationResultStatus.PARTIAL,
    ).as_dict()
    assert record["status"] == "PARTIAL"


def test_failed_verification():
    record = RequirementVerification(
        id="VER-003",
        requirement_id="REQ-011",
        status=VerificationResultStatus.FAIL,
    ).as_dict()
    assert record["status"] == "FAIL"
