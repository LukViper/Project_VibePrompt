"""Product regression: rejected features must never become positive requirements."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.nlp.contradiction import classify_relationship, find_slot_conflict
from app.nlp.drift import analyze_scope, calculate_drift
from app.nlp.extraction import extract_information
from app.nlp.intent import classify_intent
from app.nlp.preprocessing import preprocess
from app.nlp.similarity import find_related_requirements
from app.services.project_state import (
    active_requirements_respect_avoid,
    apply_analysis_to_state,
    apply_constraint_cues,
    empty_state,
    enforce_rejection_polarity,
    public_state,
)
from app.services.prompt_compiler import compilation_gate, render_prompt, _normalize_from_state
from app.services.specification import _markdown, _structured


def _apply_conversation(conversation: list[str]) -> dict:
    state = empty_state()
    for content in conversation:
        prepared = preprocess(content)
        intent = classify_intent(prepared["text"])
        extraction = extract_information(prepared["text"])
        related = find_related_requirements(prepared["text"], state.get("requirements") or [])
        slot_conflict = find_slot_conflict(state, extraction)
        relationship = classify_relationship(
            prepared["text"],
            related,
            intent["intent"],
            extraction.domains,
            [],
            slot_conflict,
        )
        new_texts = [req.text for req in extraction.requirements]
        if intent["intent"] != "REMOVE_REQUIREMENT":
            drift = calculate_drift(state, new_texts)
        else:
            drift = {"potential_drift": False, "drifted": [], "requirements": [], "backend": "n/a"}
        scope = analyze_scope(state, extraction.domains, len(new_texts))
        analysis = {
            "intent": intent,
            "extraction": extraction,
            "related": related,
            "relationship": relationship,
            "slot_conflict": slot_conflict,
            "drift": drift,
            "scope": scope,
        }
        state = apply_analysis_to_state(state, analysis, reason=intent["intent"])
        state = apply_constraint_cues(state, prepared["text"])
        state = public_state(state)
    return state


def _active_texts(state: dict) -> list[str]:
    return [
        (r.get("text") or "")
        for r in (state.get("requirements") or [])
        if r.get("status") == "active"
    ]


def _prompt_requirement_block(prompt: str) -> str:
    """Text from REQUIREMENTS through (but not including) CONSTRAINTS."""
    lines = prompt.splitlines()
    out: list[str] = []
    capturing = False
    for line in lines:
        upper = line.strip().upper()
        if upper.startswith("REQUIREMENTS") or upper.startswith("FUNCTIONAL REQUIREMENTS"):
            capturing = True
        if capturing and upper.startswith("CONSTRAINTS"):
            break
        if capturing:
            out.append(line)
    return "\n".join(out)


def test_echo_api_rejection_polarity_end_to_end():
    """Core product scenario: REST echo API + explicit Redis/API rejection."""
    state = _apply_conversation(
        [
            "The system must provide a REST echo API that returns the request payload.",
            "Do not use Redis.",
            "Do not use external APIs.",
        ]
    )
    active = _active_texts(state)
    avoid = (state.get("constraints") or {}).get("avoid") or []

    assert any("echo" in t.lower() for t in active)
    assert not any("redis" in t.lower() for t in active)
    assert not any("external api" in t.lower() for t in active)
    assert any("redis" in a.lower() for a in avoid)
    assert any("external" in a.lower() for a in avoid)
    assert (state.get("technology") or {}).get("database") not in {"Redis", "redis"}
    assert active_requirements_respect_avoid(state)

    structured = _structured(state)
    for req in (structured.get("functional") or []) + (structured.get("nonfunctional") or []):
        assert "redis" not in (req.get("text") or "").lower()
    assert any("redis" in a.lower() for a in (structured.get("constraints") or {}).get("avoid") or [])

    gate = compilation_gate(state)
    for item in gate.get("included_requirements") or []:
        assert "redis" not in (item.get("text") or "").lower()

    prompt = render_prompt(
        _normalize_from_state(state, structured),
        _markdown(structured, state),
        state,
    )
    req_block = _prompt_requirement_block(prompt).lower()
    assert "redis" not in req_block
    assert "database: redis" not in prompt.lower()
    # Explicit rejection preserved — not softened to "prefer avoiding"
    avoid_lines = [ln for ln in prompt.splitlines() if "avoid" in ln.lower()]
    assert avoid_lines
    assert any("redis" in ln.lower() for ln in avoid_lines)
    assert not any("prefer avoiding" in ln.lower() for ln in avoid_lines)


def test_use_redis_remains_positive_requirement():
    state = _apply_conversation(["Use Redis for caching."])
    active = _active_texts(state)
    avoid = (state.get("constraints") or {}).get("avoid") or []
    assert any("redis" in t.lower() for t in active)
    assert not any("redis" in a.lower() for a in avoid)
    assert (state.get("technology") or {}).get("database") == "Redis"

    prompt = render_prompt(
        _normalize_from_state(state, _structured(state)),
        _markdown(_structured(state), state),
        state,
    )
    assert "redis" in _prompt_requirement_block(prompt).lower() or "database: redis" in prompt.lower()


def test_mixed_postgres_positive_redis_rejected():
    state = _apply_conversation(["Use PostgreSQL.", "Do not use Redis."])
    active = " ".join(_active_texts(state)).lower()
    avoid = (state.get("constraints") or {}).get("avoid") or []
    tech = state.get("technology") or {}
    assert "postgres" in active or tech.get("database") == "PostgreSQL"
    assert "redis" not in active
    assert any("redis" in a.lower() for a in avoid)
    assert tech.get("database") != "Redis"
    assert "redis" not in " ".join(tech.get("databases") or []).lower()
    assert active_requirements_respect_avoid(state)


def test_enforce_rejection_polarity_removes_conflicting_active_requirement():
    state = empty_state()
    state["constraints"]["avoid"] = ["Redis"]
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": "Use Redis as the database",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "type": "constraint",
            "slot": "database",
            "slot_value": "Redis",
        }
    ]
    state["technology"]["database"] = "Redis"
    state["technology"]["databases"] = ["Redis"]
    state = enforce_rejection_polarity(state)
    assert state["requirements"][0]["status"] == "removed"
    assert state["requirements"][0]["assertion_status"] == "REJECTED"
    assert state["technology"]["database"] is None
    assert state["technology"]["databases"] == []
    assert active_requirements_respect_avoid(state)


def test_generic_rejected_feature_not_redis_specific():
    state = _apply_conversation(
        [
            "The system must provide a message queue helper.",
            "Do not use Kafka.",
        ]
    )
    active = _active_texts(state)
    avoid = (state.get("constraints") or {}).get("avoid") or []
    assert not any("kafka" in t.lower() for t in active)
    assert any("kafka" in a.lower() for a in avoid)
    prompt = render_prompt(
        _normalize_from_state(state, _structured(state)),
        _markdown(_structured(state), state),
        state,
    )
    assert "kafka" not in _prompt_requirement_block(prompt).lower()


def test_merge_validated_llm_cannot_override_explicit_avoid():
    """LLM merge must not inject a positive that restates constraints.avoid."""
    from app.nlp.extraction import ExtractionResult, merge_validated_llm

    base = ExtractionResult(
        requirements=[],
        avoid=["Redis"],
        method="rules",
    )
    merged = merge_validated_llm(
        base,
        {
            "requirements": [
                {"type": "constraint", "text": "Use Redis for caching", "slot": "database", "slot_value": "Redis"}
            ],
            "databases": ["Redis"],
            "avoid": [],
        },
    )
    assert any("redis" in a.lower() for a in merged.avoid)
    assert not any("redis" in (r.text or "").lower() for r in merged.requirements)
    assert not any("redis" in str(d).lower() for d in merged.databases)
    assert "+llm_validated" in merged.method


def test_proposed_conflicting_requirement_cannot_confirm_while_avoided():
    """PROPOSED avoid-conflict must not become CONFIRMED/ACTIVE until rejection is removed."""
    import uuid

    from app.schemas.assertions import AssertionStatus
    from app.services.assertion_promotion import promote_assertion

    class _FakeProject:
        def __init__(self, state):
            self.id = uuid.uuid4()
            self.state = state
            self.updated_at = None

    class _FakeSession:
        def add(self, _row):
            return None

    state = empty_state()
    state["constraints"]["avoid"] = ["Redis"]
    # Bypass _new_requirement polarity so we can seed a stale PROPOSED conflict.
    state["requirements"] = [
        {
            "id": "REQ-001",
            "type": "constraint",
            "text": "Use Redis as the database",
            "status": "active",
            "assertion_status": AssertionStatus.PROPOSED.value,
            "slot": "database",
            "slot_value": "Redis",
            "provenance": {},
        }
    ]
    project = _FakeProject(state)
    try:
        promote_assertion(
            _FakeSession(),
            project,
            "REQ-001",
            target_status=AssertionStatus.CONFIRMED.value,
            reason="test confirm",
        )
        raise AssertionError("expected confirm to be blocked")
    except ValueError as exc:
        assert "constraints.avoid" in str(exc)

    # After the user removes the rejection, confirmation is allowed.
    state["constraints"]["avoid"] = []
    project.state = state
    result = promote_assertion(
        _FakeSession(),
        project,
        "REQ-001",
        target_status=AssertionStatus.CONFIRMED.value,
        reason="user removed rejection then confirmed",
    )
    assert result["to_status"] == AssertionStatus.CONFIRMED.value
    confirmed = next(r for r in result["state"]["requirements"] if r["id"] == "REQ-001")
    assert confirmed["status"] == "active"
    assert confirmed["assertion_status"] == AssertionStatus.CONFIRMED.value


def test_new_requirement_respects_avoid_polarity():
    """Direct requirement creation cannot leave an avoid-matching item ACTIVE."""
    from app.services.project_state import _new_requirement, active_requirements_respect_avoid

    state = empty_state()
    state["constraints"]["avoid"] = ["Redis"]
    created = _new_requirement(state, "Use Redis for caching", "constraint", slot="database", slot_value="Redis")
    assert created["status"] == "removed"
    assert created["assertion_status"] == "REJECTED"
    assert active_requirements_respect_avoid(state)


def test_grill_proposed_requirement_respects_avoid():
    from app.services.grill_session import _create_proposed_requirement
    from app.services.project_state import active_requirements_respect_avoid

    state = empty_state()
    state["constraints"]["avoid"] = ["Redis"]
    item = _create_proposed_requirement(
        state,
        text="Use Redis for session caching",
        acceptance=None,
        req_type="constraint",
        reason="grill test",
    )
    assert item["status"] == "removed"
    assert item["assertion_status"] == "REJECTED"
    assert active_requirements_respect_avoid(state)
