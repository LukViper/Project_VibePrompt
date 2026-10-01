"""Deterministic assertion lifecycle rules."""

from __future__ import annotations

from app.schemas.assertions import (
    ACTIVE_ASSERTION_STATUSES,
    AUTHORITATIVE_ASSERTION_STATUSES,
    EXPLICIT_CONFIRMABLE_ORIGINS,
    INACTIVE_ASSERTION_STATUSES,
    PROPOSED_ONLY_ORIGINS,
    AssertionOrigin,
    AssertionStatus,
)
from app.schemas.provenance import ProvenanceSource


def is_active_assertion(status: str | AssertionStatus | None) -> bool:
    if status is None:
        return False
    if isinstance(status, AssertionStatus):
        return status in ACTIVE_ASSERTION_STATUSES
    try:
        return AssertionStatus(status) in ACTIVE_ASSERTION_STATUSES
    except ValueError:
        return False


def is_authoritative_assertion(status: str | AssertionStatus | None) -> bool:
    if status is None:
        return False
    if isinstance(status, AssertionStatus):
        return status in AUTHORITATIVE_ASSERTION_STATUSES
    try:
        return AssertionStatus(status) in AUTHORITATIVE_ASSERTION_STATUSES
    except ValueError:
        return False


def is_inactive_assertion(status: str | AssertionStatus | None) -> bool:
    if status is None:
        return False
    if isinstance(status, AssertionStatus):
        return status in INACTIVE_ASSERTION_STATUSES
    try:
        return AssertionStatus(status) in INACTIVE_ASSERTION_STATUSES
    except ValueError:
        return False


def inferred_not_confirmed(status: str | AssertionStatus | None) -> bool:
    if status is None:
        return True
    try:
        parsed = status if isinstance(status, AssertionStatus) else AssertionStatus(status)
    except ValueError:
        return True
    return parsed != AssertionStatus.CONFIRMED and parsed != AssertionStatus.LOCKED


def promotion_allowed(current: str | AssertionStatus, target: str | AssertionStatus) -> bool:
    """Only explicit promotions along the lifecycle — never skip to CONFIRMED from silent inference."""
    try:
        cur = current if isinstance(current, AssertionStatus) else AssertionStatus(current)
        tgt = target if isinstance(target, AssertionStatus) else AssertionStatus(target)
    except ValueError:
        return False
    if cur in INACTIVE_ASSERTION_STATUSES:
        return False
    allowed = {
        AssertionStatus.MENTIONED: {
            AssertionStatus.INFERRED,
            AssertionStatus.PROPOSED,
            AssertionStatus.REJECTED,
        },
        AssertionStatus.INFERRED: {
            AssertionStatus.PROPOSED,
            AssertionStatus.REJECTED,
        },
        AssertionStatus.PROPOSED: {
            AssertionStatus.CONFIRMED,
            AssertionStatus.REJECTED,
            AssertionStatus.SUPERSEDED,
        },
        AssertionStatus.CONFIRMED: {
            AssertionStatus.LOCKED,
            AssertionStatus.SUPERSEDED,
            AssertionStatus.REJECTED,
        },
        AssertionStatus.LOCKED: {AssertionStatus.SUPERSEDED},
    }
    return tgt in allowed.get(cur, set())


def normalize_assertion_origin(origin: AssertionOrigin | str | None) -> AssertionOrigin | None:
    if origin is None or origin == "":
        return None
    if isinstance(origin, AssertionOrigin):
        return origin
    try:
        return AssertionOrigin(origin)
    except ValueError:
        return None


def default_status_for_origin(origin: AssertionOrigin | str) -> AssertionStatus:
    """Map assertion origin → initial lifecycle status. Never silently confirms non-explicit origins."""
    parsed = normalize_assertion_origin(origin) or AssertionOrigin.SYSTEM_GENERATED
    if parsed in EXPLICIT_CONFIRMABLE_ORIGINS:
        return AssertionStatus.CONFIRMED
    if parsed == AssertionOrigin.LLM_INFERRED:
        return AssertionStatus.PROPOSED
    if parsed in PROPOSED_ONLY_ORIGINS:
        return AssertionStatus.PROPOSED
    return AssertionStatus.PROPOSED


def infer_origin_from_provenance(
    provenance_source: ProvenanceSource | str,
    *,
    explicit: bool = False,
    origin_hint: AssertionOrigin | str | None = None,
) -> AssertionOrigin:
    hinted = normalize_assertion_origin(origin_hint)
    if hinted is not None:
        return hinted
    if isinstance(provenance_source, str):
        try:
            provenance_source = ProvenanceSource(provenance_source)
        except ValueError:
            provenance_source = ProvenanceSource.INFERRED
    if provenance_source == ProvenanceSource.USER:
        return AssertionOrigin.USER_EXPLICIT if explicit else AssertionOrigin.USER_INFERRED
    if provenance_source == ProvenanceSource.RESEARCH:
        return AssertionOrigin.RESEARCH_DERIVED
    if provenance_source == ProvenanceSource.AI_RECOMMENDATION:
        return AssertionOrigin.LLM_INFERRED
    if provenance_source == ProvenanceSource.SYSTEM_DEFAULT:
        return AssertionOrigin.SYSTEM_GENERATED
    if provenance_source == ProvenanceSource.INFERRED:
        return AssertionOrigin.LLM_INFERRED
    return AssertionOrigin.SYSTEM_GENERATED


def default_requirement_assertion_status(
    *,
    provenance_source: ProvenanceSource | str,
    user_approved: bool | None = None,
    origin: AssertionOrigin | str | None = None,
    explicit: bool = False,
) -> AssertionStatus:
    """Prefer AssertionOrigin when provided; fall back to provenance heuristics."""
    resolved_origin = infer_origin_from_provenance(
        provenance_source,
        explicit=explicit or bool(user_approved and origin is None),
        origin_hint=origin,
    )
    # Only USER_EXPLICIT may start CONFIRMED. user_approved alone is insufficient for RESEARCH.
    if resolved_origin == AssertionOrigin.USER_EXPLICIT:
        return AssertionStatus.CONFIRMED
    return default_status_for_origin(resolved_origin)


def migrate_requirement_assertion_status(req: dict) -> dict:
    """Attach assertion_status / assertion_origin to legacy requirements."""
    if not req.get("assertion_origin"):
        prov = req.get("provenance") or {}
        source = prov.get("source") or ProvenanceSource.USER.value
        # Legacy active+user_approved USER reqs treated as USER_EXPLICIT for backwards compatibility.
        explicit = bool(prov.get("user_approved")) and source == ProvenanceSource.USER.value
        if req.get("origin") == "grill_response":
            req["assertion_origin"] = AssertionOrigin.GRILL_DERIVED.value
        elif source == ProvenanceSource.RESEARCH.value:
            req["assertion_origin"] = AssertionOrigin.RESEARCH_DERIVED.value
        else:
            req["assertion_origin"] = infer_origin_from_provenance(
                source, explicit=explicit
            ).value
    if req.get("assertion_status"):
        return req
    legacy_status = str(req.get("status") or "active").lower()
    if legacy_status in {"removed", "rejected"}:
        req["assertion_status"] = AssertionStatus.REJECTED.value
    elif legacy_status == "superseded":
        req["assertion_status"] = AssertionStatus.SUPERSEDED.value
    else:
        req["assertion_status"] = default_status_for_origin(req["assertion_origin"]).value
    return req


def requirement_is_compilable(req: dict) -> bool:
    """Requirements compiled only when authoritative and legacy-active."""
    if str(req.get("status") or "").lower() not in {"active"}:
        return False
    return is_authoritative_assertion(req.get("assertion_status"))
