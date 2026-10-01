"""Attack ontology for adversarial Grill."""

from __future__ import annotations

from enum import Enum


class AttackOntology(str, Enum):
    RESOURCE_FEASIBILITY = "RESOURCE_FEASIBILITY"
    DATA_AVAILABILITY = "DATA_AVAILABILITY"
    LATENCY = "LATENCY"
    SCALABILITY = "SCALABILITY"
    SECURITY = "SECURITY"
    EVALUATION = "EVALUATION"
    DEPENDENCY = "DEPENDENCY"
    SCOPE = "SCOPE"
    COST = "COST"
    TIMELINE = "TIMELINE"
    ASSUMPTION = "ASSUMPTION"
    CONTRADICTION = "CONTRADICTION"
    REQUIREMENT_AMBIGUITY = "REQUIREMENT_AMBIGUITY"
    ARCHITECTURE_MISMATCH = "ARCHITECTURE_MISMATCH"
    TECHNOLOGY_JUSTIFICATION = "TECHNOLOGY_JUSTIFICATION"
    DEPLOYMENT = "DEPLOYMENT"
    RELIABILITY = "RELIABILITY"
    MAINTAINABILITY = "MAINTAINABILITY"


# Map legacy dimension names → ontology types
DIMENSION_TO_ONTOLOGY = {
    "problem_clarity": AttackOntology.REQUIREMENT_AMBIGUITY,
    "scope": AttackOntology.SCOPE,
    "dataset": AttackOntology.DATA_AVAILABILITY,
    "feasibility": AttackOntology.RESOURCE_FEASIBILITY,
    "ai_necessity": AttackOntology.TECHNOLOGY_JUSTIFICATION,
    "evaluation": AttackOntology.EVALUATION,
    "research_potential": AttackOntology.EVALUATION,
    "deployment": AttackOntology.DEPLOYMENT,
    "security": AttackOntology.SECURITY,
    "dependency_risk": AttackOntology.DEPENDENCY,
    "timeline": AttackOntology.TIMELINE,
    "objective_alignment": AttackOntology.REQUIREMENT_AMBIGUITY,
}
