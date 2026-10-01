"""Phase 5 — research-on-demand."""

from app.nlp.intent import classify_intent
from app.schemas.provenance import ProvenanceSource
from app.schemas.state import ConversationStage
from app.services.research import _normalize_finding, format_research_for_chat


def test_research_intent_rules():
    assert classify_intent("Are there any existing systems for phishing detection?")["intent"] == "REQUEST_RESEARCH"
    assert classify_intent("Find datasets for spam classification")["intent"] == "REQUEST_RESEARCH"


def test_normalize_finding_strips_suspect_url_paper_combo():
    cleaned = _normalize_finding(
        {
            "finding": "Transformers help phishing detection.",
            "source": "https://fake.example/arxiv Something 2024",
            "source_type": "paper",
            "verification_status": "unverified",
        },
        "phishing systems",
    )
    assert cleaned is not None
    assert cleaned["source"] == ""
    assert cleaned["provenance"]["source"] == ProvenanceSource.RESEARCH.value


def test_research_message_stores_findings(client):
    created = client.post("/projects", json={"description": "I need a project for NLP."})
    project_id = created.json()["id"]
    msg = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Are there any existing systems for phishing email detection?"},
    )
    assert msg.status_code == 200
    body = msg.json()
    assert body["stage"] == ConversationStage.RESEARCH.value
    state = body["state"]
    assert state["research"]
    finding = state["research"][-1]
    assert finding["finding"]
    assert finding["provenance"]["source"] in {
        ProvenanceSource.RESEARCH.value,
        ProvenanceSource.SYSTEM_DEFAULT.value,
    }
    assert "Research level" not in body["assistant_message"]["content"]
    content = body["assistant_message"]["content"].lower()
    assert "research for:" not in content
    assert any(token in content for token in ("checked", "found", "evidence", "source", "narrow", "looks relevant"))


def test_format_research_for_chat():
    text = format_research_for_chat(
        "existing systems?",
        [{
            "finding": "SpamAssassin exists",
            "source": "",
            "source_type": "unknown",
            "project_impact": "Can study rule+ML hybrids",
            "verification_status": "unverified",
        }],
    )
    assert "SpamAssassin" in text
    assert "RESEARCH provenance" not in text
    assert "AI_RECOMMENDATION" not in text
    assert "LEVEL_" not in text


def test_format_research_inconclusive_is_natural():
    text = format_research_for_chat(
        "Are there existing systems or datasets for churn?",
        [{
            "finding": "Evidence inconclusive / no verified external sources",
            "source": "",
            "source_type": "system",
            "verification_status": "unverified",
        }],
        inconclusive=True,
    )
    lowered = text.lower()
    assert "research level" not in lowered
    assert "evidence inconclusive." not in lowered
    assert "don't want to invent" in lowered or "do not invent" in lowered or "invent sources" in lowered
    assert "churn" in lowered