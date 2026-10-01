"""Phase 1 — ProjectState schema, provenance, migration, versioning."""

from app.schemas.provenance import ProvenanceSource, make_provenance
from app.schemas.state import ConversationStage, empty_state_dict, migrate_state, validate_state
from app.services.project_state import empty_state, public_state
from app.services.versioning import StateVersioning


def test_empty_state_has_v2_fields_and_technology_shape():
    state = empty_state()
    assert state["schema_version"] == 2
    assert state["conversation_stage"] == ConversationStage.DISCOVERY.value
    assert state["state_version"] == 1
    tech = state["technology"]
    for key in ("languages", "frameworks", "databases", "models", "hardware", "other"):
        assert key in tech
        assert isinstance(tech[key], list)
    assert "research" in state
    assert "grill_findings" in state
    assert "prompt_metrics" in state
    assert "architecture" in state


def test_migrate_legacy_v1_adds_provenance_and_stage():
    legacy = {
        "project": {"title": "Demo", "problem": "x", "objective": "y"},
        "academic": {"subject": "NLP", "required_concepts": []},
        "requirements": [
            {
                "id": "REQ-001",
                "type": "functional",
                "text": "Detect phishing",
                "status": "active",
                "version": 1,
            }
        ],
        "decisions": [{"kind": "note", "summary": "started", "details": {}}],
        "technology": {"model": "BERT"},
        "constraints": {"team_size": 1, "duration": "5 weeks", "budget": None, "avoid": []},
        "features": [],
        "domains": ["nlp"],
        "conflicts": [],
        "open_questions": [],
        "rejected_ideas": [],
        "idea": {"base_idea": None, "user_customizations": [], "alternatives": []},
    }
    migrated = migrate_state(legacy)
    assert migrated["schema_version"] == 2
    assert migrated["conversation_stage"] == "DISCOVERY"
    assert migrated["project"]["subject"] == "NLP"
    assert migrated["requirements"][0]["provenance"]["source"] == ProvenanceSource.USER.value
    assert migrated["decisions"][0]["provenance"]["source"] == ProvenanceSource.INFERRED.value
    assert "languages" in migrated["technology"]
    assert migrated["technology"]["model"] == "BERT"
    validate_state(migrated)


def test_make_provenance_dict():
    prov = make_provenance(ProvenanceSource.RESEARCH, reason="paper survey", confidence=0.7)
    assert prov["source"] == "RESEARCH"
    assert prov["reason"] == "paper survey"
    assert prov["confidence"] == 0.7


def test_version_bump_increments_counter():
    state = empty_state_dict()
    bumped = StateVersioning.bump(state, "test")
    assert bumped["state_version"] == 2
    assert bumped["_last_version_reason"] == "test"
    cleaned = public_state(bumped)
    assert "_last_version_reason" not in cleaned


def test_version_snapshot_persists(client):
    created = client.post("/projects", json={"title": "Snap"})
    assert created.status_code == 200
    project_id = created.json()["id"]
    msg = client.post(f"/projects/{project_id}/messages", json={"content": "I need a project for NLP."})
    assert msg.status_code == 200
    state = msg.json()["state"]
    assert state["schema_version"] == 2
    assert state["state_version"] >= 2
    for decision in state.get("decisions") or []:
        assert "provenance" in decision
        assert decision["provenance"]["source"] in {s.value for s in ProvenanceSource}
    from uuid import UUID

    from app.database.session import SessionLocal
    from app.models import Project

    with SessionLocal() as session:
        project = session.get(Project, UUID(project_id))
        assert project is not None
        assert len(project.versions) >= 1
