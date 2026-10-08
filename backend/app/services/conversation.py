"""Message handling.

Each message is stored, analysed, compared with project state, and answered
from the relevant state rather than the entire transcript.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import TaskKind
from app.llm.gemini import extract_json
from app.llm.prompts import conversation_prompt, extraction_prompt
from app.llm.router import get_provider
from app.models import Conversation, Idea, Message, Project
from app.nlp.contradiction import classify_relationship, find_slot_conflict
from app.nlp.drift import analyze_scope, calculate_drift
from app.nlp.embeddings import create_embedding
from app.nlp.extraction import extract_information, merge_validated_llm
from app.nlp.intent import classify_intent
from app.nlp.preprocessing import preprocess
from app.nlp.similarity import cosine_similarity, find_related_requirements
from app.orchestration.conversation_manager import ConversationManager, OrchestratorAction
from app.services import idea_generation, prompt_compiler, specification
from app.services.grill import conversational_challenge, grill, professional_review
from app.database.base import utcnow
from app.schemas.state import migrate_state
from app.services.idea_generation import format_ideas_for_chat, wants_ideation
from app.services.project_state import (
    apply_analysis,
    apply_constraint_cues,
    apply_research_findings,
    begin_new_direction,
    empty_state,
    mark_finalized,
    public_state,
    reject_idea,
    select_idea,
    set_stage,
)
from app.services.prompt_compiler import conversational_gate_message
from app.services.research import run_research


def ensure_conversation(session: Session, project: Project) -> Conversation:
    if project.conversation is None:
        project.conversation = Conversation(project_id=project.id, summary="")
        session.add(project.conversation)
        session.flush()
    return project.conversation


def post_message(session: Session, project: Project, content: str) -> dict:
    if not project.state:
        project.state = empty_state()
    conversation = ensure_conversation(session, project)
    prepared = preprocess(content)
    intent = classify_intent(prepared["text"])
    manager = ConversationManager()
    pre_state = migrate_state(project.state or {})
    direction_change = manager.detect_direction_change(prepared["text"], pre_state)
    if direction_change:
        focus_hint = _direction_focus(prepared["text"])
        state = begin_new_direction(pre_state, prepared["text"], new_focus=focus_hint)
        project.state = public_state(state)
        session.flush()

    extraction = extract_information(prepared["text"])
    extraction = _maybe_llm_extract(prepared["text"], project.state, extraction)
    related = find_related_requirements(prepared["text"], project.state.get("requirements") or [])
    slot_conflict = find_slot_conflict(project.state, extraction)
    core_domains = []
    subject = (project.state.get("academic") or {}).get("subject")
    if subject:
        core_domains.extend(_domain_ids(subject))
    core = project.state.get("core_idea") or {}
    if core.get("primary_domain"):
        core_domains.extend(_domain_ids(core["primary_domain"]))
    core_domains.extend(_domain_ids(core.get("primary_objective") or ""))
    relationship = classify_relationship(
        prepared["text"],
        related,
        intent["intent"],
        extraction.domains,
        list(dict.fromkeys(core_domains)),
        slot_conflict,
    )
    new_texts = [req.text for req in extraction.requirements]
    if intent["intent"] != "REMOVE_REQUIREMENT":
        drift = calculate_drift(project.state, new_texts)
    else:
        drift = {"potential_drift": False, "drifted": [], "requirements": [], "backend": "n/a"}
    if direction_change:
        drift = {"potential_drift": False, "drifted": [], "requirements": [], "backend": "n/a"}
    scope = analyze_scope(project.state, extraction.domains, len(new_texts))
    analysis = {
        "intent": intent,
        "extraction": extraction,
        "related": related,
        "relationship": relationship,
        "slot_conflict": slot_conflict,
        "drift": drift,
        "scope": scope,
        "preprocessing": {"method": prepared["method"], "prompt_injection": prepared["prompt_injection"]},
        "embedding_backend": create_embedding.__module__,
    }
    state = apply_analysis(session, project, analysis, reason=intent["intent"])
    from app.services.impact_analysis import (
        analyze_message_impact,
        apply_impact_to_state,
        format_impact_for_chat,
    )

    state = apply_constraint_cues(state, prepared["text"])
    impact = analyze_message_impact(state, prepared["text"])
    if impact.get("findings"):
        state = apply_impact_to_state(state, impact)
    project.state = public_state(state)
    managed = manager.advance_after_message(state, intent["intent"], prepared["text"])
    if direction_change:
        managed.direction_change = True
        managed.action = OrchestratorAction.RESET_OR_CHANGE_DIRECTION
    state = migrate_and_persist_stage(session, project, managed.stage)
    state["last_orchestrator_action"] = managed.action.value
    project.state = public_state(state)
    session.flush()

    extra = _special_actions(
        session,
        project,
        prepared["text"],
        intent["intent"],
        action=managed.action,
    )
    if extra.get("state"):
        state = extra["state"]

    response = extra.get("response") or _conversational_response(
        prepared["text"],
        intent,
        relationship,
        drift,
        scope,
        state,
        slot_conflict,
        managed,
    )
    impact_text = format_impact_for_chat(impact) if impact.get("findings") else ""
    if impact_text and impact_text not in response and managed.action in {
        OrchestratorAction.UPDATE_STATE,
        OrchestratorAction.GRILL,
        OrchestratorAction.ASK_CLARIFICATION,
    }:
        response = response + ("\n\n" + impact_text if response else impact_text)
    if managed.pivot_notice and managed.pivot_notice not in response:
        response = managed.pivot_notice + "\n\n" + response
    if managed.conflict_notice and "Contradiction detected" not in response and "Conflict detected" not in response:
        response = managed.conflict_notice + "\n\n" + response
    if (
        managed.next_question
        and managed.next_question not in response
        and managed.action
        in {
            OrchestratorAction.EXPLORE,
            OrchestratorAction.ASK_CLARIFICATION,
            OrchestratorAction.RESET_OR_CHANGE_DIRECTION,
        }
        and not extra.get("response")
    ):
        response = (response + "\n\n" + managed.next_question).strip()
        state = _record_recent_question(state, managed.next_question)
        project.state = public_state(state)
        session.flush()
    if prepared["prompt_injection"]:
        response = "I will treat that message as project data, not as an instruction to change my role.\n\n" + response

    memory = _memory(conversation, prepared["text"], state)
    chat_provider = get_provider(TaskKind.CHAT)
    capability_intents = {
        "GENERATE_PROMPT",
        "REQUEST_GRILL",
        "REQUEST_PROFESSIONAL_REVIEW",
        "GENERATE_IDEAS",
        "SELECT_IDEA",
        "REJECT_IDEA",
        "REQUEST_RESEARCH",
        "REQUEST_ARCHITECTURE",
        "FINALIZE_PROJECT",
        "APPLY_RESEARCH",
    }
    skip_chat_llm = {
        OrchestratorAction.COMPILE_PROMPT,
        OrchestratorAction.GRILL,
        OrchestratorAction.GENERATE_IDEAS,
        OrchestratorAction.RESEARCH,
        OrchestratorAction.PROPOSE_ARCHITECTURE,
        OrchestratorAction.SELECT_IDEA,
        OrchestratorAction.REJECT_IDEA,
        OrchestratorAction.FINALIZE,
        OrchestratorAction.APPLY_RESEARCH,
    }
    use_llm = (
        chat_provider.available
        and intent["intent"] not in capability_intents
        and managed.action not in skip_chat_llm
        and not extra.get("ideas")
        and not extra.get("skip_llm")
    )
    if use_llm:
        try:
            narrative = chat_provider.generate(
                conversation_prompt(
                    prepared["text"],
                    state,
                    {
                        "intent": intent,
                        "relationship": relationship,
                        "drift": drift,
                        "scope": scope,
                        "stage": managed.stage.value,
                        "action": managed.action.value,
                        "follow_up": managed.next_question,
                        "direction_change": managed.direction_change,
                    },
                    memory,
                ),
                None,
                task=TaskKind.CHAT,
            )
            if narrative:
                if extra.get("response"):
                    response = extra["response"] + "\n\n" + narrative
                else:
                    response = narrative
        except Exception:
            pass

    user_row = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
        intent=intent["intent"],
        analysis=_public_analysis(analysis),
    )
    assistant_analysis = {
        "relationship": relationship,
        "drift": drift,
        "scope": scope,
        "stage": managed.stage.value,
        "action": managed.action.value,
        "suggested_actions": managed.suggested_actions,
        "direction_change": managed.direction_change,
    }
    if extra.get("ideas"):
        assistant_analysis["ideas"] = extra["ideas"]
    assistant_row = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response,
        intent=intent["intent"] if not extra.get("ideas") else "GENERATE_IDEAS",
        analysis=assistant_analysis,
    )
    session.add(user_row)
    session.add(assistant_row)
    conversation.summary = _update_summary(conversation.summary, intent["intent"], content)
    session.flush()
    return {
        "user_message": _message_dict(user_row),
        "assistant_message": _message_dict(assistant_row),
        "intent": intent,
        "relationship": relationship,
        "drift": drift,
        "scope": scope,
        "conflicts": state.get("conflicts") or [],
        "stage": managed.stage.value,
        "action": managed.action.value,
        "state": state,
        "ideas": extra.get("ideas") or [],
    }


def migrate_and_persist_stage(session, project, stage) -> dict:
    state = migrate_state(project.state or {})
    state = set_stage(state, stage)
    project.state = public_state(state)
    project.updated_at = utcnow()
    session.flush()
    return public_state(state)


def _maybe_llm_extract(text, state, extraction):
    provider = get_provider(TaskKind.EXTRACTION)
    if not provider.available:
        return extraction
    try:
        raw = provider.generate(extraction_prompt(text, state), None, task=TaskKind.EXTRACTION)
        return merge_validated_llm(extraction, extract_json(raw))
    except Exception:
        return extraction


def _special_actions(session, project, text, intent, *, action: OrchestratorAction | None = None) -> dict:
    accept = _maybe_accept_decision(session, project, text)
    if accept:
        return accept

    resolved = action or OrchestratorAction.RESPOND
    if resolved == OrchestratorAction.GRILL or intent in {"REQUEST_GRILL", "ASK_FEASIBILITY"}:
        from app.services.capability_harness import CapabilityKind, gate_capability, gated_message

        grill_gate = gate_capability(project.state or {}, CapabilityKind.GRILL)
        if not grill_gate.allowed:
            return {
                "response": gated_message(CapabilityKind.GRILL, grill_gate),
                "state": public_state(project.state or {}),
                "skip_llm": True,
                "provenance": grill_gate.provenance,
            }
        # Prefer a single conversational challenge; full grill report on explicit grill request.
        if intent == "REQUEST_GRILL" and re.search(r"\bgrill\b", text, re.I):
            report = grill(project.state, persist_on_project=project, session=session)
            return {"response": report["narrative"], "state": report.get("state") or public_state(project.state or {})}
        challenge = conversational_challenge(project.state or {}, text)
        if challenge.get("state"):
            project.state = public_state(challenge["state"])
            session.flush()
        return {"response": challenge["narrative"], "state": public_state(project.state or {}), "skip_llm": True}
    if intent == "REQUEST_PROFESSIONAL_REVIEW":
        report = professional_review(project.state)
        return {"response": report["narrative"]}
    if resolved == OrchestratorAction.RESEARCH or intent == "REQUEST_RESEARCH" or ConversationManager()._wants_research(text):
        result = run_research(session, project, text)
        return {"response": result["narrative"], "state": result["state"]}
    if resolved == OrchestratorAction.GENERATE_IDEAS or intent == "GENERATE_IDEAS" or wants_ideation(text, project.state or {}):
        from app.services.capability_harness import run_ideation

        result = run_ideation(session, project)
        if result.get("blocked"):
            return {
                "response": result["response"],
                "state": result.get("state") or public_state(project.state or {}),
                "skip_llm": True,
                "provenance": result.get("provenance"),
            }
        rows = result.get("ideas") or []
        payloads = [_idea_payload(row, index + 1) for index, row in enumerate(rows)]
        state = dict(result.get("state") or public_state(project.state or {}))
        provenance = dict(state.get("capability_provenance") or {})
        provenance["IDEATION"] = result.get("provenance") or {}
        state["capability_provenance"] = provenance
        project.state = state
        session.flush()
        return {
            "response": result.get("response") or format_ideas_for_chat(rows),
            "state": public_state(state),
            "ideas": payloads,
            "provenance": result.get("provenance"),
        }
    if resolved == OrchestratorAction.APPLY_RESEARCH or intent == "APPLY_RESEARCH":
        result = apply_research_findings(session, project)
        return {"response": result["narrative"], "state": result["state"]}
    if (
        resolved == OrchestratorAction.PROPOSE_ARCHITECTURE
        or intent == "REQUEST_ARCHITECTURE"
        or ConversationManager()._wants_architecture(text)
    ):
        from app.services.capability_harness import run_architecture

        result = run_architecture(session, project)
        if result.get("blocked"):
            return {
                "response": result["response"],
                "state": result.get("state") or public_state(project.state or {}),
                "skip_llm": True,
                "provenance": result.get("provenance"),
            }
        return {"response": result["narrative"], "state": result["state"], "provenance": result.get("provenance")}
    if resolved == OrchestratorAction.COMPILE_PROMPT or intent == "GENERATE_PROMPT":
        try:
            prompt = prompt_compiler.compile_prompt(session, project)
            validation = (prompt.details or {}).get("validation") or {}
            metrics = validation.get("metrics") or {}
            quality = (
                f"\n\nPrompt quality: requirement coverage "
                f"{metrics.get('requirement_coverage', 'n/a')}, "
                f"tokens ~{metrics.get('token_count', 'n/a')}. "
                f"{validation.get('summary') or ''}"
            )
            return {
                "response": "I compiled the agent-ready prompt from the confirmed project state.\n\n" + prompt.content + quality,
                "state": public_state(project.state or {}),
            }
        except ValueError:
            return {
                "response": conversational_gate_message(migrate_state(project.state or {})),
                "state": public_state(project.state or {}),
                "skip_llm": True,
            }
    if resolved == OrchestratorAction.FINALIZE or intent == "FINALIZE_PROJECT":
        state = mark_finalized(session, project)
        spec = specification.build_specification(session, project)
        return {
            "response": (
                "The project is marked ready for review. A specification was generated from the structured state.\n\n"
                + spec.markdown[:1500]
            ),
            "state": state,
        }
    if resolved == OrchestratorAction.SELECT_IDEA or intent == "SELECT_IDEA":
        idea = _match_idea(session, project, text)
        if idea:
            state = select_idea(session, project, idea)
            return {"response": f"Selected idea: {idea.title}. It is now the locked core direction.", "state": state}
        return {"response": "I could not match that to a generated idea. Select one from the ideas list, or say 'idea 2'."}
    if resolved == OrchestratorAction.REJECT_IDEA or intent == "REJECT_IDEA":
        idea = _match_idea(session, project, text)
        if idea:
            state = reject_idea(session, project, idea)
            return {"response": f"Rejected idea: {idea.title}.", "state": state}
    return {}


def _maybe_accept_decision(session, project, text: str) -> dict | None:
    """Capture natural-language approval without requiring decision UUIDs."""
    lowered = (text or "").lower()
    approval = re.search(
        r"\b("
        r"accept|approve|go with|choose|lock in|"
        r"i('ll| will) use|let'?s use|yes[,.]?\s*(let'?s|use|go)|"
        r"use postgres(ql)?|use fastapi|use flutter|use react|"
        r"sounds good|that works|go ahead with"
        r")\b",
        lowered,
    )
    if not approval:
        return None
    from app.services.decisions import approve_decision, proposed_decisions
    from app.schemas.decisions import DecisionStatus, propose_decision
    from app.schemas.provenance import ProvenanceSource
    from app.services.project_state import refresh_readiness
    from app.services.versioning import StateVersioning

    state = migrate_state(project.state or {})
    proposed = proposed_decisions(state)
    chosen = None
    for item in proposed:
        value = str(item.get("value") or item.get("summary") or "").lower()
        name = value
        details = item.get("details") or {}
        if details.get("name"):
            name = str(details["name"]).lower()
        tokens = [t for t in re.split(r"[^a-z0-9+]+", f"{name} {value}") if len(t) > 2]
        # postgres ↔ postgresql
        aliases = set(tokens)
        if "postgres" in aliases:
            aliases.add("postgresql")
        if "postgresql" in aliases:
            aliases.add("postgres")
        if any(token in lowered for token in aliases) or (value and value[:20] in lowered):
            chosen = item
            break

    # Direct technology confirmation even without a prior PROPOSED decision.
    if chosen is None:
        tech_match = re.search(
            r"\b(postgresql|postgres|mysql|mongodb|sqlite|fastapi|django|flask|react|flutter|vue)\b",
            lowered,
        )
        if tech_match and re.search(r"\b(yes|use|let'?s|go with|choose|approve)\b", lowered):
            name = tech_match.group(1)
            db_names = {"postgresql", "postgres", "mysql", "mongodb", "sqlite"}
            backend_names = {"fastapi", "django", "flask"}
            if name in db_names:
                slot = "database"
            elif name in backend_names:
                slot = "backend"
            else:
                slot = "frontend_framework"
            canonical_map = {
                "postgres": "PostgreSQL",
                "postgresql": "PostgreSQL",
                "mongodb": "MongoDB",
                "mysql": "MySQL",
                "sqlite": "SQLite",
                "fastapi": "FastAPI",
                "django": "Django",
                "flask": "Flask",
                "react": "React",
                "flutter": "Flutter",
                "vue": "Vue",
            }
            canonical = canonical_map.get(name, name)
            from app.services.project_state import _text_matches_avoid, enforce_rejection_polarity

            avoid = list((state.get("constraints") or {}).get("avoid") or [])
            if _text_matches_avoid(canonical, avoid):
                return {
                    "response": (
                        f"{canonical} is on your avoid list, so I won't activate it. "
                        "Remove that rejection first if you want to use it."
                    ),
                    "state": public_state(state),
                    "skip_llm": True,
                }
            decision = propose_decision(
                kind="technology",
                summary=f"Use {canonical}",
                value=canonical,
                slot=slot,
                details={"name": canonical},
                source=ProvenanceSource.USER,
                reason="natural language confirmation",
                status=DecisionStatus.ACTIVE,
            )
            from app.services.decisions import append_decision, apply_active_decision_to_state, supersede_slot

            supersede_slot(state, slot, new_decision_id=decision["id"])
            append_decision(state, decision)
            apply_active_decision_to_state(state, decision)
            state = enforce_rejection_polarity(state)
            state = refresh_readiness(state)
            state = StateVersioning.bump(state, "nl_technology_confirm")
            project.state = public_state(state)
            StateVersioning.snapshot(session, project, "nl_technology_confirm")
            return {
                "response": f"Got it — {canonical} is now an active technology choice.",
                "state": public_state(state),
                "skip_llm": True,
            }

    if chosen is None and re.search(r"\b(accept|approve) (all|these|the recommendations?)\b", lowered):
        return {
            "response": (
                "I can activate recommendations one at a time. "
                "Name the option (for example: 'Yes, let's use PostgreSQL' or 'Go with Flutter')."
            ),
            "state": public_state(state),
            "skip_llm": True,
        }
    if chosen is None:
        return None
    try:
        state = approve_decision(session, project, chosen["id"])
    except ValueError:
        return None
    label = chosen.get("summary") or chosen.get("value") or "that option"
    return {
        "response": f"Sounds good — {label} is now active.",
        "state": state,
        "skip_llm": True,
    }


def _idea_payload(row: Idea, index: int) -> dict:
    details = row.details or {}
    return {
        "id": str(row.id),
        "index": index,
        "title": row.title,
        "problem": row.problem,
        "objective": row.objective,
        "why_it_matters": details.get("why_it_matters") or "",
        "solution": details.get("solution") or "",
        "features": row.features or [],
        "technology": row.technology or [],
        "difficulty": row.difficulty,
        "estimated_scope": row.estimated_scope,
        "details": details,
        "selected": row.selected,
        "rejected": row.rejected,
    }


def _match_idea(session, project, text) -> Idea | None:
    ideas = session.scalars(select(Idea).where(Idea.project_id == project.id, Idea.rejected.is_(False))).all()
    if not ideas:
        return None
    number = re.search(r"idea\s+(\d+)", text, re.I)
    if number:
        index = int(number.group(1)) - 1
        if 0 <= index < len(ideas):
            return ideas[index]
    lowered = text.lower()
    for idea in ideas:
        if idea.title.lower() in lowered:
            return idea
    query = create_embedding(text)
    best = None
    best_score = 0.0
    for idea in ideas:
        score = cosine_similarity(query, create_embedding(idea.title))
        if score > best_score:
            best = idea
            best_score = score
    if best and best_score >= 0.45:
        return best
    return None


def _conversational_response(text, intent, relationship, drift, scope, state, slot_conflict, managed) -> str:
    """Natural partner-style reply. Never dumps 'I captured…' or missing-field lists."""
    parts: list[str] = []
    lowered = (text or "").lower()
    intent_label = intent.get("intent") if isinstance(intent, dict) else intent
    constraints = state.get("constraints") or {}
    core = state.get("core_idea") or {}
    project = state.get("project") or {}
    action = managed.action if managed else OrchestratorAction.RESPOND

    if managed and managed.direction_change:
        focus = (state.get("exploration") or {}).get("current_direction") or _direction_focus(text) or "the new direction"
        parts.append(f"Sure. Let's explore {focus} instead.")
        return " ".join(parts)

    # Silent constraint acknowledgement when the user just stated team/duration.
    only_constraints = bool(
        re.search(r"\b(alone|solo|team|weeks?|months?)\b", lowered)
        and not re.search(r"\b(build|detect|analy[sz]|phish|nlp|cyber|idea|project for)\b", lowered)
    )
    if only_constraints and (constraints.get("team_size") is not None or constraints.get("duration")):
        bits = []
        if constraints.get("team_size") == 1:
            bits.append("working alone")
        elif constraints.get("team_size"):
            bits.append(f"a team of {constraints['team_size']}")
        if constraints.get("duration"):
            bits.append(f"{constraints['duration']}")
        if bits:
            parts.append("Got it — I'll keep the scope suitable for " + " and ".join(bits) + ".")
            return " ".join(parts)

    if slot_conflict and relationship.get("relationship") == "CONTRADICTS":
        parts.append(
            f"That conflicts with the current choice on {slot_conflict.get('slot')}: "
            f"{slot_conflict.get('existing')} versus {slot_conflict.get('incoming')}. "
            "Which should we keep?"
        )
        return " ".join(parts)

    if drift.get("potential_drift") and not (managed and managed.direction_change):
        domains = []
        for item in drift.get("drifted") or []:
            domains.extend(item.get("domains") or [])
        from app.nlp.lexicon import DOMAIN_LABELS

        labeled = [DOMAIN_LABELS.get(d, d.replace("_", " ").title()) for d in dict.fromkeys(domains)]
        domain_text = ", ".join(labeled) or "an unrelated area"
        objective = core.get("primary_objective") or project.get("objective") or "the current objective"
        parts.append(
            f"Potential project drift detected. New domain: {domain_text}. "
            f"This does not directly support the current {objective} objective — "
            "the decision remains yours. Want to explore it as a new branch, or keep it as an optional extension?"
        )
        return " ".join(parts)

    if action == OrchestratorAction.EXPLORE:
        subject = ((state.get("academic") or {}).get("subject") or "").strip()
        direction = ((state.get("exploration") or {}).get("current_direction") or "").lower()
        blob = f"{lowered} {subject.lower()} {direction}"
        from app.nlp.extraction import compose_subject_label, detect_domains

        domain_ids = list(
            dict.fromkeys(
                [
                    *detect_domains(blob),
                    *[
                        d
                        for d in (state.get("domains") or [])
                        if isinstance(d, str)
                    ],
                ]
            )
        )
        composed = compose_subject_label(domain_ids) or subject
        if re.search(r"\bchurn\b", blob):
            parts.append("Got it — churn prediction is a concrete direction.")
        elif composed and " + " in composed:
            parts.append(f"Got it — you're thinking about a {composed} project.")
        elif re.search(r"\b(computer\s+networks?|computer\s+networking|networking)\b", blob) or (
            "computer networks" in subject.lower()
        ):
            parts.append("Got it — you're thinking about a computer networks project.")
        elif re.search(r"\b(data\s*science|foundation of data)\b", blob) or "data science" in subject.lower():
            parts.append("Got it — you're thinking about a data science project.")
        elif re.search(r"\bnlp\b|natural language", blob):
            parts.append("Got it — you're looking for an NLP project.")
        elif re.search(r"\b(cyber(?:security)?|infosec)\b", blob) or "cybersecurity" in subject.lower():
            parts.append("Got it — something in cybersecurity.")
        elif re.search(r"\blog\b", blob):
            parts.append("A Linux log analyzer is a solid direction.")
        elif re.search(r"\bphish", blob):
            parts.append("Phishing detection is a clear project direction.")
        elif re.search(r"\bmachine learning|\bml\b", blob):
            parts.append("Got it — a machine-learning project.")
        else:
            topic = _soft_ack_topic(lowered, subject.lower())
            if topic:
                parts.append(f"Got it — you're thinking about {topic}.")
            else:
                parts.append("Got it.")
        return " ".join(parts)

    if action == OrchestratorAction.UPDATE_STATE:
        tech = state.get("technology") or {}
        if tech.get("database") or tech.get("backend") or tech.get("model"):
            labels = [
                x
                for x in [
                    tech.get("database"),
                    tech.get("backend"),
                    tech.get("model"),
                ]
                if x
            ]
            if labels:
                parts.append("Noted — " + ", ".join(labels) + ".")
                return " ".join(parts)
        parts.append("Understood — I've updated the project with that.")
        return " ".join(parts)

    if scope.get("detected") and scope.get("message"):
        parts.append(scope["message"])
        return " ".join(parts)

    # Answer how/users questions about the locked idea instead of a one-line ack.
    if intent_label in {"ASK_QUESTION", "ASK_FEASIBILITY"} or re.search(
        r"^\s*(how|what|who|why)\b",
        lowered,
    ):
        explained = _explain_locked_idea(state, lowered)
        if explained:
            parts.append(explained)
            return " ".join(parts)

    objective = project.get("objective") or core.get("primary_objective")
    if objective:
        parts.append(f"Got it. We're still centered on {objective}.")
    else:
        parts.append("Got it.")
    return " ".join(parts)


# Backwards-compatible alias for any imports of the old name.
def _response(text, intent, relationship, drift, scope, state, slot_conflict) -> str:
    class _Stub:
        action = OrchestratorAction.RESPOND
        direction_change = False
        next_question = None

    return _conversational_response(text, intent, relationship, drift, scope, state, slot_conflict, _Stub())


def _direction_focus(text: str) -> str | None:
    lowered = (text or "").lower()
    match = re.search(
        r"(?:forget .{0,40}?[,.]\s*)?(?:i want (?:to (?:build|make|work on) )?|let'?s (?:build|explore) )"
        r"(.+?)(?:[.!?]|$)",
        lowered,
        re.I,
    )
    if match:
        focus = match.group(1).strip(" .")
        if focus and len(focus) < 120:
            return focus
    if re.search(r"\bphish", lowered):
        return "a phishing detection system"
    if re.search(r"\blog\s+analy", lowered):
        return "a Linux log analyzer"
    if re.search(r"\bchurn\b", lowered):
        return "churn prediction"
    return None


def _soft_ack_topic(lowered: str, subject: str) -> str | None:
    subject_l = (subject or "").lower()
    has_networks = bool(
        re.search(r"\bcomputer\s+networks?|computer\s+networking|networking\b", lowered)
        or "computer networks" in subject_l
    )
    has_cyber = bool(
        re.search(r"\bcyber(?:security)?|infosec\b", lowered) or "cybersecurity" in subject_l
    )
    has_ds = bool(re.search(r"\bdata\s*science|foundation of data\b", lowered) or "data science" in subject_l)
    if has_ds and has_networks and has_cyber:
        return "a Data Science + Cybersecurity + Computer Networks project"
    if has_networks and has_cyber:
        return "a cybersecurity + computer networks project"
    if has_networks:
        return "a computer networks project"
    if has_cyber:
        return "a cybersecurity project"
    if has_ds:
        return "a data science project"
    if subject and "foundation of" not in subject and subject not in {"the course", "course"}:
        cleaned = re.sub(r"^(on|about|for|in)\s+", "", subject.strip(), flags=re.I)
        # Allow multi-domain subjects like "Cybersecurity + Computer Networks".
        if cleaned and len(cleaned.split()) <= 10:
            return f"a {cleaned} project"
    return None


def _explain_locked_idea(state: dict, lowered: str) -> str | None:
    """Deterministic how/users explanation when the chat LLM is unavailable."""
    core = state.get("core_idea") or {}
    project = state.get("project") or {}
    if not (core.get("locked") or project.get("title") or core.get("primary_objective")):
        return None
    title = project.get("title") or core.get("title") or "this project"
    problem = project.get("problem") or core.get("problem") or ""
    objective = project.get("objective") or core.get("primary_objective") or ""
    features = [
        str(f)
        for f in (project.get("features") or core.get("features") or state.get("features") or [])
        if f
    ][:5]
    users_hint = ""
    alts = (state.get("idea") or {}).get("alternatives") or []
    for alt in alts:
        if isinstance(alt, dict) and title.lower() in str(alt.get("title") or "").lower():
            users_hint = str(alt.get("users") or "")
            if not problem:
                problem = str(alt.get("problem") or "")
            if not objective:
                objective = str(alt.get("objective") or "")
            if not features:
                features = [str(f) for f in (alt.get("features") or []) if f][:5]
            break

    asks_users = bool(re.search(r"\b(user|users|end[- ]?user)\b", lowered))
    asks_how = bool(re.search(r"\bhow\b", lowered))
    if asks_users:
        who = users_hint or "students, instructors, or operators working with the project’s domain"
        return (
            f"For “{title}”, the common end users are {who}. "
            "They typically open the tool, pick a scenario or input (capture, topology, or dataset), "
            "run the analysis/visualization, and use the result to learn, debug, or decide what to fix next."
        )
    if asks_how:
        feat_text = (", ".join(features) + ". ") if features else ""
        return (
            f"Here’s how “{title}” works in practice: "
            f"{(problem + ' ') if problem else ''}"
            f"{('The system aims to ' + objective + '. ') if objective else ''}"
            f"{feat_text}"
            "A user provides input, the backend processes it through the analysis pipeline, "
            "and the UI shows step-by-step results they can inspect or export."
        )
    return None


def _record_recent_question(state: dict, question: str | None) -> dict:
    if not question:
        return state
    state = migrate_state(state)
    ctx = dict(state.get("conversation_context") or {})
    recent = list(ctx.get("recent_questions") or [])
    q = question.strip()
    if q and q not in recent:
        recent.append(q)
    ctx["recent_questions"] = recent[-8:]
    # Keep conversational open questions distinct from readiness gaps.
    open_q = [item for item in (ctx.get("open_questions") or []) if item != q]
    open_q.append(q)
    ctx["open_questions"] = open_q[-6:]
    state["conversation_context"] = ctx
    return state


def _memory(conversation: Conversation, text: str, state: dict) -> dict:
    messages = list(conversation.messages or [])
    recent = messages[-4:]
    related = find_related_requirements(text, state.get("requirements") or [], limit=5)
    return {
        "summary": conversation.summary,
        "relevant_messages": [{"role": msg.role, "content": msg.content} for msg in recent],
        "relevant_requirements": related,
        "conversation_context": state.get("conversation_context") or {},
        "exploration": state.get("exploration") or {},
    }


def _update_summary(summary: str, intent: str, content: str) -> str:
    line = f"{intent}: {content[:160]}"
    lines = [item for item in (summary or "").splitlines() if item][-6:]
    lines.append(line)
    return "\n".join(lines)


def _public_analysis(analysis: dict) -> dict:
    extraction = analysis["extraction"]
    return {
        "intent": analysis["intent"],
        "extraction": extraction.model_dump(),
        "relationship": analysis["relationship"],
        "related": analysis["related"],
        "drift": analysis["drift"],
        "scope": analysis["scope"],
        "prompt_injection": analysis["preprocessing"]["prompt_injection"],
    }


def _message_dict(row: Message) -> dict:
    return {
        "id": str(row.id),
        "role": row.role,
        "content": row.content,
        "intent": row.intent,
        "analysis": row.analysis,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _domain_ids(text: str) -> list[str]:
    from app.nlp.extraction import detect_domains

    found = detect_domains(text or "")
    lowered = (text or "").lower()
    if lowered == "nlp" or "nlp" in lowered:
        found.append("nlp")
    if "cyber" in lowered or "phishing" in lowered:
        found.append("cybersecurity")
    return list(dict.fromkeys(found))
