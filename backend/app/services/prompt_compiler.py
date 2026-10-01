"""Compile an agent-ready prompt from ProjectState.

Pipeline: normalize → conflicts check → architecture/tech → structure →
dedupe → inject constraints → optional polish → invariants.
The raw conversation transcript is never an input.
"""

from __future__ import annotations

import re

from sqlalchemy import select

from app.llm.base import TaskKind
from app.llm.prompts import prompt_compiler_prompt
from app.llm.router import get_provider
from app.models import FinalPrompt, Specification
from app.schemas.state import ConversationStage, migrate_state
from app.services.project_state import public_state, set_stage
from app.services.specification import build_specification
from app.services.versioning import StateVersioning


REQUIRED_LINES = [
    "You are a senior software engineer.",
    "Build the following project completely.",
    "Do not remove or silently alter required functionality.",
    "Do not replace required functionality with placeholders.",
]


def compile_prompt(session, project, specification=None, *, force: bool = False) -> FinalPrompt:
    state = migrate_state(project.state or {})
    gate = compilation_gate(state)
    if gate["blocked"] and not force:
        raise ValueError(gate["message"])

    if specification is None:
        specification = session.scalars(
            select(Specification)
            .where(Specification.project_id == project.id)
            .order_by(Specification.version.desc())
        ).first()
        if specification is None:
            specification = build_specification(session, project)

    structured = _normalize_from_state(state, specification.structured)
    content = render_prompt(structured, specification.markdown, state)
    content = _remove_redundancy(content)
    content = _optional_polish(content)
    content = _enforce_invariants(content, structured)

    # Late import avoids circular dependency with validator ↔ compiler.
    from app.services.prompt_validator import validate_and_repair
    from app.services.audit_log import append_audit_event

    validation = validate_and_repair(content, structured, state)
    content = validation["prompt"]

    req_ids = [
        req["id"]
        for req in (structured.get("functional") or []) + (structured.get("nonfunctional") or [])
    ]
    report = dict(gate)
    report["compilation_mode"] = "forced compilation" if force else "normal compilation"
    report["forced"] = bool(force)

    row = FinalPrompt(
        project_id=project.id,
        specification_id=specification.id,
        content=content,
        details={
            "requirement_ids": req_ids,
            "source": "project_state",
            "gate": report,
            "compilation_report": report,
            "validation": validation["report"],
            "forced": force,
        },
    )
    session.add(row)
    session.flush()

    if force:
        append_audit_event(
            state,
            event_type="FORCED_COMPILATION",
            entity_type="PROMPT",
            entity_id=str(row.id),
            actor="user",
            before={
                "blocking_issues": gate.get("blocking_issues") or [],
                "reasons": gate.get("reasons") or [],
                "can_compile": gate.get("can_compile"),
            },
            after={
                "prompt_version": str(row.id),
                "requirement_ids": req_ids,
                "compilation_mode": "forced compilation",
            },
            reason="force=true bypassed compilation gate",
        )
    append_audit_event(
        state,
        event_type="PROMPT_COMPILED",
        entity_type="PROMPT",
        entity_id=str(row.id),
        actor="system",
        after={"requirement_ids": req_ids, "forced": force, "compilation_mode": report["compilation_mode"]},
        reason="compile_prompt",
    )
    state["prompt"] = {
        "content_preview": content[:500],
        "final_prompt_id": str(row.id),
        "compilation_report": report,
    }
    state["prompt_metrics"] = validation["report"].get("metrics")
    state = set_stage(state, ConversationStage.PROMPT_GENERATION)
    if validation["report"].get("acceptable"):
        state = set_stage(state, ConversationStage.VALIDATION)
    state = StateVersioning.bump(state, "compile_prompt")
    project.state = public_state(state)
    StateVersioning.snapshot(session, project, "compile_prompt")
    return row


def compilation_gate(state: dict) -> dict:
    """Block compile when critical conflicts/gaps remain (unless force=True)."""
    from app.services.assertion_lifecycle import requirement_is_compilable
    from app.services.traceability import blocking_grill_attacks, validate_traceability

    open_conflicts = [c for c in (state.get("conflicts") or []) if c.get("status") == "open"]
    missing_objective = not (
        (state.get("project") or {}).get("objective")
        or (state.get("core_idea") or {}).get("primary_objective")
    )
    all_reqs = list(state.get("requirements") or [])
    active = [r for r in all_reqs if r.get("status") == "active"]
    compilable = [r for r in active if requirement_is_compilable(r)]
    excluded = []
    for req in all_reqs:
        if requirement_is_compilable(req):
            continue
        excluded.append({
            "id": req.get("id"),
            "text": req.get("text"),
            "reason": _exclusion_reason(req),
            "assertion_status": req.get("assertion_status"),
            "status": req.get("status"),
        })
    trace = validate_traceability(state)
    grill_attacks = list(state.get("grill_attacks") or [])
    evidence = list(state.get("evidence") or [])
    reasons = []
    blocking_issues = list(trace.get("blocking_issues") or [])
    if open_conflicts:
        reasons.append(f"{len(open_conflicts)} open conflict(s) must be resolved")
    if missing_objective:
        reasons.append("project objective is missing")
    if not active:
        reasons.append("no active requirements")
    if active and not compilable:
        reasons.append("no confirmed/locked requirements eligible for compilation")
    for issue in blocking_issues:
        if issue.get("type") == "UNRESOLVED_GRILL_ATTACK":
            reasons.append(f"unresolved grill attack {issue.get('id')}")
    blocked = bool(reasons)
    return {
        "blocked": blocked,
        "can_compile": not blocked,
        "reasons": reasons,
        "blocking_issues": blocking_issues,
        "warnings": trace.get("warnings") or [],
        "included_requirements": [
            {"id": r.get("id"), "text": r.get("text"), "assertion_status": r.get("assertion_status")}
            for r in compilable
        ],
        "excluded_requirements": excluded,
        "traceability_status": {
            "valid": trace.get("valid"),
            "blocking_issues": trace.get("blocking_issues") or [],
            "warnings": trace.get("warnings") or [],
            "link_count": len(state.get("trace_links") or []),
        },
        "grill_status": {
            "open": sum(1 for a in grill_attacks if a.get("status") in {"OPEN", "UNRESOLVED", "RESPONDED"}),
            "blocking": len(blocking_grill_attacks(state)),
            "resolved": sum(1 for a in grill_attacks if a.get("status") == "RESOLVED"),
            "deferred": sum(1 for a in grill_attacks if a.get("status") == "DEFERRED"),
        },
        "evidence_status": {
            "total": len(evidence),
            "unverified": sum(1 for e in evidence if e.get("verification_status") == "UNVERIFIED"),
            "verified": sum(1 for e in evidence if e.get("verification_status") == "VERIFIED"),
        },
        "message": (
            "Prompt compilation blocked: " + "; ".join(reasons) + ". Resolve these or compile with force=true."
            if blocked
            else "ready"
        ),
        "stage": state.get("conversation_stage"),
    }


def _exclusion_reason(req: dict) -> str:
    status = str(req.get("status") or "").lower()
    assertion = str(req.get("assertion_status") or "")
    if status == "superseded" or assertion == "SUPERSEDED":
        superseded_by = req.get("superseded_by")
        if superseded_by:
            return f"SUPERSEDED by {superseded_by}"
        return "SUPERSEDED"
    if status in {"removed", "rejected"} or assertion == "REJECTED":
        return "REJECTED"
    if assertion == "INFERRED":
        return "INFERRED — not user-confirmed"
    if assertion == "PROPOSED":
        return "PROPOSED but not user-confirmed"
    if assertion == "MENTIONED":
        return "MENTIONED — not promoted"
    if status != "active":
        return f"status={status}"
    if not assertion:
        return "missing assertion_status"
    return f"assertion_status={assertion} is not compilable"


def conversational_gate_message(state: dict) -> str:
    """Natural clarification when compile is not ready — never a hard 'blocked' dump."""
    gate = compilation_gate(state)
    if not gate["blocked"]:
        return "The project looks ready to compile."
    reasons = gate.get("reasons") or []
    project = state.get("project") or {}
    core = state.get("core_idea") or {}
    objective = project.get("objective") or core.get("primary_objective")
    domains = state.get("domains") or []
    if "project objective is missing" in reasons:
        return (
            "Before I compile the final Cursor prompt, we still need a clear objective. "
            "What should the finished system actually do for its users?"
        )
    if "no active requirements" in reasons:
        if objective and any("log" in (d or "").lower() for d in domains + [objective]):
            return (
                "Before I compile the final Cursor prompt, we haven't decided what the system "
                "should actually detect. Should it focus on suspicious authentication activity, "
                "malware-related logs, or general system anomalies?"
            )
        if objective and re.search(r"phish", (objective or "").lower()):
            return (
                "Before I compile the final Cursor prompt, we need at least one concrete requirement. "
                "Should the first version detect phishing emails, suspicious URLs, or both?"
            )
        return (
            "Before I compile the final Cursor prompt, we haven't locked any active requirements yet. "
            "What must the first version definitely do?"
        )
    if any("conflict" in r for r in reasons):
        return (
            "There's still an open conflict in the project decisions. "
            "Which option should win before I compile the final prompt?"
        )
    return (
        "We're close, but a few decisions are still open. "
        "What should we settle first so the Cursor prompt stays accurate?"
    )


def _normalize_from_state(state: dict, spec: dict) -> dict:
    """Prefer live ProjectState fields over a stale specification snapshot."""
    merged = dict(spec or {})
    project = state.get("project") or {}
    merged["title"] = project.get("title") or merged.get("title") or ""
    merged["problem"] = project.get("problem") or merged.get("problem") or ""
    merged["objective"] = (
        project.get("objective")
        or (state.get("core_idea") or {}).get("primary_objective")
        or merged.get("objective")
        or ""
    )
    merged["constraints"] = state.get("constraints") or merged.get("constraints") or {}
    tech = dict(state.get("technology") or {})
    # Drop recommendation-only noise from the agent prompt stack block.
    tech.pop("recommendations", None)
    tech.pop("provenance", None)
    merged["technology"] = tech or merged.get("technology") or {}
    arch = state.get("architecture") or {}
    merged["architecture"] = arch.get("logical") or arch or merged.get("architecture")
    merged["database"] = state.get("database") or merged.get("database")
    merged["apis"] = state.get("apis") or merged.get("apis") or []

    active = [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
    if active:
        from app.services.assertion_lifecycle import requirement_is_compilable

        functional = []
        nonfunctional = []
        for req in active:
            if not requirement_is_compilable(req):
                continue
            item = {
                "id": req.get("id"),
                "text": req.get("text"),
                "acceptance": req.get("acceptance"),
                "actor": req.get("actor"),
                "capability": req.get("capability"),
            }
            if (req.get("type") or "functional") == "functional":
                functional.append(item)
            else:
                nonfunctional.append(item)
        merged["functional"] = functional
        merged["nonfunctional"] = nonfunctional
    return merged


def render_prompt(spec: dict, specification_markdown: str, state: dict | None = None) -> str:
    state = state or {}
    functional = spec.get("functional") or []
    nonfunctional = spec.get("nonfunctional") or []
    tech = spec.get("technology") or {}
    constraints = spec.get("constraints") or {}
    arch = spec.get("architecture") or {}
    database = spec.get("database") or {}
    apis = spec.get("apis") or []
    grill = state.get("grill_findings") or {}

    def block(rows: list[dict]) -> str:
        if not rows:
            return "- None recorded."
        lines = []
        for req in rows:
            lines.append(f"{req['id']}:\n{req['text']}")
            if req.get("acceptance"):
                lines.append(f"  Acceptance: {req['acceptance']}")
        return "\n".join(lines)

    criteria_parts = []
    for req in functional + nonfunctional:
        if req.get("acceptance"):
            criteria_parts.append(f"[ ] {req['id']}: {req['acceptance']}")
        else:
            criteria_parts.append(f"[ ] {req['id']} implemented")
    criteria_parts.extend(["[ ] Tests pass", "[ ] Application runs successfully"])
    criteria = "\n".join(criteria_parts)

    stack = "\n".join([
        f"Backend: {tech.get('backend') or (', '.join(tech.get('languages') or []) or 'unspecified')}",
        f"Model: {tech.get('model') or (', '.join(tech.get('models') or []) or 'unspecified')}",
        f"Database: {tech.get('database') or (', '.join(tech.get('databases') or []) or 'unspecified')}",
        f"Frameworks: {', '.join(tech.get('frameworks') or []) or 'unspecified'}",
        f"Hardware: {', '.join(tech.get('hardware') or []) or 'none'}",
    ])

    arch_lines = []
    if isinstance(arch, dict):
        if arch.get("layers"):
            arch_lines.append("Layers: " + ", ".join(arch["layers"]))
        if arch.get("components"):
            arch_lines.append("Components: " + "; ".join(arch["components"]))
        if arch.get("implementation") and isinstance(arch["implementation"], dict):
            arch_lines.append("Style: " + str(arch["implementation"].get("style") or ""))
    arch_text = "\n".join(arch_lines) or "Use a modular monolith unless ProjectState specifies otherwise."

    db_text = "Use the database named in TECH STACK."
    if isinstance(database, dict) and database.get("entities"):
        names = ", ".join(e.get("name", "") for e in database["entities"] if e.get("name"))
        db_text = f"Entities: {names}."
        if database.get("relationships"):
            db_text += " Relationships: " + "; ".join(database["relationships"])

    api_text = "Implement an operation for every functional requirement."
    if apis:
        api_text = "\n".join(
            f"- {a.get('method')} {a.get('path')}: {a.get('purpose')}" for a in apis
        )

    grill_text = ""
    if grill.get("questions_that_must_be_resolved"):
        grill_text = (
            "\nOPEN GRILL QUESTIONS (resolve during implementation if still open)\n"
            + "\n".join(f"- {q}" for q in grill["questions_that_must_be_resolved"][:8])
            + "\n"
        )

    research = state.get("research") or []
    research_text = ""
    applied = [r for r in research if r.get("applied") or r.get("source_type") != "system"]
    if applied:
        research_text = "\nRESEARCH CONSTRAINTS\n" + "\n".join(
            f"- {r.get('project_impact') or r.get('finding')}" for r in applied[-5:]
        ) + "\n"

    return f"""You are a senior software engineer.

Build the following project completely.

ROLE
You are a senior software engineer implementing a student project from a validated ProjectState specification. Inspect the existing repository before writing code.

PROJECT
{spec.get("title")}

OBJECTIVE
{spec.get("objective") or "See the specification."}

PROBLEM
{spec.get("problem") or "See the specification."}

REQUIREMENTS
Functional and non-functional requirements below are mandatory. Preserve every requirement ID.

FUNCTIONAL REQUIREMENTS
{block(functional)}

NON-FUNCTIONAL REQUIREMENTS
{block(nonfunctional)}

CONSTRAINTS
- Team size: {constraints.get("team_size")}
- Duration: {constraints.get("duration")}
- Budget: {constraints.get("budget")}
- Avoid: {", ".join(constraints.get("avoid") or []) or "none"}
{research_text}
TECH STACK
{stack}

ARCHITECTURE
{arch_text}

DATABASE
{db_text}

API
{api_text}

SECURITY
Keep secrets in environment variables. Validate input. Do not expose credentials.

TESTING
Write a test mapped from each requirement ID. Run the tests.

ACCEPTANCE CRITERIA
{criteria}
{grill_text}
IMPLEMENTATION PROCESS
1. Inspect the existing repository.
2. Understand the requirements.
3. Create the required architecture.
4. Implement the components.
5. Configure dependencies.
6. Implement database, API, and frontend components.
7. Write tests.
8. Run tests.
9. Fix implementation errors.
10. Verify every acceptance criterion.
11. Provide setup instructions.

DELIVERABLES
- Working implementation of every requirement ID
- Tests
- Setup instructions
- A short note mapping each acceptance criterion to evidence

Do not remove or silently alter required functionality.
Do not replace required functionality with placeholders.
"""


def _remove_redundancy(content: str) -> str:
    # Drop duplicate consecutive headings / near-duplicate ROLE/OBJECTIVE blocks.
    lines = content.splitlines()
    cleaned = []
    seen_headings = set()
    for line in lines:
        heading = line.strip().upper()
        if heading in {
            "ROLE", "PROJECT", "OBJECTIVE", "PROBLEM", "REQUIREMENTS",
            "FUNCTIONAL REQUIREMENTS", "NON-FUNCTIONAL REQUIREMENTS",
            "CONSTRAINTS", "TECH STACK", "ARCHITECTURE", "DATABASE", "API",
            "SECURITY", "TESTING", "ACCEPTANCE CRITERIA", "IMPLEMENTATION PROCESS",
            "DELIVERABLES",
        }:
            if heading in seen_headings:
                continue
            seen_headings.add(heading)
        # Collapse repeated identical lines.
        if cleaned and cleaned[-1] == line and line.strip():
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _optional_polish(content: str) -> str:
    provider = get_provider(TaskKind.COMPILE)
    if not provider.available:
        return content
    try:
        polished = provider.generate(prompt_compiler_prompt(content), None, task=TaskKind.COMPILE)
    except Exception:
        return content
    if not polished:
        return content
    return polished


def _enforce_invariants(content: str, spec: dict) -> str:
    for line in REQUIRED_LINES:
        if line not in content:
            content += f"\n{line}\n"
    for req in (spec.get("functional") or []) + (spec.get("nonfunctional") or []):
        if req["id"] not in content:
            content += f"\n{req['id']}:\n{req['text']}\n"
    for heading in ("ACCEPTANCE CRITERIA", "IMPLEMENTATION PROCESS", "DELIVERABLES", "TECH STACK"):
        if heading not in content:
            content += f"\n{heading}\nSee the validated specification.\n"
    return content


def coverage(spec: dict, prompt: str) -> dict:
    ids = [req["id"] for req in (spec.get("functional") or []) + (spec.get("nonfunctional") or [])]
    present = [req_id for req_id in ids if req_id in prompt]
    return {
        "requirement_count": len(ids),
        "represented": len(present),
        "coverage": (len(present) / len(ids)) if ids else 1.0,
        "missing": [req_id for req_id in ids if req_id not in present],
    }
