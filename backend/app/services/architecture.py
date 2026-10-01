"""Architecture, technology, database, and API recommendation engine.

Writes justified decisions into ProjectState with AI_RECOMMENDATION provenance.
Does not invent paid APIs or unverifiable external services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.llm.base import TaskKind
from app.llm.router import get_provider
from app.schemas.provenance import ProvenanceSource, make_provenance
from app.schemas.state import ConversationStage, migrate_state
from app.services.versioning import StateVersioning

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Project


def propose_architecture(session: "Session", project: "Project") -> dict:
    from app.schemas.decisions import DecisionStatus, propose_decision
    from app.services.project_state import public_state, set_stage

    state = migrate_state(project.state or {})
    logical = _logical_architecture(state)
    implementation = _implementation_architecture(state)
    tech = _technology_recommendations(state)
    database = _database_design(state)
    apis = _api_contracts(state)

    state["architecture"] = {
        "logical": logical,
        "implementation": implementation,
        "status": DecisionStatus.PROPOSED.value,
        "user_approved": False,
        "provenance": make_provenance(
            ProvenanceSource.AI_RECOMMENDATION,
            reason="architecture engine",
            confidence=0.7,
            user_approved=False,
        ),
    }
    existing = state.get("technology") or {}
    # Keep recommendations separate; do not promote them to ACTIVE tech slots.
    state["technology"] = {
        **existing,
        "recommendations": tech,
        "provenance": make_provenance(
            ProvenanceSource.AI_RECOMMENDATION,
            reason="technology engine — awaiting user decision",
            confidence=0.65,
            user_approved=False,
        ),
    }
    state["database"] = {
        **(state.get("database") or {}),
        "proposed": database,
        "provenance": make_provenance(
            ProvenanceSource.AI_RECOMMENDATION,
            reason="database engine — awaiting user decision",
            confidence=0.65,
            user_approved=False,
        ),
    }
    state["apis"] = [{"status": "PROPOSED", **api} for api in apis]

    for item in tech:
        state.setdefault("decisions", []).append(
            propose_decision(
                kind="tech_recommendation",
                summary=f"Recommend {item['name']} for {item['purpose']}",
                value=item["name"],
                slot=_slot_for_tech(item),
                details=item,
                source=ProvenanceSource.AI_RECOMMENDATION,
                reason=item.get("reason") or "tech recommendation",
                alternatives=[{
                    "name": item.get("alternative") or "n/a",
                    "pros": [],
                    "cons": [item.get("trade_off") or ""],
                }],
                status=DecisionStatus.PROPOSED,
                confidence=0.65,
            )
        )

    state.setdefault("decisions", []).append(
        propose_decision(
            kind="architecture_recommendation",
            summary="Architecture proposal ready for review",
            value=implementation.get("style"),
            slot="architecture",
            details={"logical": logical, "implementation": implementation},
            source=ProvenanceSource.AI_RECOMMENDATION,
            reason="architecture engine",
            status=DecisionStatus.PROPOSED,
            confidence=0.7,
        )
    )

    state = set_stage(state, ConversationStage.ARCHITECTURE)
    state = StateVersioning.bump(state, "architecture")
    project.state = public_state(state)
    StateVersioning.snapshot(session, project, "architecture")
    narrative = format_architecture_for_chat(state)
    provider = get_provider(TaskKind.ARCHITECTURE)
    if provider.available:
        try:
            polished = provider.generate(
                "Summarize this architecture proposal for a student in plain, conversational prose. "
                "Do not invent new components. Do not mention internal labels like AI_RECOMMENDATION, "
                "PROPOSED, ACTIVE, or provenance. Emphasize that the student still chooses.\n\n"
                + narrative,
                {"state": public_state(state)},
                task=TaskKind.ARCHITECTURE,
            )
            if polished:
                narrative = polished.strip()
        except Exception:
            pass
    return {
        "state": public_state(state),
        "narrative": narrative,
        "architecture": state["architecture"],
        "proposed_decisions": [
            d for d in state.get("decisions") or [] if d.get("status") == DecisionStatus.PROPOSED.value
        ][-len(tech) - 1 :],
    }


def _slot_for_tech(item: dict) -> str:
    purpose = (item.get("purpose") or "").lower()
    name = (item.get("name") or "").lower()
    if "database" in purpose or "postgres" in name or "sqlite" in name:
        return "database"
    if "backend" in purpose or "fastapi" in name or "django" in name:
        return "backend"
    if "frontend" in purpose or "flutter" in name or "react" in name:
        return "frontend_framework"
    if "model" in purpose or "bert" in name or "transformer" in name:
        return "model"
    return "technology"


def format_architecture_for_chat(state: dict) -> str:
    """Conversational architecture explanation. Decision status stays in Project State."""
    arch = state.get("architecture") or {}
    tech = (state.get("technology") or {}).get("recommendations") or []
    db = state.get("database") or {}
    db_view = db.get("proposed") if isinstance(db.get("proposed"), dict) else db
    apis = state.get("apis") or []
    objective = (
        (state.get("core_idea") or {}).get("primary_objective")
        or (state.get("project") or {}).get("objective")
        or "what we've discussed"
    )

    lines = [
        f"Based on {objective}, here's an architecture I'd use — structured around a few clear layers:",
        "",
    ]
    logical = arch.get("logical") or {}
    layers = logical.get("layers") or []
    if layers:
        for index, layer in enumerate(layers, start=1):
            lines.append(f"{index}. {layer}")
        lines.append("")
    if logical.get("components"):
        lines.append("Key pieces: " + "; ".join(logical["components"]) + ".")
        lines.append("")
    impl = arch.get("implementation") or {}
    if impl.get("style"):
        lines.append(f"Implementation style: {impl['style']}.")
    if impl.get("notes"):
        lines.append(str(impl["notes"]))
    if tech:
        lines.append("")
        lines.append("For technology choices, this stack fits well:")
        for item in tech:
            name = item.get("name") or "component"
            reason = item.get("reason") or item.get("purpose") or ""
            alt = item.get("alternative")
            trade = item.get("trade_off")
            line = f"- {name}: {reason}".rstrip(".")
            if alt:
                line += f" (alternative: {alt}"
                if trade:
                    line += f"; trade-off: {trade}"
                line += ")"
            elif trade:
                line += f" Trade-off: {trade}."
            else:
                line += "."
            lines.append(line)
    if db_view.get("entities"):
        lines.append("")
        lines.append("Data you'd likely store: " + ", ".join(e["name"] for e in db_view["entities"]) + ".")
        if db_view.get("relationships"):
            lines.append("Relationships: " + "; ".join(db_view["relationships"]) + ".")
    if apis:
        lines.append("")
        lines.append("Suggested API surfaces:")
        for api in apis:
            lines.append(f"- {api['method']} {api['path']}: {api['purpose']}")
    else:
        lines.append("")
        lines.append("I wouldn't invent external APIs until a clear need shows up.")
    lines.append("")
    lines.append(
        "These are recommendations for you to accept or adjust — nothing is locked until you choose. "
        "Which parts do you want to keep, change, or research further?"
    )
    return "\n".join(lines)


def _logical_architecture(state: dict) -> dict:
    layers = ["Presentation", "Application / API", "Domain / NLP", "Data"]
    components = [
        "Chat / client UI",
        "Backend API service",
        "Analysis / model inference module",
        "Persistent store",
    ]
    domains = state.get("domains") or []
    if "browser_extension" in domains or any(
        "extension" in (req.get("text") or "").lower()
        for req in state.get("requirements") or []
        if req.get("status") == "active"
    ):
        components.append("Browser extension client (optional V1.1)")
    return {"layers": layers, "components": components}


def _implementation_architecture(state: dict) -> dict:
    team = (state.get("constraints") or {}).get("team_size")
    style = "Modular monolith"
    notes = "Prefer one deployable backend with clear module boundaries for a student timeline."
    if team and team > 3:
        style = "Modular monolith with optional service split later"
        notes = "Keep a monolith first; split only if team ownership requires it."
    return {"style": style, "notes": notes}


def _technology_recommendations(state: dict) -> list[dict]:
    existing = state.get("technology") or {}
    subject = ((state.get("academic") or {}).get("subject") or "").upper()
    recs = []
    if not existing.get("backend") and not (existing.get("languages") or []):
        recs.append({
            "name": "Python + FastAPI",
            "purpose": "Backend API and orchestration",
            "reason": "Fast to prototype; strong NLP ecosystem overlap.",
            "alternative": "Django",
            "trade_off": "FastAPI is lighter; Django gives admin/ORM batteries.",
        })
    if subject == "NLP" or "nlp" in (state.get("domains") or []):
        if not existing.get("model"):
            recs.append({
                "name": existing.get("model") or "sentence-transformers or a small encoder (e.g. MiniLM/BERT-family)",
                "purpose": "Text classification / similarity",
                "reason": "Matches NLP course concepts without requiring a huge GPU budget.",
                "alternative": "Classical TF-IDF + logistic regression baseline",
                "trade_off": "Transformers improve quality; classical models are easier to evaluate and explain.",
            })
    if not existing.get("database") and not (existing.get("databases") or []):
        recs.append({
            "name": "PostgreSQL",
            "purpose": "Primary relational store",
            "reason": "Reliable for structured project data; SQLite acceptable for local demos.",
            "alternative": "SQLite",
            "trade_off": "Postgres is closer to production; SQLite is zero-ops for solo demos.",
        })
    return recs


def _database_design(state: dict) -> dict:
    entities = [
        {"name": "User", "fields": ["id", "role"]},
        {"name": "Document", "fields": ["id", "source", "raw_text", "created_at"]},
        {"name": "Prediction", "fields": ["id", "document_id", "label", "confidence"]},
        {"name": "Explanation", "fields": ["id", "prediction_id", "highlights"]},
    ]
    objective = ((state.get("core_idea") or {}).get("primary_objective") or "").lower()
    if "phish" in objective or "email" in objective:
        entities[1] = {"name": "Email", "fields": ["id", "subject", "body", "headers", "created_at"]}
    relationships = [
        "Document/Email 1—* Prediction",
        "Prediction 1—0..1 Explanation",
    ]
    return {"entities": entities, "relationships": relationships, "notes": "Keep schema minimal for V1."}


def _api_contracts(state: dict) -> list[dict]:
    """Only propose APIs justified by requirements — never invent third-party SaaS."""
    apis = [
        {
            "method": "POST",
            "path": "/analyze",
            "purpose": "Submit text/email for classification",
            "request": {"text": "string"},
            "response": {"label": "string", "confidence": "number"},
            "justification": "Core product capability",
        },
        {
            "method": "GET",
            "path": "/health",
            "purpose": "Liveness check",
            "request": {},
            "response": {"status": "ok"},
            "justification": "Operational baseline",
        },
    ]
    active = [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
    if any("extension" in (r.get("text") or "").lower() for r in active):
        apis.append({
            "method": "POST",
            "path": "/analyze/batch",
            "purpose": "Score multiple messages for an extension client",
            "request": {"items": [{"id": "string", "text": "string"}]},
            "response": {"results": [{"id": "string", "label": "string", "confidence": "number"}]},
            "justification": "Browser extension requirement present",
        })
    return apis
