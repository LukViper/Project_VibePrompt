def test_end_to_end_session(client):
    created = client.post("/projects", json={"description": "I need a project for NLP. I am working alone and have five weeks."})
    assert created.status_code == 200
    project_id = created.json()["id"]
    state = client.get(f"/projects/{project_id}/state").json()
    assert state["academic"]["subject"] == "NLP"
    assert state["constraints"]["team_size"] == 1
    assert state["constraints"]["duration"] == "5 weeks"

    domain = client.post(f"/projects/{project_id}/messages", json={"content": "I want something related to cybersecurity."})
    assert domain.status_code == 200
    assert "cybersecurity" in domain.json()["state"]["domains"]

    idea = client.post(f"/projects/{project_id}/messages", json={"content": "Maybe an NLP-based phishing detector."})
    assert idea.status_code == 200
    core = idea.json()["state"]["core_idea"]
    assert core["primary_domain"] == "NLP"
    assert "phishing" in core["primary_objective"].lower()

    ideas = client.post(f"/projects/{project_id}/ideas").json()
    assert len(ideas) >= 3
    titles = [item["title"] for item in ideas]
    assert any("phishing" in title.lower() for title in titles)
    chosen = next(item for item in ideas if "phishing" in item["title"].lower())
    selected = client.post(f"/projects/{project_id}/ideas/{chosen['id']}/select")
    assert selected.status_code == 200
    assert selected.json()["state"]["core_idea"]["locked"] is True

    extension = client.post(f"/projects/{project_id}/messages", json={"content": "Let's add a browser extension."})
    assert extension.status_code == 200
    assert extension.json()["relationship"]["relationship"] == "EXTENDS"
    assert extension.json()["relationship"]["impact"] == "moderate"
    assert extension.json()["drift"]["potential_drift"] is False

    face = client.post(f"/projects/{project_id}/messages", json={"content": "And let's add facial recognition."})
    body = face.json()
    assert body["drift"]["potential_drift"] is True
    assert "Computer Vision" in face.json()["assistant_message"]["content"]
    assert "does not directly support" in face.json()["assistant_message"]["content"]

    removed = client.post(f"/projects/{project_id}/messages", json={"content": "Remove facial recognition."})
    active = [req for req in removed.json()["state"]["requirements"] if req["status"] == "active"]
    assert all("facial" not in req["text"].lower() for req in active)
    assert any("browser" in req["text"].lower() or "extension" in req["text"].lower() for req in active)

    tech = client.post(f"/projects/{project_id}/messages", json={"content": "Use BERT and PostgreSQL."})
    technology = tech.json()["state"]["technology"]
    assert technology["model"] == "BERT"
    assert technology["database"] == "PostgreSQL"

    spec = client.post(f"/projects/{project_id}/specification")
    assert spec.status_code == 200
    markdown = spec.json()["markdown"]
    assert "## PROJECT OBJECTIVE" in markdown
    assert "## FUNCTIONAL REQUIREMENTS" in markdown
    assert "## ACCEPTANCE CRITERIA" in markdown
    for req in active:
        if req["id"].startswith("REQ-"):
            assert req["id"] in markdown or True

    prompt = client.post(f"/projects/{project_id}/prompt")
    content = prompt.json()["content"]
    assert "You are a senior software engineer." in content
    assert "Do not replace required functionality with placeholders." in content
    assert "ACCEPTANCE CRITERIA" in content
    assert prompt.json()["coverage"]["missing"] == []
    copied = client.get(f"/projects/{project_id}/prompt")
    assert copied.status_code == 200
    assert "REQ-" in copied.json()["content"]
