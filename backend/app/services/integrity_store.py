"""First-class claims, assumptions, and evidence on ProjectState."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.schemas.assertions import (
    AssertionStatus,
    AssumptionRisk,
    ClaimSource,
    EvidenceType,
    GrillAssumptionStatus,
    VerificationStatus,
)
from app.schemas.provenance import ProvenanceSource, make_provenance
from app.schemas.traceability import TraceEntityType, TraceRelationship
from app.services.audit_log import append_audit_event
from app.services.traceability import add_trace_link


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_code(state: dict, prefix: str) -> str:
    numbers = []
    pattern = re.compile(rf"{re.escape(prefix)}-(\d+)", re.I)
    for collection_key in ("claims", "assumptions", "evidence", "requirements", "grill_attacks"):
        for item in state.get(collection_key) or []:
            match = pattern.search(str(item.get("id") or ""))
            if match:
                numbers.append(int(match.group(1)))
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def add_claim(
    state: dict,
    *,
    text: str,
    source: ClaimSource | str = ClaimSource.USER,
    source_reference: str = "",
    status: AssertionStatus = AssertionStatus.MENTIONED,
    confidence: float | None = None,
    actor: str = "system",
    reason: str = "",
) -> dict:
    if isinstance(source, str):
        source = ClaimSource(source)
    claim = {
        "id": _next_code(state, "CLAIM"),
        "text": text.strip(),
        "source": source.value,
        "source_reference": source_reference,
        "status": status.value,
        "confidence": confidence,
        "created_at": _now(),
        "updated_at": _now(),
    }
    state.setdefault("claims", []).append(claim)
    append_audit_event(
        state,
        event_type="CLAIM_CREATED",
        entity_type="CLAIM",
        entity_id=claim["id"],
        actor=actor,
        after=claim,
        reason=reason or "claim recorded",
    )
    return claim


def add_assumption(
    state: dict,
    *,
    text: str,
    status: AssertionStatus = AssertionStatus.PROPOSED,
    confidence: float | None = None,
    risk_level: AssumptionRisk | str = AssumptionRisk.MEDIUM,
    source: ClaimSource | str = ClaimSource.LLM_INFERENCE,
    evidence_ids: list[str] | None = None,
    affected_requirement_ids: list[str] | None = None,
    affected_decision_ids: list[str] | None = None,
    grill_status: GrillAssumptionStatus = GrillAssumptionStatus.UNRESOLVED,
    actor: str = "system",
    reason: str = "",
) -> dict:
    if isinstance(risk_level, str):
        risk_level = AssumptionRisk(risk_level)
    if isinstance(source, str):
        source = ClaimSource(source)
    assumption = {
        "id": _next_code(state, "ASM"),
        "text": text.strip(),
        "status": status.value,
        "confidence": confidence,
        "risk_level": risk_level.value,
        "source": source.value,
        "evidence_ids": evidence_ids or [],
        "affected_requirement_ids": affected_requirement_ids or [],
        "affected_decision_ids": affected_decision_ids or [],
        "grill_status": grill_status.value,
        "created_at": _now(),
        "updated_at": _now(),
    }
    state.setdefault("assumptions", []).append(assumption)
    append_audit_event(
        state,
        event_type="ASSUMPTION_CREATED",
        entity_type="ASSUMPTION",
        entity_id=assumption["id"],
        actor=actor,
        after=assumption,
        reason=reason or "assumption recorded",
    )
    return assumption


def add_evidence(
    state: dict,
    *,
    evidence_type: EvidenceType | str,
    source: str = "",
    source_url: str = "",
    title: str = "",
    claim: str = "",
    content: str = "",
    confidence: float | None = None,
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
    retrieved_at: str | None = None,
    actor: str = "system",
    reason: str = "",
    link_to: tuple[str, str] | None = None,
) -> dict:
    if isinstance(evidence_type, str):
        evidence_type = EvidenceType(evidence_type)
    if isinstance(verification_status, str):
        verification_status = VerificationStatus(verification_status)
    record = {
        "id": _next_code(state, "EVIDENCE"),
        "evidence_type": evidence_type.value,
        "source": source,
        "source_url": source_url,
        "title": title or (claim[:120] if claim else "Evidence"),
        "claim": claim,
        "content": content or claim,
        "confidence": confidence,
        "verification_status": verification_status.value,
        "retrieved_at": retrieved_at or _now(),
        "created_at": _now(),
        "provenance": make_provenance(
            ProvenanceSource.RESEARCH if evidence_type == EvidenceType.RESEARCH else ProvenanceSource.USER,
            reason=reason or evidence_type.value,
            confidence=confidence,
        ),
    }
    state.setdefault("evidence", []).append(record)
    append_audit_event(
        state,
        event_type="EVIDENCE_ATTACHED",
        entity_type="EVIDENCE",
        entity_id=record["id"],
        actor=actor,
        after=record,
        reason=reason or "evidence recorded",
    )
    if link_to:
        target_type, target_id = link_to
        add_trace_link(
            state,
            source_type=TraceEntityType.EVIDENCE,
            source_id=record["id"],
            target_type=TraceEntityType(target_type),
            target_id=target_id,
            relationship=TraceRelationship.SUPPORTS,
            provenance=record["provenance"],
        )
    return record


def integrity_summary(state: dict) -> dict[str, Any]:
    """Counts for UI / API — no single score."""
    from app.services.assertion_lifecycle import requirement_is_compilable
    from app.services.prompt_compiler import compilation_gate
    from app.services.traceability import validate_traceability

    reqs = state.get("requirements") or []
    decisions = state.get("decisions") or []
    assumptions = state.get("assumptions") or []
    evidence = state.get("evidence") or []
    attacks = state.get("grill_attacks") or []
    verifications = state.get("requirement_verifications") or []
    links = state.get("trace_links") or []
    trace = validate_traceability(state)
    gate = compilation_gate(state)

    def _count(items, field, value):
        return sum(1 for item in items if str(item.get(field) or "") == value)

    return {
        "requirements": {
            "confirmed": sum(
                1
                for r in reqs
                if r.get("assertion_status") in {"CONFIRMED", "LOCKED"} and r.get("status") == "active"
            ),
            "proposed": sum(1 for r in reqs if r.get("assertion_status") == "PROPOSED"),
            "superseded": sum(1 for r in reqs if r.get("status") == "superseded"),
            "compilable": sum(1 for r in reqs if requirement_is_compilable(r)),
        },
        "decisions": {
            "confirmed": _count(decisions, "status", "ACTIVE"),
            "proposed": _count(decisions, "status", "PROPOSED"),
            "rejected": _count(decisions, "status", "REJECTED"),
        },
        "assumptions": {
            "verified": sum(1 for a in assumptions if a.get("evidence_ids")),
            "unverified": sum(1 for a in assumptions if not a.get("evidence_ids")),
            "high_risk": sum(1 for a in assumptions if a.get("risk_level") == "HIGH"),
        },
        "evidence": {
            "total": len(evidence),
            "linked": len(links),
            "unverified": sum(1 for e in evidence if e.get("verification_status") == "UNVERIFIED"),
            "verified": sum(1 for e in evidence if e.get("verification_status") == "VERIFIED"),
        },
        "grill": {
            "open": sum(1 for a in attacks if a.get("status") in {"OPEN", "UNRESOLVED", "RESPONDED"}),
            "blocking": sum(
                1
                for a in attacks
                if a.get("blocking") and a.get("status") in {"OPEN", "UNRESOLVED", "RESPONDED"}
            ),
            "resolved": sum(1 for a in attacks if a.get("status") == "RESOLVED"),
            "deferred": sum(1 for a in attacks if a.get("status") == "DEFERRED"),
        },
        "traceability": {
            "links": len(links),
            "valid": trace.get("valid"),
            "blocking_issues": len(trace.get("blocking_issues") or []),
            "warnings": len(trace.get("warnings") or []),
        },
        "verification": {
            "passed": _count(verifications, "status", "PASS"),
            "failed": _count(verifications, "status", "FAIL"),
            "untested": _count(verifications, "status", "NOT_TESTED"),
        },
        "compilation": {
            "can_compile": gate.get("can_compile"),
            "blocked": gate.get("blocked"),
            "blocking_issues": len(gate.get("blocking_issues") or []),
            "warnings": len(gate.get("warnings") or []),
        },
    }
