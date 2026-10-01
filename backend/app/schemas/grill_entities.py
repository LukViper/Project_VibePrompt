"""Structured adversarial Grill entities."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GrillTargetType(str, Enum):
    REQUIREMENT = "REQUIREMENT"
    ASSUMPTION = "ASSUMPTION"
    CLAIM = "CLAIM"
    DECISION = "DECISION"
    ARCHITECTURE = "ARCHITECTURE"
    RESEARCH_FINDING = "RESEARCH_FINDING"
    CONSTRAINT = "CONSTRAINT"
    PROJECT = "PROJECT"


class GrillAttackStatus(str, Enum):
    OPEN = "OPEN"
    RESPONDED = "RESPONDED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    UNRESOLVED = "UNRESOLVED"


class GrillResolutionType(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"


class GrillAttack(BaseModel):
    id: str
    project_id: str | None = None
    target_type: GrillTargetType
    target_id: str
    attack_type: str
    claim: str = ""
    challenge: str
    rationale: str = ""
    evidence_required: str = ""
    failure_condition: str = ""
    severity: str = "MEDIUM"
    status: GrillAttackStatus = GrillAttackStatus.OPEN
    response_id: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None
    blocking: bool = True

    model_config = {"extra": "allow"}

    def as_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["target_type"] = self.target_type.value
        data["status"] = self.status.value
        return data


class GrillResponse(BaseModel):
    id: str
    attack_id: str
    response_text: str
    resolution_type: GrillResolutionType
    new_evidence_ids: list[str] = Field(default_factory=list)
    new_decision_id: str | None = None
    new_requirement_ids: list[str] = Field(default_factory=list)
    state_changes: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None

    model_config = {"extra": "allow"}

    def as_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["resolution_type"] = self.resolution_type.value
        return data
