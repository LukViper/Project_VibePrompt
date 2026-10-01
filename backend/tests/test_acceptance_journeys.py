"""Phase 13 — acceptance journeys A1–A7 (backend)."""


def test_a1_clueless_nlp_cyber_pipeline(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP related to cybersecurity. I don't know what to build."},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]
    ideas = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "I don't know what to build, suggest ideas"},
    )
    assert ideas.status_code == 200
    assert ideas.json()["stage"] == "IDEATION"
    generated = client.post(f"/projects/{project_id}/ideas").json()
    assert len(generated) >= 3
    chosen = generated[0]
    selected = client.post(f"/projects/{project_id}/ideas/{chosen['id']}/select")
    assert selected.json()["state"]["core_idea"]["locked"] is True
    client.post(f"/projects/{project_id}/messages", json={"content": "Use BERT and PostgreSQL."})
    grill = client.post(f"/projects/{project_id}/grill")
    assert grill.status_code == 200
    assert grill.json()["dimensions"]
    arch = client.post(f"/projects/{project_id}/architecture")
    assert arch.status_code == 200
    prompt = client.post(f"/projects/{project_id}/prompt", json={"force": True})
    assert prompt.status_code == 200
    assert prompt.json()["validation"]["metrics"]["requirement_coverage"] >= 0.99


def test_a2_owned_phishing_idea(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks."},
    )
    project_id = created.json()["id"]
    idea = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Maybe an NLP-based phishing detector."},
    )
    assert idea.json()["state"]["core_idea"]
    research = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Are there any existing systems for phishing detection?"},
    )
    assert research.json()["stage"] == "RESEARCH"
    grill = client.post(f"/projects/{project_id}/grill")
    assert "weaknesses" in grill.json() or "dimensions" in grill.json()
    arch = client.post(f"/projects/{project_id}/architecture")
    assert arch.json()["state"]["architecture"]
    prompt = client.post(f"/projects/{project_id}/prompt", json={"force": True})
    assert "phishing" in prompt.json()["content"].lower() or "REQ-" in prompt.json()["content"]


def test_a3_technology_pivot_notice(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Phishing detector. Use React."},
    )
    project_id = created.json()["id"]
    client.post(f"/projects/{project_id}/messages", json={"content": "Use React for the frontend."})
    pivot = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Actually switch to Flutter for the frontend"},
    )
    content = pivot.json()["assistant_message"]["content"].lower()
    assert "flutter" in content or "pivot" in content or "switch" in content


def test_a4_guest_vs_permanent_save(client):
    guest = client.post("/auth/guest").json()
    gtoken = guest["access_token"]
    ephemeral = client.post(
        "/projects",
        json={"title": "Temp"},
        headers={"Authorization": f"Bearer {gtoken}"},
    )
    assert ephemeral.json()["is_ephemeral"] is True

    registered = client.post(
        "/auth/register",
        json={"email": "a4@example.com", "password": "password123"},
    ).json()
    permanent = client.post(
        "/projects",
        json={"title": "Keep"},
        headers={"Authorization": f"Bearer {registered['access_token']}"},
    )
    assert permanent.json()["is_ephemeral"] is False
    # Guest cannot claim permanent-save without registering — claim requires registered
    claim_attempt = client.post(
        f"/projects/{ephemeral.json()['id']}/claim",
        headers={"Authorization": f"Bearer {gtoken}"},
    )
    assert claim_attempt.status_code == 403


def test_a5_research_on_demand(client):
    created = client.post("/projects", json={"description": "I need a project for NLP."})
    project_id = created.json()["id"]
    msg = client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Are there any existing systems for phishing email detection?"},
    )
    assert msg.json()["stage"] == "RESEARCH"
    assert msg.json()["state"]["research"]


def test_a6_compile_dense_prompt(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks. Phishing detector using BERT."},
    )
    project_id = created.json()["id"]
    client.post(f"/projects/{project_id}/messages", json={"content": "Add email classification with confidence scores."})
    prompt = client.post(f"/projects/{project_id}/prompt", json={"force": True}).json()
    content = prompt["content"]
    assert "You are a senior software engineer." in content
    assert "hope this helps" not in content.lower()
    assert "ACCEPTANCE CRITERIA" in content
    assert prompt["coverage"]["missing"] == []


def test_a7_validator_high_coverage(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Phishing detector. Alone, five weeks."},
    )
    project_id = created.json()["id"]
    client.post(f"/projects/{project_id}/messages", json={"content": "Add browser extension alerts."})
    client.post(f"/projects/{project_id}/prompt", json={"force": True})
    report = client.post(f"/projects/{project_id}/prompt/validate", json={"repair": True}).json()["report"]
    assert report["metrics"]["requirement_coverage"] >= 0.99
    assert report["metrics"]["redundancy"] <= 0.5
