"""Master Spec §38 critical regression scenarios + decision lifecycle."""

from app.schemas.decisions import DecisionStatus, normalize_decision
from app.schemas.state import empty_state_dict, migrate_state
from app.services.impact_analysis import analyze_message_impact, apply_impact_to_state
from app.services.project_state import apply_constraint_cues, empty_state
from app.services.research import select_research_level
from app.services.grill import grill


def test_decision_normalize_lifecycle():
    legacy = {"kind": "tech_recommendation", "summary": "Recommend Flutter", "details": {}}
    normalized = normalize_decision(legacy)
    assert normalized["status"] == DecisionStatus.PROPOSED.value
    assert normalized["user_approved"] is False
    assert normalized["id"]
    assert "provenance" in normalized


def test_1_web_to_android_ios_web_scope_change():
    state = empty_state()
    state["project"]["platform"] = ["Web"]
    impact = analyze_message_impact(state, "I now want Android, iOS and Web")
    assert impact["change_kind"] == "SCOPE_CHANGE"
    assert impact["requires_user_decision"] is True
    finding = impact["findings"][0]
    assert finding["incoming"] == ["Android", "iOS", "Web"]
    assert "frontend architecture" in finding["affected_components"]
    assert any("PWA" in (alt.get("name") or "") for alt in finding["alternatives"])
    # Must not silently convert to PWA-only in state
    state = apply_impact_to_state(state, impact)
    assert state["project"]["platform"] == ["Android", "iOS", "Web"]
    proposed = [d for d in state["decisions"] if d.get("status") == "PROPOSED"]
    assert proposed


def test_2_no_auth_then_private_histories_conflict():
    state = empty_state()
    state = apply_constraint_cues(state, "Users should have no login")
    assert "authentication_required=false" in state["security"]
    impact = analyze_message_impact(state, "Users should have private project histories")
    assert any(f["kind"] == "CONFLICT" for f in impact["findings"])
    assert "authentication" in impact["findings"][0]["affected_components"]


def test_3_postgres_to_mongodb_impact():
    state = empty_state()
    state["technology"]["database"] = "PostgreSQL"
    impact = analyze_message_impact(state, "Switch the database to MongoDB")
    assert impact["findings"]
    assert impact["findings"][0]["slot"] == "database"
    assert impact["findings"][0]["incoming"] == "MongoDB"
    assert "migrations" in impact["findings"][0]["affected_components"]


def test_4_no_login_to_login_required_conflict():
    state = empty_state()
    state = apply_constraint_cues(state, "Build it with no login")
    impact = analyze_message_impact(state, "Actually login required for all users")
    assert any(f["kind"] == "CONFLICT" and f["slot"] == "authentication" for f in impact["findings"])


def test_5_uncertain_tech_decision():
    state = empty_state()
    impact = analyze_message_impact(state, "I am not sure whether to use Flutter or React Native")
    assert impact["change_kind"] == "UNCERTAIN"
    assert impact["findings"][0]["kind"] == "UNCERTAIN"


def test_research_levels_adaptive():
    assert select_research_level("add dark mode", {}) == "LEVEL_0"
    assert select_research_level("What approach for Android + iOS + Web?", {}) == "LEVEL_1"
    assert select_research_level("Compare Flutter versus React Native trade-offs", {}) in {"LEVEL_1", "LEVEL_2"}
    assert select_research_level("Survey existing products and literature datasets for novelty", {}) == "LEVEL_3"


def test_grill_structured_report_shape():
    state = empty_state_dict()
    state["core_idea"] = {
        "primary_objective": "Real-time custom NLP on Android iOS Web",
        "locked": True,
        "problem": "too much",
    }
    state["constraints"] = {"team_size": 1, "duration": "3 weeks", "avoid": [], "budget": None}
    state["project"]["platform"] = ["Android", "iOS", "Web"]
    report = grill(state)
    structured = report["structured"]
    for key in (
        "blocking",
        "high_risk",
        "concerns",
        "validated",
        "change_required",
        "alternatives",
        "realistic_plan",
        "open_questions",
    ):
        assert key in structured
    assert "GRILL RESULT" in report["narrative"]
    assert "BLOCKING" in report["narrative"]


def test_architecture_recommendations_are_proposed(client):
    created = client.post("/projects", json={"description": "NLP phishing detector, solo, five weeks."})
    assert created.status_code == 200
    pid = created.json()["id"]
    client.post(f"/projects/{pid}/messages", json={"content": "Maybe an NLP-based phishing detector."})
    ideas = client.post(f"/projects/{pid}/ideas").json()
    chosen = ideas[0]
    client.post(f"/projects/{pid}/ideas/{chosen['id']}/select")
    arch = client.post(f"/projects/{pid}/architecture")
    assert arch.status_code == 200
    body = arch.json()
    state = body["state"]
    assert (state.get("architecture") or {}).get("status") == "PROPOSED"
    tech_decisions = [
        d for d in state.get("decisions") or [] if d.get("kind") == "tech_recommendation"
    ]
    assert tech_decisions
    assert all(d.get("status") == "PROPOSED" for d in tech_decisions)
    assert all(d.get("user_approved") is False for d in tech_decisions)
    target = tech_decisions[0]
    approved = client.post(f"/projects/{pid}/decisions/{target['id']}/approve")
    assert approved.status_code == 200
    active = [
        d
        for d in approved.json()["state"]["decisions"]
        if d.get("id") == target["id"]
    ][0]
    assert active["status"] == "ACTIVE"
    assert active["user_approved"] is True


def test_migrate_adds_decision_lifecycle_fields():
    legacy = migrate_state({
        "decisions": [{"kind": "note", "summary": "started", "details": {}}],
        "project": {"title": "x"},
    })
    decision = legacy["decisions"][0]
    assert decision["status"]
    assert "user_approved" in decision
    assert decision["id"]
