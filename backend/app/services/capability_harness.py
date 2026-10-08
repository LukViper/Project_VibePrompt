"""Capability harness — gate ideas / architecture / grill so VibePrompt isn't misused.

All three capabilities must run through this layer (chat or REST). The harness:
1. Requires enough ProjectState before a capability may run
2. Keeps ideation grounded in the stated subject/domain
3. Records provenance for audit / evaluation
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import HTTPException

from app.nlp.extraction import detect_domains
from app.nlp.lexicon import DOMAIN_LABELS, domains_conflict
from app.schemas.state import migrate_state


class CapabilityKind(str, Enum):
    IDEATION = "IDEATION"
    ARCHITECTURE = "ARCHITECTURE"
    GRILL = "GRILL"


@dataclass
class GateResult:
    allowed: bool
    reason: str = ""
    guidance: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def raise_if_blocked(self) -> None:
        if self.allowed:
            return
        raise HTTPException(
            status_code=400,
            detail={
                "error": "capability_gated",
                "reason": self.reason,
                "guidance": self.guidance,
                "provenance": self.provenance,
            },
        )


def _core_domain_ids(state: dict) -> list[str]:
    found: list[str] = []
    subject = ((state.get("academic") or {}).get("subject") or "")
    found.extend(detect_domains(subject))
    core = state.get("core_idea") or {}
    if core.get("primary_domain"):
        found.extend(detect_domains(str(core["primary_domain"])))
    found.extend(detect_domains(str((state.get("project") or {}).get("objective") or "")))
    found.extend(detect_domains(str((state.get("project") or {}).get("problem") or "")))
    found.extend(detect_domains(str((state.get("exploration") or {}).get("current_direction") or "")))
    for item in state.get("domains") or []:
        if isinstance(item, str) and item not in found:
            found.append(item)
    # de-dupe preserving order
    return list(dict.fromkeys(found))


def _has_direction(state: dict) -> bool:
    academic = state.get("academic") or {}
    project = state.get("project") or {}
    core = state.get("core_idea") or {}
    exploration = state.get("exploration") or {}
    return bool(
        academic.get("subject")
        or _core_domain_ids(state)
        or project.get("objective")
        or project.get("problem")
        or core.get("primary_objective")
        or exploration.get("current_direction")
    )


def _has_project_substance(state: dict) -> bool:
    project = state.get("project") or {}
    core = state.get("core_idea") or {}
    reqs = [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
    return bool(
        project.get("objective")
        or project.get("problem")
        or core.get("primary_objective")
        or core.get("locked")
        or len(reqs) >= 1
    )


def gate_capability(state: dict | None, kind: CapabilityKind) -> GateResult:
    """Decide whether a capability may run on the current ProjectState."""
    state = migrate_state(state or {})
    domains = _core_domain_ids(state)
    subject = ((state.get("academic") or {}).get("subject") or "").strip()
    provenance = {
        "capability": kind.value,
        "subject": subject or None,
        "domains": domains,
        "labels": [DOMAIN_LABELS.get(d, d) for d in domains],
    }

    if kind == CapabilityKind.IDEATION:
        if not _has_direction(state):
            return GateResult(
                allowed=False,
                reason="missing_domain",
                guidance=(
                    "Tell me the course or domain first (e.g. Computer Networks, NLP, "
                    "Cybersecurity, Data Science) before I suggest project ideas."
                ),
                provenance=provenance,
            )
        return GateResult(allowed=True, provenance=provenance)

    if kind == CapabilityKind.ARCHITECTURE:
        if not _has_project_substance(state):
            return GateResult(
                allowed=False,
                reason="missing_core_idea",
                guidance=(
                    "Pick or describe a concrete project direction first, then I can "
                    "propose an architecture grounded in that ProjectState."
                ),
                provenance=provenance,
            )
        return GateResult(allowed=True, provenance=provenance)

    if kind == CapabilityKind.GRILL:
        if not _has_project_substance(state):
            return GateResult(
                allowed=False,
                reason="missing_project_to_grill",
                guidance=(
                    "Grill needs a real project to challenge. Share a direction or "
                    "requirements first — otherwise grilling is just generic criticism."
                ),
                provenance=provenance,
            )
        return GateResult(allowed=True, provenance=provenance)

    return GateResult(allowed=False, reason="unknown_capability", guidance="Unsupported capability.", provenance=provenance)


_SUBJECT_HINTS: dict[str, list[str]] = {
    "computer networks": ["network", "packet", "protocol", "routing", "sdn", "tcp", "wifi", "wireless", "iot", "traffic", "subnet"],
    "nlp": ["text", "language", "nlp", "token", "sentiment", "classification", "ner", "citation", "forum"],
    "cybersecurity": ["phish", "malware", "security", "vulnerab", "intrusion", "log", "threat", "cve"],
    "data science": ["churn", "forecast", "segment", "fraud", "demand", "predict", "cluster", "regression", "tabular"],
    "machine learning": ["model", "train", "classif", "cluster", "predict", "learning", "feature"],
}


def idea_matches_domain(idea_blob: str, state: dict) -> bool:
    """True unless the idea clearly drifts away from the project's subject/domain.

    Reject-only: related cross-topic ideas (e.g. NLP + phishing) stay allowed.
    Hard blocks catch known misuse patterns like Data-Science churn cards on
    Computer Networks / NLP / Cybersecurity subjects.
    """
    state = migrate_state(state or {})
    subject = ((state.get("academic") or {}).get("subject") or "").strip().lower()
    core = _core_domain_ids(state)
    blob = (idea_blob or "").lower()
    idea_domains = detect_domains(blob)

    if core and idea_domains and domains_conflict(set(core), set(idea_domains)):
        return False

    ds_template = bool(
        re.search(
            r"\b(customer churn|sales forecasting|customer segmentation|demand prediction)\b",
            blob,
        )
    )
    non_ds_subject = bool(
        re.search(r"\b(computer\s+networks?|nlp|cyber|security|networking)\b", subject)
    ) or any(d in {"computer_networks", "nlp", "cybersecurity"} for d in core)
    if ds_template and non_ds_subject:
        return False

    # Computer Networks: require at least a light networking signal when subject is set.
    if "computer network" in subject or "computer_networks" in core:
        hints = _SUBJECT_HINTS["computer networks"]
        if not any(h in blob for h in hints):
            return False
    return True


def filter_ideas_to_domain(ideas: list[Any], state: dict) -> tuple[list[Any], list[str]]:
    """Drop ideas that conflict with the locked subject/domain. Returns (kept, dropped_titles)."""
    kept = []
    dropped: list[str] = []
    for idea in ideas:
        title = getattr(idea, "title", None) or (idea.get("title") if isinstance(idea, dict) else "") or ""
        problem = getattr(idea, "problem", None) or (idea.get("problem") if isinstance(idea, dict) else "") or ""
        objective = getattr(idea, "objective", None) or (idea.get("objective") if isinstance(idea, dict) else "") or ""
        blob = f"{title} {problem} {objective}"
        if idea_matches_domain(blob, state):
            kept.append(idea)
        else:
            dropped.append(str(title))
    return kept, dropped


def gated_message(kind: CapabilityKind, gate: GateResult) -> str:
    return gate.guidance or f"{kind.value} is blocked until ProjectState is ready."


def run_ideation(session, project) -> dict[str, Any]:
    """Gate + generate ideas + domain filter. Shared by chat and REST."""
    from app.services import idea_generation
    from app.services.project_state import public_state

    state = migrate_state(project.state or {})
    gate = gate_capability(state, CapabilityKind.IDEATION)
    if not gate.allowed:
        return {
            "blocked": True,
            "response": gated_message(CapabilityKind.IDEATION, gate),
            "state": public_state(state),
            "ideas": [],
            "provenance": gate.provenance,
        }

    rows = idea_generation.generate_ideas(session, project)
    generated_count = len(rows)
    kept, dropped = filter_ideas_to_domain(rows, project.state or {})

    if dropped:
        from app.models import Idea

        keep_ids = {getattr(r, "id", None) for r in kept}
        for row in list(rows):
            if getattr(row, "id", None) not in keep_ids:
                session.delete(row)
        session.flush()

    # If the provider drifted entirely, regenerate from deterministic templates only.
    if not kept:
        from app.models import Idea
        from app.services.idea_generation import _templates

        session.query(Idea).filter(
            Idea.project_id == project.id,
            Idea.selected.is_(False),
            Idea.rejected.is_(False),
        ).delete()
        drafts = _templates(migrate_state(project.state or {}))
        kept_drafts, _ = filter_ideas_to_domain(drafts, project.state or {})
        kept = []
        for draft in kept_drafts[:5]:
            row = Idea(
                project_id=project.id,
                title=draft.title,
                problem=draft.problem,
                objective=draft.objective,
                required_concepts=draft.required_concepts,
                features=draft.features,
                technology=draft.technology,
                difficulty=draft.difficulty,
                estimated_scope=draft.estimated_scope,
                extensions=draft.extensions,
                details=draft.details_dict(),
                source="harness_domain_fallback",
                perspective="single",
            )
            session.add(row)
            kept.append(row)
        session.flush()

    provenance = {
        **gate.provenance,
        "generated": generated_count,
        "kept": len(kept),
        "dropped_titles": dropped,
        "harness": "capability_harness",
    }
    return {
        "blocked": False,
        "response": idea_generation.format_ideas_for_chat(kept),
        "state": public_state(project.state or {}),
        "ideas": kept,
        "provenance": provenance,
    }


def run_architecture(session, project) -> dict[str, Any]:
    from app.services.architecture import propose_architecture
    from app.services.project_state import public_state

    state = migrate_state(project.state or {})
    gate = gate_capability(state, CapabilityKind.ARCHITECTURE)
    if not gate.allowed:
        return {
            "blocked": True,
            "response": gated_message(CapabilityKind.ARCHITECTURE, gate),
            "state": public_state(state),
            "provenance": gate.provenance,
        }
    result = propose_architecture(session, project)
    result["provenance"] = {**gate.provenance, "harness": "capability_harness"}
    result["blocked"] = False
    return result


def run_grill(session, project) -> dict[str, Any]:
    from app.services.grill_session import create_grill_session
    from app.services.project_state import public_state

    state = migrate_state(project.state or {})
    gate = gate_capability(state, CapabilityKind.GRILL)
    if not gate.allowed:
        return {
            "blocked": True,
            "response": gated_message(CapabilityKind.GRILL, gate),
            "state": public_state(state),
            "provenance": gate.provenance,
        }
    report = create_grill_session(session, project)
    if isinstance(report, dict):
        report["provenance"] = {**gate.provenance, "harness": "capability_harness"}
        report["blocked"] = False
    return report
