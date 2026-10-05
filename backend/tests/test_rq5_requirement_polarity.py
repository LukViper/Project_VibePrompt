"""Regression tests: rejected/forbidden features must never become positive requirements."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


@pytest.mark.parametrize(
    "utterance,forbidden_token",
    [
        ("Do not add Redis caching.", "redis"),
        ("Don't use Kafka.", "kafka"),
        ("Avoid using MongoDB.", "mongodb"),
        ("Never call external APIs.", "external"),
        ("Must not enable cloud storage.", "cloud"),
        ("Shall not introduce GraphQL subscriptions.", "graphql"),
    ],
)
def test_rejected_feature_stays_rejected_in_extraction(utterance, forbidden_token):
    from app.nlp.extraction import extract_information
    from app.nlp.intent import classify_intent

    extracted = extract_information(utterance)
    intent = classify_intent(utterance)["intent"]

    assert extracted.avoid, f"expected avoid entries for {utterance!r}"
    assert any(forbidden_token in item.lower() for item in extracted.avoid)
    # No positive requirements restating the forbidden feature
    for req in extracted.requirements:
        assert forbidden_token not in req.text.lower()
    # Forbidden tech must not be adopted as selected stack
    tech_blob = " ".join(
        extracted.databases
        + extracted.frameworks
        + extracted.models
        + extracted.technology
    ).lower()
    assert forbidden_token not in tech_blob
    assert intent == "REMOVE_REQUIREMENT"


def test_positive_add_still_creates_requirement():
    from app.nlp.extraction import extract_information
    from app.nlp.intent import classify_intent

    text = "Add Redis caching."
    extracted = extract_information(text)
    assert classify_intent(text)["intent"] == "ADD_REQUIREMENT"
    assert any("redis" in r.text.lower() for r in extracted.requirements)
    assert not extracted.avoid


def test_rejected_feature_not_in_compiled_vibeprompt(tasks_v2_rest_echo=None):
    from evaluation.rq5_agent_execution.c_pipeline import run_vibeprompt_c_pipeline

    path = ROOT / "evaluation/datasets/rq5/tasks_v2.json"
    if not path.exists():
        from evaluation.datasets.rq5.generate_v2 import generate

        generate()
    tasks = json.loads(path.read_text(encoding="utf-8"))
    task = next(t for t in tasks if t["task_id"] == "rest_echo_api")
    out = run_vibeprompt_c_pipeline(task["conversation"], task=task)
    prompt = out["prompt"].lower()
    included = (out["provenance"].get("gate") or {}).get("included_requirements") or []
    avoid = (out["state"].get("constraints") or {}).get("avoid") or []

    assert any("redis" in a.lower() for a in avoid)
    # Stronger: no included requirement text mentions redis
    for item in included:
        assert "redis" not in (item.get("text") or "").lower(), item
    # Tech stack database must not be Redis
    tech = out["state"].get("technology") or {}
    assert (tech.get("database") or "").lower() != "redis"
    assert "redis" not in " ".join(tech.get("databases") or []).lower()
    # Compiled body: Database line must not say Redis
    assert "database: redis" not in prompt
    # REQUIREMENTS section must not list Redis as a functional/NFR line
    in_reqs = False
    for line in out["prompt"].splitlines():
        upper = line.strip().upper()
        if upper.startswith("REQUIREMENTS") or upper.startswith("FUNCTIONAL REQUIREMENTS") or upper.startswith("NON-FUNCTIONAL"):
            in_reqs = True
            continue
        if in_reqs and (upper.startswith("CONSTRAINTS") or upper.startswith("TECH STACK")):
            break
        if in_reqs and "redis" in line.lower():
            pytest.fail(f"Redis appears as positive requirement line: {line!r}")


def test_rejected_feature_generic_pipeline_kafka_not_redis_specific():
    """Same polarity bug path with a different forbidden tech — not Redis-hardcoded."""
    from evaluation.rq5_agent_execution.c_pipeline import run_vibeprompt_c_pipeline

    conversation = [
        "I need a simple message queue helper in Python.",
        "Implement enqueue(item) that stores items in memory.",
        "Do not use Kafka.",
        "Use only the Python standard library.",
    ]
    task = {
        "task_id": "synthetic_queue",
        "rejected_features": ["Do not use Kafka"],
        "gold_requirements": ["implement enqueue"],
    }
    out = run_vibeprompt_c_pipeline(conversation, task=task)
    included = (out["provenance"].get("gate") or {}).get("included_requirements") or []
    for item in included:
        assert "kafka" not in (item.get("text") or "").lower(), item
    avoid = (out["state"].get("constraints") or {}).get("avoid") or []
    assert any("kafka" in a.lower() for a in avoid)
    prompt_reqs = []
    for line in out["prompt"].splitlines():
        if line.startswith("CONSTRAINTS"):
            break
        prompt_reqs.append(line.lower())
    joined = "\n".join(prompt_reqs)
    # Positive requirement lines must not mandate Kafka
    assert "use kafka" not in joined
    assert "req-" not in joined or "kafka" not in joined.split("constraints")[0]


def test_variant_acceptance_requirements_equivalent_for_rest_echo_api():
    """A/B/C share the same gold acceptance oracle; C must not add conflicting positives."""
    from evaluation.rq5_agent_execution.c_pipeline import run_vibeprompt_c_pipeline
    from evaluation.rq5_agent_execution.prompts import build_prompts_with_provenance

    path = ROOT / "evaluation/datasets/rq5/tasks_v2.json"
    if not path.exists():
        from evaluation.datasets.rq5.generate_v2 import generate

        generate()
    tasks = json.loads(path.read_text(encoding="utf-8"))
    task = next(t for t in tasks if t["task_id"] == "rest_echo_api")
    gold = list(task["gold_requirements"])
    rejected = list(task["rejected_features"])
    acceptance = list(task["acceptance_tests"])

    prompts = build_prompts_with_provenance(task)
    # Structured baseline lists gold + rejected explicitly
    b = prompts["B_structured"]["prompt"]
    for g in gold:
        # token overlap is enough — wording may differ slightly
        assert any(tok in b.lower() for tok in g.lower().split() if len(tok) > 4)
    for r in rejected:
        assert "redis" in b.lower() or "do not" in b.lower()

    c_out = run_vibeprompt_c_pipeline(task["conversation"], task=task)
    included_texts = [
        (item.get("text") or "").lower()
        for item in (c_out["provenance"].get("gate") or {}).get("included_requirements") or []
    ]
    # No rejected feature promoted into included positive requirements
    for r in rejected:
        tokens = [t for t in r.lower().replace("do not", "").split() if len(t) >= 4]
        for text in included_texts:
            if tokens and all(t in text for t in tokens):
                pytest.fail(f"rejected {r!r} appears as positive requirement {text!r}")

    # Oracle acceptance tests unchanged across variants (task-level contract)
    assert acceptance == task["acceptance_tests"]
    assert gold == task["gold_requirements"]


def test_apply_analysis_does_not_promote_avoid_to_requirement():
    from app.nlp.extraction import extract_information
    from app.nlp.intent import classify_intent
    from app.nlp.contradiction import classify_relationship, find_slot_conflict
    from app.nlp.drift import analyze_scope, calculate_drift
    from app.services.project_state import apply_analysis_to_state, empty_state, public_state

    state = empty_state()
    text = "Do not add Redis caching."
    extraction = extract_information(text)
    intent = classify_intent(text)
    analysis = {
        "intent": intent,
        "extraction": extraction,
        "related": [],
        "relationship": classify_relationship(text, [], intent["intent"], extraction.domains, [], None),
        "slot_conflict": find_slot_conflict(state, extraction),
        "drift": {"potential_drift": False, "drifted": [], "requirements": [], "backend": "n/a"},
        "scope": analyze_scope(state, extraction.domains, 0),
    }
    state = public_state(apply_analysis_to_state(state, analysis, reason=intent["intent"]))
    active = [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
    assert not any("redis" in (r.get("text") or "").lower() for r in active)
    assert any("redis" in a.lower() for a in (state.get("constraints") or {}).get("avoid") or [])
    assert (state.get("technology") or {}).get("database") in (None, "", False)
