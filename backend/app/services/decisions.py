"""Decision lifecycle operations on ProjectState."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Project
from app.schemas.decisions import DecisionStatus, normalize_decision, propose_decision
from app.schemas.provenance import ProvenanceSource
from app.schemas.state import migrate_state
from app.services.project_state import public_state
from app.services.versioning import StateVersioning


def list_decisions(state: dict, *, status: str | None = None) -> list[dict]:
    rows = [normalize_decision(item) for item in (state.get("decisions") or []) if isinstance(item, dict)]
    if status:
        rows = [item for item in rows if item.get("status") == status]
    return rows


def active_decisions(state: dict) -> list[dict]:
    return list_decisions(state, status=DecisionStatus.ACTIVE.value)


def proposed_decisions(state: dict) -> list[dict]:
    return list_decisions(state, status=DecisionStatus.PROPOSED.value)


def append_decision(state: dict, decision: dict) -> dict:
    state.setdefault("decisions", [])
    state["decisions"].append(normalize_decision(decision))
    return state


def supersede_slot(state: dict, slot: str, *, new_decision_id: str | None = None) -> dict:
    for item in state.get("decisions") or []:
        if not isinstance(item, dict):
            continue
        if item.get("slot") == slot and item.get("status") == DecisionStatus.ACTIVE.value:
            item["status"] = DecisionStatus.SUPERSEDED.value
            item["user_approved"] = False
            if new_decision_id:
                item["superseded_by"] = new_decision_id
            prov = dict(item.get("provenance") or {})
            prov["user_approved"] = False
            item["provenance"] = prov
    return state


def approve_decision(session: Session, project: Project, decision_id: str) -> dict:
    """Promote a PROPOSED / UNCERTAIN decision to ACTIVE after explicit user choice."""
    state = migrate_state(project.state or {})
    target = None
    for item in state.get("decisions") or []:
        if isinstance(item, dict) and item.get("id") == decision_id:
            target = item
            break
    if target is None:
        raise ValueError(f"Decision not found: {decision_id}")
    if target.get("status") == DecisionStatus.ACTIVE.value and target.get("user_approved"):
        return public_state(state)

    slot = target.get("slot")
    if slot:
        supersede_slot(state, slot, new_decision_id=decision_id)

    target["status"] = DecisionStatus.ACTIVE.value
    target["user_approved"] = True
    prov = dict(target.get("provenance") or {})
    prov["user_approved"] = True
    # Keep source; marking approved does not rewrite provenance source to USER unless it was a user choice.
    if prov.get("source") == ProvenanceSource.AI_RECOMMENDATION.value:
        prov["reason"] = (prov.get("reason") or "") + " (user approved)"
    target["provenance"] = prov

    _apply_active_decision_to_state(state, target)
    state = StateVersioning.bump(state, "approve_decision")
    project.state = public_state(state)
    StateVersioning.snapshot(session, project, "approve_decision")
    return public_state(state)


def reject_decision(session: Session, project: Project, decision_id: str) -> dict:
    state = migrate_state(project.state or {})
    target = None
    for item in state.get("decisions") or []:
        if isinstance(item, dict) and item.get("id") == decision_id:
            target = item
            break
    if target is None:
        raise ValueError(f"Decision not found: {decision_id}")
    target["status"] = DecisionStatus.REJECTED.value
    target["user_approved"] = False
    prov = dict(target.get("provenance") or {})
    prov["user_approved"] = False
    target["provenance"] = prov
    state = StateVersioning.bump(state, "reject_decision")
    project.state = public_state(state)
    StateVersioning.snapshot(session, project, "reject_decision")
    return public_state(state)


def apply_active_decision_to_state(state: dict, decision: dict) -> None:
    """Apply approved tech/platform/database decisions into ProjectState slots."""
    _apply_active_decision_to_state(state, decision)


def _apply_active_decision_to_state(state: dict, decision: dict) -> None:
    """Apply approved tech/platform/database decisions into ProjectState slots."""
    slot = decision.get("slot")
    value = decision.get("value")
    details = decision.get("details") or {}
    tech = state.setdefault("technology", {})
    if slot in {"frontend_framework", "framework"} and value:
        tech["framework"] = value if isinstance(value, str) else str(value)
        frameworks = tech.setdefault("frameworks", [])
        if isinstance(value, str) and value not in frameworks:
            frameworks.append(value)
    elif slot == "database" and value:
        tech["database"] = value if isinstance(value, str) else str(value)
        databases = tech.setdefault("databases", [])
        if isinstance(value, str) and value not in databases:
            databases.append(value)
        state.setdefault("database", {})["engine"] = value
    elif slot == "backend" and value:
        tech["backend"] = value if isinstance(value, str) else str(value)
        frameworks = tech.setdefault("frameworks", [])
        if isinstance(value, str) and value not in frameworks:
            frameworks.append(value)
    elif slot == "platform" and value:
        platforms = value if isinstance(value, list) else [value]
        state.setdefault("project", {})["platform"] = platforms
    elif slot == "authentication":
        state.setdefault("security", [])
        flag = details.get("authentication_required")
        if flag is False:
            note = "authentication_required=false"
        elif flag is True:
            note = "authentication_required=true"
        else:
            note = str(value)
        if note not in state["security"]:
            state["security"].append(note)
    # Record acceptance as an explicit USER-facing decision trail item if needed.
    _ = propose_decision  # keep import used for type clarity in callers
