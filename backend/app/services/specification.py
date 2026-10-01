"""Formal project specification generated from structured state, not raw chat.

Master Spec §18 — include only relevant sections; never dump conversation history.
"""

from __future__ import annotations

from app.llm.base import TaskKind
from app.llm.prompts import specification_prompt
from app.llm.router import get_provider
from app.models import Specification
from app.services.project_state import public_state

# Master Spec section order (only emit when content exists / is relevant).
SECTION_ORDER = [
    ("PROJECT OBJECTIVE", "objective"),
    ("PROBLEM", "problem"),
    ("TARGET USERS", "users"),
    ("SCOPE", "scope"),
    ("FUNCTIONAL REQUIREMENTS", "functional"),
    ("NON-FUNCTIONAL REQUIREMENTS", "nonfunctional"),
    ("CONSTRAINTS", "constraints"),
    ("ARCHITECTURE", "architecture"),
    ("TECHNOLOGY STACK", "technology"),
    ("DATABASE", "database"),
    ("API CONTRACTS", "apis"),
    ("AI/NLP PIPELINE", "ai_nlp"),
    ("SECURITY", "security"),
    ("TESTING", "testing"),
    ("DEPLOYMENT", "deployment"),
    ("ACCEPTANCE CRITERIA", "acceptance"),
    ("IMPLEMENTATION ORDER", "implementation_plan"),
    ("KNOWN RISKS", "risks"),
]


def build_specification(session, project) -> Specification:
    state = public_state(project.state or {})
    structured = _structured(state)
    markdown = _markdown(structured, state)
    markdown = _maybe_polish(markdown, state)
    markdown = _restore_requirements(markdown, structured)
    version = len(project.specifications) + 1
    row = Specification(
        project_id=project.id,
        version=version,
        markdown=markdown,
        structured=structured,
    )
    session.add(row)
    session.flush()
    return row


def _active(state: dict, kind: str | None = None) -> list[dict]:
    from app.services.assertion_lifecycle import requirement_is_compilable

    rows = [
        req
        for req in state.get("requirements") or []
        if req.get("status") == "active" and requirement_is_compilable(req)
    ]
    if kind:
        return [req for req in rows if req.get("type") == kind]
    return rows


def _structured(state: dict) -> dict:
    functional = _active(state, "functional")
    nonfunctional = [req for req in _active(state) if req.get("type") != "functional"]
    tech = state.get("technology") or {}
    arch = state.get("architecture") or {}
    database = state.get("database") or {}
    proposed_db = database.get("proposed") if isinstance(database.get("proposed"), dict) else database
    project = state.get("project") or {}
    constraints = state.get("constraints") or {}
    platforms = project.get("platform") or []
    if isinstance(platforms, str):
        platforms = [platforms]
    acceptance = []
    for req in functional + nonfunctional:
        text = req.get("text") or ""
        actor = (req.get("actor") or "user")
        capability = req.get("capability") or text
        acceptance.append({
            "id": req["id"],
            "criterion": req.get("acceptance") or f"Given typical input, the system supports: {capability}",
            "actor": actor,
        })
    return {
        "title": project.get("title") or "Untitled project",
        "problem": project.get("problem") or "",
        "objective": project.get("objective") or (state.get("core_idea") or {}).get("primary_objective") or "",
        "users": project.get("target_users") or "Primary users of this project (to be refined).",
        "scope": project.get("scope") or (
            f"Platforms: {', '.join(platforms)}" if platforms else "Scope derived from active requirements."
        ),
        "functional": functional,
        "nonfunctional": nonfunctional,
        "academic": state.get("academic") or {},
        "technology": tech,
        "architecture": arch,
        "database": proposed_db or database,
        "apis": state.get("apis") or [],
        "ai_nlp": state.get("ai_nlp") or {},
        "security": state.get("security") or [],
        "testing": state.get("testing") or {},
        "deployment": state.get("deployment") or {},
        "constraints": constraints,
        "implementation_plan": state.get("implementation_plan") or [],
        "risks": state.get("risks") or [],
        "acceptance": acceptance,
        "core_idea": state.get("core_idea"),
        "conflicts": [item for item in state.get("conflicts") or [] if item.get("status") == "open"],
        "active_decisions": [
            d for d in (state.get("decisions") or [])
            if isinstance(d, dict) and d.get("status") == "ACTIVE"
        ],
    }


def _markdown(spec: dict, state: dict) -> str:
    lines = [f"# {spec['title']}", "", "Validated project specification compiled from ProjectState.", ""]
    functional = _lines(spec["functional"]) or "- None recorded yet."
    nonfunctional = _lines(spec["nonfunctional"]) or "- None recorded yet."
    tech = spec["technology"]
    stack_lines = [
        f"- Backend: {tech.get('backend') or 'not set'}",
        f"- Model: {tech.get('model') or 'not set'}",
        f"- Database: {tech.get('database') or (spec.get('database') or {}).get('engine') or 'not set'}",
        f"- Languages: {', '.join(tech.get('languages') or []) or 'not set'}",
        f"- Frameworks: {', '.join(tech.get('frameworks') or []) or 'not set'}",
    ]
    recs = tech.get("recommendations") or []
    if recs:
        stack_lines.append("- Proposed (not ACTIVE until approved):")
        for item in recs:
            stack_lines.append(f"  - {item.get('name')}: {item.get('purpose')}")

    arch = spec.get("architecture") or {}
    arch_text = ""
    if arch.get("logical"):
        arch_text += "Layers: " + ", ".join((arch["logical"] or {}).get("layers") or []) + "\n"
        comps = (arch["logical"] or {}).get("components") or []
        if comps:
            arch_text += "Components: " + "; ".join(comps) + "\n"
    if (arch.get("implementation") or {}).get("style"):
        arch_text += f"Style: {arch['implementation']['style']}\n"
    if not arch_text.strip():
        arch_text = "Architecture not yet proposed.\n"

    db = spec.get("database") or {}
    db_text = ""
    if db.get("entities"):
        db_text += "Entities: " + ", ".join(e.get("name", "") for e in db["entities"]) + "\n"
    if db.get("relationships"):
        db_text += "Relationships: " + "; ".join(db["relationships"]) + "\n"
    if not db_text.strip():
        db_text = "Database design not yet proposed.\n"

    apis = spec.get("apis") or []
    api_text = "\n".join(
        f"- {a.get('method')} {a.get('path')}: {a.get('purpose')}" for a in apis
    ) or "- None justified yet."

    constraints = spec.get("constraints") or {}
    constraint_lines = [
        f"- Team size: {constraints.get('team_size')}",
        f"- Duration: {constraints.get('duration')}",
        f"- Budget: {constraints.get('budget')}",
        f"- Avoid: {', '.join(constraints.get('avoid') or []) or 'none'}",
        f"- Scope note: {spec.get('scope')}",
    ]

    acceptance = "\n".join(
        f"- [ ] {item['id']}: {item['criterion']}" for item in (spec.get("acceptance") or [])
    ) or "- [ ] Core objective demonstrated end-to-end\n- [ ] Tests pass"

    plan = "\n".join(f"- {item}" for item in (spec.get("implementation_plan") or [])) or (
        "- Lock ACTIVE decisions\n- Implement thin vertical slice\n- Re-run Grill after material changes"
    )
    risks = "\n".join(f"- {item}" for item in (spec.get("risks") or [])) or "- See latest Grill report."

    security = "\n".join(f"- {item}" for item in (spec.get("security") or [])) or (
        "- Keep secrets in environment variables.\n- Validate inputs.\n- Do not trust LLM output as privileged instructions."
    )

    ai_nlp = spec.get("ai_nlp") or {}
    ai_text = "\n".join(f"- {k}: {v}" for k, v in ai_nlp.items()) if ai_nlp else "- Use only if required by the locked objective."

    sections = {
        "objective": spec.get("objective") or "Not yet stated.",
        "problem": spec.get("problem") or "Not yet stated.",
        "users": spec.get("users"),
        "scope": spec.get("scope"),
        "functional": functional,
        "nonfunctional": nonfunctional,
        "constraints": "\n".join(constraint_lines),
        "architecture": arch_text.strip(),
        "technology": "\n".join(stack_lines),
        "database": db_text.strip(),
        "apis": api_text,
        "ai_nlp": ai_text,
        "security": security,
        "testing": (spec.get("testing") or {}).get("notes")
        or "Map each ACTIVE functional requirement to at least one test.",
        "deployment": (spec.get("deployment") or {}).get("notes")
        or "Document local run and a containerized or scripted deploy path.",
        "acceptance": acceptance,
        "implementation_plan": plan,
        "risks": risks,
    }

    for title, key in SECTION_ORDER:
        value = sections.get(key)
        if value is None or str(value).strip() == "":
            continue
        lines.append(f"## {title}")
        lines.append("")
        lines.append(str(value).rstrip())
        lines.append("")

    active = spec.get("active_decisions") or []
    if active:
        lines.append("## ACTIVE DECISIONS")
        lines.append("")
        for item in active[-12:]:
            lines.append(f"- {item.get('summary')} [{item.get('slot') or item.get('kind')}]")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _lines(requirements: list[dict]) -> str:
    return "\n".join(f"- {req['id']}: {req['text']}" for req in requirements)


def _maybe_polish(markdown: str, state: dict) -> str:
    provider = get_provider(TaskKind.COMPILE)
    if not provider.available:
        return markdown
    try:
        polished = provider.generate(specification_prompt(state, markdown), None, task=TaskKind.COMPILE)
    except Exception:
        return markdown
    # Keep polish only if Master Spec anchors remain.
    required = ["## PROJECT OBJECTIVE", "## FUNCTIONAL REQUIREMENTS", "## ACCEPTANCE CRITERIA"]
    if not polished or not all(heading in polished for heading in required):
        return markdown
    return polished


def _restore_requirements(markdown: str, spec: dict) -> str:
    missing = [req for req in spec["functional"] + spec["nonfunctional"] if req["id"] not in markdown]
    if not missing:
        return markdown
    extra = "\n".join(f"- {req['id']}: {req['text']}" for req in missing)
    return markdown + "\n\n## Restored requirements\n\n" + extra + "\n"
