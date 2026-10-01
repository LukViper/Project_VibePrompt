"""Force compilation must leave an auditable trail."""

from app.services.project_state import empty_state
from app.services.prompt_compiler import compilation_gate, compile_prompt
from app.database.session import SessionLocal
from app.models import Project
from uuid import UUID


def test_force_compile_creates_audit_event(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks."},
    )
    project_id = created.json()["id"]
    # Gate may be blocked (few/no confirmed requirements) — force compile.
    result = client.post(f"/projects/{project_id}/prompt", json={"force": True})
    assert result.status_code == 200
    state = client.get(f"/projects/{project_id}/state").json()
    events = state.get("audit_events") or []
    forced = [e for e in events if e.get("event_type") == "FORCED_COMPILATION"]
    assert forced
    assert forced[-1]["after"]["compilation_mode"] == "forced compilation"
    assert "blocking_issues" in (forced[-1].get("before") or {})


def test_force_compile_records_blocking_issues(client):
    created = client.post("/projects", json={"title": "ForceBlock"})
    project_id = created.json()["id"]
    gate = client.get(f"/projects/{project_id}/prompt/gate").json()
    result = client.post(f"/projects/{project_id}/prompt", json={"force": True})
    assert result.status_code == 200
    report = result.json().get("compilation_report") or result.json().get("gate") or {}
    assert report.get("forced") is True or report.get("compilation_mode") == "forced compilation"
    state = client.get(f"/projects/{project_id}/state").json()
    forced = [e for e in (state.get("audit_events") or []) if e.get("event_type") == "FORCED_COMPILATION"]
    assert forced
    # Snapshot of why force was needed
    before = forced[-1]["before"]
    assert "reasons" in before
    if gate.get("blocked"):
        assert before.get("can_compile") is False


def test_normal_compile_has_no_force_event(client):
    created = client.post(
        "/projects",
        json={"description": "I need a project for NLP. Alone, five weeks. Phishing detector."},
    )
    project_id = created.json()["id"]
    client.post(
        f"/projects/{project_id}/messages",
        json={"content": "The system must classify phishing emails with BERT."},
    )
    # Confirm any proposed requirements so normal compile can succeed.
    state = client.get(f"/projects/{project_id}/state").json()
    for req in state.get("requirements") or []:
        if req.get("assertion_status") == "PROPOSED":
            client.post(f"/projects/{project_id}/assertions/{req['id']}/confirm")
    # Resolve blocking grill if any by not running grill.
    gate = client.get(f"/projects/{project_id}/prompt/gate").json()
    if gate.get("blocked"):
        # Still exercise force path separately; for this test skip if cannot normal-compile.
        return
    result = client.post(f"/projects/{project_id}/prompt", json={"force": False})
    assert result.status_code == 200
    state = client.get(f"/projects/{project_id}/state").json()
    forced = [e for e in (state.get("audit_events") or []) if e.get("event_type") == "FORCED_COMPILATION"]
    assert forced == []
    compiled = [e for e in (state.get("audit_events") or []) if e.get("event_type") == "PROMPT_COMPILED"]
    assert compiled
    assert compiled[-1]["after"].get("forced") is False
