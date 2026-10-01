"""Attach evidence to claims, assumptions, requirements, decisions, grill responses."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import Project
from app.schemas.assertions import EvidenceType, VerificationStatus
from app.schemas.state import migrate_state
from app.schemas.traceability import TraceEntityType, TraceRelationship
from app.services.integrity_store import add_evidence
from app.services.project_state import public_state
from app.services.traceability import add_trace_link
from app.services.versioning import StateVersioning


_ATTACH_MAP = {
    "claim": TraceEntityType.CLAIM,
    "claims": TraceEntityType.CLAIM,
    "assumption": TraceEntityType.ASSUMPTION,
    "assumptions": TraceEntityType.ASSUMPTION,
    "requirement": TraceEntityType.REQUIREMENT,
    "requirements": TraceEntityType.REQUIREMENT,
    "decision": TraceEntityType.DECISION,
    "decisions": TraceEntityType.DECISION,
    "attack": TraceEntityType.ATTACK,
    "grill_response": TraceEntityType.ATTACK,
    "grill_responses": TraceEntityType.ATTACK,
}


def attach_evidence(
    session: Session,
    project: Project,
    *,
    evidence_type: str = EvidenceType.USER_PROVIDED.value,
    source: str = "",
    source_url: str = "",
    title: str = "",
    claim: str = "",
    content: str = "",
    confidence: float | None = None,
    verification_status: str = VerificationStatus.UNVERIFIED.value,
    attach_to_type: str | None = None,
    attach_to_id: str | None = None,
    actor: str = "user",
    reason: str = "",
) -> dict:
    state = migrate_state(project.state or {})

    # Never silently upgrade to verified.
    status = VerificationStatus(verification_status)
    if status == VerificationStatus.VERIFIED and actor != "verifier":
        # Explicit API clients must pass verification_status=VERIFIED deliberately;
        # still require source_url or source for verified claims.
        if not (source or source_url):
            status = VerificationStatus.UNVERIFIED

    record = add_evidence(
        state,
        evidence_type=EvidenceType(evidence_type),
        source=source,
        source_url=source_url,
        title=title,
        claim=claim,
        content=content or claim,
        confidence=confidence,
        verification_status=status,
        actor=actor,
        reason=reason or "evidence attached via API",
    )

    if attach_to_type and attach_to_id:
        key = attach_to_type.lower()
        target_type = _ATTACH_MAP.get(key)
        if target_type is None:
            raise ValueError(f"Unsupported attach_to_type: {attach_to_type}")
        add_trace_link(
            state,
            source_type=TraceEntityType.EVIDENCE,
            source_id=record["id"],
            target_type=target_type,
            target_id=attach_to_id,
            relationship=TraceRelationship.SUPPORTS,
            provenance=record.get("provenance"),
        )
        if target_type == TraceEntityType.ASSUMPTION:
            for asm in state.get("assumptions") or []:
                if asm.get("id") == attach_to_id:
                    asm.setdefault("evidence_ids", []).append(record["id"])
                    break
        if target_type == TraceEntityType.DECISION:
            for dec in state.get("decisions") or []:
                if dec.get("id") == attach_to_id:
                    dec.setdefault("evidence", []).append(
                        {"evidence_id": record["id"], "claim": record.get("claim")}
                    )
                    break
        if key in {"grill_response", "grill_responses"}:
            for resp in state.get("grill_responses") or []:
                if resp.get("id") == attach_to_id:
                    resp.setdefault("new_evidence_ids", []).append(record["id"])
                    break

    state = StateVersioning.bump(state, "attach_evidence")
    project.state = public_state(state)
    project.updated_at = utcnow()
    StateVersioning.snapshot(session, project, "attach_evidence")
    return {"evidence": record, "state": public_state(state)}
