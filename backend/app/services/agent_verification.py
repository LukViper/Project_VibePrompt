"""AgentRun / RequirementVerification helpers — reuses schema models only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.agent_verification import (
    AgentRun,
    ExecutionStatus,
    RequirementVerification,
    VerificationResultStatus,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_agent_run_id() -> str:
    return f"RUN-{uuid4().hex[:12]}"


def new_verification_id() -> str:
    return f"VER-{uuid4().hex[:12]}"


def build_agent_run(
    *,
    project_id: str,
    agent: str,
    repository: str | None,
    started_at: str | None,
    completed_at: str | None,
    build_status: str | None,
    test_status: str | None,
    output_summary: str = "",
    prompt_id: str | None = None,
    model: str | None = None,
    model_version: str | None = None,
    commit_before: str | None = None,
    commit_after: str | None = None,
    **extra: Any,
) -> AgentRun:
    """Construct an AgentRun record without fabricating performance."""
    return AgentRun(
        id=new_agent_run_id(),
        project_id=project_id,
        prompt_id=prompt_id,
        agent=agent,
        model=model,
        model_version=model_version,
        repository=repository,
        commit_before=commit_before,
        commit_after=commit_after,
        started_at=started_at,
        completed_at=completed_at,
        build_status=build_status,
        test_status=test_status,
        output_summary=output_summary,
        **extra,
    )


def build_requirement_verification(
    *,
    requirement_id: str,
    agent_run_id: str | None,
    status: VerificationResultStatus,
    evidence: list[str] | None = None,
    verification_method: str | None = None,
    test_results: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> RequirementVerification:
    """Construct a RequirementVerification. Missing evidence must not become PASS."""
    if status == VerificationResultStatus.PASS and not evidence:
        status = VerificationResultStatus.UNVERIFIED
        verification_method = verification_method or "denied_pass_without_evidence"
    return RequirementVerification(
        id=new_verification_id(),
        requirement_id=requirement_id,
        agent_run_id=agent_run_id,
        status=status,
        evidence=list(evidence or []),
        test_results=dict(test_results or {}),
        confidence=confidence,
        verified_at=_now() if status != VerificationResultStatus.NOT_TESTED else None,
        verification_method=verification_method,
    )


def classify_execution_status(
    *,
    agent_exit_code: int | None,
    agent_timed_out: bool,
    build_status: str | None,
    test_status: str | None,
) -> ExecutionStatus:
    if agent_exit_code is None:
        return ExecutionStatus.NOT_EXECUTED
    if agent_timed_out or agent_exit_code != 0:
        return ExecutionStatus.FAILED_INFRASTRUCTURE
    build_ok = build_status in {"PASS", "NOT_CONFIGURED", None}
    test_ok = test_status in {"PASS", "NOT_CONFIGURED", None}
    if build_status == "NOT_CONFIGURED" and test_status == "NOT_CONFIGURED":
        return ExecutionStatus.EXECUTED
    if build_status == "FAIL" or test_status == "FAIL":
        return ExecutionStatus.EXECUTED_WITH_VALIDATION
    if build_ok and test_ok and build_status != "NOT_CONFIGURED" and test_status != "NOT_CONFIGURED":
        return ExecutionStatus.EXECUTED_WITH_VALIDATION
    if build_status == "NOT_CONFIGURED" or test_status == "NOT_CONFIGURED":
        return ExecutionStatus.EXECUTED_WITH_PARTIAL_VALIDATION
    return ExecutionStatus.EXECUTED


def append_to_state(state: dict, agent_run: AgentRun, verifications: list[RequirementVerification]) -> dict:
    state.setdefault("agent_runs", []).append(agent_run.as_dict())
    state.setdefault("requirement_verifications", []).extend(v.as_dict() for v in verifications)
    return state
