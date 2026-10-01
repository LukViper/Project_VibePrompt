from app.nlp.drift import calculate_drift
from app.nlp.similarity import cosine_similarity
from app.nlp.embeddings import create_embedding
from app.services.project_state import empty_state


def test_identical_text_similarity():
    text = "Detect phishing emails."
    score = cosine_similarity(create_embedding(text), create_embedding(text))
    assert score > 0.99


def test_facial_recognition_is_drift_from_phishing_objective():
    state = empty_state()
    state["academic"]["subject"] = "NLP"
    state["project"]["objective"] = "NLP-based phishing detection"
    state["core_idea"] = {
        "problem": "Detect phishing emails",
        "primary_domain": "NLP",
        "primary_objective": "NLP-based phishing detection",
        "locked": True,
    }
    state["domains"] = ["nlp", "cybersecurity"]
    report = calculate_drift(state, ["Facial recognition"])
    assert report["potential_drift"] is True
    assert any("Computer Vision" in item["domains"] for item in report["drifted"])


def test_browser_extension_is_not_domain_drift():
    state = empty_state()
    state["academic"]["subject"] = "NLP"
    state["core_idea"] = {
        "primary_domain": "NLP",
        "primary_objective": "Classify phishing emails",
        "locked": True,
    }
    state["domains"] = ["nlp", "cybersecurity"]
    report = calculate_drift(state, ["Browser extension"])
    assert report["potential_drift"] is False
