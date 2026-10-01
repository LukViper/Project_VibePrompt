"""Phase 2A — conversational quality journeys (context-aware replies)."""

from __future__ import annotations

from app.services.idea_generation import _templates
from app.services.architecture import format_architecture_for_chat
from app.schemas.state import empty_state_dict


INTERNAL_MARKERS = (
    "let's explore that.",
    "what problem or user outcome are you most interested in tackling first?",
    "i captured",
    "research level:",
    "evidence inconclusive.",
    "ai_recommendation",
    "research for:",
)


def _reply(client, project_id: str, content: str) -> dict:
    response = client.post(f"/projects/{project_id}/messages", json={"content": content})
    assert response.status_code == 200, response.text
    return response.json()


def _text(body: dict) -> str:
    return ((body.get("assistant_message") or {}).get("content") or "").lower()


def _assert_human(text: str) -> None:
    for marker in INTERNAL_MARKERS:
        assert marker not in text, f"Internal/diagnostic marker in chat: {marker!r}"


def test_a_nlp_specific_exploration(client):
    project_id = client.post("/projects", json={"title": "Blank"}).json()["id"]
    body = _reply(client, project_id, "I need an NLP project.")
    text = _text(body)
    _assert_human(text)
    assert "nlp" in text
    assert any(token in text for token in ("classification", "extraction", "generation", "misinformation"))


def test_b_cybersecurity_specific_exploration(client):
    project_id = client.post("/projects", json={"title": "Blank"}).json()["id"]
    body = _reply(client, project_id, "I want something related to cybersecurity.")
    text = _text(body)
    _assert_human(text)
    assert any(token in text for token in ("threat", "phish", "malware", "forensic", "log", "cyber"))


def test_c_linux_log_analyzer_followup(client):
    project_id = client.post("/projects", json={"title": "Blank"}).json()["id"]
    body = _reply(client, project_id, "I want to build a Linux log analyzer.")
    text = _text(body)
    _assert_human(text)
    assert "log" in text
    assert any(token in text for token in ("suspicious", "failure", "anomal", "summar", "attack"))


def test_d_churn_specific_followup(client):
    project_id = client.post("/projects", json={"title": "Blank"}).json()["id"]
    body = _reply(client, project_id, "I want a churn prediction project.")
    text = _text(body)
    _assert_human(text)
    assert "churn" in text
    assert any(token in text for token in ("leave", "explain", "interven", "predict", "why"))
    assert "user outcome" not in text


def test_d2_data_science_not_generic_explore(client):
    project_id = client.post("/projects", json={"title": "Blank"}).json()["id"]
    body = _reply(client, project_id, "project on foundation of data science")
    text = _text(body)
    _assert_human(text)
    assert "data science" in text or "prediction" in text or "classification" in text
    assert "let's explore that" not in text


def test_d3_does_not_repeat_generic_question(client):
    project_id = client.post("/projects", json={"title": "Blank"}).json()["id"]
    first = _reply(client, project_id, "I want a data science project.")
    second = _reply(client, project_id, "Churn prediction.")
    text = _text(second)
    _assert_human(text)
    assert "churn" in text
    # Should progress, not re-ask the open-ended outcome question.
    assert "user outcome" not in text
    recent = ((first["state"].get("conversation_context") or {}).get("recent_questions") or [])
    assert recent  # first turn recorded a question


def test_e_constraints_silent(client):
    project_id = client.post("/projects", json={"description": "I need an NLP project."}).json()["id"]
    body = _reply(client, project_id, "I'm working alone and have six weeks.")
    text = _text(body)
    _assert_human(text)
    assert body["state"]["constraints"]["team_size"] == 1
    assert "6" in str(body["state"]["constraints"]["duration"])


def test_f_direction_change(client):
    project_id = client.post("/projects", json={"description": "I want a fake citation detector."}).json()["id"]
    _reply(client, project_id, "I want to build a fake citation detector.")
    body = _reply(client, project_id, "Actually forget this. I want phishing detection.")
    text = _text(body)
    _assert_human(text)
    assert "phish" in text
    assert (body["state"].get("exploration") or {}).get("history")


def test_g_research_natural(client):
    project_id = client.post("/projects", json={"description": "I want churn prediction."}).json()["id"]
    body = _reply(client, project_id, "Are there existing systems or datasets?")
    text = _text(body)
    _assert_human(text)
    assert "research level" not in text
    assert body.get("action") == "RESEARCH" or body.get("stage") == "RESEARCH"


def test_h_architecture_natural(client):
    project_id = client.post(
        "/projects",
        json={"description": "I want a Linux log analyzer for suspicious activity."},
    ).json()["id"]
    body = _reply(client, project_id, "How should I build it?")
    text = _text(body)
    _assert_human(text)
    assert "ai_recommendation" not in text
    assert any(token in text for token in ("layer", "backend", "structure", "fastapi", "python", "architect"))


def test_i_grill_conversational(client):
    project_id = client.post(
        "/projects",
        json={"description": "I want real-time threat detection with custom machine learning."},
    ).json()["id"]
    _reply(client, project_id, "I'm working alone and have six weeks.")
    body = _reply(client, project_id, "This idea is too big.")
    text = _text(body)
    _assert_human(text)
    assert body.get("action") == "GRILL" or body.get("stage") == "GRILL"


def test_j_compile_natural_gate(client):
    project_id = client.post("/projects", json={"title": "Sparse"}).json()["id"]
    body = _reply(client, project_id, "Generate the final Cursor prompt.")
    text = _text(body)
    assert "prompt compilation blocked" not in text
    assert "ai_recommendation" not in text


def test_idea_templates_no_raw_subject_prototype():
    state = empty_state_dict()
    state["academic"]["subject"] = "Data Science"
    state["exploration"]["current_direction"] = "foundation of data science"
    titles = [idea.title.lower() for idea in _templates(state)]
    assert all("project prototype" not in title for title in titles)
    assert any("churn" in title for title in titles)


def test_architecture_chat_format_hides_internal_labels():
    state = empty_state_dict()
    state["architecture"] = {
        "logical": {"layers": ["Presentation", "Backend/API", "Analysis", "Data"], "components": ["API"]},
        "implementation": {"style": "modular monolith", "notes": "Keep it small."},
    }
    state["technology"] = {
        "recommendations": [
            {"name": "FastAPI", "purpose": "backend", "reason": "fits Python stack", "alternative": "Django", "trade_off": "ecosystem"},
        ]
    }
    text = format_architecture_for_chat(state).lower()
    assert "ai_recommendation" not in text
    assert "proposed, not locked" not in text
    assert "presentation" in text
    assert "fastapi" in text
