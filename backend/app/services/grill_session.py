"""Grill attack listing, prioritization, and response-driven state mutation."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import Project
from app.schemas.assertions import AssertionStatus, ClaimSource, EvidenceType, VerificationStatus
from app.schemas.decisions import DecisionStatus, propose_decision
from app.schemas.grill_entities import GrillAttackStatus, GrillResolutionType, GrillResponse
from app.schemas.provenance import ProvenanceSource, make_provenance
from app.schemas.state import ConversationStage, migrate_state
from app.schemas.traceability import TraceEntityType, TraceRelationship
from app.services.audit_log import append_audit_event
from app.services.grill import grill as run_full_grill
from app.services.grill_attack_generators import generate_attacks_from_state
from app.services.integrity_store import add_claim, add_evidence
from app.services.project_state import public_state, set_stage
from app.services.traceability import add_trace_link
from app.services.versioning import StateVersioning

_OPEN = {
    GrillAttackStatus.OPEN.value,
    GrillAttackStatus.UNRESOLVED.value,
    GrillAttackStatus.RESPONDED.value,
}
_SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
_ATTACK_TYPE_PRIORITY = {
    "ObjectiveAlignmentAttackGenerator": 0,
    "FeasibilityAttackGenerator": 1,
    "DatasetAttackGenerator": 2,
    "DependencyAttackGenerator": 3,
    "ArchitectureAttackGenerator": 4,
    "SecurityAttackGenerator": 5,
    "ScopeAttackGenerator": 6,
    "EvaluationAttackGenerator": 7,
    "TimelineAttackGenerator": 8,
    "AINecessityAttackGenerator": 9,
    "ResearchAttackGenerator": 10,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def target_fingerprint(state: dict, target_type: str, target_id: str) -> str:
    """Hash of the target's current text/status so we can detect stale duplicates."""
    blob = f"{target_type}:{target_id}"
    if target_type == "REQUIREMENT":
        for req in state.get("requirements") or []:
            if req.get("id") == target_id:
                blob = "|".join(
                    [
                        str(req.get("id")),
                        str(req.get("text") or ""),
                        str(req.get("status") or ""),
                        str(req.get("assertion_status") or ""),
                        str(req.get("acceptance") or ""),
                        str(req.get("version") or ""),
                    ]
                )
                break
    elif target_type == "ASSUMPTION":
        for item in state.get("assumptions") or []:
            if item.get("id") == target_id:
                blob = "|".join(
                    [
                        str(item.get("id")),
                        str(item.get("text") or ""),
                        str(item.get("status") or ""),
                        str(item.get("grill_status") or ""),
                        ",".join(item.get("evidence_ids") or []),
                    ]
                )
                break
    elif target_type == "DECISION":
        for item in state.get("decisions") or []:
            if item.get("id") == target_id:
                blob = "|".join(
                    [
                        str(item.get("id")),
                        str(item.get("summary") or ""),
                        str(item.get("status") or ""),
                        str(item.get("value") or ""),
                    ]
                )
                break
    elif target_type == "CLAIM":
        for item in state.get("claims") or []:
            if item.get("id") == target_id:
                blob = "|".join([str(item.get("id")), str(item.get("text") or ""), str(item.get("status") or "")])
                break
    elif target_type in {"PROJECT", "CONSTRAINT", "ARCHITECTURE"}:
        project = state.get("project") or {}
        constraints = state.get("constraints") or {}
        arch = state.get("architecture") or {}
        blob = "|".join(
            [
                str(project.get("objective") or ""),
                str((state.get("core_idea") or {}).get("primary_objective") or ""),
                str(constraints.get("duration") or ""),
                str(constraints.get("team_size") or ""),
                str(arch.get("logical") or arch)[:200],
            ]
        )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def list_grill_attacks(state: dict) -> dict[str, Any]:
    attacks = list(state.get("grill_attacks") or [])
    open_attacks = [a for a in attacks if a.get("status") in _OPEN]
    resolved = [a for a in attacks if a.get("status") == GrillAttackStatus.RESOLVED.value]
    deferred = [a for a in attacks if a.get("status") == GrillAttackStatus.DEFERRED.value]
    rejected = [a for a in attacks if a.get("status") == GrillAttackStatus.REJECTED.value]
    blocking = [
        a for a in open_attacks if a.get("blocking") and a.get("status") in _OPEN
    ]
    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for attack in attacks:
        sev = str(attack.get("severity") or "MEDIUM").upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1
        atype = str(attack.get("attack_type") or "unknown")
        by_type[atype] = by_type.get(atype, 0) + 1
    return {
        "open": open_attacks,
        "resolved": resolved,
        "deferred": deferred,
        "rejected": rejected,
        "blocking": blocking,
        "counts": {
            "total": len(attacks),
            "open": len(open_attacks),
            "resolved": len(resolved),
            "deferred": len(deferred),
            "rejected": len(rejected),
            "blocking": len(blocking),
            "by_severity": by_severity,
            "by_type": by_type,
        },
        "next": get_next_grill_attack(state),
    }


def get_next_grill_attack(state: dict) -> dict | None:
    """Highest-priority unresolved attack; None if Grill is clear."""
    candidates = [
        a
        for a in (state.get("grill_attacks") or [])
        if a.get("status") in {GrillAttackStatus.OPEN.value, GrillAttackStatus.UNRESOLVED.value}
    ]
    if not candidates:
        return None

    def sort_key(attack: dict):
        severity = str(attack.get("severity") or "MEDIUM").upper()
        blocking = 0 if attack.get("blocking") else 1
        atype = str(attack.get("attack_type") or "")
        type_rank = _ATTACK_TYPE_PRIORITY.get(atype, 50)
        # Unsupported assumptions / missing evidence: prefer dataset/feasibility
        return (blocking, _SEVERITY_RANK.get(severity, 9), type_rank, attack.get("id") or "")

    return sorted(candidates, key=sort_key)[0]


def create_grill_session(session: Session, project: Project) -> dict:
    """Generate/persist targeted attacks via the existing grill engine."""
    report = run_full_grill(project.state or {}, persist_on_project=project, session=session)
    state = migrate_state(project.state or {})
    # Ensure fingerprints exist on all open attacks
    for attack in state.get("grill_attacks") or []:
        if not attack.get("target_fingerprint"):
            attack["target_fingerprint"] = target_fingerprint(
                state, str(attack.get("target_type") or "PROJECT"), str(attack.get("target_id") or "")
            )
    project.state = public_state(state)
    project.updated_at = utcnow()
    StateVersioning.snapshot(session, project, "grill_session")
    listing = list_grill_attacks(state)
    report["grill"] = listing
    report["state"] = public_state(state)
    return report


def respond_to_grill_attack(
    session: Session,
    project: Project,
    attack_id: str,
    *,
    response_text: str,
    resolution_type: str = GrillResolutionType.RESOLVED.value,
    create_requirement: dict | None = None,
    create_evidence: dict | None = None,
    create_decision: dict | None = None,
    create_claim: dict | None = None,
    mutate: bool = True,
) -> dict:
    """Apply a GrillResponse with controlled state transitions."""
    state = migrate_state(project.state or {})
    attacks = state.get("grill_attacks") or []
    attack = next((a for a in attacks if a.get("id") == attack_id), None)
    if attack is None:
        raise ValueError(f"Unknown attack {attack_id}")

    state_changes: list[dict] = []
    new_requirement_ids: list[str] = []
    new_evidence_ids: list[str] = []
    new_decision_id: str | None = None
    new_claim_ids: list[str] = []

    if mutate and resolution_type not in {
        GrillResolutionType.REJECTED.value,
        GrillResolutionType.DEFERRED.value,
    }:
        inferred = _infer_mutations(state, attack, response_text)
        create_requirement = create_requirement or inferred.get("requirement")
        create_evidence = create_evidence or inferred.get("evidence")
        create_decision = create_decision or inferred.get("decision")
        create_claim = create_claim or inferred.get("claim")

        if create_requirement:
            req = _create_proposed_requirement(
                state,
                text=create_requirement.get("text") or response_text.strip(),
                acceptance=create_requirement.get("acceptance"),
                req_type=create_requirement.get("type") or "nonfunctional",
                reason=f"grill response to {attack_id}",
            )
            new_requirement_ids.append(req["id"])
            state_changes.append({"type": "REQUIREMENT_CREATED", "id": req["id"], "status": req["assertion_status"]})
            add_trace_link(
                state,
                source_type=TraceEntityType.ATTACK,
                source_id=attack_id,
                target_type=TraceEntityType.REQUIREMENT,
                target_id=req["id"],
                relationship=TraceRelationship.RESOLVES,
                provenance=make_provenance(ProvenanceSource.USER, reason="grill response"),
            )
            if attack.get("target_type") == "REQUIREMENT" and attack.get("target_id"):
                add_trace_link(
                    state,
                    source_type=TraceEntityType.REQUIREMENT,
                    source_id=req["id"],
                    target_type=TraceEntityType.REQUIREMENT,
                    target_id=str(attack["target_id"]),
                    relationship=TraceRelationship.AFFECTS,
                )

        if create_claim:
            claim = add_claim(
                state,
                text=create_claim.get("text") or response_text.strip(),
                source=ClaimSource.USER,
                source_reference=attack_id,
                status=AssertionStatus.PROPOSED,
                reason=f"grill response to {attack_id}",
                actor="user",
            )
            new_claim_ids.append(claim["id"])
            state_changes.append({"type": "CLAIM_CREATED", "id": claim["id"]})
            add_trace_link(
                state,
                source_type=TraceEntityType.ATTACK,
                source_id=attack_id,
                target_type=TraceEntityType.CLAIM,
                target_id=claim["id"],
                relationship=TraceRelationship.RESOLVES,
            )

        if create_evidence:
            evidence = add_evidence(
                state,
                evidence_type=EvidenceType(create_evidence.get("evidence_type") or EvidenceType.USER_PROVIDED.value),
                source=create_evidence.get("source") or "user",
                source_url=create_evidence.get("source_url") or "",
                title=create_evidence.get("title") or "Grill response evidence",
                claim=create_evidence.get("claim") or response_text.strip(),
                content=create_evidence.get("content") or response_text.strip(),
                confidence=create_evidence.get("confidence"),
                verification_status=VerificationStatus.UNVERIFIED,
                reason=f"grill response to {attack_id}",
                actor="user",
            )
            new_evidence_ids.append(evidence["id"])
            state_changes.append(
                {
                    "type": "EVIDENCE_ATTACHED",
                    "id": evidence["id"],
                    "verification_status": evidence["verification_status"],
                }
            )
            add_trace_link(
                state,
                source_type=TraceEntityType.ATTACK,
                source_id=attack_id,
                target_type=TraceEntityType.EVIDENCE,
                target_id=evidence["id"],
                relationship=TraceRelationship.RESOLVES,
            )
            if new_claim_ids:
                add_trace_link(
                    state,
                    source_type=TraceEntityType.CLAIM,
                    source_id=new_claim_ids[0],
                    target_type=TraceEntityType.EVIDENCE,
                    target_id=evidence["id"],
                    relationship=TraceRelationship.SUPPORTED_BY,
                )
            if attack.get("target_type") == "ASSUMPTION":
                for asm in state.get("assumptions") or []:
                    if asm.get("id") == attack.get("target_id"):
                        asm.setdefault("evidence_ids", []).append(evidence["id"])
                        asm["grill_status"] = "RESOLVED"
                        asm["updated_at"] = _now()
                        break

        if create_decision:
            decision = propose_decision(
                kind=create_decision.get("kind") or "architecture_choice",
                summary=create_decision.get("summary") or response_text.strip()[:200],
                value=create_decision.get("value") or create_decision.get("summary") or response_text.strip(),
                slot=create_decision.get("slot"),
                details={
                    "attack_id": attack_id,
                    "response": response_text,
                    **(create_decision.get("details") or {}),
                },
                source=ProvenanceSource.USER,
                reason=f"grill response to {attack_id}",
                evidence=[{"evidence_id": eid} for eid in new_evidence_ids],
                dependencies=new_requirement_ids
                or ([attack["target_id"]] if attack.get("target_type") == "REQUIREMENT" else []),
                status=DecisionStatus.PROPOSED,
            )
            state.setdefault("decisions", []).append(decision)
            new_decision_id = decision["id"]
            state_changes.append({"type": "DECISION_PROPOSED", "id": decision["id"]})
            append_audit_event(
                state,
                event_type="DECISION_PROPOSED",
                entity_type="DECISION",
                entity_id=decision["id"],
                actor="user",
                after=decision,
                reason=f"grill response to {attack_id}",
            )
            add_trace_link(
                state,
                source_type=TraceEntityType.ATTACK,
                source_id=attack_id,
                target_type=TraceEntityType.DECISION,
                target_id=decision["id"],
                relationship=TraceRelationship.RESOLVES,
            )
            for rid in new_requirement_ids or (
                [attack["target_id"]] if attack.get("target_type") == "REQUIREMENT" else []
            ):
                add_trace_link(
                    state,
                    source_type=TraceEntityType.DECISION,
                    source_id=decision["id"],
                    target_type=TraceEntityType.REQUIREMENT,
                    target_id=rid,
                    relationship=TraceRelationship.AFFECTS,
                )

    response = GrillResponse(
        id=f"GR-{len(state.get('grill_responses') or []) + 1:03d}",
        attack_id=attack_id,
        response_text=response_text,
        resolution_type=GrillResolutionType(resolution_type),
        new_evidence_ids=new_evidence_ids,
        new_decision_id=new_decision_id,
        new_requirement_ids=new_requirement_ids,
        state_changes=state_changes,
        created_at=_now(),
    ).as_dict()
    if new_claim_ids:
        response["new_claim_ids"] = new_claim_ids
    state.setdefault("grill_responses", []).append(response)

    attack["response_id"] = response["id"]
    if resolution_type in {GrillResolutionType.RESOLVED.value, GrillResolutionType.ACCEPTED.value}:
        attack["status"] = GrillAttackStatus.RESOLVED.value
        attack["blocking"] = False
        attack["resolved_at"] = _now()
    elif resolution_type == GrillResolutionType.DEFERRED.value:
        attack["status"] = GrillAttackStatus.DEFERRED.value
        attack["blocking"] = False
    elif resolution_type == GrillResolutionType.REJECTED.value:
        attack["status"] = GrillAttackStatus.REJECTED.value
        attack["blocking"] = False
        attack["resolved_at"] = _now()
    else:
        attack["status"] = GrillAttackStatus.RESPONDED.value

    append_audit_event(
        state,
        event_type="GRILL_ATTACK_RESOLVED",
        entity_type="ATTACK",
        entity_id=attack_id,
        actor="user",
        before={"status": GrillAttackStatus.OPEN.value},
        after={
            "response_id": response["id"],
            "resolution": resolution_type,
            "state_changes": state_changes,
        },
        reason=response_text[:200],
    )

    # Re-evaluate and generate next attacks without duplicating unchanged targets
    generate_attacks_from_state(state, replace_open=False)
    for item in state.get("grill_attacks") or []:
        if not item.get("target_fingerprint"):
            item["target_fingerprint"] = target_fingerprint(
                state, str(item.get("target_type") or "PROJECT"), str(item.get("target_id") or "")
            )

    state = set_stage(state, ConversationStage.GRILL)
    state = StateVersioning.bump(state, "grill_response")
    project.state = public_state(state)
    project.updated_at = utcnow()
    StateVersioning.snapshot(session, project, "grill_response")

    return {
        "response": response,
        "attack": attack,
        "next_attack": get_next_grill_attack(state),
        "state": public_state(state),
        "grill": list_grill_attacks(state),
    }


def _create_proposed_requirement(
    state: dict,
    *,
    text: str,
    acceptance: str | None,
    req_type: str,
    reason: str,
) -> dict:
    from app.schemas.assertions import AssertionOrigin
    from app.services.project_state import _next_code

    item = {
        "id": _next_code(state),
        "type": req_type,
        "text": text.strip(),
        "status": "active",
        "assertion_status": AssertionStatus.PROPOSED.value,
        "assertion_origin": AssertionOrigin.GRILL_DERIVED.value,
        "version": 1,
        "slot": None,
        "slot_value": None,
        "domain": None,
        "actor": None,
        "acceptance": acceptance,
        "capability": text.strip(),
        "origin": "grill_response",
        "provenance": make_provenance(
            ProvenanceSource.USER,
            reason=reason,
            user_approved=False,
        ),
        "versions": [{"version": 1, "text": text.strip(), "status": "active"}],
        "lineage": [],
    }
    state.setdefault("requirements", []).append(item)
    append_audit_event(
        state,
        event_type="REQUIREMENT_CREATED",
        entity_type="REQUIREMENT",
        entity_id=item["id"],
        actor="user",
        after=item,
        reason=reason,
    )
    return item


def _infer_mutations(state: dict, attack: dict, response_text: str) -> dict[str, Any]:
    """Heuristically map common Grill answers into controlled mutations."""
    text = (response_text or "").strip()
    lowered = text.lower()
    out: dict[str, Any] = {}
    challenge = str(attack.get("challenge") or "").lower()
    attack_type = str(attack.get("attack_type") or "")

    latency = re.search(
        r"(?:under|below|<=|less than|within)\s*(\d+(?:\.\d+)?)\s*(ms|milliseconds|s|seconds)",
        lowered,
    ) or re.search(r"(\d+(?:\.\d+)?)\s*(ms|milliseconds)\b", lowered)
    if latency or "latency" in challenge or "real-time" in challenge or "real time" in challenge:
        if latency:
            value, unit = latency.group(1), latency.group(2)
            unit_norm = "ms" if unit.startswith("m") else "s"
            acceptance = f"Measured end-to-end latency <= {value}{unit_norm}"
            req_text = f"Response latency must be <= {value}{unit_norm}"
        else:
            acceptance = text
            req_text = f"Clarify real-time constraint: {text}"
        out["requirement"] = {
            "text": req_text,
            "acceptance": acceptance,
            "type": "nonfunctional",
        }

    if any(token in lowered for token in ("websocket", "web socket", "sse", "server-sent")):
        choice = "WebSocket" if "websocket" in lowered or "web socket" in lowered else "SSE"
        if "rest" in lowered and "poll" in lowered:
            choice = "REST polling"
        out["decision"] = {
            "kind": "architecture_choice",
            "slot": "transport",
            "summary": f"Use {choice}",
            "value": choice,
            "details": {"source": "grill_response"},
        }

    if any(token in lowered for token in ("paper", "study", "benchmark", "dataset", "evidence", "arxiv", "doi")):
        out["evidence"] = {
            "evidence_type": EvidenceType.USER_PROVIDED.value,
            "source": "user",
            "claim": text,
            "title": "User-cited evidence from Grill",
        }
        out["claim"] = {"text": text}

    if "Architecture" in attack_type and "decision" not in out and len(text) > 8:
        out.setdefault(
            "decision",
            {
                "kind": "architecture_choice",
                "summary": text[:200],
                "value": text[:200],
            },
        )

    if not out and len(text) > 12 and resolution_worthy(challenge):
        # Default clarifying answer → proposed requirement, never locked.
        out["requirement"] = {
            "text": text if len(text) < 240 else text[:237] + "...",
            "acceptance": text if len(text) < 240 else text[:237] + "...",
            "type": "functional",
        }
    return out


def resolution_worthy(challenge: str) -> bool:
    return any(
        token in challenge
        for token in ("what", "how", "which", "define", "threshold", "missing", "dataset", "evidence")
    )
