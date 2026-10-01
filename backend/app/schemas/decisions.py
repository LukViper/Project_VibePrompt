"""Decision lifecycle and structured decision records (Master Spec §§6–7)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.provenance import Provenance, ProvenanceSource, make_provenance


class DecisionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


class ChangeKind(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    SCOPE_CHANGE = "SCOPE_CHANGE"
    CONFLICT = "CONFLICT"
    UNCERTAIN = "UNCERTAIN"


class StructuredDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: str = "decision"
    slot: str | None = None
    value: Any = None
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    status: DecisionStatus = DecisionStatus.PROPOSED
    provenance: Provenance = Field(default_factory=lambda: Provenance(source=ProvenanceSource.INFERRED))
    reason: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    alternatives_considered: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    user_approved: bool = False
    superseded_by: str | None = None

    model_config = {"extra": "allow"}

    def as_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["status"] = self.status.value
        data["provenance"] = (
            self.provenance.as_dict()
            if isinstance(self.provenance, Provenance)
            else dict(self.provenance or {})
        )
        return data


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_decision(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade legacy decision dicts onto the structured lifecycle shape."""
    item = dict(raw or {})
    item.setdefault("id", str(uuid4()))
    item.setdefault("kind", item.get("kind") or "decision")
    item.setdefault("summary", item.get("summary") or "")
    item.setdefault("details", item.get("details") or {})
    item.setdefault("value", item.get("value") if "value" in item else item.get("summary"))
    item.setdefault("slot", item.get("slot"))
    item.setdefault("reason", item.get("reason") or (item.get("provenance") or {}).get("reason") or "")
    item.setdefault("timestamp", item.get("timestamp") or now_iso())
    item.setdefault("alternatives_considered", item.get("alternatives_considered") or [])
    item.setdefault("evidence", item.get("evidence") or [])
    item.setdefault("dependencies", item.get("dependencies") or [])
    item.setdefault("superseded_by", item.get("superseded_by"))

    status = item.get("status")
    if status not in {s.value for s in DecisionStatus}:
        # Legacy user decisions that mutated state were effectively ACTIVE.
        kind = (item.get("kind") or "").lower()
        if kind in {"select_idea", "technology_change", "finalize"}:
            item["status"] = DecisionStatus.ACTIVE.value
            item["user_approved"] = True
        elif kind in {"tech_recommendation", "architecture_recommendation", "research_finding"}:
            item["status"] = DecisionStatus.PROPOSED.value
            item["user_approved"] = False
        else:
            item["status"] = DecisionStatus.ACTIVE.value
            item.setdefault("user_approved", True)
    else:
        item.setdefault("user_approved", item.get("status") == DecisionStatus.ACTIVE.value)

    if "provenance" not in item or not isinstance(item.get("provenance"), dict):
        item["provenance"] = make_provenance(
            ProvenanceSource.INFERRED,
            reason="migrated decision",
            user_approved=bool(item.get("user_approved")),
        )
    else:
        prov = dict(item["provenance"])
        if prov.get("user_approved") is None:
            prov["user_approved"] = bool(item.get("user_approved"))
        item["provenance"] = prov
    return item


def propose_decision(
    *,
    kind: str,
    summary: str,
    value: Any = None,
    slot: str | None = None,
    details: dict | None = None,
    source: ProvenanceSource = ProvenanceSource.AI_RECOMMENDATION,
    reason: str = "",
    alternatives: list[dict] | None = None,
    evidence: list[dict] | None = None,
    dependencies: list[str] | None = None,
    confidence: float | None = None,
    status: DecisionStatus = DecisionStatus.PROPOSED,
) -> dict[str, Any]:
    approved = status == DecisionStatus.ACTIVE
    return StructuredDecision(
        kind=kind,
        slot=slot,
        value=value if value is not None else summary,
        summary=summary,
        details=details or {},
        status=status,
        provenance=Provenance(
            source=source,
            reason=reason or kind,
            user_approved=approved,
            confidence=confidence,
        ),
        reason=reason or kind,
        alternatives_considered=alternatives or [],
        evidence=evidence or [],
        dependencies=dependencies or [],
        user_approved=approved,
    ).as_dict()
