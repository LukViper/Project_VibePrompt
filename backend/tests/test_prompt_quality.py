"""Phase 10–11 — prompt compiler gate + validator."""

from app.services.prompt_compiler import compilation_gate, render_prompt
from app.services.prompt_validator import repair_prompt, validate_and_repair, validate_prompt
from app.schemas.state import empty_state_dict


def test_compilation_gate_blocks_empty():
    state = empty_state_dict()
    gate = compilation_gate(state)
    assert gate["blocked"] is True
    assert any("objective" in r or "requirements" in r for r in gate["reasons"])


def test_validator_repairs_missing_requirement():
    spec = {
        "functional": [{"id": "REQ-001", "text": "Classify phishing emails", "acceptance": "F1 score reported"}],
        "nonfunctional": [],
        "constraints": {"team_size": 1, "duration": "5 weeks"},
    }
    broken = "You are a senior software engineer.\nBuild the following project completely.\nTECH STACK\nx\n"
    report = validate_prompt(broken, spec)
    assert report["acceptable"] is False
    assert "REQ-001" in report["metrics"]["missing_requirements"]
    fixed = repair_prompt(broken, spec, report)
    again = validate_and_repair(fixed, spec)
    assert "REQ-001" in again["prompt"]
    assert again["report"]["metrics"]["requirement_coverage"] == 1.0


def test_render_prompt_is_dense_without_filler():
    spec = {
        "title": "PhishDetect",
        "objective": "Detect phishing",
        "problem": "Phishing emails",
        "functional": [{"id": "REQ-001", "text": "Classify emails", "acceptance": "Labels produced"}],
        "nonfunctional": [],
        "constraints": {"team_size": 1, "duration": "5 weeks", "budget": None, "avoid": []},
        "technology": {"backend": "Python", "model": "BERT", "database": "PostgreSQL"},
        "architecture": {"layers": ["API", "NLP"], "components": ["classifier"]},
        "database": {"entities": [{"name": "Email"}], "relationships": []},
        "apis": [{"method": "POST", "path": "/analyze", "purpose": "classify"}],
    }
    text = render_prompt(spec, "", {"grill_findings": {}, "research": []})
    assert "REQ-001" in text
    assert "ACCEPTANCE CRITERIA" in text
    assert "hope this helps" not in text.lower()
    assert text.count("OBJECTIVE") <= 2


def test_compile_and_validate_endpoint(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks. Phishing detector."},
    )
    project_id = created.json()["id"]
    client.post(f"/projects/{project_id}/messages", json={"content": "Maybe an NLP-based phishing detector."})
    client.post(f"/projects/{project_id}/messages", json={"content": "Use BERT and PostgreSQL."})

    gate = client.get(f"/projects/{project_id}/prompt/gate")
    assert gate.status_code == 200
    # May or may not be blocked depending on extracted requirements
    prompt = client.post(f"/projects/{project_id}/prompt", json={"force": True})
    assert prompt.status_code == 200
    body = prompt.json()
    assert "You are a senior software engineer." in body["content"]
    assert body["coverage"]["missing"] == [] or body["validation"]["metrics"]["requirement_coverage"] >= 0.99
    assert body.get("validation")

    validated = client.post(f"/projects/{project_id}/prompt/validate", json={"repair": True})
    assert validated.status_code == 200
    assert validated.json()["report"]["metrics"]["token_count"] > 0
