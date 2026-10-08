"""Capability harness gates ideas / architecture / grill against misuse."""

from app.services.capability_harness import (
    CapabilityKind,
    filter_ideas_to_domain,
    gate_capability,
    idea_matches_domain,
)
from app.services.idea_generation import IdeaDraft
from app.schemas.state import empty_state_dict


def test_ideation_gated_without_domain():
    gate = gate_capability(empty_state_dict(), CapabilityKind.IDEATION)
    assert gate.allowed is False
    assert gate.reason == "missing_domain"


def test_architecture_and_grill_gated_without_substance():
    state = empty_state_dict()
    state["academic"]["subject"] = "Computer Networks"
    assert gate_capability(state, CapabilityKind.IDEATION).allowed is True
    assert gate_capability(state, CapabilityKind.ARCHITECTURE).allowed is False
    assert gate_capability(state, CapabilityKind.GRILL).allowed is False


def test_networks_rejects_data_science_ideas():
    state = empty_state_dict()
    state["academic"]["subject"] = "Computer Networks"
    assert idea_matches_domain("Customer Churn Prediction with Explainable AI", state) is False
    assert idea_matches_domain("Network Traffic Analyzer with Anomaly Detection", state) is True


def test_filter_drops_cross_domain_templates():
    state = empty_state_dict()
    state["academic"]["subject"] = "Computer Networks"
    drafts = [
        IdeaDraft(title="Customer Churn Prediction with Explainable AI", problem="x", objective="y"),
        IdeaDraft(title="Network Traffic Analyzer", problem="packet capture", objective="analyze traffic"),
    ]
    kept, dropped = filter_ideas_to_domain(drafts, state)
    assert len(kept) == 1
    assert "Churn" in dropped[0]


def test_api_ideas_gated_on_blank_project(client):
    pid = client.post("/projects", json={"title": "Blank"}).json()["id"]
    resp = client.post(f"/projects/{pid}/ideas")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error"] == "capability_gated"
    assert detail["reason"] == "missing_domain"


def test_cyber_and_networks_combined_not_flip_flop(client):
    created = client.post(
        "/projects",
        json={"description": "I want to build a project in Cyber + Computer Networks"},
    )
    pid = created.json()["id"]
    state = client.get(f"/projects/{pid}/state").json()
    subject = state["academic"]["subject"]
    assert "Cybersecurity" in subject
    assert "Computer Networks" in subject
    assert " + " in subject

    reply = client.post(
        f"/projects/{pid}/messages",
        json={"content": "Cybersecurity and Computer Networks"},
    ).json()
    text = (reply.get("assistant_message") or {}).get("content") or reply.get("response") or ""
    assert "cybersecurity + computer networks" in text.lower()
    assert "phishing" not in text.lower() or "intersection" in text.lower() or "network" in text.lower()

    # Later single-domain mention should not erase the other half.
    client.post(f"/projects/{pid}/messages", json={"content": "I want in Cyber"})
    state = client.get(f"/projects/{pid}/state").json()
    subject = state["academic"]["subject"]
    assert "Cybersecurity" in subject
    assert "Computer Networks" in subject


def test_three_domains_include_data_science(client):
    created = client.post(
        "/projects",
        json={"description": "i want a project in data Science , Computer networks and cyber"},
    )
    pid = created.json()["id"]
    state = client.get(f"/projects/{pid}/state").json()
    subject = state["academic"]["subject"]
    assert "Data Science" in subject
    assert "Cybersecurity" in subject
    assert "Computer Networks" in subject

    # Typo-heavy restatement should still keep all three.
    reply = client.post(
        f"/projects/{pid}/messages",
        json={"content": "i am thinking about data scienc + Compueter netwroks _+ Cyber"},
    ).json()
    text = ((reply.get("assistant_message") or {}).get("content") or "").lower()
    assert "data science" in text
    assert "computer networks" in text
    assert "cybersecurity" in text
    state = client.get(f"/projects/{pid}/state").json()
    subject = state["academic"]["subject"]
    assert "Data Science" in subject


def test_how_it_works_answers_locked_idea(client):
    from app.nlp.intent import classify_intent

    assert classify_intent("how it works")["intent"] == "ASK_QUESTION"
    assert classify_intent("what is common for and end user")["intent"] == "ASK_QUESTION"

    created = client.post(
        "/projects",
        json={"description": "for computer networks ?"},
    )
    pid = created.json()["id"]
    ideas = client.post(f"/projects/{pid}/ideas").json()
    chosen = next(i for i in ideas if "protocol" in i["title"].lower() or "visual" in i["title"].lower())
    client.post(f"/projects/{pid}/ideas/{chosen['id']}/select")
    reply = client.post(
        f"/projects/{pid}/messages",
        json={"content": "how it works"},
    ).json()
    text = ((reply.get("assistant_message") or {}).get("content") or "").lower()
    assert "how" in text or "works" in text or "user" in text
    assert "got it — you're thinking about" not in text
    assert len(text) > 80


def test_api_domain_ideas_architecture_grill(client):
    created = client.post("/projects", json={"description": "for computer networks ?"})
    pid = created.json()["id"]
    state = client.get(f"/projects/{pid}/state").json()
    assert state["academic"]["subject"] == "Computer Networks"

    ideas = client.post(f"/projects/{pid}/ideas")
    assert ideas.status_code == 200
    body = ideas.json()
    titles = " ".join(item["title"].lower() for item in body)
    assert "churn" not in titles
    assert any(tok in titles for tok in ("network", "traffic", "protocol", "sdn", "wireless"))

    chosen = body[0]
    client.post(f"/projects/{pid}/ideas/{chosen['id']}/select")

    arch = client.post(f"/projects/{pid}/architecture")
    assert arch.status_code == 200
    assert (arch.json().get("provenance") or {}).get("harness") == "capability_harness"

    grill = client.post(f"/projects/{pid}/grill")
    assert grill.status_code == 200
    assert (grill.json().get("provenance") or {}).get("harness") == "capability_harness"
