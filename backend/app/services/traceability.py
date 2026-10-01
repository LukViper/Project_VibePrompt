"""Trace links and pre-compilation traceability checks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.grill_entities import GrillAttackStatus
from app.schemas.traceability import TraceEntityType, TraceRelationship
from app.services.assertion_lifecycle import is_authoritative_assertion, requirement_is_compilable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_trace_link(
    state: dict,
    *,
    source_type: TraceEntityType | str,
    source_id: str,
    target_type: TraceEntityType | str,
    target_id: str,
    relationship: TraceRelationship | str,
    confidence: float | None = None,
    provenance: dict | None = None,
) -> dict:
    if isinstance(source_type, str):
        source_type = TraceEntityType(source_type)
    if isinstance(target_type, str):
        target_type = TraceEntityType(target_type)
    if isinstance(relationship, str):
        relationship = TraceRelationship(relationship)
    link = {
        "id": f"TRACE-{len(state.get('trace_links') or []) + 1:04d}",
        "source_type": source_type.value,
        "source_id": source_id,
        "target_type": target_type.value,
        "target_id": target_id,
        "relationship": relationship.value,
        "confidence": confidence,
        "provenance": provenance or {},
        "created_at": _now(),
    }
    state.setdefault("trace_links", []).append(link)
    return link


def blocking_grill_attacks(state: dict) -> list[dict]:
    attacks = state.get("grill_attacks") or []
    blocking_statuses = {
        GrillAttackStatus.OPEN.value,
        GrillAttackStatus.UNRESOLVED.value,
        GrillAttackStatus.RESPONDED.value,
    }
    return [
        a
        for a in attacks
        if a.get("blocking") and str(a.get("status") or "") in blocking_statuses
    ]


def validate_traceability(state: dict) -> dict[str, Any]:
    """Deterministic pre-compile checks. Returns warnings and blocking issues."""
    blocking: list[dict] = []
    warnings: list[dict] = []

    active_reqs = [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
    for req in active_reqs:
        rid = req.get("id")
        if not req.get("provenance"):
            warnings.append({"type": "MISSING_PROVENANCE", "id": rid})
        if not req.get("assertion_status"):
            warnings.append({"type": "MISSING_ASSERTION_STATUS", "id": rid})
        if is_authoritative_assertion(req.get("assertion_status")) and not req.get("acceptance"):
            warnings.append({"type": "MISSING_ACCEPTANCE_CRITERIA", "id": rid})

    for attack in blocking_grill_attacks(state):
        blocking.append({"type": "UNRESOLVED_GRILL_ATTACK", "id": attack.get("id")})

    for req in active_reqs:
        if req.get("assertion_status") in {"REJECTED", "SUPERSEDED"}:
            blocking.append({"type": "INACTIVE_REQUIREMENT_ACTIVE", "id": req.get("id")})

    high_risk = [
        a
        for a in (state.get("assumptions") or [])
        if a.get("risk_level") == "HIGH" and not a.get("evidence_ids")
        and a.get("grill_status") not in {"DEFERRED", "RESOLVED"}
    ]
    for asm in high_risk:
        warnings.append({"type": "HIGH_RISK_ASSUMPTION_UNRESOLVED", "id": asm.get("id")})

    return {
        "valid": not blocking,
        "blocking_issues": blocking,
        "warnings": warnings,
        "compilable_requirements": [r["id"] for r in active_reqs if requirement_is_compilable(r)],
    }


def record_requirement_version_lineage(
    req: dict,
    *,
    changed_by: str,
    change_reason: str,
    affected: dict | None = None,
) -> None:
    lineage = {
        "changed_by": changed_by,
        "change_reason": change_reason,
        "previous_version": int(req.get("version") or 1) - 1,
        "new_version": int(req.get("version") or 1),
        "affected_decisions": (affected or {}).get("decisions") or [],
        "affected_architecture": (affected or {}).get("architecture") or [],
        "affected_tests": (affected or {}).get("tests") or [],
        "affected_prompt_versions": (affected or {}).get("prompt_versions") or [],
        "recorded_at": _now(),
        "lineage_id": str(uuid4()),
    }
    req.setdefault("lineage", []).append(lineage)


def get_requirement_lineage(state: dict, requirement_id: str) -> dict[str, Any]:
    """Build structured lineage chains rooted at a requirement."""
    links = state.get("trace_links") or []
    related = [
        link
        for link in links
        if link.get("source_id") == requirement_id or link.get("target_id") == requirement_id
    ]

    # BFS outward from the requirement in both directions.
    adjacency: dict[str, list[dict]] = {}
    for link in links:
        src = f"{link.get('source_type')}:{link.get('source_id')}"
        tgt = f"{link.get('target_type')}:{link.get('target_id')}"
        adjacency.setdefault(src, []).append({"node": tgt, "relationship": link.get("relationship"), "link": link})
        adjacency.setdefault(tgt, []).append({"node": src, "relationship": link.get("relationship"), "link": link})

    root = f"REQUIREMENT:{requirement_id}"
    chains: list[list[dict]] = []

    def walk(node: str, path: list[dict], visited: set[str]) -> None:
        neighbors = [n for n in adjacency.get(node, []) if n["node"] not in visited]
        if not neighbors:
            if len(path) > 1:
                chains.append(path[:])
            return
        for neighbor in neighbors:
            ntype, nid = neighbor["node"].split(":", 1)
            step = {
                "entity_type": ntype,
                "entity_id": nid,
                "relationship": neighbor["relationship"],
            }
            path.append(step)
            visited.add(neighbor["node"])
            walk(neighbor["node"], path, visited)
            visited.remove(neighbor["node"])
            path.pop()

    walk(root, [{"entity_type": "REQUIREMENT", "entity_id": requirement_id, "relationship": None}], {root})

    # Also include version lineage recorded on the requirement itself.
    req = next((r for r in (state.get("requirements") or []) if r.get("id") == requirement_id), None)
    return {
        "requirement_id": requirement_id,
        "requirement": req,
        "direct_links": related,
        "chains": chains,
        "version_lineage": list((req or {}).get("lineage") or []),
    }
