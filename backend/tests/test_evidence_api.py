"""Evidence attachment API."""


def _project(client):
    created = client.post("/projects", json={"description": "NLP phishing detector alone five weeks"})
    return created.json()["id"]


def test_attach_evidence_to_claim(client):
    project_id = _project(client)
    # Create a claim via research path or direct evidence with claim text
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "Are there existing systems for phishing email detection?"},
    )
    state = client.get(f"/projects/{project_id}/state").json()
    claims = state.get("claims") or []
    claim_id = claims[0]["id"] if claims else None
    body = {
        "claim": "BERT improves phishing F1 on public datasets",
        "source": "user",
        "evidence_type": "USER_PROVIDED",
        "verification_status": "UNVERIFIED",
    }
    if claim_id:
        body["attach_to_type"] = "claim"
        body["attach_to_id"] = claim_id
    result = client.post(f"/projects/{project_id}/evidence", json=body)
    assert result.status_code == 200
    evidence = result.json()["evidence"]
    assert evidence["id"].startswith("EVIDENCE-")
    if claim_id:
        links = result.json()["state"]["trace_links"]
        assert any(link["target_id"] == claim_id for link in links)


def test_attach_evidence_to_assumption(client):
    project_id = _project(client)
    # Seed an assumption via integrity_store path using grill response isn't required —
    # use evidence attach after creating assumption through research/state if present.
    from app.database.session import SessionLocal
    from app.models import Project
    from app.services.integrity_store import add_assumption
    from app.services.project_state import public_state
    from uuid import UUID

    with SessionLocal() as session:
        project = session.get(Project, UUID(project_id))
        state = public_state(project.state or {})
        asm = add_assumption(state, text="Local GPU training is available", risk_level="HIGH")
        project.state = state
        session.commit()
        asm_id = asm["id"]

    result = client.post(
        f"/projects/{project_id}/evidence",
        json={
            "claim": "Team has a spare RTX 3060",
            "attach_to_type": "assumption",
            "attach_to_id": asm_id,
            "verification_status": "UNVERIFIED",
        },
    )
    assert result.status_code == 200
    state = result.json()["state"]
    assumption = next(a for a in state["assumptions"] if a["id"] == asm_id)
    assert result.json()["evidence"]["id"] in assumption.get("evidence_ids", [])


def test_attach_evidence_to_requirement(client):
    project_id = _project(client)
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "The system must classify phishing emails."},
    )
    state = client.get(f"/projects/{project_id}/state").json()
    req_id = state["requirements"][0]["id"]
    result = client.post(
        f"/projects/{project_id}/evidence",
        json={
            "claim": "Acceptance demo script exists",
            "attach_to_type": "requirement",
            "attach_to_id": req_id,
        },
    )
    assert result.status_code == 200
    links = result.json()["state"]["trace_links"]
    assert any(link["target_id"] == req_id and link["source_type"] == "EVIDENCE" for link in links)


def test_unverified_evidence_remains_unverified(client):
    project_id = _project(client)
    result = client.post(
        f"/projects/{project_id}/evidence",
        json={
            "claim": "LLM said BERT is best",
            "verification_status": "UNVERIFIED",
            "source": "",
        },
    )
    assert result.status_code == 200
    assert result.json()["evidence"]["verification_status"] == "UNVERIFIED"
