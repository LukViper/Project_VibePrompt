"""Adversarial Grill attack entities."""

from app.services.grill import grill
from app.services.grill_attack_generators import apply_grill_response, generate_attacks_from_state
from app.services.project_state import empty_state
from app.services.traceability import blocking_grill_attacks
from app.services.prompt_compiler import compilation_gate


def _state_with_gap():
    state = empty_state()
    state["project"]["objective"] = "Analyze real-time network traffic using deep learning."
    state["requirements"] = [
        {
            "id": "REQ-001",
            "type": "functional",
            "text": "Analyze real-time network traffic using deep learning.",
            "status": "active",
            "assertion_status": "CONFIRMED",
            "version": 1,
            "provenance": {"source": "USER", "user_approved": True},
        }
    ]
    state["academic"] = {"subject": "NLP", "required_concepts": []}
    return state


def test_attack_targets_specific_entity():
    state = _state_with_gap()
    created = generate_attacks_from_state(state)
    assert created
    attack = created[0]
    assert attack["target_id"] in {"REQ-001", "PROJECT", "CONSTRAINT"}
    assert attack["challenge"]


def test_unresolved_attack_blocks_compilation():
    state = _state_with_gap()
    generate_attacks_from_state(state)
    gate = compilation_gate(state)
    if blocking_grill_attacks(state):
        assert gate["blocked"]
        assert any(i["type"] == "UNRESOLVED_GRILL_ATTACK" for i in gate["blocking_issues"])


def test_resolved_attack_not_blocking():
    state = _state_with_gap()
    attacks = generate_attacks_from_state(state)
    attack_id = attacks[0]["id"]
    apply_grill_response(
        state,
        attack_id=attack_id,
        response_text="Latency must be under 500ms.",
        resolution_type="RESOLVED",
        new_requirement_ids=["REQ-002"],
    )
    resolved = next(a for a in state["grill_attacks"] if a["id"] == attack_id)
    assert resolved["status"] == "RESOLVED"
    assert not resolved.get("blocking")


def test_grill_persists_attacks_in_report():
    state = _state_with_gap()
    report = grill(state)
    assert report.get("attacks") is not None
