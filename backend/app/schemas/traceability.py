"""Traceability links between project-state entities."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TraceEntityType(str, Enum):
    REQUIREMENT = "REQUIREMENT"
    CLAIM = "CLAIM"
    ASSUMPTION = "ASSUMPTION"
    EVIDENCE = "EVIDENCE"
    DECISION = "DECISION"
    ATTACK = "ATTACK"
    VERIFICATION = "VERIFICATION"
    AGENT_RUN = "AGENT_RUN"
    ARCHITECTURE = "ARCHITECTURE"
    RESEARCH_FINDING = "RESEARCH_FINDING"


class TraceRelationship(str, Enum):
    SUPPORTS = "SUPPORTS"
    DERIVED_FROM = "DERIVED_FROM"
    DEPENDS_ON = "DEPENDS_ON"
    AFFECTS = "AFFECTS"
    CHALLENGES = "CHALLENGES"
    RESOLVES = "RESOLVES"
    VERIFIES = "VERIFIES"
    SUPERSEDES = "SUPERSEDES"
    SUPPORTED_BY = "SUPPORTED_BY"


class TraceLink(BaseModel):
    id: str
    project_id: str | None = None
    source_type: TraceEntityType
    source_id: str
    target_type: TraceEntityType
    target_id: str
    relationship: TraceRelationship
    confidence: float | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None

    model_config = {"extra": "allow"}

    def as_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["source_type"] = self.source_type.value
        data["target_type"] = self.target_type.value
        data["relationship"] = self.relationship.value
        return data
