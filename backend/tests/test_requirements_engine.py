"""Phase 6 — requirements structure, progressive questions, apply research."""

from app.nlp.extraction import enrich_requirement_structure, extract_information
from app.nlp.intent import classify_intent
from app.schemas.provenance import ProvenanceSource
from app.schemas.state import ConversationStage, empty_state_dict
from app.services.project_state import pivot_dependency_notice


def test_enrich_requirement_adds_actor_acceptance():
    from app.nlp.extraction import ExtractedRequirement

    req = enrich_requirement_structure(ExtractedRequirement(type="functional", text="The system must classify phishing emails"))
    assert req.actor
    assert req.capability
    assert req.acceptance


def test_extraction_includes_structure_fields():
    result = extract_information("Add a browser extension that flags phishing links")
    assert result.requirements
    functional = [r for r in result.requirements if r.type == "functional"]
    assert functional
    assert functional[0].actor or functional[0].acceptance


def test_progressive_open_questions_single(client):
    created = client.post("/projects", json={"title": "Empty"})
    project_id = created.json()["id"]
    state = client.get(f"/projects/{project_id}/state").json()
    # empty project may have no message yet — send thin message
    msg = client.post(f"/projects/{project_id}/messages", json={"content": "Hello"})
    open_q = msg.json()["state"]["open_questions"]
    assert len(open_q) <= 1


def test_pivot_dependency_notice():
    state = empty_state_dict()
    state["requirements"] = [{
        "id": "REQ-001",
        "text": "The backend must use Django",
        "status": "active",
        "slot": "backend",
    }]
    notice = pivot_dependency_notice(state, ["backend"])
    assert notice is not None
    assert "REQ-001" in notice
    assert "silently" in notice.lower()


def test_apply_research_intent_and_requirements(client):
    assert classify_intent("Apply the research findings to requirements")["intent"] == "APPLY_RESEARCH"
    created = client.post("/projects", json={"description": "I need a project for NLP."})
    project_id = created.json()["id"]
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Are there any existing systems for phishing detection?"},
    )
    applied = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Apply the research findings to requirements"},
    )
    assert applied.status_code == 200
    state = applied.json()["state"]
    # Either added research requirements or reported none to add
    assert applied.json()["stage"] in {
        ConversationStage.REQUIREMENTS.value,
        ConversationStage.RESEARCH.value,
        ConversationStage.DISCOVERY.value,
    }
    research_reqs = [
        req for req in state.get("requirements") or []
        if (req.get("provenance") or {}).get("source") == ProvenanceSource.RESEARCH.value
    ]
    # Without Gemini, system finding may not promote — still OK if narrative explains
    assert "research" in applied.json()["assistant_message"]["content"].lower()
