"""Research-on-demand engine.

Triggered when the user (or Conversation Manager heuristic) needs external evidence.
Findings are validated lightly and stored on ProjectState with RESEARCH provenance.
Never fabricates sources — empty source is allowed; invented URLs are stripped.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.llm.base import TaskKind
from app.llm.prompts import research_prompt
from app.llm.research import ResearchProvider
from app.llm.router import get_provider
from app.models import Project
from app.schemas.provenance import ProvenanceSource, make_provenance
from app.schemas.state import ConversationStage, migrate_state
from app.services.project_state import public_state, set_stage
from app.services.versioning import StateVersioning

_URL_RE = re.compile(r"https?://\S+", re.I)
# Common fabrication tells — reject if source looks like a fake academic citation with year
_FAKE_PAPER_RE = re.compile(r"\b(arxiv|doi|ieee|acm)\b.*\b(20\d{2})\b", re.I)


def select_research_level(query: str, state: dict | None = None) -> str:
    """Adaptive research levels (Master Spec §12)."""
    text = (query or "").lower()
    state = state or {}
    deep = any(
        key in text
        for key in (
            "existing product",
            "competitor",
            "literature",
            "dataset",
            "novelty",
            "differentiation",
            "survey papers",
            "state of the art",
            "ecosystem",
        )
    )
    if deep:
        return "LEVEL_3"
    evidence = any(
        key in text
        for key in ("compare", "versus", "vs", "pros and cons", "trade-off", "tradeoff", "which should i")
    )
    if evidence:
        return "LEVEL_2"
    technical = any(
        key in text
        for key in (
            "android",
            "ios",
            "flutter",
            "react native",
            "architecture",
            "database",
            "auth",
            "approach",
            "existing systems",
            "api",
        )
    )
    if technical:
        return "LEVEL_1"
    # Trivial UI polish / already-stable prefs
    if re.search(r"\b(dark mode|rename|title|button color|font)\b", text):
        return "LEVEL_0"
    if (state.get("core_idea") or {}).get("locked") and len(text) < 40:
        return "LEVEL_0"
    return "LEVEL_1"


def run_research(session: Session, project: Project, query: str) -> dict:
    """Execute research and merge findings into ProjectState."""
    from app.services.analytics import track

    track("research_started")
    state = migrate_state(project.state or {})
    level = select_research_level(query, state)
    state["research_level_last"] = level
    if level == "LEVEL_0":
        note = {
            "finding": (
                "LEVEL_0: no external research required for this request. "
                "I will not invent sources for a stable/simple preference."
            ),
            "source": "",
            "source_type": "system",
            "timestamp": _now(),
            "relevance": "low",
            "confidence": 1.0,
            "project_impact": "None — proceed from ProjectState.",
            "verification_status": "not_applicable",
            "provenance": make_provenance(
                ProvenanceSource.SYSTEM_DEFAULT,
                reason="research level 0",
                confidence=1.0,
            ),
            "query": query,
            "research_level": level,
        }
        state.setdefault("research", []).append(note)
        state = set_stage(state, ConversationStage.RESEARCH)
        state = StateVersioning.bump(state, "research_level_0")
        project.state = public_state(state)
        project.updated_at = utcnow()
        StateVersioning.snapshot(session, project, "research_level_0")
        return {
            "query": query,
            "research_level": level,
            "findings": [note],
            "narrative": (
                "This question doesn't need external research yet — we can decide from what "
                "you've already told me about the project. If you want outside evidence, ask "
                "something more specific (for example existing tools, datasets, or papers)."
            ),
            "state": public_state(state),
        }

    provider = get_provider(TaskKind.RESEARCH)
    findings: list[dict] = []
    if isinstance(provider, ResearchProvider) and provider.available:
        findings = provider.research(query, project_context={"state": public_state(state), "level": level})
    if not findings and provider.available:
        # Fallback: structured prompt via generate_structured
        try:
            data = provider.generate_structured(
                research_prompt(query, state) + f"\nResearch level: {level}. "
                "If evidence is inconclusive, say so explicitly and do not pick a winner.",
                {
                    "type": "object",
                    "properties": {"findings": {"type": "array"}},
                    "required": ["findings"],
                },
                {"state": public_state(state)},
                task=TaskKind.RESEARCH,
            )
            raw = data.get("findings") if isinstance(data, dict) else []
            if isinstance(raw, list):
                findings = [item for item in raw if isinstance(item, dict)]
        except Exception:
            findings = []

    cleaned = [_normalize_finding(item, query) for item in findings]
    cleaned = [item for item in cleaned if item]
    for item in cleaned:
        item["research_level"] = level
    if not cleaned:
        cleaned = [{
            "finding": (
                "Evidence inconclusive / no verified external sources were retrieved for this query. "
                "I will not invent papers or URLs. Rephrase the question or supply a known source."
            ),
            "source": "",
            "source_type": "system",
            "timestamp": _now(),
            "relevance": "high",
            "confidence": 0.0,
            "project_impact": "Research gap remains open; do not treat absence as evidence.",
            "verification_status": "unverified",
            "provenance": make_provenance(
                ProvenanceSource.SYSTEM_DEFAULT,
                reason="no research results",
                confidence=0.0,
            ),
            "query": query,
            "research_level": level,
        }]

    state.setdefault("research", [])
    state["research"].extend(cleaned)
    inconclusive = all(
        (item.get("confidence") in (None, 0, 0.0) or item.get("source_type") == "system")
        for item in cleaned
    )
    for item in cleaned:
        if item.get("source_type") == "system":
            continue
        impact = item.get("project_impact") or item.get("finding")
        from app.schemas.decisions import DecisionStatus, propose_decision

        state["decisions"].append(
            propose_decision(
                kind="research_finding",
                summary=f"Research: {str(item.get('finding') or '')[:160]}",
                value=item.get("finding"),
                details={"query": query, "impact": impact, "level": level},
                source=ProvenanceSource.RESEARCH,
                reason=query,
                evidence=[{"source": item.get("source"), "finding": item.get("finding")}],
                status=DecisionStatus.PROPOSED,
                confidence=item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else None,
            )
        )
    state = set_stage(state, ConversationStage.RESEARCH)
    state = StateVersioning.bump(state, "research")
    project.state = public_state(state)
    project.updated_at = utcnow()
    StateVersioning.snapshot(session, project, "research")
    narrative = format_research_for_chat(query, cleaned, level=level, inconclusive=inconclusive)
    return {
        "query": query,
        "research_level": level,
        "findings": cleaned,
        "narrative": narrative,
        "state": public_state(state),
    }


def format_research_for_chat(
    query: str,
    findings: list[dict],
    *,
    level: str = "LEVEL_1",
    inconclusive: bool = False,
) -> str:
    """User-facing narrative. Provenance/level stay on ProjectState, not in chat."""
    usable = [
        item
        for item in findings
        if item.get("source_type") != "system"
        and item.get("finding")
        and "evidence inconclusive" not in str(item.get("finding") or "").lower()
    ]
    if inconclusive or not usable:
        focus_hint = ""
        lowered = (query or "").lower()
        if "churn" in lowered:
            focus_hint = " existing churn-prediction systems or public churn datasets"
        elif "phish" in lowered:
            focus_hint = " phishing detectors or public phishing email/URL datasets"
        elif "log" in lowered:
            focus_hint = " security log analysis tools or public log datasets"
        else:
            focus_hint = " existing systems or public datasets for this problem"
        return (
            "I checked for existing systems and datasets, but I couldn't verify enough "
            "external evidence to make a reliable claim yet. I don't want to invent sources. "
            f"If you want, we can narrow the search to{focus_hint}."
        )

    lines = [
        "Here's what I found that looks relevant (I'll keep sources on the project record "
        "rather than inventing citations):",
        "",
    ]
    for index, item in enumerate(usable[:5], start=1):
        finding = str(item.get("finding") or "").strip()
        source = str(item.get("source") or "").strip()
        impact = str(item.get("project_impact") or "").strip()
        lines.append(f"{index}. {finding}")
        if source:
            lines.append(f"   Source noted: {source}")
        if impact:
            lines.append(f"   Why it matters for your project: {impact}")
        lines.append("")
    lines.append(
        "These are research leads, not locked requirements. "
        "Tell me which ones you want to apply, and I'll turn those into explicit requirements."
    )
    return "\n".join(lines)


def _normalize_finding(item: dict, query: str) -> dict | None:
    finding = str(item.get("finding") or "").strip()
    if not finding:
        return None
    source = str(item.get("source") or "").strip()
    # Drop clearly fabricated URL+paper combos when confidence is missing and source looks invented.
    if source and _URL_RE.search(source) and _FAKE_PAPER_RE.search(source) and item.get("verification_status") != "verified":
        # Keep finding text but clear unverifiable URL claims
        source = ""
    return {
        "finding": finding,
        "source": source,
        "source_type": str(item.get("source_type") or ("unknown" if not source else "web")),
        "timestamp": item.get("timestamp") or _now(),
        "relevance": item.get("relevance"),
        "confidence": item.get("confidence"),
        "project_impact": item.get("project_impact"),
        "verification_status": str(item.get("verification_status") or "unverified"),
        "provenance": make_provenance(
            ProvenanceSource.RESEARCH,
            reason=query,
            confidence=item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else None,
        ),
        "query": query,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
