"""Provenance for requirements and decisions.

Origins distinguish user intent from research, recommendations, and inference.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProvenanceSource(str, Enum):
    USER = "USER"
    RESEARCH = "RESEARCH"
    AI_RECOMMENDATION = "AI_RECOMMENDATION"
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"
    INFERRED = "INFERRED"


class Provenance(BaseModel):
    source: ProvenanceSource = ProvenanceSource.USER
    reason: str = ""
    user_approved: bool | None = None
    confidence: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "reason": self.reason,
            "user_approved": self.user_approved,
            "confidence": self.confidence,
        }


def make_provenance(
    source: ProvenanceSource | str = ProvenanceSource.USER,
    reason: str = "",
    user_approved: bool | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    if isinstance(source, str):
        source = ProvenanceSource(source)
    return Provenance(
        source=source,
        reason=reason,
        user_approved=user_approved,
        confidence=confidence,
    ).as_dict()


def ensure_provenance(item: dict, default_source: ProvenanceSource = ProvenanceSource.USER) -> dict:
    """Attach provenance to a requirement/decision dict if missing."""
    if "provenance" not in item or not isinstance(item.get("provenance"), dict):
        item["provenance"] = make_provenance(default_source, reason="legacy or unspecified")
    else:
        raw = item["provenance"]
        try:
            Provenance.model_validate(raw)
        except Exception:
            item["provenance"] = make_provenance(
                default_source,
                reason=str(raw.get("reason") or "repaired invalid provenance"),
            )
    return item
