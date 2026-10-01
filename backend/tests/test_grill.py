"""Phase 7 — adversarial grill dimensions and persistence."""

from app.schemas.state import ConversationStage
from app.services.grill import grill


def test_grill_covers_adversarial_dimensions():
    state = {
        "project": {"objective": "Detect phishing emails"},
        "core_idea": {"primary_objective": "Detect phishing emails", "locked": True},
        "academic": {"subject": "NLP", "required_concepts": []},
        "constraints": {"team_size": 1, "duration": "2 weeks"},
        "requirements": [
            {"id": "REQ-001", "text": "Classify emails", "status": "active", "origin": "original"},
            {"id": "REQ-002", "text": "Add facial recognition login", "status": "active", "origin": "added", "domain": "computer_vision"},
        ],
        "technology": {"models": ["BERT", "GPT"], "languages": [], "frameworks": [], "databases": [], "hardware": [], "other": []},
        "conflicts": [],
        "open_questions": [],
        "research": [],
        "security": [],
        "testing": {},
        "deployment": {},
        "ai_nlp": {},
        "drift": {"potential_drift": True},
        "scope": {},
    }
    report = grill(state)
    dims = {item["dimension"] for item in report["dimensions"]}
    for required in (
        "problem_clarity",
        "scope",
        "dataset",
        "feasibility",
        "ai_necessity",
        "evaluation",
        "research_potential",
        "deployment",
        "security",
        "dependency_risk",
        "timeline",
    ):
        assert required in dims
    assert "strengths" in report
    assert "weaknesses" in report
    assert "missing_information" in report
    assert "risks" in report
    assert "recommended_changes" in report
    assert "questions_that_must_be_resolved" in report
    assert "score" not in report
    assert "vanity" not in report["summary"].lower()


def test_grill_persists_on_project(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks. Phishing detector."},
    )
    project_id = created.json()["id"]
    report = client.post(f"/projects/{project_id}/grill")
    assert report.status_code == 200
    body = report.json()
    assert body["mode"] == "grill"
    assert body["dimensions"]
    state = client.get(f"/projects/{project_id}/state").json()
    assert state["grill_findings"]
    assert state["grill_findings"]["iteration"] >= 1
    assert state["conversation_stage"] == ConversationStage.GRILL.value

    # Second grill increments iteration
    again = client.post(f"/projects/{project_id}/grill")
    assert again.json()["iteration"] >= 2
