"""Phase 4 — detailed ideation."""

from app.nlp.intent import classify_intent
from app.schemas.state import ConversationStage
from app.services.idea_generation import IdeaDraft, format_ideas_for_chat, wants_ideation


def test_idea_draft_has_detailed_fields():
    draft = IdeaDraft(
        title="Demo",
        problem="p",
        why_it_matters="w",
        solution="s",
        users="u",
        objective="o",
        architecture="a",
        ai_nlp="nlp",
        data="d",
        research_extension="r",
        risks=["bias"],
    )
    details = draft.details_dict()
    assert details["why_it_matters"] == "w"
    assert details["risks"] == ["bias"]


def test_generate_ideas_endpoint_returns_details(client):
    created = client.post("/projects", json={"description": "I need a project for NLP related to cybersecurity."})
    project_id = created.json()["id"]
    ideas = client.post(f"/projects/{project_id}/ideas")
    assert ideas.status_code == 200
    body = ideas.json()
    assert len(body) >= 3
    first = body[0]
    assert first["title"]
    assert "why_it_matters" in first
    assert "solution" in first
    assert "architecture" in first
    assert "risks" in first
    state = client.get(f"/projects/{project_id}/state").json()
    assert state["idea"]["alternatives"]
    assert state["conversation_stage"] in {
        ConversationStage.IDEATION.value,
        ConversationStage.DISCOVERY.value,
        ConversationStage.IDEA_SELECTED.value,
        ConversationStage.CUSTOMIZATION.value,
        ConversationStage.REQUIREMENTS.value,
    }


def test_chat_generate_ideas_intent(client):
    created = client.post("/projects", json={"description": "I need a project for NLP. Team of 1, five weeks."})
    project_id = created.json()["id"]
    assert classify_intent("I don't know what to build, suggest ideas")["intent"] == "GENERATE_IDEAS"
    msg = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "I don't know what to build, suggest ideas"},
    )
    assert msg.status_code == 200
    content = msg.json()["assistant_message"]["content"]
    assert "detailed project ideas" in content.lower() or "Idea" in content or "1." in content
    assert msg.json()["stage"] == ConversationStage.IDEATION.value


def test_wants_ideation_respects_locked_core():
    assert wants_ideation("suggest ideas", {"core_idea": None})
    assert not wants_ideation("suggest ideas", {"core_idea": {"locked": True}})


def test_format_ideas_for_chat_includes_sections():
    class _Idea:
        title = "T"
        problem = "P"
        objective = "O"
        features = ["F1"]
        technology = ["Python"]
        difficulty = "medium"
        estimated_scope = "small"
        details = {
            "why_it_matters": "W",
            "solution": "S",
            "users": "U",
            "architecture": "A",
            "ai_nlp": "N",
            "research_extension": "R",
            "risks": ["risk1"],
        }

    text = format_ideas_for_chat([_Idea()])
    assert "Why it matters" in text
    assert "Architecture" in text
