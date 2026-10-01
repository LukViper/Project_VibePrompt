"""Strongly typed ProjectState.

Conversation history is not the source of truth. This schema validates and
documents the structured state. Extra keys are allowed for forward compatibility.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.provenance import Provenance, ProvenanceSource, make_provenance
from app.schemas.decisions import DecisionStatus, normalize_decision


class ConversationStage(str, Enum):
    DISCOVERY = "DISCOVERY"
    IDEATION = "IDEATION"
    IDEA_SELECTED = "IDEA_SELECTED"
    CUSTOMIZATION = "CUSTOMIZATION"
    RESEARCH = "RESEARCH"
    REQUIREMENTS = "REQUIREMENTS"
    GRILL = "GRILL"
    ARCHITECTURE = "ARCHITECTURE"
    TECH_STACK = "TECH_STACK"
    IMPLEMENTATION_PLAN = "IMPLEMENTATION_PLAN"
    REVIEW = "REVIEW"
    PROMPT_GENERATION = "PROMPT_GENERATION"
    VALIDATION = "VALIDATION"
    COMPLETED = "COMPLETED"


class ProjectInfo(BaseModel):
    title: str = ""
    problem: str = ""
    objective: str = ""
    subject: str | None = None
    domain: str | None = None
    target_users: str | None = None
    platform: list[str] | str | None = None
    scope: str | None = None


class AcademicInfo(BaseModel):
    subject: str | None = None
    required_concepts: list[str] = Field(default_factory=list)


class ConstraintInfo(BaseModel):
    team_size: int | None = None
    duration: str | None = None
    budget: str | None = None
    avoid: list[str] = Field(default_factory=list)
    skill_level: str | None = None
    research_required: bool | None = None


class CoreIdea(BaseModel):
    problem: str | None = None
    primary_domain: str | None = None
    primary_objective: str | None = None
    locked: bool = False
    idea_id: str | None = None
    title: str | None = None
    user_customizations: list[str] = Field(default_factory=list)


class IdeaBlock(BaseModel):
    base_idea: dict[str, Any] | None = None
    user_customizations: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)


class RequirementRecord(BaseModel):
    id: str
    type: str = "functional"
    text: str
    status: str = "active"
    version: int = 1
    slot: str | None = None
    slot_value: str | None = None
    domain: str | None = None
    origin: str = "added"
    provenance: Provenance = Field(default_factory=lambda: Provenance(source=ProvenanceSource.USER))
    versions: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class DecisionRecord(BaseModel):
    id: str | None = None
    kind: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    slot: str | None = None
    value: Any = None
    status: DecisionStatus = DecisionStatus.ACTIVE
    provenance: Provenance = Field(default_factory=lambda: Provenance(source=ProvenanceSource.INFERRED))
    reason: str = ""
    timestamp: str | None = None
    alternatives_considered: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    user_approved: bool = False
    superseded_by: str | None = None

    model_config = {"extra": "allow"}


class GrillReport(BaseModel):
    """Master Spec §15 structured grill output."""

    blocking: list[str] = Field(default_factory=list)
    high_risk: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    validated: list[str] = Field(default_factory=list)
    change_required: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    realistic_plan: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    iteration: int = 1
    summary: str = ""
    dimensions: list[dict[str, Any]] = Field(default_factory=list)


class ResearchLevel(str, Enum):
    LEVEL_0 = "LEVEL_0"
    LEVEL_1 = "LEVEL_1"
    LEVEL_2 = "LEVEL_2"
    LEVEL_3 = "LEVEL_3"


class ResearchFinding(BaseModel):
    finding: str
    source: str = ""
    source_type: str = "unknown"
    timestamp: str | None = None
    relevance: str | None = None
    confidence: float | None = None
    project_impact: str | None = None
    verification_status: str = "unverified"


class PromptMetrics(BaseModel):
    token_count: int | None = None
    requirement_coverage: float | None = None
    constraint_coverage: float | None = None
    acceptance_coverage: float | None = None
    redundancy: float | None = None
    ambiguity: float | None = None
    missing_requirements: list[str] = Field(default_factory=list)


class ConversationContext(BaseModel):
    """Layer A — conversational memory (not hard project constraints)."""

    topic: str | None = None
    last_intent: str | None = None
    interests: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    statements: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recent_questions: list[str] = Field(default_factory=list)
    learning_context: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class ExplorationState(BaseModel):
    """Layer B — ideas and directions under discussion."""

    current_direction: str | None = None
    ideas_proposed: list[dict[str, Any]] = Field(default_factory=list)
    ideas_selected: list[dict[str, Any]] = Field(default_factory=list)
    ideas_rejected: list[dict[str, Any]] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    user_reactions: list[str] = Field(default_factory=list)
    unresolved_decisions: list[str] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class ProjectStateModel(BaseModel):
    schema_version: int = 2
    conversation_stage: ConversationStage = ConversationStage.DISCOVERY
    conversation_context: ConversationContext = Field(default_factory=ConversationContext)
    exploration: ExplorationState = Field(default_factory=ExplorationState)
    project: ProjectInfo = Field(default_factory=ProjectInfo)
    academic: AcademicInfo = Field(default_factory=AcademicInfo)
    idea: IdeaBlock = Field(default_factory=IdeaBlock)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    constraints: ConstraintInfo = Field(default_factory=ConstraintInfo)
    technology: dict[str, Any] = Field(default_factory=dict)
    architecture: dict[str, Any] = Field(default_factory=dict)
    database: dict[str, Any] = Field(default_factory=dict)
    apis: list[dict[str, Any]] = Field(default_factory=list)
    ai_nlp: dict[str, Any] = Field(default_factory=dict)
    security: list[str] = Field(default_factory=list)
    testing: dict[str, Any] = Field(default_factory=dict)
    deployment: dict[str, Any] = Field(default_factory=dict)
    research: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    decision_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    implementation_plan: list[str] = Field(default_factory=list)
    grill_findings: dict[str, Any] | None = None
    grill_report: dict[str, Any] | None = None
    last_impact: dict[str, Any] | None = None
    rejected_ideas: list = Field(default_factory=list)
    # Readiness gaps for compile/grill — NOT auto-asked in ordinary dialogue.
    open_questions: list[str] = Field(default_factory=list)
    readiness_gaps: list[str] = Field(default_factory=list)
    core_idea: CoreIdea | None = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    drift: dict[str, Any] | None = None
    scope: dict[str, Any] | None = None
    domains: list[str] = Field(default_factory=list)
    prompt: dict[str, Any] = Field(default_factory=dict)
    prompt_metrics: PromptMetrics | None = None
    state_version: int = 1
    research_level_last: str | None = None
    last_orchestrator_action: str | None = None

    model_config = {"extra": "allow"}

    @field_validator("conversation_stage", mode="before")
    @classmethod
    def _coerce_stage(cls, value):
        if value is None or value == "":
            return ConversationStage.DISCOVERY
        if isinstance(value, ConversationStage):
            return value
        return ConversationStage(str(value))


def _default_technology() -> dict[str, Any]:
    return {
        "languages": [],
        "frameworks": [],
        "databases": [],
        "models": [],
        "hardware": [],
        "other": [],
        "backend": None,
        "database": None,
        "model": None,
    }


def empty_state_dict() -> dict[str, Any]:
    data = ProjectStateModel().model_dump(mode="json")
    data["technology"] = _default_technology()
    data["architecture"] = data.get("architecture") or {}
    data["database"] = data.get("database") or {}
    data["testing"] = data.get("testing") or {}
    data["deployment"] = data.get("deployment") or {}
    data["ai_nlp"] = data.get("ai_nlp") or {}
    data["prompt"] = data.get("prompt") or {}
    return data


def migrate_state(raw: dict | None) -> dict[str, Any]:
    """Upgrade legacy v1 JSON onto the current schema without dropping data."""
    base = empty_state_dict()
    if not raw:
        return base
    merged = {**base, **raw}
    for key, default in base.items():
        if key not in merged or merged[key] is None:
            merged[key] = default
    # Preserve nested technology list keys used by NLP merge.
    tech = merged.get("technology")
    if not isinstance(tech, dict):
        merged["technology"] = _default_technology()
    else:
        for key, value in _default_technology().items():
            tech.setdefault(key, value)
    # Mirror academic subject into project.subject when missing.
    academic = merged.get("academic") or {}
    project = merged.setdefault("project", {})
    if isinstance(project, dict) and not project.get("subject") and academic.get("subject"):
        project["subject"] = academic["subject"]
    for req in merged.get("requirements") or []:
        if isinstance(req, dict) and "provenance" not in req:
            req["provenance"] = make_provenance(
                ProvenanceSource.USER if req.get("origin") != "original" else ProvenanceSource.USER,
                reason="migrated from legacy requirement",
            )
    for decision in merged.get("decisions") or []:
        if isinstance(decision, dict):
            # normalize_decision adds provenance + lifecycle fields
            pass
    merged["decisions"] = [
        normalize_decision(item) for item in (merged.get("decisions") or []) if isinstance(item, dict)
    ]
    merged.setdefault("decision_dependencies", [])
    merged.setdefault("grill_report", merged.get("grill_report"))
    merged.setdefault("last_impact", merged.get("last_impact"))
    merged.setdefault("conversation_context", {})
    merged.setdefault("exploration", {})
    merged.setdefault("readiness_gaps", merged.get("readiness_gaps") or [])
    merged["schema_version"] = 2
    # Validate then dump to normalize enums/types.
    return ProjectStateModel.model_validate(merged).model_dump(mode="json")


def validate_state(raw: dict) -> ProjectStateModel:
    return ProjectStateModel.model_validate(migrate_state(raw))
