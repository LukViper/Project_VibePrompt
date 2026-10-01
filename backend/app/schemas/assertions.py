"""Shared assertion lifecycle for requirements, claims, assumptions, and decisions."""

from __future__ import annotations

from enum import Enum


class AssertionStatus(str, Enum):
    MENTIONED = "MENTIONED"
    INFERRED = "INFERRED"
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    LOCKED = "LOCKED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ClaimSource(str, Enum):
    USER = "USER"
    RESEARCH = "RESEARCH"
    LLM_INFERENCE = "LLM_INFERENCE"
    SYSTEM = "SYSTEM"
    AGENT = "AGENT"


class AssertionOrigin(str, Enum):
    """How an assertion entered ProjectState — orthogonal to AssertionStatus."""

    USER_EXPLICIT = "USER_EXPLICIT"
    USER_INFERRED = "USER_INFERRED"
    LLM_INFERRED = "LLM_INFERRED"
    GRILL_DERIVED = "GRILL_DERIVED"
    RESEARCH_DERIVED = "RESEARCH_DERIVED"
    SYSTEM_GENERATED = "SYSTEM_GENERATED"
    AGENT_DERIVED = "AGENT_DERIVED"


# Origins that may start as CONFIRMED without an extra promotion step.
EXPLICIT_CONFIRMABLE_ORIGINS = frozenset({AssertionOrigin.USER_EXPLICIT})

# Origins that must remain non-authoritative until explicit user confirmation.
PROPOSED_ONLY_ORIGINS = frozenset(
    {
        AssertionOrigin.USER_INFERRED,
        AssertionOrigin.LLM_INFERRED,
        AssertionOrigin.GRILL_DERIVED,
        AssertionOrigin.RESEARCH_DERIVED,
        AssertionOrigin.SYSTEM_GENERATED,
        AssertionOrigin.AGENT_DERIVED,
    }
)


class AssumptionRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GrillAssumptionStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    CHALLENGED = "CHALLENGED"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"


class EvidenceType(str, Enum):
    USER_PROVIDED = "USER_PROVIDED"
    RESEARCH = "RESEARCH"
    DOCUMENTATION = "DOCUMENTATION"
    EXPERIMENT = "EXPERIMENT"
    BENCHMARK = "BENCHMARK"
    AGENT_OUTPUT = "AGENT_OUTPUT"
    TEST_RESULT = "TEST_RESULT"
    SYSTEM_OBSERVATION = "SYSTEM_OBSERVATION"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# Statuses that may appear in compiled specifications / active integrity views.
ACTIVE_ASSERTION_STATUSES = frozenset(
    {
        AssertionStatus.MENTIONED,
        AssertionStatus.INFERRED,
        AssertionStatus.PROPOSED,
        AssertionStatus.CONFIRMED,
        AssertionStatus.LOCKED,
    }
)

AUTHORITATIVE_ASSERTION_STATUSES = frozenset(
    {
        AssertionStatus.CONFIRMED,
        AssertionStatus.LOCKED,
    }
)

INACTIVE_ASSERTION_STATUSES = frozenset(
    {
        AssertionStatus.REJECTED,
        AssertionStatus.SUPERSEDED,
    }
)
