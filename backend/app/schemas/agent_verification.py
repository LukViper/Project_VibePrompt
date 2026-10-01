"""Agent execution and requirement verification records (data model + interface)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VerificationResultStatus(str, Enum):
    NOT_TESTED = "NOT_TESTED"
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ExecutionStatus(str, Enum):
    """RQ5 scientific execution state — distinct from agent quality."""

    NOT_EXECUTED = "NOT_EXECUTED"
    EXECUTED = "EXECUTED"
    FAILED_INFRASTRUCTURE = "FAILED_INFRASTRUCTURE"
    EXECUTED_WITH_VALIDATION = "EXECUTED_WITH_VALIDATION"
    EXECUTED_WITH_PARTIAL_VALIDATION = "EXECUTED_WITH_PARTIAL_VALIDATION"


class AgentRun(BaseModel):
    id: str
    project_id: str
    prompt_id: str | None = None
    agent: str = "manual"
    model: str | None = None
    model_version: str | None = None
    repository: str | None = None
    commit_before: str | None = None
    commit_after: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    build_status: str | None = None
    test_status: str | None = None
    output_summary: str = ""

    model_config = {"extra": "allow"}

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class RequirementVerification(BaseModel):
    id: str
    requirement_id: str
    agent_run_id: str | None = None
    status: VerificationResultStatus = VerificationResultStatus.NOT_TESTED
    evidence: list[str] = Field(default_factory=list)
    test_results: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    verified_at: str | None = None
    verification_method: str | None = None

    model_config = {"extra": "allow"}

    def as_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["status"] = self.status.value
        return data
