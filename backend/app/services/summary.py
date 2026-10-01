"""Project resume / summary (Master Spec §22)."""

from __future__ import annotations

from app.schemas.decisions import DecisionStatus
from app.schemas.state import migrate_state
from app.services.decisions import active_decisions, proposed_decisions


def build_project_summary(state: dict | None) -> dict:
    state = migrate_state(state or {})
    project = state.get("project") or {}
    core = state.get("core_idea") or {}
    constraints = state.get("constraints") or {}
    tech = state.get("technology") or {}
    arch = state.get("architecture") or {}
    grill = state.get("grill_report") or (state.get("grill_findings") or {}).get("structured") or {}
    active = active_decisions(state)
    proposed = proposed_decisions(state)
    conflicts = [c for c in (state.get("conflicts") or []) if c.get("status") == "open"]
    platforms = project.get("platform") or []
    if isinstance(platforms, str):
        platforms = [platforms]

    major_decisions = [
        {
            "summary": item.get("summary"),
            "slot": item.get("slot"),
            "value": item.get("value"),
            "status": item.get("status"),
        }
        for item in active[-10:]
    ]

    last_changes = []
    for item in reversed(state.get("decisions") or []):
        if not isinstance(item, dict):
            continue
        last_changes.append({
            "summary": item.get("summary"),
            "status": item.get("status"),
            "timestamp": item.get("timestamp"),
        })
        if len(last_changes) >= 5:
            break

    return {
        "project": project.get("title") or "Untitled project",
        "objective": project.get("objective") or core.get("primary_objective") or "",
        "current_scope": project.get("scope")
        or (", ".join(platforms) if platforms else "Scope still forming"),
        "major_active_decisions": major_decisions,
        "architecture": {
            "status": arch.get("status"),
            "style": (arch.get("implementation") or {}).get("style"),
            "layers": (arch.get("logical") or {}).get("layers") or [],
        },
        "important_constraints": {
            "team_size": constraints.get("team_size"),
            "duration": constraints.get("duration"),
            "budget": constraints.get("budget"),
            "avoid": constraints.get("avoid") or [],
            "platforms": platforms,
            "technology": {
                "backend": tech.get("backend"),
                "database": tech.get("database"),
                "model": tech.get("model"),
            },
        },
        "open_questions": state.get("open_questions") or [],
        "known_risks": state.get("risks") or grill.get("high_risk") or [],
        "open_conflicts": conflicts,
        "proposed_decisions_awaiting_user": [
            {"id": d.get("id"), "summary": d.get("summary"), "slot": d.get("slot")}
            for d in proposed[:10]
        ],
        "last_major_changes": last_changes,
        "conversation_stage": state.get("conversation_stage"),
        "grill_blocking": grill.get("blocking") or [],
    }


def format_summary_for_chat(summary: dict) -> str:
    lines = [
        f"Project: {summary.get('project')}",
        f"Objective: {summary.get('objective') or 'not set'}",
        f"Current scope: {summary.get('current_scope')}",
        f"Stage: {summary.get('conversation_stage')}",
        "",
        "Major ACTIVE decisions:",
    ]
    decisions = summary.get("major_active_decisions") or []
    if not decisions:
        lines.append("- None yet.")
    for item in decisions:
        lines.append(f"- {item.get('summary')}")
    lines.append("")
    lines.append("Important constraints:")
    c = summary.get("important_constraints") or {}
    lines.append(f"- Team {c.get('team_size')} · {c.get('duration')}")
    lines.append(f"- Platforms: {', '.join(c.get('platforms') or []) or 'not set'}")
    tech = c.get("technology") or {}
    lines.append(
        f"- Tech: backend={tech.get('backend') or '-'} db={tech.get('database') or '-'} model={tech.get('model') or '-'}"
    )
    lines.append("")
    lines.append("Open questions:")
    questions = summary.get("open_questions") or []
    lines.extend([f"- {q}" for q in questions] or ["- None."])
    lines.append("")
    lines.append("Known risks:")
    risks = summary.get("known_risks") or []
    lines.extend([f"- {r}" for r in risks[:8]] or ["- None recorded."])
    proposed = summary.get("proposed_decisions_awaiting_user") or []
    if proposed:
        lines.append("")
        lines.append("Awaiting your decision:")
        for item in proposed:
            lines.append(f"- {item.get('summary')}")
    lines.append("")
    lines.append("Last major changes:")
    for item in summary.get("last_major_changes") or []:
        lines.append(f"- [{item.get('status')}] {item.get('summary')}")
    return "\n".join(lines)
