"""Phase 1 — Conversation Manager orchestration (actions, not form fields)."""

from app.orchestration.conversation_manager import (
    ConversationManager,
    OrchestratorAction,
    research_needed,
)
from app.schemas.state import ConversationStage, empty_state_dict


def test_discovery_explores_instead_of_form_fields():
    manager = ConversationManager()
    state = empty_state_dict()
    result = manager.advance_after_message(state, "PROJECT_DESCRIPTION", "I need an NLP project.")
    assert result.stage == ConversationStage.DISCOVERY
    assert result.action == OrchestratorAction.EXPLORE
    assert result.next_question is not None
    q = result.next_question.lower()
    assert "team" not in q
    assert "duration" not in q
    assert "how long" not in q
    assert "nlp" in q or "classification" in q or "extraction" in q


def test_cybersecurity_explores_domain():
    manager = ConversationManager()
    state = empty_state_dict()
    result = manager.advance_after_message(
        state, "PROJECT_DESCRIPTION", "I want something in cybersecurity."
    )
    assert result.action == OrchestratorAction.EXPLORE
    assert result.next_question
    assert "team" not in result.next_question.lower()
    assert "cyber" in result.next_question.lower() or "security" in result.next_question.lower() or "threat" in result.next_question.lower()


def test_grill_and_prompt_intents_set_stage():
    manager = ConversationManager()
    state = empty_state_dict()
    grill = manager.advance_after_message(state, "REQUEST_GRILL", "Grill this project")
    assert grill.stage == ConversationStage.GRILL
    assert grill.action == OrchestratorAction.GRILL
    prompt = manager.advance_after_message(state, "GENERATE_PROMPT", "Compile the prompt")
    assert prompt.stage == ConversationStage.PROMPT_GENERATION
    assert prompt.action == OrchestratorAction.COMPILE_PROMPT


def test_too_big_selects_grill_action():
    manager = ConversationManager()
    state = empty_state_dict()
    state["core_idea"] = {
        "primary_objective": "real-time threat detection with custom ML",
        "locked": False,
        "user_customizations": [],
    }
    result = manager.advance_after_message(state, "ASK_FEASIBILITY", "This idea is too big.")
    assert result.action == OrchestratorAction.GRILL


def test_direction_change_detected():
    manager = ConversationManager()
    state = empty_state_dict()
    state["core_idea"] = {
        "primary_objective": "fake citation detector",
        "locked": True,
        "user_customizations": [],
    }
    assert manager.detect_direction_change(
        "Actually, forget this. I want a phishing detection system.", state
    )
    result = manager.advance_after_message(
        state, "CHANGE_SCOPE", "Actually, forget this. I want a phishing detection system."
    )
    assert result.action == OrchestratorAction.RESET_OR_CHANGE_DIRECTION
    assert result.direction_change


def test_architecture_and_research_actions():
    manager = ConversationManager()
    state = empty_state_dict()
    arch = manager.advance_after_message(state, "ASK_QUESTION", "How should I build it?")
    assert arch.action == OrchestratorAction.PROPOSE_ARCHITECTURE
    research = manager.advance_after_message(
        state, "REQUEST_RESEARCH", "Are there existing systems for this?"
    )
    assert research.action == OrchestratorAction.RESEARCH


def test_locked_idea_moves_to_customization_or_requirements():
    manager = ConversationManager()
    state = empty_state_dict()
    state["core_idea"] = {
        "problem": "phishing",
        "primary_domain": "NLP",
        "primary_objective": "detect phishing",
        "locked": True,
        "user_customizations": [],
    }
    custom = manager.advance_after_message(state, "PROJECT_DESCRIPTION", "Make the UI simpler")
    assert custom.stage == ConversationStage.CUSTOMIZATION
    reqs = manager.advance_after_message(state, "ADD_REQUIREMENT", "Add email classification")
    assert reqs.stage == ConversationStage.REQUIREMENTS


def test_pivot_detection():
    manager = ConversationManager()
    state = empty_state_dict()
    state["technology"]["frameworks"] = ["React"]
    notice = manager.detect_pivot("Actually switch to Flutter for the frontend", state)
    assert notice is not None
    assert "Flutter" in notice or "flutter" in notice.lower()


def test_conflict_summary():
    manager = ConversationManager()
    state = empty_state_dict()
    state["conflicts"] = [{
        "status": "open",
        "explanation": "Conflict on backend: existing value is Django, incoming value is FastAPI.",
    }]
    summary = manager.conflict_summary(state)
    assert summary is not None
    assert "not silently" in summary.lower()


def test_research_needed_heuristic():
    assert research_needed("Are there any existing systems for phishing detection?")
    assert research_needed("Find datasets for spam classification")
    assert not research_needed("Add a login page")


def test_message_response_includes_stage(client):
    created = client.post("/projects", json={"description": "I need a project for NLP."})
    project_id = created.json()["id"]
    msg = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "I want an NLP phishing detector."},
    )
    assert msg.status_code == 200
    body = msg.json()
    assert "stage" in body
    assert body["stage"] in {stage.value for stage in ConversationStage}
    assert body["state"]["conversation_stage"] == body["stage"]
    assert "action" in body
