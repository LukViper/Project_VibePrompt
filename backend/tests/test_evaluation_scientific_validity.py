"""Scientific validity tests for RQ1 / RQ3 / RQ4 / RQ5 evaluation harnesses."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def test_rq1_does_not_use_gold_state_as_prediction():
    from evaluation.rq1_requirement_preservation.runner import vibeprompt_pipeline

    messages = [
        "I want a phishing detection system.",
        "Use BERT.",
        "Actually don't use BERT.",
        "Response time must be below 500 ms.",
    ]
    gold = ["phishing detection system", "response time below 500 ms"]
    pred = vibeprompt_pipeline(messages)
    assert pred.get("_from_gold") is False
    assert pred["requirements"] is not gold
    # Must not be an exact identity copy of the gold list content shortcut
    assert not (
        isinstance(pred["requirements"], list)
        and pred["requirements"] == gold
        and pred.get("method") == "gold_state_simulation"
    )


def test_rq1_gold_only_used_for_evaluation():
    from evaluation.rq1_requirement_preservation.annotations import gold_from_case
    from evaluation.rq1_requirement_preservation.evaluator import evaluate_case
    from evaluation.rq1_requirement_preservation.runner import run_all_systems

    case = {
        "id": "T-001",
        "messages": ["Build a spam classifier.", "Use TF-IDF."],
        "gold_requirements": ["spam classifier"],
        "gold_constraints": ["tf-idf"],
        "gold_technologies": ["tf-idf"],
        "rejected": [],
        "superseded": [],
        "assertion_origins": {"spam classifier": "USER_EXPLICIT"},
    }
    gold = gold_from_case(case)
    preds = run_all_systems(case["messages"])
    # Ensure runners never received gold
    for p in preds.values():
        assert p.get("requirements") is not gold.requirements
    scored = evaluate_case(case, preds)
    assert "vibeprompt" in scored["systems"]
    assert "metrics" in scored["systems"]["vibeprompt"]


def test_rq1_assertion_origin_accuracy():
    from evaluation.rq1_requirement_preservation.evaluator import assertion_origin_accuracy

    pred = {"Detect phishing emails": "USER_EXPLICIT", "Maybe dark mode": "USER_INFERRED"}
    gold = {"Detect phishing emails": "USER_EXPLICIT", "Maybe dark mode": "USER_INFERRED"}
    assert assertion_origin_accuracy(pred, gold) == 1.0
    bad = {"Detect phishing emails": "LLM_INFERRED"}
    assert assertion_origin_accuracy(bad, {"Detect phishing emails": "USER_EXPLICIT"}) == 0.0


def test_rq1_rejected_requirement_leakage():
    from evaluation.common.metrics import leakage_rate

    leaked = leakage_rate(["use bert"], ["use bert", "phishing detector"])
    clean = leakage_rate(["use bert"], ["phishing detector", "use sqlite"])
    assert leaked > 0
    assert clean == 0.0


def test_grill_target_identification():
    from app.services.project_state import empty_state
    from app.services.targeted_grill import generate_targeted_attacks

    state = empty_state()
    state["project"]["objective"] = "Train a 7B model locally on hardware with insufficient VRAM."
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": state["project"]["objective"],
            "status": "active",
            "assertion_status": "CONFIRMED",
            "version": 1,
        }
    ]
    attacks = generate_targeted_attacks(state)
    assert attacks
    assert any(a.get("target_id") for a in attacks)
    assert any(a.get("target_type") in {"ASSUMPTION", "REQUIREMENT", "PROJECT", "CLAIM"} for a in attacks)


def test_grill_attack_type_identification():
    from app.schemas.grill_ontology import AttackOntology
    from app.services.project_state import empty_state
    from app.services.targeted_grill import generate_targeted_attacks

    state = empty_state()
    state["project"]["objective"] = "Deep learning classifier with no dataset identified."
    state["requirements"] = [
        {"id": "REQ-001", "text": state["project"]["objective"], "status": "active", "version": 1}
    ]
    attacks = generate_targeted_attacks(state)
    types = {a.get("attack_type") for a in attacks}
    assert AttackOntology.DATA_AVAILABILITY.value in types


def test_grill_attack_severity():
    from app.services.project_state import empty_state
    from app.services.targeted_grill import generate_targeted_attacks

    state = empty_state()
    state["project"]["objective"] = "Train a 7B model locally on insufficient VRAM."
    state["requirements"] = [
        {"id": "REQ-001", "text": state["project"]["objective"], "status": "active", "version": 1}
    ]
    attacks = generate_targeted_attacks(state)
    assert any(a.get("severity") in {"HIGH", "MEDIUM"} for a in attacks)


def test_grill_diagnostic_output(tmp_path):
    from evaluation.rq3_grill.diagnostics import build_diagnostics, write_diagnostics

    cases = [
        {
            "id": "RQ3-001",
            "scenario": "Train 7B locally",
            "target_entity_type": "ASSUMPTION",
            "attack_type": "RESOURCE_FEASIBILITY",
            "severity": "HIGH",
            "expected_issue": "vram",
        }
    ]
    preds = [
        {
            "id": "RQ3-001",
            "detected": False,
            "predicted_attack_types": [],
            "predicted_target_types": [],
            "predicted_severities": [],
            "attacks": [],
        }
    ]
    rows = build_diagnostics(cases, preds)
    assert rows
    assert rows[0]["gold_attack_type"] == "RESOURCE_FEASIBILITY"
    jp, mp = write_diagnostics(tmp_path, rows)
    assert jp.exists() and mp.exists()
    payload = json.loads(jp.read_text(encoding="utf-8"))
    assert payload["n_misses"] >= 1


def test_rq4_unsupported_decision():
    from evaluation.rq4_evidence.run import classify_decision, with_evidence_tracking

    case = {"decision": "Use Kubernetes", "evidence_text": "", "evidence_verified": False}
    assert classify_decision(case) == "unsupported"
    tracked = with_evidence_tracking(case)
    assert tracked["unsupported"] is True
    assert tracked["evidence_coverage"] == 0.0


def test_rq4_unverified_evidence():
    from evaluation.rq4_evidence.run import classify_decision

    case = {
        "decision": "Use PostgreSQL",
        "evidence_text": "unverified blog post",
        "evidence_verified": False,
        "evidence_variant": "weak_evidence",
    }
    assert classify_decision(case) == "unverified"


def test_rq4_contradictory_evidence():
    from evaluation.rq4_evidence.run import classify_decision

    case = {
        "decision": "Use Kafka",
        "evidence_text": "contradictory cost analysis opposing Kafka",
        "evidence_verified": False,
    }
    assert classify_decision(case) == "contradicted"


def test_rq5_missing_agent_command(monkeypatch, tmp_path):
    monkeypatch.delenv("VIBEPROMPT_AGENT_CMD", raising=False)
    # Ensure dataset exists
    from evaluation.datasets.generate import generate_rq5

    generate_rq5()
    from evaluation.rq5_agent_execution import run as rq5

    # Point results to tmp by monkeypatching new_run_dir
    import evaluation.common.reporting as reporting

    monkeypatch.setattr(reporting, "new_run_dir", lambda prefix=None: tmp_path / f"run_{prefix}")
    monkeypatch.setattr(rq5, "new_run_dir", lambda prefix=None: tmp_path / f"run_{prefix}")

    payload = rq5.main()
    assert payload["status"] == "NOT EXECUTED"
    assert "unavailable" in (payload.get("reason") or "").lower()
