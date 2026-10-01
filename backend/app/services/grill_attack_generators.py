"""Convert legacy Grill dimensions into entity-targeted attacks."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.grill_entities import GrillAttack, GrillAttackStatus, GrillTargetType
from app.services.grill import _active, _dimension_checks, _objective


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_attack_id(state: dict) -> str:
    existing = state.get("grill_attacks") or []
    numbers = []
    for item in existing:
        raw = str(item.get("id") or "")
        if raw.startswith("ATTACK-"):
            try:
                numbers.append(int(raw.split("-")[1]))
            except ValueError:
                continue
    return f"ATTACK-{max(numbers, default=0) + 1:03d}"


_GENERATOR_MAP = {
    "problem_clarity": "ObjectiveAlignmentAttackGenerator",
    "scope": "ScopeAttackGenerator",
    "dataset": "DatasetAttackGenerator",
    "feasibility": "FeasibilityAttackGenerator",
    "ai_necessity": "AINecessityAttackGenerator",
    "evaluation": "EvaluationAttackGenerator",
    "research_potential": "ResearchAttackGenerator",
    "deployment": "ArchitectureAttackGenerator",
    "security": "SecurityAttackGenerator",
    "dependency_risk": "DependencyAttackGenerator",
    "timeline": "TimelineAttackGenerator",
    "objective_alignment": "ObjectiveAlignmentAttackGenerator",
}


def _pick_target(state: dict, dimension: dict) -> tuple[GrillTargetType, str, str]:
    active = _active(state)
    if active:
        # Prefer first requirement lacking acceptance when dimension mentions thresholds/criteria.
        for req in active:
            if not req.get("acceptance"):
                return GrillTargetType.REQUIREMENT, req["id"], req.get("text") or ""
        req = active[0]
        return GrillTargetType.REQUIREMENT, req["id"], req.get("text") or ""
    objective = _objective(state)
    if objective:
        return GrillTargetType.PROJECT, "PROJECT", objective
    return GrillTargetType.CONSTRAINT, "CONSTRAINT", "project constraints"


def _dimension_to_attack(state: dict, dimension: dict) -> GrillAttack | None:
    if dimension.get("positive"):
        return None
    if dimension.get("severity") not in {"high", "medium"}:
        return None
    target_type, target_id, target_text = _pick_target(state, dimension)
    dim_name = dimension.get("dimension") or "general"
    generator = _GENERATOR_MAP.get(dim_name, "ScopeAttackGenerator")
    challenge = dimension.get("must_resolve") or dimension.get("question") or dimension.get("detail")
    failure = (
        f"The implementation may satisfy surface features while failing the intended "
        f"{dim_name.replace('_', ' ')} constraint for {target_id}."
    )
    return GrillAttack(
        id=_next_attack_id(state),
        target_type=target_type,
        target_id=target_id,
        attack_type=generator,
        claim=target_text[:240],
        challenge=str(challenge),
        rationale=str(dimension.get("detail") or ""),
        evidence_required=str(dimension.get("recommendation") or "User clarification or supporting evidence"),
        failure_condition=failure,
        severity=str(dimension.get("severity") or "MEDIUM").upper(),
        status=GrillAttackStatus.OPEN,
        created_at=_now(),
        blocking=dimension.get("severity") == "high",
    )


def generate_attacks_from_state(state: dict, *, replace_open: bool = False) -> list[dict]:
    """Run all attack generators (via dimension checks) and append structured attacks."""
    from app.services.grill_session import target_fingerprint

    objective = _objective(state)
    dimensions = _dimension_checks(state, objective)
    if replace_open:
        kept = [
            a
            for a in (state.get("grill_attacks") or [])
            if a.get("status") not in {GrillAttackStatus.OPEN.value, GrillAttackStatus.UNRESOLVED.value}
        ]
        state["grill_attacks"] = kept
    created: list[dict] = []
    for dim in dimensions:
        attack = _dimension_to_attack(state, dim)
        if attack is None:
            continue
        fingerprint = target_fingerprint(state, attack.target_type.value, attack.target_id)
        # Avoid duplicate open attacks for the same unchanged target + challenge
        duplicate = any(
            a.get("target_id") == attack.target_id
            and a.get("challenge") == attack.challenge
            and a.get("status") in {GrillAttackStatus.OPEN.value, GrillAttackStatus.UNRESOLVED.value}
            and (a.get("target_fingerprint") or fingerprint) == fingerprint
            for a in (state.get("grill_attacks") or [])
        )
        # Also skip if a resolved attack exists for the same fingerprint+challenge
        # (state unchanged) — allow regeneration only when fingerprint differs.
        stale_resolved_same = any(
            a.get("target_id") == attack.target_id
            and a.get("challenge") == attack.challenge
            and a.get("status")
            in {
                GrillAttackStatus.RESOLVED.value,
                GrillAttackStatus.DEFERRED.value,
                GrillAttackStatus.REJECTED.value,
            }
            and a.get("target_fingerprint") == fingerprint
            for a in (state.get("grill_attacks") or [])
        )
        if duplicate or stale_resolved_same:
            continue
        payload = attack.as_dict()
        payload["target_fingerprint"] = fingerprint
        # Attach ontology type alongside legacy generator name
        from app.schemas.grill_ontology import DIMENSION_TO_ONTOLOGY

        dim_name = str(dim.get("name") or "")
        ontology = DIMENSION_TO_ONTOLOGY.get(dim_name)
        if ontology:
            payload["ontology_type"] = ontology.value
        state.setdefault("grill_attacks", []).append(payload)
        created.append(payload)
    # Targeted ontology attacks (assumptions/claims → concrete entities)
    from app.services.targeted_grill import generate_targeted_attacks

    created.extend(generate_targeted_attacks(state))
    return created


def apply_grill_response(
    state: dict,
    *,
    attack_id: str,
    response_text: str,
    resolution_type: str,
    new_requirement_ids: list[str] | None = None,
    new_evidence_ids: list[str] | None = None,
    new_decision_id: str | None = None,
) -> dict:
    """Lightweight in-memory responder used by unit tests.

    Production paths should use grill_session.respond_to_grill_attack which
    performs controlled mutations, audit events, and re-evaluation.
    """
    from app.schemas.grill_entities import GrillResolutionType, GrillResponse
    from app.services.audit_log import append_audit_event

    attacks = state.get("grill_attacks") or []
    attack = next((a for a in attacks if a.get("id") == attack_id), None)
    if attack is None:
        raise ValueError(f"Unknown attack {attack_id}")
    response = GrillResponse(
        id=f"GR-{len(state.get('grill_responses') or []) + 1:03d}",
        attack_id=attack_id,
        response_text=response_text,
        resolution_type=GrillResolutionType(resolution_type),
        new_evidence_ids=new_evidence_ids or [],
        new_decision_id=new_decision_id,
        new_requirement_ids=new_requirement_ids or [],
        state_changes=[],
        created_at=_now(),
    ).as_dict()
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
    else:
        attack["status"] = GrillAttackStatus.RESPONDED.value
    append_audit_event(
        state,
        event_type="GRILL_ATTACK_RESOLVED",
        entity_type="ATTACK",
        entity_id=attack_id,
        actor="user",
        before=None,
        after={"response_id": response["id"], "resolution": resolution_type},
        reason=response_text[:200],
    )
    return response
