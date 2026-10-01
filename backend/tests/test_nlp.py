from app.nlp.contradiction import classify_relationship, find_slot_conflict
from app.nlp.extraction import ExtractionResult, ExtractedRequirement, extract_information
from app.nlp.intent import classify_intent
from app.services.project_state import empty_state


def test_remove_intent():
    result = classify_intent("Let's remove the mobile application.")
    assert result["intent"] == "REMOVE_REQUIREMENT"
    assert result["confidence"] >= 0.9


def test_onboarding_extraction():
    text = (
        "I have to build a project for NLP. I am working alone and have six weeks. "
        "The professor expects tokenization, Named Entity Recognition and sentiment analysis. "
        "I don't want to build a basic sentiment-analysis application."
    )
    extracted = extract_information(text)
    assert extracted.subject == "NLP"
    assert extracted.team_size == 1
    assert extracted.duration == "6 weeks"
    assert "tokenization" in extracted.required_topics
    assert "Named Entity Recognition" in extracted.required_topics
    assert any("basic sentiment analysis" in item for item in extracted.avoid)


def test_phishing_requirement_extraction():
    extracted = extract_information(
        "The system should classify phishing emails using BERT and provide a confidence score."
    )
    texts = [req.text.lower() for req in extracted.requirements]
    assert any("classify phishing emails" in text for text in texts)
    assert any("confidence score" in text for text in texts)
    assert "BERT" in extracted.technology
    assert "BERT" in extracted.models


def test_python_java_slot_conflict():
    state = empty_state()
    state["technology"]["backend"] = "Python"
    state["requirements"].append({
        "id": "REQ-001",
        "text": "The backend must use Python",
        "status": "active",
        "slot": "backend",
        "slot_value": "Python",
    })
    extraction = ExtractionResult(requirements=[
        ExtractedRequirement(type="constraint", text="The backend must use Java", slot="backend", slot_value="Java")
    ])
    conflict = find_slot_conflict(state, extraction)
    assert conflict is not None
    relationship = classify_relationship("The backend must use Java.", [], "ADD_REQUIREMENT", [], ["nlp"], conflict)
    assert relationship["relationship"] == "CONTRADICTS"
