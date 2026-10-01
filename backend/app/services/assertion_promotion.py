"""Explicit assertion promotion / demotion on ProjectState entities."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import Project
from app.schemas.assertions import AssertionStatus
from app.schemas.state import migrate_state
from app.schemas.traceability import TraceEntityType, TraceRelationship
from app.services.assertion_lifecycle import promotion_allowed
from app.services.audit_log import append_audit_event
from app.services.project_state import public_state
from app.services.traceability import add_trace_link
from app.services.versioning import StateVersioning


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_COLLECTIONS = {
    "REQUIREMENT": "requirements",
    "CLAIM": "claims",
    "ASSUMPTION": "assumptions",
}


def find_assertion(state: dict, assertion_id: str) -> tuple[str, dict]:
    for entity_type, key in _COLLECTIONS.items():
        for item in state.get(key) or []:
            if item.get("id") == assertion_id:
                return entity_type, item
    raise ValueError(f"Assertion not found: {assertion_id}")


def promote_assertion(
    session: Session,
    project: Project,
    assertion_id: str,
    *,
    target_status: str,
    actor: str = "user",
    reason: str = "",
    superseded_by: str | None = None,
) -> dict:
    state = migrate_state(project.state or {})
    entity_type, item = find_assertion(state, assertion_id)
    current = item.get("assertion_status") or item.get("status")
    # Requirements use assertion_status; claims/assumptions use status as assertion lifecycle.
    if entity_type == "REQUIREMENT":
        current_status = item.get("assertion_status") or AssertionStatus.PROPOSED.value
    else:
        current_status = item.get("status") or AssertionStatus.MENTIONED.value

    target = AssertionStatus(target_status)
    if not promotion_allowed(current_status, target):
        raise ValueError(
            f"Illegal promotion {current_status} → {target.value} for {assertion_id}"
        )

    before = {
        "assertion_status": item.get("assertion_status"),
        "status": item.get("status"),
    }
    if entity_type == "REQUIREMENT":
        item["assertion_status"] = target.value
        if target == AssertionStatus.REJECTED:
            item["status"] = "removed"
        elif target == AssertionStatus.SUPERSEDED:
            item["status"] = "superseded"
            if superseded_by:
                item["superseded_by"] = superseded_by
                add_trace_link(
                    state,
                    source_type=TraceEntityType.REQUIREMENT,
                    source_id=superseded_by,
                    target_type=TraceEntityType.REQUIREMENT,
                    target_id=assertion_id,
                    relationship=TraceRelationship.SUPERSEDES,
                )
        elif target in {AssertionStatus.CONFIRMED, AssertionStatus.LOCKED, AssertionStatus.PROPOSED}:
            item["status"] = "active"
        prov = dict(item.get("provenance") or {})
        if target in {AssertionStatus.CONFIRMED, AssertionStatus.LOCKED}:
            prov["user_approved"] = True
        elif target == AssertionStatus.REJECTED:
            prov["user_approved"] = False
        item["provenance"] = prov
        item["updated_at"] = _now()
    else:
        item["status"] = target.value
        item["updated_at"] = _now()

    event_type = {
        AssertionStatus.CONFIRMED: "REQUIREMENT_MODIFIED" if entity_type == "REQUIREMENT" else "CLAIM_CREATED",
        AssertionStatus.LOCKED: "REQUIREMENT_MODIFIED",
        AssertionStatus.REJECTED: "REQUIREMENT_MODIFIED",
        AssertionStatus.SUPERSEDED: "REQUIREMENT_SUPERSEDED",
        AssertionStatus.PROPOSED: "REQUIREMENT_MODIFIED",
    }.get(target, "REQUIREMENT_MODIFIED")
    if entity_type == "CLAIM" and target == AssertionStatus.CONFIRMED:
        event_type = "CLAIM_CREATED"
    if entity_type == "ASSUMPTION":
        event_type = "ASSUMPTION_CREATED"

    # More precise event names for promotions
    if target == AssertionStatus.CONFIRMED:
        event_type = f"{entity_type}_CONFIRMED"
    elif target == AssertionStatus.LOCKED:
        event_type = f"{entity_type}_LOCKED"
    elif target == AssertionStatus.REJECTED:
        event_type = f"{entity_type}_REJECTED"
    elif target == AssertionStatus.SUPERSEDED:
        event_type = f"{entity_type}_SUPERSEDED"

    append_audit_event(
        state,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=assertion_id,
        actor=actor,
        before=before,
        after={
            "assertion_status": item.get("assertion_status"),
            "status": item.get("status"),
            "superseded_by": item.get("superseded_by"),
        },
        reason=reason or f"promote to {target.value}",
    )

    state = StateVersioning.bump(state, f"assertion_{target.value.lower()}")
    project.state = public_state(state)
    project.updated_at = utcnow()
    StateVersioning.snapshot(session, project, f"assertion_{target.value.lower()}")
    return {
        "assertion_id": assertion_id,
        "entity_type": entity_type,
        "from_status": current_status,
        "to_status": target.value,
        "state": public_state(state),
    }
