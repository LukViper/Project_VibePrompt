"""Phase 1 — conversational orchestration journeys (Tests 1–10)."""

from __future__ import annotations


FORM_MARKERS = (
    "i captured",
    "what is the team size",
    "how long do you have",
    "what subject or course",
    "i still need:",
)


def _reply(client, project_id: str, content: str) -> dict:
    response = client.post(f"/projects/{project_id}/messages", json={"content": content})
    assert response.status_code == 200, response.text
    return response.json()


def _text(body: dict) -> str:
    return ((body.get("assistant_message") or {}).get("content") or "").lower()


def _assert_not_form(text: str) -> None:
    for marker in FORM_MARKERS:
        assert marker not in text, f"Form-filling marker found: {marker!r} in {text!r}"


def test_1_nlp_project_explores_not_questionnaire(client):
    created = client.post("/projects", json={"title": "Blank"})
    project_id = created.json()["id"]
    body = _reply(client, project_id, "I need an NLP project.")
    text = _text(body)
    _assert_not_form(text)
    assert body.get("action") in {"EXPLORE", "RESPOND", "ASK_CLARIFICATION"}
    assert any(
        token in text
        for token in ("nlp", "classification", "extraction", "generation", "interest", "explore")
    )


def test_2_cybersecurity_continues_exploration(client):
    created = client.post("/projects", json={"title": "Blank"})
    project_id = created.json()["id"]
    body = _reply(client, project_id, "I want something in cybersecurity.")
    text = _text(body)
    _assert_not_form(text)
    assert "team size" not in text
    assert "how long" not in text
    assert any(
        token in text
        for token in ("cyber", "security", "threat", "malware", "forensic", "phish", "network", "interest", "explore")
    )


def test_3_linux_log_analyzer_updates_and_explores(client):
    created = client.post("/projects", json={"title": "Blank"})
    project_id = created.json()["id"]
    body = _reply(client, project_id, "I want to build a Linux log analyzer.")
    text = _text(body)
    _assert_not_form(text)
    state = body["state"]
    blob = " ".join(
        filter(
            None,
            [
                (state.get("project") or {}).get("problem"),
                (state.get("project") or {}).get("objective"),
                ((state.get("core_idea") or {}) or {}).get("primary_objective"),
                ((state.get("exploration") or {}) or {}).get("current_direction"),
                text,
            ],
        )
    ).lower()
    assert "log" in blob
    assert any(
        token in text
        for token in ("suspicious", "failure", "summar", "anomal", "correlat", "focus", "log")
    )


def test_4_constraints_update_silently(client):
    created = client.post("/projects", json={"description": "I need an NLP project."})
    project_id = created.json()["id"]
    body = _reply(client, project_id, "I'm working alone and have six weeks.")
    text = _text(body)
    _assert_not_form(text)
    constraints = body["state"]["constraints"]
    assert constraints.get("team_size") == 1
    assert constraints.get("duration")
    assert "6" in str(constraints.get("duration")) or "six" in str(constraints.get("duration")).lower()
    assert "missing" not in text
    assert "i still need" not in text


def test_5_direction_change_avoids_contamination(client):
    created = client.post("/projects", json={"description": "I want a fake citation detector."})
    project_id = created.json()["id"]
    first = _reply(client, project_id, "I want to build a fake citation detector for academic papers.")
    old_objective = (
        (first["state"].get("project") or {}).get("objective")
        or ((first["state"].get("core_idea") or {}) or {}).get("primary_objective")
        or ""
    )
    body = _reply(client, project_id, "Actually, forget this. I want a phishing detection system.")
    text = _text(body)
    _assert_not_form(text)
    assert body.get("action") == "RESET_OR_CHANGE_DIRECTION" or body["assistant_message"]["analysis"].get(
        "direction_change"
    )
    state = body["state"]
    history = (state.get("exploration") or {}).get("history") or []
    assert history, "previous exploration should be archived"
    active_reqs = [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
    # Old citation requirements should not remain active.
    for req in active_reqs:
        assert "citation" not in (req.get("text") or "").lower()
    blob = " ".join(
        filter(
            None,
            [
                (state.get("project") or {}).get("objective"),
                (state.get("project") or {}).get("problem"),
                ((state.get("exploration") or {}) or {}).get("current_direction"),
                text,
            ],
        )
    ).lower()
    assert "phish" in blob
    if old_objective:
        assert "citation" not in ((state.get("project") or {}).get("objective") or "").lower()


def test_6_too_big_enters_grill_refinement(client):
    created = client.post(
        "/projects",
        json={"description": "I want real-time threat detection with custom machine learning."},
    )
    project_id = created.json()["id"]
    _reply(client, project_id, "I'm working alone and have six weeks.")
    body = _reply(client, project_id, "This idea is too big.")
    text = _text(body)
    _assert_not_form(text)
    assert body.get("action") == "GRILL" or body.get("stage") == "GRILL"
    assert any(
        token in text
        for token in ("scope", "narrow", "cut", "defer", "essential", "version", "large", "too", "mvp", "priorit")
    )


def test_7_existing_systems_invokes_research(client):
    created = client.post("/projects", json={"description": "I want a phishing detection system."})
    project_id = created.json()["id"]
    body = _reply(client, project_id, "Are there existing systems for this?")
    text = _text(body)
    _assert_not_form(text)
    assert body.get("action") == "RESEARCH" or body.get("stage") == "RESEARCH"
    assert any(token in text for token in ("research", "exist", "system", "finding", "tool", "paper", "dataset"))


def test_8_how_should_i_build_invokes_architecture(client):
    created = client.post("/projects", json={"description": "I want a Linux log analyzer for suspicious activity."})
    project_id = created.json()["id"]
    body = _reply(client, project_id, "How should I build it?")
    text = _text(body)
    _assert_not_form(text)
    assert body.get("action") == "PROPOSE_ARCHITECTURE" or body.get("stage") == "ARCHITECTURE"
    assert any(
        token in text
        for token in ("architecture", "component", "layer", "stack", "backend", "api", "module", "service")
    )


def test_9_natural_language_postgres_decision(client):
    created = client.post("/projects", json={"description": "I want a phishing detector with a web API."})
    project_id = created.json()["id"]
    body = _reply(client, project_id, "Yes, let's use PostgreSQL.")
    text = _text(body)
    _assert_not_form(text)
    assert "7ba695db" not in text  # no internal UUID required
    tech = body["state"].get("technology") or {}
    db = (tech.get("database") or "").lower()
    databases = [str(x).lower() for x in (tech.get("databases") or [])]
    decisions = body["state"].get("decisions") or []
    active_pg = any(
        d.get("status") == "ACTIVE"
        and "postgres" in str(d.get("value") or d.get("summary") or "").lower()
        for d in decisions
        if isinstance(d, dict)
    )
    assert "postgres" in db or any("postgres" in x for x in databases) or active_pg
    assert "postgres" in text or "database" in text or "active" in text or "got it" in text


def test_10_compile_prompt_conversational_gate(client):
    created = client.post("/projects", json={"title": "Sparse"})
    project_id = created.json()["id"]
    body = _reply(client, project_id, "Generate the final Cursor prompt.")
    text = _text(body)
    assert "prompt compilation blocked" not in text
    # Either compiled (unlikely on empty) or asked a natural clarification.
    if "you are a senior software engineer" in text:
        assert True
    else:
        assert any(
            token in text
            for token in ("before i compile", "objective", "requirement", "detect", "decide", "what should")
        )
        _assert_not_form(text)
