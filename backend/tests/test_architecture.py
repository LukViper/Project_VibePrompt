"""Phase 8 — architecture / tech / DB / API engines."""

from app.nlp.intent import classify_intent
from app.schemas.provenance import ProvenanceSource
from app.schemas.state import ConversationStage


def test_architecture_intent():
    assert classify_intent("Propose an architecture and tech stack")["intent"] == "REQUEST_ARCHITECTURE"


def test_architecture_endpoint_writes_state(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Phishing detector. Alone, five weeks."},
    )
    project_id = created.json()["id"]
    result = client.post(f"/projects/{project_id}/architecture")
    assert result.status_code == 200
    body = result.json()
    assert "Architecture" in body["narrative"] or "architecture" in body["narrative"].lower()
    state = body["state"]
    assert state["conversation_stage"] == ConversationStage.ARCHITECTURE.value
    assert state["architecture"].get("logical")
    assert state["architecture"]["provenance"]["source"] == ProvenanceSource.AI_RECOMMENDATION.value
    assert state["architecture"].get("status") == "PROPOSED"
    assert state["architecture"].get("user_approved") is False
    assert (state["database"].get("proposed") or {}).get("entities")
    assert isinstance(state["apis"], list)
    assert state["apis"]
    assert state["apis"][0].get("status") == "PROPOSED"
    recs = (state.get("technology") or {}).get("recommendations") or []
    assert recs
    assert "purpose" in recs[0] and "trade_off" in recs[0]
    tech_decisions = [d for d in state.get("decisions") or [] if d.get("kind") == "tech_recommendation"]
    assert tech_decisions and all(d.get("status") == "PROPOSED" for d in tech_decisions)


def test_architecture_via_chat(client):
    created = client.post("/projects", json={"description": "I need a project for NLP."})
    project_id = created.json()["id"]
    msg = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Recommend an architecture and tech stack"},
    )
    assert msg.status_code == 200
    assert msg.json()["stage"] == ConversationStage.ARCHITECTURE.value
    assert msg.json()["state"]["architecture"]
