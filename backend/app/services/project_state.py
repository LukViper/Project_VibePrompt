"""Structured project state.

The conversation is not the source of truth. This module owns updates,
stable requirement IDs, versions, decisions, snapshots, and provenance.
"""

from __future__ import annotations

import copy
import re
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import Decision, Project, Requirement, RequirementVersion
from app.nlp.extraction import detect_domains
from app.nlp.lexicon import DOMAIN_LABELS
from app.nlp.similarity import cosine_similarity
from app.nlp.embeddings import create_embedding
from app.schemas.provenance import ProvenanceSource, make_provenance
from app.schemas.state import ConversationStage, empty_state_dict, migrate_state
from app.services.assertion_lifecycle import (
    default_requirement_assertion_status,
    infer_origin_from_provenance,
)
from app.schemas.assertions import AssertionOrigin
from app.services.traceability import record_requirement_version_lineage
from app.services.versioning import StateVersioning


def empty_state() -> dict:
    return empty_state_dict()


def public_state(state: dict) -> dict:
    from app.services.integrity_store import integrity_summary

    cloned = migrate_state(state or {})
    for req in cloned.get("requirements") or []:
        req.pop("embedding", None)
    cloned.pop("_last_version_reason", None)
    cloned["integrity"] = integrity_summary(cloned)
    return cloned


def _set_auth_flag(state: dict, required: bool, reason: str) -> None:
    flag = f"authentication_required={'true' if required else 'false'}"
    security = state.setdefault("security", [])
    opposite = f"authentication_required={'false' if required else 'true'}"
    state["security"] = [item for item in security if item not in {flag, opposite}]
    state["security"].append(flag)
    _add_decision(
        state,
        "authentication_constraint",
        flag,
        {"authentication_required": required, "reason": reason[:200]},
        source=ProvenanceSource.USER,
        reason="user authentication constraint",
        status="ACTIVE",
        slot="authentication",
        value=required,
        user_approved=True,
    )


def _avoid_tokens(phrase: str) -> set[str]:
    stop = {
        "a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "with", "using",
        "add", "use", "include", "call", "build", "do", "not", "don't", "never", "no",
    }
    return {
        t
        for t in re.findall(r"[a-z0-9_]{3,}", (phrase or "").lower())
        if t not in stop
    }


def _text_matches_avoid(text: str, avoid_items: list[str]) -> bool:
    """True when requirement/tech text is a positive restatement of a rejected feature."""
    blob = (text or "").lower()
    if not blob:
        return False
    for item in avoid_items or []:
        tokens = _avoid_tokens(item)
        if not tokens:
            continue
        # Require all distinctive tokens from the avoid phrase to appear.
        if all(t in blob for t in tokens):
            return True
        item_l = (item or "").lower().strip()
        if item_l and item_l in blob:
            return True
    return False


def _filter_extraction_polarity(extraction, state: dict):
    """Drop positive requirements/tech that restate constraints.avoid (polarity guard).

    Uses state avoid + this turn's avoid for filtering, but does not rewrite
    ``extraction.avoid`` to include prior state avoids (keeps turn provenance clean).
    """
    state_avoid = list((state.get("constraints") or {}).get("avoid") or [])
    new_avoid = list(getattr(extraction, "avoid", None) or [])
    combined = list(dict.fromkeys([*state_avoid, *new_avoid]))
    if not combined:
        return extraction

    kept_reqs = []
    for req in list(getattr(extraction, "requirements", None) or []):
        if _text_matches_avoid(getattr(req, "text", "") or "", combined):
            phrase = (getattr(req, "text", None) or "").strip()
            if phrase and phrase not in new_avoid:
                new_avoid.append(phrase)
            continue
        if getattr(req, "slot_value", None) and _text_matches_avoid(str(req.slot_value), combined):
            continue
        kept_reqs.append(req)
    extraction.requirements = kept_reqs

    for field in ("databases", "frameworks", "models", "hardware", "technology", "programming_languages"):
        values = list(getattr(extraction, field, None) or [])
        setattr(
            extraction,
            field,
            [v for v in values if not _text_matches_avoid(str(v), combined)],
        )
    extraction.avoid = new_avoid
    return extraction


def enforce_rejection_polarity(state: dict) -> dict:
    """Invariant: rejected/avoid features ∩ positive active requirements = ∅.

    Also clears technology slots that restate an explicit avoid. Idempotent.
    """
    state = migrate_state(state or {})
    avoid = list((state.get("constraints") or {}).get("avoid") or [])
    if not avoid:
        return state
    for req in state.get("requirements") or []:
        if req.get("status") != "active":
            continue
        if _text_matches_avoid(req.get("text") or "", avoid) or (
            req.get("slot_value") and _text_matches_avoid(str(req.get("slot_value")), avoid)
        ):
            req["status"] = "removed"
            req["assertion_status"] = "REJECTED"
            req["removed_reason"] = req.get("removed_reason") or "rejected_feature_polarity"
    tech = state.get("technology") or {}
    for key in ("database", "backend", "model"):
        value = tech.get(key)
        if value and _text_matches_avoid(str(value), avoid):
            tech[key] = None
    for field in ("databases", "frameworks", "models", "hardware", "other", "languages"):
        values = list(tech.get(field) or [])
        tech[field] = [v for v in values if not _text_matches_avoid(str(v), avoid)]
    return state


def active_requirements_respect_avoid(state: dict) -> bool:
    """Return True when no active requirement restates constraints.avoid."""
    avoid = list((state.get("constraints") or {}).get("avoid") or [])
    if not avoid:
        return True
    for req in state.get("requirements") or []:
        if req.get("status") != "active":
            continue
        if _text_matches_avoid(req.get("text") or "", avoid):
            return False
        if req.get("slot_value") and _text_matches_avoid(str(req.get("slot_value")), avoid):
            return False
    return True


def apply_constraint_cues(state: dict, message: str) -> dict:
    """Apply explicit auth/platform cues from the raw message into ProjectState."""
    text = (message or "").lower()
    if re.search(r"\b(no login|without (login|sign[- ]?in)|no authentication)\b", text):
        _set_auth_flag(state, False, message)
    elif re.search(r"\b(login required|require(s|d)? login|must (log|sign) ?in)\b", text):
        _set_auth_flag(state, True, message)
    from app.services.impact_analysis import extract_platforms

    platforms = extract_platforms(message)
    if platforms:
        state.setdefault("project", {})["platform"] = platforms
    return state


def set_stage(state: dict, stage: ConversationStage | str) -> dict:
    state = migrate_state(state)
    if isinstance(stage, str):
        stage = ConversationStage(stage)
    state["conversation_stage"] = stage.value
    return state


def _next_code(state: dict) -> str:
    numbers = []
    for req in state.get("requirements") or []:
        match = re.search(r"REQ-(\d+)", str(req.get("id") or ""))
        if match:
            numbers.append(int(match.group(1)))
    return f"REQ-{max(numbers, default=0) + 1:03d}"


def _append_unique(items: list, value) -> None:
    if value and value not in items:
        items.append(value)


def _primary_domain(state: dict, domains: list[str]) -> str:
    subject = (state.get("academic") or {}).get("subject")
    if subject:
        return subject
    if "nlp" in domains:
        return "NLP"
    if domains:
        return DOMAIN_LABELS.get(domains[0], domains[0])
    return ""


def _title_from(extraction, state: dict) -> str:
    objective = extraction.objective or ""
    if "phishing" in objective.lower():
        subject = (state.get("academic") or {}).get("subject") or "NLP"
        return f"{subject} Phishing Detector"
    if extraction.objective:
        return extraction.objective[:80]
    return state["project"]["title"]


def missing_questions(state: dict) -> list[str]:
    """Readiness gaps for compile/grill — NOT used to drive ordinary dialogue."""
    questions = []
    if not (state.get("academic") or {}).get("subject"):
        questions.append("What subject or course is this project for?")
    if not (state.get("constraints") or {}).get("duration"):
        questions.append("How long do you have to complete the project?")
    if (state.get("constraints") or {}).get("team_size") is None:
        questions.append("What is the team size?")
    if not (state.get("project") or {}).get("objective") and not state.get("core_idea"):
        questions.append("What problem should the project solve?")
    return questions


def highest_value_question(state: dict) -> str | None:
    """First readiness gap. Kept for compile/readiness tooling — not for chat turns."""
    questions = missing_questions(state)
    return questions[0] if questions else None


def refresh_readiness(state: dict) -> dict:
    """Store schema gaps as readiness metadata without making them dialogue questions."""
    gaps = missing_questions(state)
    state["readiness_gaps"] = gaps
    # Preserve grill/ambiguity open questions; strip legacy form-field prompts.
    form_prompts = set(gaps)
    conversational = [
        q for q in (state.get("open_questions") or []) if q and q not in form_prompts
    ]
    state["open_questions"] = conversational
    return state


def begin_new_direction(state: dict, message: str, *, new_focus: str | None = None) -> dict:
    """Archive current exploration/project branch and start a clean direction."""
    state = migrate_state(state)
    exploration = dict(state.get("exploration") or {})
    history = list(exploration.get("history") or [])
    snapshot = {
        "archived_at": utcnow().isoformat(),
        "reason": "direction_change",
        "trigger": (message or "")[:240],
        "core_idea": copy.deepcopy(state.get("core_idea")),
        "project": copy.deepcopy(state.get("project")),
        "requirements": copy.deepcopy(
            [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
        ),
        "technology": copy.deepcopy(state.get("technology")),
        "decisions": copy.deepcopy(state.get("decisions") or [])[-10:],
        "direction": exploration.get("current_direction"),
    }
    history.append(snapshot)
    exploration["history"] = history[-8:]
    exploration["current_direction"] = new_focus or None
    exploration["user_reactions"] = list(exploration.get("user_reactions") or []) + [
        f"direction_change: {(message or '')[:160]}"
    ]
    exploration["unresolved_decisions"] = []
    state["exploration"] = exploration

    # Soft-deactivate prior active requirements so they do not contaminate the new branch.
    for req in state.get("requirements") or []:
        if req.get("status") == "active":
            req["status"] = "superseded"
            req["origin"] = req.get("origin") or "archived_direction"

    state["core_idea"] = None
    state["idea"] = {"base_idea": None, "user_customizations": [], "alternatives": []}
    project = dict(state.get("project") or {})
    project["problem"] = ""
    project["objective"] = ""
    project["title"] = ""
    project["domain"] = None
    project["scope"] = None
    state["project"] = project
    state["architecture"] = {}
    state["grill_findings"] = None
    state["grill_report"] = None
    state["conflicts"] = []
    state["domains"] = []
    state["open_questions"] = []
    state["conversation_stage"] = ConversationStage.DISCOVERY.value
    ctx = dict(state.get("conversation_context") or {})
    ctx["topic"] = new_focus
    ctx["last_intent"] = "CHANGE_DIRECTION"
    ctx["ambiguities"] = []
    ctx["open_questions"] = []
    state["conversation_context"] = ctx
    _add_decision(
        state,
        "direction_change",
        f"Changed direction: {(new_focus or message or '')[:120]}",
        {"trigger": message[:200], "archived": True},
        source=ProvenanceSource.USER,
        reason="user changed project direction",
    )
    return refresh_readiness(state)


def pivot_dependency_notice(state: dict, changed_slots: list[str]) -> str | None:
    """When technology pivots, list dependent requirements that may need review."""
    if not changed_slots:
        return None
    dependents = []
    for req in state.get("requirements") or []:
        if req.get("status") != "active":
            continue
        slot = req.get("slot")
        text = (req.get("text") or "").lower()
        if slot in changed_slots or any(slot_name in text for slot_name in changed_slots):
            dependents.append(req["id"])
    if not dependents:
        return (
            f"Technology pivot on {', '.join(changed_slots)} recorded. "
            "No existing requirements explicitly depend on those slots, but architecture may still need review."
        )
    return (
        f"Technology pivot on {', '.join(changed_slots)} may affect "
        f"{', '.join(dependents)}. Confirm whether those requirements still hold — "
        "I will not silently rewrite them."
    )


def apply_research_findings(session: Session, project: Project, limit: int = 5) -> dict:
    """Promote recent research findings into candidate requirements (user-approved provenance)."""
    state = migrate_state(project.state or {})
    research = list(state.get("research") or [])
    if not research:
        return {"added": [], "state": public_state(state), "narrative": "No research findings to apply."}
    pending = [item for item in research if not item.get("applied")][-limit:]
    added = []
    for item in pending:
        if item.get("source_type") == "system":
            continue
        impact = item.get("project_impact") or item.get("finding")
        if not impact:
            continue
        text = f"Incorporate research insight: {impact}"
        if any(req.get("text") == text and req.get("status") == "active" for req in state["requirements"]):
            item["applied"] = True
            continue
        created = _new_requirement(
            state,
            text,
            "constraint",
            source=ProvenanceSource.RESEARCH,
            reason=item.get("query") or "applied research finding",
            capability=impact,
            acceptance=f"Design and implementation reflect: {impact}",
            origin=AssertionOrigin.RESEARCH_DERIVED,
            explicit=False,
        )
        item["applied"] = True
        added.append(created["id"])
        _add_decision(
            state,
            "apply_research",
            f"Applied research into {created['id']}",
            {"requirement_id": created["id"], "finding": item.get("finding")},
            source=ProvenanceSource.RESEARCH,
            reason="user requested apply research",
        )
    state = refresh_readiness(state)
    state["conversation_stage"] = ConversationStage.REQUIREMENTS.value
    state = StateVersioning.bump(state, "apply_research")
    project.state = public_state(state)
    project.updated_at = utcnow()
    StateVersioning.snapshot(session, project, "apply_research")
    _sync_requirements(session, project, state)
    _sync_decisions(session, project, state)
    if not added:
        narrative = "Research findings were reviewed; no new requirements were added (already applied or system-only)."
    else:
        narrative = (
            "Applied research into requirements: "
            + ", ".join(added)
            + ". Review them — RESEARCH provenance marks their origin."
        )
    return {"added": added, "state": public_state(state), "narrative": narrative}



def _add_decision(
    state: dict,
    kind: str,
    summary: str,
    details: dict | None = None,
    *,
    source: ProvenanceSource = ProvenanceSource.INFERRED,
    reason: str = "",
    status: str | None = None,
    slot: str | None = None,
    value=None,
    alternatives: list | None = None,
    user_approved: bool | None = None,
) -> None:
    from app.schemas.decisions import DecisionStatus, propose_decision

    if status is None:
        if source == ProvenanceSource.USER:
            status = DecisionStatus.ACTIVE
            user_approved = True if user_approved is None else user_approved
        elif source == ProvenanceSource.AI_RECOMMENDATION:
            status = DecisionStatus.PROPOSED
            user_approved = False if user_approved is None else user_approved
        else:
            status = DecisionStatus.ACTIVE
            user_approved = True if user_approved is None else user_approved
    decision = propose_decision(
        kind=kind,
        summary=summary,
        value=value if value is not None else summary,
        slot=slot,
        details=details or {},
        source=source,
        reason=reason or kind,
        alternatives=alternatives or [],
        status=DecisionStatus(status) if isinstance(status, str) else status,
    )
    if user_approved is not None:
        decision["user_approved"] = user_approved
        decision["provenance"]["user_approved"] = user_approved
    state.setdefault("decisions", []).append(decision)


def _link(state: dict, text: str, threshold: float = 0.78) -> dict | None:
    best = None
    best_score = 0.0
    query = create_embedding(text)
    for req in state["requirements"]:
        if req.get("status") != "active":
            continue
        score = cosine_similarity(query, create_embedding(req["text"]))
        if score > best_score:
            best = req
            best_score = score
    if best is not None and best_score >= threshold:
        return best
    return None


def _new_requirement(
    state: dict,
    text: str,
    req_type: str,
    slot=None,
    slot_value=None,
    domain=None,
    *,
    source: ProvenanceSource = ProvenanceSource.USER,
    reason: str = "extracted from user message",
    actor: str | None = None,
    acceptance: str | None = None,
    capability: str | None = None,
    origin: AssertionOrigin | str | None = None,
    explicit: bool = True,
) -> dict:
    """Create a requirement with explicit AssertionOrigin semantics.

    USER message extraction defaults to USER_EXPLICIT → CONFIRMED.
    Callers that infer or derive requirements must pass origin/explicit accordingly.
    """
    locked = bool((state.get("core_idea") or {}).get("locked") or state.get("core_idea"))
    resolved_origin = infer_origin_from_provenance(
        source,
        explicit=explicit and origin is None,
        origin_hint=origin,
    )
    # If caller passed origin explicitly, honor it; if source=USER and explicit=True → USER_EXPLICIT.
    if origin is None and source == ProvenanceSource.USER and explicit:
        resolved_origin = AssertionOrigin.USER_EXPLICIT
    elif origin is None and source == ProvenanceSource.USER and not explicit:
        resolved_origin = AssertionOrigin.USER_INFERRED
    assertion = default_requirement_assertion_status(
        provenance_source=source,
        origin=resolved_origin,
        explicit=resolved_origin == AssertionOrigin.USER_EXPLICIT,
    )
    user_approved = assertion.value in {"CONFIRMED", "LOCKED"}
    avoid = list((state.get("constraints") or {}).get("avoid") or [])
    conflicts_avoid = _text_matches_avoid(text, avoid) or (
        slot_value is not None and _text_matches_avoid(str(slot_value), avoid)
    )
    # Invariant: avoid ∩ active positives = ∅ — never create an active conflict.
    status = "removed" if conflicts_avoid else "active"
    assertion_value = "REJECTED" if conflicts_avoid else assertion.value
    if conflicts_avoid:
        user_approved = False
    item = {
        "id": _next_code(state),
        "type": req_type,
        "text": text,
        "status": status,
        "assertion_status": assertion_value,
        "assertion_origin": resolved_origin.value,
        "version": 1,
        "slot": slot,
        "slot_value": slot_value,
        "domain": domain,
        "actor": actor,
        "acceptance": acceptance,
        "capability": capability,
        "origin": "original" if not locked else "added",
        "provenance": make_provenance(source, reason=reason, user_approved=user_approved),
        "versions": [{"version": 1, "text": text, "status": status}],
    }
    if conflicts_avoid:
        item["removed_reason"] = "rejected_feature_polarity"
    state["requirements"].append(item)
    return item


def _revise(req: dict, text: str, status: str = "active", *, changed_by: str = "user", change_reason: str = "") -> None:
    previous = int(req.get("version") or 1)
    req["version"] = previous + 1
    req["text"] = text
    req["status"] = status
    req.setdefault("versions", []).append({"version": req["version"], "text": text, "status": status})
    record_requirement_version_lineage(
        req,
        changed_by=changed_by,
        change_reason=change_reason or f"status={status}",
    )


def _remove_matching(state: dict, target: str) -> dict | None:
    needle = target.lower().strip()
    for req in state["requirements"]:
        if req.get("status") != "active":
            continue
        haystack = req["text"].lower()
        if needle in haystack or haystack in needle or _token_overlap(needle, haystack) >= 0.6:
            _revise(req, req["text"], "removed")
            _add_decision(
                state,
                "remove_requirement",
                f"Removed {req['id']}: {req['text']}",
                {"id": req["id"]},
                source=ProvenanceSource.USER,
                reason="user requested removal",
            )
            return req
    return None


def _token_overlap(left: str, right: str) -> float:
    a = set(re.findall(r"[a-z0-9]+", left))
    b = set(re.findall(r"[a-z0-9]+", right))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def _merge_technology(state: dict, extraction, allow_overwrite: bool) -> None:
    tech = state["technology"]
    for language in extraction.programming_languages:
        _append_unique(tech["languages"], language)
        if allow_overwrite or not tech.get("backend"):
            if extraction.requirements and any(req.slot == "backend" for req in extraction.requirements):
                tech["backend"] = language
            elif re.search(r"backend", " ".join(req.text for req in extraction.requirements), re.I):
                tech["backend"] = language
    for framework in extraction.frameworks:
        _append_unique(tech["frameworks"], framework)
    for database in extraction.databases:
        _append_unique(tech["databases"], database)
        if allow_overwrite or not tech.get("database"):
            tech["database"] = database
    for model in extraction.models:
        _append_unique(tech["models"], model)
        if allow_overwrite or not tech.get("model"):
            tech["model"] = model
    for item in extraction.hardware:
        _append_unique(tech["hardware"], item)
    for item in extraction.technology:
        if item not in tech["languages"] + tech["frameworks"] + tech["databases"] + tech["models"] + tech["hardware"]:
            _append_unique(tech["other"], item)


def _infer_stage(state: dict, intent: str) -> ConversationStage:
    current = state.get("conversation_stage") or ConversationStage.DISCOVERY.value
    try:
        stage = ConversationStage(current)
    except ValueError:
        stage = ConversationStage.DISCOVERY
    if intent == "REQUEST_GRILL":
        return ConversationStage.GRILL
    if intent == "GENERATE_PROMPT":
        return ConversationStage.PROMPT_GENERATION
    if intent == "FINALIZE_PROJECT":
        return ConversationStage.REVIEW
    if intent == "SELECT_IDEA":
        return ConversationStage.IDEA_SELECTED
    if (state.get("core_idea") or {}).get("locked"):
        if intent in {"ADD_REQUIREMENT", "REMOVE_REQUIREMENT", "MODIFY_REQUIREMENT", "CHANGE_TECHNOLOGY"}:
            return ConversationStage.REQUIREMENTS
        if stage in {ConversationStage.DISCOVERY, ConversationStage.IDEATION}:
            return ConversationStage.CUSTOMIZATION
    if intent == "PROJECT_DESCRIPTION" and not state.get("core_idea"):
        return ConversationStage.DISCOVERY
    return stage


def apply_analysis_to_state(state: dict, analysis: dict, reason: str = "message") -> dict:
    """Apply extraction analysis to ProjectState without DB I/O.

    Used by production apply_analysis and by RQ1 evaluation (no gold contamination).
    """
    state = migrate_state(state or {})
    extraction = analysis["extraction"]
    intent = analysis["intent"]["intent"]
    relationship = analysis["relationship"]["relationship"]
    conflict = analysis.get("slot_conflict")

    # Polarity guard: rejected/forbidden features must never become positive requirements
    # or selected technology slots (e.g. "Do not add Redis" → avoid, not REQ/database).
    extraction = _filter_extraction_polarity(extraction, state)
    analysis = {**analysis, "extraction": extraction}

    if extraction.subject:
        from app.nlp.extraction import merge_subject_labels

        merged = merge_subject_labels(
            (state.get("academic") or {}).get("subject"),
            extraction.subject,
        )
        state["academic"]["subject"] = merged
        state["project"]["subject"] = merged
    if extraction.team_size is not None:
        state["constraints"]["team_size"] = extraction.team_size
    if extraction.duration:
        state["constraints"]["duration"] = extraction.duration
    if extraction.budget:
        state["constraints"]["budget"] = extraction.budget
    for topic in extraction.required_topics:
        _append_unique(state["academic"]["required_concepts"], topic)
    for item in extraction.avoid:
        _append_unique(state["constraints"]["avoid"], item)
    # Enforce avoid ∩ active requirements = ∅ (and clear forbidden tech slots).
    state = enforce_rejection_polarity(state)

    for req in extraction.requirements or []:
        text = (req.text or "").lower()
        if re.search(r"\b(no login|without (login|sign[- ]?in)|no authentication)\b", text):
            _set_auth_flag(state, False, text)
        elif re.search(r"\b(login required|must (log|sign) ?in|authenticate)\b", text):
            _set_auth_flag(state, True, text)

    allow_overwrite = relationship == "MODIFIES" or (intent == "CHANGE_TECHNOLOGY" and not conflict)
    if not conflict or allow_overwrite:
        _merge_technology(state, extraction, allow_overwrite)
        if allow_overwrite and extraction.programming_languages:
            _add_decision(
                state,
                "technology_change",
                f"Technology updated toward {', '.join(extraction.programming_languages)}",
                {"languages": extraction.programming_languages},
                source=ProvenanceSource.USER,
                reason="user technology change",
            )

    if extraction.core_idea_proposed and not (state.get("core_idea") or {}).get("locked"):
        state["core_idea"] = {
            "problem": extraction.problem or extraction.objective,
            "primary_domain": _primary_domain(state, extraction.domains),
            "primary_objective": extraction.objective or extraction.problem,
            "locked": False,
            "user_customizations": [],
        }
        state["idea"]["base_idea"] = {
            "problem": state["core_idea"]["problem"],
            "objective": state["core_idea"]["primary_objective"],
            "domain": state["core_idea"]["primary_domain"],
        }
        state["project"]["problem"] = state["core_idea"]["problem"]
        state["project"]["objective"] = state["core_idea"]["primary_objective"]
        if not state["project"]["title"]:
            state["project"]["title"] = _title_from(extraction, state)
        for req in state["requirements"]:
            if req.get("status") == "active":
                req["origin"] = "original"

    if intent != "REMOVE_REQUIREMENT":
        for domain in extraction.domains:
            _append_unique(state["domains"], domain)
            if not state["project"].get("domain") and domain:
                state["project"]["domain"] = domain
    if intent == "REMOVE_REQUIREMENT" and extraction.removal_target:
        removed = _remove_matching(state, extraction.removal_target)
        if removed and removed.get("domain"):
            still_used = any(
                req.get("domain") == removed["domain"] and req.get("status") == "active"
                for req in state["requirements"]
            )
            core_blob = " ".join([
                state["project"].get("objective") or "",
                state["project"].get("problem") or "",
                state["academic"].get("subject") or "",
            ])
            if not still_used and removed["domain"] not in detect_domains(core_blob):
                state["domains"] = [domain for domain in state["domains"] if domain != removed["domain"]]
    elif conflict and relationship == "CONTRADICTS":
        state["conflicts"].append({
            "id": f"CON-{len(state['conflicts']) + 1:03d}",
            "status": "open",
            "slot": conflict.get("slot"),
            "existing": conflict.get("existing"),
            "incoming": conflict.get("incoming"),
            "requirement_id": conflict.get("requirement_id"),
            "explanation": (
                f"Conflict on {conflict.get('slot')}: existing value is "
                f"{conflict.get('existing')}, incoming value is {conflict.get('incoming')}."
            ),
        })
        _add_decision(state, "conflict", state["conflicts"][-1]["explanation"], conflict)
    else:
        for req in extraction.requirements:
            linked = _link(state, req.text)
            if linked and relationship in {"SUPPORTS", "MODIFIES"}:
                if linked["text"] != req.text:
                    _revise(linked, req.text)
                    _add_decision(
                        state,
                        "modify_requirement",
                        f"Updated {linked['id']}",
                        {"id": linked["id"]},
                        source=ProvenanceSource.USER,
                        reason="user modified requirement",
                    )
                if req.slot:
                    linked["slot"] = req.slot
                    linked["slot_value"] = req.slot_value
                continue
            if any(existing["text"].lower() == req.text.lower() and existing["status"] == "active" for existing in state["requirements"]):
                continue
            created = _new_requirement(
                state,
                req.text,
                req.type,
                req.slot,
                req.slot_value,
                req.domain,
                actor=getattr(req, "actor", None),
                acceptance=getattr(req, "acceptance", None),
                capability=getattr(req, "capability", None),
            )
            if relationship == "EXTENDS":
                _add_decision(
                    state,
                    "extend",
                    f"Added {created['id']}: {created['text']}",
                    {"id": created["id"]},
                    source=ProvenanceSource.USER,
                    reason="user extended scope",
                )

    state = refresh_readiness(state)
    state["drift"] = analysis.get("drift")
    state["scope"] = analysis.get("scope")
    state["conversation_stage"] = _infer_stage(state, intent).value
    ctx = dict(state.get("conversation_context") or {})
    ctx["last_intent"] = intent
    if extraction.problem or extraction.objective:
        focus = extraction.objective or extraction.problem
        ctx["topic"] = focus
        exploration = dict(state.get("exploration") or {})
        exploration["current_direction"] = focus
        state["exploration"] = exploration
    if extraction.domains:
        interests = list(ctx.get("interests") or [])
        for domain in extraction.domains:
            if domain not in interests:
                interests.append(domain)
        ctx["interests"] = interests[-12:]
    state["conversation_context"] = ctx
    if intent == "CHANGE_TECHNOLOGY" or relationship == "MODIFIES":
        slots = []
        for req in extraction.requirements:
            if req.slot:
                slots.append(req.slot)
        for key in ("backend", "database", "model"):
            if (state.get("technology") or {}).get(key):
                if intent == "CHANGE_TECHNOLOGY":
                    slots.append(key)
        notice = pivot_dependency_notice(state, list(dict.fromkeys(slots)))
        if notice:
            notices = list(state.get("notices") or [])
            if notice not in notices:
                notices.append(notice)
            state["notices"] = notices[-5:]
    # Final polarity pass after requirement merges / tech updates.
    state = enforce_rejection_polarity(state)
    return StateVersioning.bump(state, reason)


def apply_analysis(session: Session, project: Project, analysis: dict, reason: str = "message") -> dict:
    state = apply_analysis_to_state(project.state or {}, analysis, reason=reason)
    project.state = public_state(state)
    project.title = state["project"]["title"] or project.title
    project.updated_at = utcnow()
    if state["project"]["objective"] or state.get("core_idea"):
        project.status = "active"
    StateVersioning.snapshot(session, project, reason)
    _sync_requirements(session, project, state)
    _sync_decisions(session, project, state)
    return public_state(state)


def select_idea(session: Session, project: Project, idea) -> dict:
    state = migrate_state(project.state or {})
    already = (state.get("core_idea") or {}).get("idea_id") == str(idea.id) and (state.get("core_idea") or {}).get(
        "locked"
    )
    if already:
        return public_state(state)

    state["core_idea"] = {
        "problem": idea.problem,
        "primary_domain": _primary_domain(state, []),
        "primary_objective": idea.objective or idea.title,
        "locked": True,
        "idea_id": str(idea.id),
        "title": idea.title,
        "user_customizations": [],
    }
    state["idea"]["base_idea"] = {
        "id": str(idea.id),
        "title": idea.title,
        "problem": idea.problem,
        "objective": idea.objective,
        "features": idea.features,
        "technology": idea.technology,
    }
    state["project"]["problem"] = idea.problem
    state["project"]["objective"] = idea.objective
    if not state["project"]["title"]:
        state["project"]["title"] = idea.title
    for req in state["requirements"]:
        if req.get("status") == "active" and req.get("origin") != "added":
            req["origin"] = "original"
    summary = f"Selected idea: {idea.title}"
    if not any(item.get("summary") == summary for item in state.get("decisions") or []):
        _add_decision(
            state,
            "select_idea",
            summary,
            {"idea_id": str(idea.id)},
            source=ProvenanceSource.USER,
            reason="user selected idea",
        )
    state = refresh_readiness(state)
    state["conversation_stage"] = ConversationStage.IDEA_SELECTED.value
    state = StateVersioning.bump(state, "select_idea")
    project.state = public_state(state)
    project.title = state["project"]["title"]
    project.status = "active"
    project.updated_at = utcnow()
    for other in project.ideas:
        other.selected = other.id == idea.id
    idea.selected = True
    StateVersioning.snapshot(session, project, "select_idea")
    _sync_decisions(session, project, state)
    return public_state(state)


def reject_idea(session: Session, project: Project, idea) -> dict:
    state = migrate_state(project.state or {})
    record = {"id": str(idea.id), "title": idea.title}
    if record not in state["rejected_ideas"]:
        state["rejected_ideas"].append(record)
    _add_decision(
        state,
        "reject_idea",
        f"Rejected idea: {idea.title}",
        record,
        source=ProvenanceSource.USER,
        reason="user rejected idea",
    )
    state = StateVersioning.bump(state, "reject_idea")
    project.state = public_state(state)
    project.updated_at = utcnow()
    idea.rejected = True
    StateVersioning.snapshot(session, project, "reject_idea")
    _sync_decisions(session, project, state)
    return public_state(state)


def mark_finalized(session: Session, project: Project) -> dict:
    state = migrate_state(project.state or {})
    _add_decision(
        state,
        "finalize",
        "Project marked ready for specification",
        {},
        source=ProvenanceSource.USER,
        reason="user finalized",
    )
    state["conversation_stage"] = ConversationStage.REVIEW.value
    state = StateVersioning.bump(state, "finalize")
    project.state = public_state(state)
    project.status = "finalized"
    project.updated_at = utcnow()
    StateVersioning.snapshot(session, project, "finalize")
    _sync_decisions(session, project, state)
    return public_state(state)


def _sync_requirements(session: Session, project: Project, state: dict) -> None:
    existing = {req.code: req for req in project.requirements}
    for item in state["requirements"]:
        row = existing.get(item["id"])
        if row is None:
            row = Requirement(
                id=uuid.uuid4(),
                project_id=project.id,
                code=item["id"],
                type=item["type"],
                text=item["text"],
                status=item["status"],
                version=item["version"],
                slot=item.get("slot"),
                slot_value=item.get("slot_value"),
                domain=item.get("domain"),
                origin=item.get("origin") or "added",
            )
            session.add(row)
            session.flush()
            session.add(RequirementVersion(
                requirement_id=row.id, version=row.version, text=row.text, type=row.type, status=row.status
            ))
        elif row.text != item["text"] or row.status != item["status"] or row.version != item["version"]:
            row.text = item["text"]
            row.status = item["status"]
            row.version = item["version"]
            row.type = item["type"]
            row.slot = item.get("slot")
            row.slot_value = item.get("slot_value")
            row.domain = item.get("domain")
            row.origin = item.get("origin") or row.origin
            row.updated_at = utcnow()
            session.add(RequirementVersion(
                requirement_id=row.id, version=row.version, text=row.text, type=row.type, status=row.status
            ))
        _store_pgvector(session, row, item["text"])


def _store_pgvector(session: Session, row: Requirement, text_value: str) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    vector = create_embedding(text_value)
    if len(vector) != 384:
        return
    literal = "[" + ",".join(f"{value:.6f}" for value in vector) + "]"
    try:
        with session.begin_nested():
            session.execute(
                text("UPDATE requirements SET embedding_vec = CAST(:vec AS vector) WHERE id = :id"),
                {"vec": literal, "id": row.id},
            )
    except Exception:
        return


def _sync_decisions(session: Session, project: Project, state: dict) -> None:
    stored = {row.summary for row in project.decisions}
    for item in state["decisions"]:
        if item["summary"] in stored:
            continue
        details = dict(item.get("details") or {})
        if item.get("provenance"):
            details["provenance"] = item["provenance"]
        session.add(Decision(
            project_id=project.id,
            kind=item["kind"],
            summary=item["summary"],
            details=details,
        ))
