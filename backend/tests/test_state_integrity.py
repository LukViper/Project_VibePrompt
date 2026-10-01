"""Assertion lifecycle, claims, assumptions, evidence."""

from app.schemas.assertions import AssertionStatus, ClaimSource, EvidenceType
from app.schemas.provenance import ProvenanceSource
from app.services.assertion_lifecycle import (
    default_requirement_assertion_status,
    inferred_not_confirmed,
    is_inactive_assertion,
    promotion_allowed,
    requirement_is_compilable,
)
from app.services.integrity_store import add_assumption, add_claim, add_evidence
from app.services.project_state import empty_state
from app.schemas.state import migrate_state


def test_inferred_not_confirmed():
    assert inferred_not_confirmed(AssertionStatus.INFERRED)
    assert inferred_not_confirmed(AssertionStatus.PROPOSED)
    assert not inferred_not_confirmed(AssertionStatus.CONFIRMED)


def test_proposed_not_confirmed():
    status = default_requirement_assertion_status(
        provenance_source=ProvenanceSource.AI_RECOMMENDATION,
        user_approved=False,
    )
    assert status == AssertionStatus.PROPOSED
    assert inferred_not_confirmed(status)


def test_rejected_not_active():
    assert is_inactive_assertion(AssertionStatus.REJECTED)
    req = {"status": "active", "assertion_status": "REJECTED"}
    assert not requirement_is_compilable(req)


def test_superseded_not_active():
    assert is_inactive_assertion(AssertionStatus.SUPERSEDED)
    req = {"status": "superseded", "assertion_status": "SUPERSEDED"}
    assert not requirement_is_compilable(req)


def test_promotion_requires_explicit_steps():
    assert promotion_allowed(AssertionStatus.INFERRED, AssertionStatus.PROPOSED)
    assert not promotion_allowed(AssertionStatus.INFERRED, AssertionStatus.CONFIRMED)


def test_claims_assumptions_evidence_on_state():
    state = empty_state()
    claim = add_claim(state, text="BERT may improve classification.", source=ClaimSource.LLM_INFERENCE)
    assumption = add_assumption(state, text="Training can run locally.", reason="feasibility")
    evidence = add_evidence(
        state,
        evidence_type=EvidenceType.USER_PROVIDED,
        claim="User supplied GPU benchmark",
        verification_status="UNVERIFIED",
    )
    assert claim["id"].startswith("CLAIM-")
    assert assumption["id"].startswith("ASM-")
    assert evidence["id"].startswith("EVIDENCE-")
    assert state["audit_events"]


def test_research_does_not_auto_create_requirement(client):
    created = client.post("/projects", json={"description": "NLP project"})
    project_id = created.json()["id"]
    before = client.get(f"/projects/{project_id}").json()["state"]
    req_count_before = len(before.get("requirements") or [])
    msg = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Are there existing systems for phishing email detection?"},
    )
    assert msg.status_code == 200
    after = msg.json()["state"]
    assert len(after.get("requirements") or []) == req_count_before
    assert after.get("evidence") or after.get("claims") or after.get("research")


def test_unverified_evidence_marked_unverified():
    state = empty_state()
    record = add_evidence(state, evidence_type=EvidenceType.RESEARCH, claim="Finding from web")
    assert record["verification_status"] == "UNVERIFIED"


def test_migrate_adds_v3_collections():
    migrated = migrate_state({"requirements": [], "schema_version": 2})
    assert migrated["schema_version"] == 3
    assert "claims" in migrated
    assert "evidence" in migrated
