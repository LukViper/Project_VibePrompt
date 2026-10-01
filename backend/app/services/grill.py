"""Adversarial Grill engine.

Dimensions cover clarity, scope, data, feasibility, AI necessity, evaluation,
research potential, deployment, security, dependency risk, and timeline.
Output is strengths/weaknesses/missing info/risks/recommended changes/questions —
never a vanity score. Findings persist on ProjectState.grill_findings.
"""

from __future__ import annotations

import re

from app.llm.base import TaskKind
from app.llm.prompts import grill_prompt, review_prompt
from app.llm.router import get_provider
from app.nlp.lexicon import DOMAIN_LABELS
from app.nlp.similarity import cosine_similarity
from app.nlp.embeddings import create_embedding
from app.schemas.state import ConversationStage, migrate_state
from app.services.project_state import public_state, set_stage
from app.services.versioning import StateVersioning


def _active(state: dict) -> list[dict]:
    return [req for req in state.get("requirements") or [] if req.get("status") == "active"]


def _objective(state: dict) -> str:
    core = state.get("core_idea") or {}
    return core.get("primary_objective") or (state.get("project") or {}).get("objective") or ""


def conversational_challenge(state: dict, message: str = "") -> dict:
    """One-turn Grill-style challenge for conversational refinement (not a full report dump)."""
    state = migrate_state(state)
    objective = _objective(state)
    constraints = state.get("constraints") or {}
    duration = constraints.get("duration") or ""
    team = constraints.get("team_size")
    lowered = (message or "").lower()
    active = _active(state)

    # Prefer the highest-severity check that asks the user to decide.
    dimensions = _dimension_checks(state, objective)
    high = [d for d in dimensions if d.get("severity") == "high"]
    medium = [d for d in dimensions if d.get("severity") == "medium"]
    pick = (high or medium or dimensions[:1] or [None])[0]

    if re.search(r"\btoo (big|broad|ambitious|much|large|complex)\b", lowered) or re.search(
        r"\bunrealistic|overscoped|narrow|scale back\b", lowered
    ):
        focus = objective or (state.get("project") or {}).get("problem") or "this idea"
        narrative = f"{focus} may be too large as stated. "
        if duration or team is not None:
            bits = []
            if team == 1:
                bits.append("a solo builder")
            elif team:
                bits.append(f"a team of {team}")
            if duration:
                bits.append(duration)
            narrative += f"With {' and '.join(bits)}, "
        narrative += (
            "which part matters most to keep—and what can we cut or defer so the core is finishable?"
        )
        question = "Which capability is essential for a first version, and which can wait?"
    elif pick and pick.get("question"):
        narrative = pick.get("detail") or pick.get("recommendation") or "Let's pressure-test the current plan."
        if pick.get("question"):
            narrative = f"{narrative.rstrip('.')} {pick['question']}"
        question = pick.get("question")
    elif not objective:
        narrative = (
            "Before we push further, the objective is still fuzzy. "
            "What should a successful first version actually demonstrate?"
        )
        question = narrative
    else:
        narrative = (
            f"For {objective}, the risk is trying to do too much at once. "
            "Should we prioritize a narrower MVP that you can evaluate cleanly?"
        )
        question = "What is the smallest useful version of this project?"

    updated = dict(state)
    updated["conversation_stage"] = ConversationStage.GRILL.value
    ctx = dict(updated.get("conversation_context") or {})
    ctx["open_questions"] = list(dict.fromkeys((ctx.get("open_questions") or []) + [question]))[-6:]
    updated["conversation_context"] = ctx
    # Conversational grill questions belong in dialogue context, not form readiness gaps.
    open_q = [q for q in (updated.get("open_questions") or []) if q]
    if question not in open_q:
        open_q.append(question)
    updated["open_questions"] = open_q[-8:]
    updated["last_orchestrator_action"] = "GRILL"
    return {
        "narrative": narrative.strip(),
        "question": question,
        "state": updated,
        "mode": "conversational_grill",
    }


def grill(state: dict, *, persist_on_project=None, session=None) -> dict:
    """Run adversarial grill. Optionally persist findings onto a Project ORM row."""
    state = migrate_state(state)
    objective = _objective(state)
    dimensions = _dimension_checks(state, objective)
    weaknesses = [item for item in dimensions if item.get("severity") in {"high", "medium"}]
    strengths = [item for item in dimensions if item.get("severity") == "low" and item.get("positive")]
    missing = [item["detail"] for item in dimensions if item.get("missing")]
    risks = {
        "technical": [d["detail"] for d in dimensions if d.get("risk_type") == "technical"],
        "scope": [d["detail"] for d in dimensions if d.get("risk_type") == "scope"],
        "research": [d["detail"] for d in dimensions if d.get("risk_type") == "research"],
        "dataset": [d["detail"] for d in dimensions if d.get("risk_type") == "dataset"],
    }
    recommended = [d["recommendation"] for d in dimensions if d.get("recommendation")]
    must_resolve = [d["question"] for d in dimensions if d.get("must_resolve")]
    report = {
        "mode": "grill",
        "objective": objective,
        "dimensions": dimensions,
        "strengths": [s["detail"] for s in strengths] or ["Core objective is stated." if objective else ""],
        "weaknesses": [{"topic": w["dimension"], "severity": w["severity"], "detail": w["detail"]} for w in weaknesses],
        "missing_information": missing,
        "risks": risks,
        "recommended_changes": recommended,
        "questions_that_must_be_resolved": must_resolve,
        "summary": _grill_summary(objective, weaknesses, must_resolve),
        "iteration": int(((state.get("grill_findings") or {}).get("iteration") or 0)) + 1,
    }
    report["strengths"] = [s for s in report["strengths"] if s]
    report["structured"] = _structured_grill_report(report)
    report["narrative"] = _narrate_structured(report)

    if persist_on_project is not None and session is not None:
        updated = migrate_state(persist_on_project.state or {})
        updated["grill_findings"] = {
            "iteration": report["iteration"],
            "strengths": report["strengths"],
            "weaknesses": report["weaknesses"],
            "missing_information": report["missing_information"],
            "risks": report["risks"],
            "recommended_changes": report["recommended_changes"],
            "questions_that_must_be_resolved": report["questions_that_must_be_resolved"],
            "summary": report["summary"],
            "structured": report["structured"],
        }
        updated["grill_report"] = report["structured"]
        updated["open_questions"] = list(
            dict.fromkeys((updated.get("open_questions") or []) + report["structured"].get("open_questions", []))
        )
        updated["implementation_plan"] = report["structured"].get("realistic_plan") or updated.get("implementation_plan") or []
        updated = set_stage(updated, ConversationStage.GRILL)
        updated = StateVersioning.bump(updated, "grill")
        persist_on_project.state = public_state(updated)
        StateVersioning.snapshot(session, persist_on_project, "grill")
        report["state"] = public_state(updated)
    return report


def _structured_grill_report(report: dict) -> dict:
    """Master Spec §15 sections — no vanity overall score."""
    blocking = []
    high_risk = []
    concerns = []
    for item in report.get("weaknesses") or []:
        detail = item.get("detail") or ""
        sev = item.get("severity")
        if sev == "high" and item.get("topic") in {"timeline", "scope", "dataset", "feasibility"}:
            blocking.append(detail)
        elif sev == "high":
            high_risk.append(detail)
        else:
            concerns.append(detail)
    for miss in report.get("missing_information") or []:
        concerns.append(miss)
    validated = list(report.get("strengths") or [])
    change_required = list(report.get("recommended_changes") or [])
    open_questions = list(report.get("questions_that_must_be_resolved") or [])
    alternatives = []
    for change in change_required[:5]:
        alternatives.append({
            "issue": change,
            "options": [
                "Reduce scope to match constraints",
                "Extend timeline / add teammates",
                "Replace the risky requirement with a simpler alternative",
            ],
        })
    realistic_plan = []
    if blocking or high_risk:
        realistic_plan.append("Resolve BLOCKING / HIGH RISK items before expanding features.")
    if change_required:
        realistic_plan.extend(change_required[:4])
    realistic_plan.append("Re-run Grill after each material decision change.")
    if not realistic_plan:
        realistic_plan.append("Proceed with implementation in thin vertical slices; keep evaluation explicit.")
    return {
        "blocking": blocking,
        "high_risk": high_risk,
        "concerns": concerns,
        "validated": validated,
        "change_required": change_required,
        "alternatives": alternatives,
        "realistic_plan": realistic_plan,
        "open_questions": open_questions,
        "iteration": report.get("iteration") or 1,
        "summary": report.get("summary") or "",
        "dimensions": report.get("dimensions") or [],
    }


def _narrate_structured(report: dict) -> str:
    structured = report.get("structured") or _structured_grill_report(report)
    lines = [
        "GRILL RESULT",
        "",
        "BLOCKING",
        *(f"- {item}" for item in (structured.get("blocking") or []) or ["None identified."]),
        "",
        "HIGH RISK",
        *(f"- {item}" for item in (structured.get("high_risk") or []) or ["None identified."]),
        "",
        "CONCERNS",
        *(f"- {item}" for item in (structured.get("concerns") or []) or ["None identified."]),
        "",
        "VALIDATED",
        *(f"- {item}" for item in (structured.get("validated") or []) or ["No strengths recorded yet."]),
        "",
        "CHANGE REQUIRED",
        *(f"- {item}" for item in (structured.get("change_required") or []) or ["None required yet."]),
        "",
        "ALTERNATIVES",
    ]
    alts = structured.get("alternatives") or []
    if not alts:
        lines.append("- Resolve open questions with explicit user decisions; do not auto-rewrite the project.")
    for alt in alts:
        lines.append(f"- Issue: {alt.get('issue')}")
        for option in alt.get("options") or []:
            lines.append(f"  • {option}")
    lines.extend([
        "",
        "REALISTIC PLAN",
        *(f"- {item}" for item in (structured.get("realistic_plan") or [])),
        "",
        "OPEN QUESTIONS",
        *(f"- {item}" for item in (structured.get("open_questions") or []) or ["None."]),
        "",
        "Grill does not automatically rewrite your project. Choose how to resolve each issue.",
    ])
    return "\n".join(lines)


def professional_review(state: dict) -> dict:
    state = public_state(state)
    objective = _objective(state)
    active = _active(state)
    second_target = any(req.get("domain") in {"browser_extension", "mobile"} for req in active)
    unrelated = (state.get("drift") or {}).get("potential_drift")
    findings = {
        "mode": "professional",
        "completeness": "partial" if state.get("open_questions") else "sufficient for a prototype specification",
        "feasibility": _dim_feasibility(state)["detail"],
        "technical_consistency": "conflict open" if any(item.get("status") == "open" for item in state.get("conflicts") or []) else "no open technology conflict",
        "academic_relevance": _dim_research_potential(state)["detail"],
        "architecture": "A single backend plus one client is enough unless a second deployment target has been accepted.",
        "scope": (state.get("scope") or {}).get("message") or "No scope expansion is currently flagged.",
        "dependencies": ", ".join((state.get("technology") or {}).get("models") or []) or "No extra model dependency is locked yet.",
        "findings": [],
        "user_decision_required": True,
    }
    if second_target:
        findings["findings"].append({
            "severity": "medium",
            "topic": "deployment",
            "explanation": (
                "This feature is technically possible, but it introduces a second deployment target "
                "and increases the project scope. Confirm that it still contributes to the stated objective."
            ),
        })
    if unrelated:
        findings["findings"].append({
            "severity": "high",
            "topic": "objective",
            "explanation": "At least one requirement does not contribute directly to the stated objective.",
        })
    if not findings["findings"]:
        findings["findings"].append({
            "severity": "low",
            "topic": "general",
            "explanation": "No blocking feasibility or consistency issue was found. The user should still review coverage before prompt compilation.",
        })
    findings["summary"] = " ".join(item["explanation"] for item in findings["findings"])
    findings["narrative"] = _narrate(review_prompt(state, findings), findings["summary"])
    return findings


def _dimension_checks(state: dict, objective: str) -> list[dict]:
    return [
        _dim_problem_clarity(state, objective),
        _dim_scope(state, objective),
        _dim_dataset(state),
        _dim_feasibility(state),
        _dim_ai_necessity(state, objective),
        _dim_evaluation(state),
        _dim_research_potential(state),
        _dim_deployment(state),
        _dim_security(state),
        _dim_dependency_risk(state),
        _dim_timeline(state),
        _dim_objective_alignment(state, objective),
    ]


def _dim_problem_clarity(state: dict, objective: str) -> dict:
    if not objective:
        return _finding(
            "problem_clarity", "high",
            "Problem / objective is missing.",
            missing=True,
            must_resolve="What concrete problem should the system solve?",
            recommendation="Lock a one-sentence objective before adding features.",
            risk_type="scope",
        )
    if len(objective.split()) < 4:
        return _finding(
            "problem_clarity", "medium",
            "Objective is too vague for adversarial review.",
            must_resolve="Can you restate the objective with user + outcome?",
            risk_type="scope",
        )
    return _finding("problem_clarity", "low", f"Objective stated: {objective}", positive=True)


def _dim_scope(state: dict, objective: str) -> dict:
    active = _active(state)
    if len(active) > 12:
        return _finding(
            "scope", "high",
            f"{len(active)} active requirements — likely oversized for a student timeline.",
            recommendation="Cut or defer non-core requirements.",
            risk_type="scope",
            must_resolve="Which requirements are must-have for the first deliverable?",
        )
    scope = state.get("scope") or {}
    if scope.get("detected"):
        return _finding(
            "scope", "medium",
            scope.get("message") or "Scope expansion detected.",
            risk_type="scope",
        )
    return _finding("scope", "low", "Scope looks manageable relative to current requirements.", positive=True)


def _dim_dataset(state: dict) -> dict:
    blob = str(state).lower()
    has_data_mention = any(token in blob for token in ("dataset", "labeled", "corpus", "training data", "emails"))
    if not has_data_mention and (state.get("academic") or {}).get("subject"):
        return _finding(
            "dataset", "high",
            "No dataset or evaluation corpus is recorded.",
            missing=True,
            risk_type="dataset",
            must_resolve="What data will you train/evaluate on, and is it obtainable?",
            recommendation="Name a concrete dataset or collection plan.",
        )
    return _finding("dataset", "low", "Data considerations appear in the state or subject context.", positive=True)


def _dim_feasibility(state: dict) -> dict:
    constraints = state.get("constraints") or {}
    team = constraints.get("team_size")
    duration = constraints.get("duration") or ""
    active = len(_active(state))
    if team == 1 and active > 8:
        return _finding(
            "feasibility", "high",
            "Solo team with many requirements is high delivery risk.",
            risk_type="scope",
            recommendation="Reduce parallel workstreams.",
            must_resolve="What is the minimum viable slice for one person?",
        )
    if "week" in duration and any(ch.isdigit() for ch in duration):
        weeks = int("".join(ch for ch in duration if ch.isdigit()) or "0")
        if weeks and weeks <= 3 and active > 6:
            return _finding(
                "feasibility", "medium",
                f"Duration {duration} is tight for {active} requirements.",
                risk_type="scope",
            )
    return _finding("feasibility", "low", "Constraints and requirement count look feasible for a prototype.", positive=True)


def _dim_ai_necessity(state: dict, objective: str) -> dict:
    tech = state.get("technology") or {}
    models = tech.get("models") or []
    ai = state.get("ai_nlp") or {}
    if models or ai:
        # Check if objective needs ML
        if objective and not any(token in objective.lower() for token in ("classif", "detect", "nlp", "predict", "recogn", "language", "spam", "phish")):
            return _finding(
                "ai_necessity", "medium",
                f"Models {models or list(ai.keys())} may be unnecessary for the stated objective.",
                risk_type="technical",
                recommendation="Justify AI vs a simpler rule/heuristic baseline.",
                must_resolve="Why is a learned model required?",
            )
        return _finding("ai_necessity", "low", "AI/NLP choice aligns with an ML-shaped objective.", positive=True)
    return _finding("ai_necessity", "low", "No heavy model is locked yet.", positive=True)


def _dim_evaluation(state: dict) -> dict:
    testing = state.get("testing") or {}
    active = _active(state)
    has_acceptance = any(req.get("acceptance") for req in active)
    if not testing and not has_acceptance:
        return _finding(
            "evaluation", "high",
            "No evaluation plan or acceptance criteria recorded.",
            missing=True,
            risk_type="technical",
            must_resolve="How will success be measured (metrics, test set, demo script)?",
            recommendation="Add acceptance criteria to core requirements.",
        )
    return _finding("evaluation", "low", "Some acceptance or testing signal exists.", positive=True)


def _dim_research_potential(state: dict) -> dict:
    academic = state.get("academic") or {}
    if academic.get("subject") and not academic.get("required_concepts"):
        return _finding(
            "research_potential", "medium",
            "Subject set but required academic concepts are empty.",
            missing=True,
            risk_type="research",
            recommendation="List course concepts the project must demonstrate.",
        )
    if academic.get("required_concepts"):
        return _finding(
            "research_potential", "low",
            "Required concepts recorded: " + ", ".join(academic["required_concepts"][:5]),
            positive=True,
        )
    return _finding("research_potential", "low", "Non-academic or concepts not yet required.", positive=True)


def _dim_deployment(state: dict) -> dict:
    active = _active(state)
    targets = [req for req in active if req.get("domain") in {"browser_extension", "mobile"}]
    if len(targets) >= 1 and not (state.get("deployment") or {}):
        return _finding(
            "deployment", "medium",
            "Extra client/deployment target without a deployment plan.",
            risk_type="scope",
            recommendation="Defer second deployment target or document packaging steps.",
        )
    return _finding("deployment", "low", "Deployment surface looks simple or unspecified (OK early).", positive=True)


def _dim_security(state: dict) -> dict:
    security = state.get("security") or []
    blob = " ".join(req.get("text", "") for req in _active(state)).lower()
    handles_user_data = any(token in blob for token in ("email", "password", "user", "auth", "personal"))
    if handles_user_data and not security:
        return _finding(
            "security", "medium",
            "User-facing data flows without recorded security requirements.",
            missing=True,
            risk_type="technical",
            recommendation="Add auth/privacy constraints if user data is stored.",
            must_resolve="What security or privacy constraints are mandatory?",
        )
    return _finding("security", "low", "No immediate security gap flagged.", positive=True)


def _dim_dependency_risk(state: dict) -> dict:
    tech = state.get("technology") or {}
    models = tech.get("models") or []
    if len(models) > 1:
        return _finding(
            "dependency_risk", "medium",
            f"Multiple models locked ({', '.join(models)}) increase dependency risk.",
            risk_type="technical",
            recommendation="Pick one primary model for V1.",
        )
    conflicts = [c for c in (state.get("conflicts") or []) if c.get("status") == "open"]
    if conflicts:
        return _finding(
            "dependency_risk", "high",
            conflicts[-1].get("explanation") or "Open technology conflict.",
            risk_type="technical",
            must_resolve="Which conflicting technology choice wins?",
        )
    return _finding("dependency_risk", "low", "Dependency surface is limited.", positive=True)


def _dim_timeline(state: dict) -> dict:
    duration = (state.get("constraints") or {}).get("duration")
    if not duration:
        return _finding(
            "timeline", "medium",
            "No project duration recorded.",
            missing=True,
            must_resolve="How many weeks do you have?",
            risk_type="scope",
        )
    return _finding("timeline", "low", f"Duration recorded: {duration}", positive=True)


def _dim_objective_alignment(state: dict, objective: str) -> dict:
    weak = []
    if objective:
        for req in _active(state):
            if req.get("origin") == "original":
                continue
            score = cosine_similarity(create_embedding(objective), create_embedding(req["text"]))
            if score < 0.35:
                weak.append(req["id"])
    if weak:
        return _finding(
            "objective_alignment", "high",
            "Requirements poorly aligned with objective: " + ", ".join(weak[:5]),
            risk_type="scope",
            recommendation="Remove or rewrite misaligned requirements.",
            must_resolve="Keep these requirements or cut them?",
        )
    drift = state.get("drift") or {}
    if drift.get("potential_drift"):
        return _finding(
            "objective_alignment", "high",
            "Potential project drift previously flagged.",
            risk_type="scope",
        )
    return _finding("objective_alignment", "low", "No strong misalignment signal.", positive=True)


def _finding(
    dimension: str,
    severity: str,
    detail: str,
    *,
    positive: bool = False,
    missing: bool = False,
    risk_type: str | None = None,
    recommendation: str | None = None,
    must_resolve: str | None = None,
    question: str | None = None,
) -> dict:
    return {
        "dimension": dimension,
        "severity": severity,
        "detail": detail,
        "positive": positive,
        "missing": missing,
        "risk_type": risk_type,
        "recommendation": recommendation,
        "must_resolve": must_resolve,
        "question": must_resolve or question,
    }


def _grill_summary(objective: str, weaknesses: list[dict], must_resolve: list[str]) -> str:
    parts = []
    if objective:
        parts.append(f"Grill against objective: {objective}.")
    else:
        parts.append("Grill cannot fully proceed — objective is missing.")
    if weaknesses:
        parts.append(f"{len(weaknesses)} adversarial concern(s) raised.")
    else:
        parts.append("No high/medium adversarial concerns on the current checklist.")
    if must_resolve:
        parts.append("Must resolve: " + "; ".join(must_resolve[:3]))
    parts.append("This is not a score — decide which weaknesses to fix before prompt compilation.")
    return " ".join(parts)


def _narrate(prompt: str, fallback: str) -> str:
    provider = get_provider(TaskKind.GRILL)
    if not provider.available:
        return fallback
    try:
        text = provider.generate(prompt, None, task=TaskKind.GRILL)
        return text.strip() or fallback
    except Exception:
        return fallback
