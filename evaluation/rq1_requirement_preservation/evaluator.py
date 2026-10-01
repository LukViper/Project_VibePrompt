"""RQ1 metrics — gold used only for scoring after system execution.

Metric documentation (all use token-Jaccard ≥ 0.55, not requirement IDs):

- Requirement Precision / Recall / F1 — predicted vs gold requirements
- Constraint Precision / Recall / F1 — predicted vs gold constraints
- Technology Precision / Recall — predicted vs gold technologies
- Rejected Requirement Leakage — fraction of gold rejected items still emitted
- Superseded Requirement Leakage — fraction of gold superseded items still emitted
- Unsupported Addition Rate — fraction of predictions with no gold match
- Assertion-Origin Accuracy — fraction of predicted texts whose origin matches gold map
"""

from __future__ import annotations

from typing import Any

from evaluation.common.metrics import (
    leakage_rate,
    set_metrics,
    summarize,
    texts_match,
    unsupported_addition_rate,
)
from evaluation.rq1_requirement_preservation.annotations import GoldAnnotation, gold_from_case


def assertion_origin_accuracy(
    predicted_origins: dict[str, str],
    gold_origins: dict[str, str],
    *,
    threshold: float = 0.55,
) -> float:
    if not gold_origins:
        return 1.0
    hits = 0
    for g_text, g_origin in gold_origins.items():
        match_origin = None
        for p_text, p_origin in predicted_origins.items():
            if texts_match(g_text, p_text, threshold=threshold):
                match_origin = p_origin
                break
        if match_origin and str(match_origin).upper() == str(g_origin).upper():
            hits += 1
    return hits / len(gold_origins)


def score_prediction(pred: dict[str, Any], gold: GoldAnnotation) -> dict[str, Any]:
    req_m = set_metrics(list(pred.get("requirements") or []), gold.requirements)
    con_m = set_metrics(list(pred.get("constraints") or []), gold.constraints)
    tech_m = set_metrics(list(pred.get("technologies") or []), gold.technologies)
    return {
        "requirement_precision": req_m["precision"],
        "requirement_recall": req_m["recall"],
        "requirement_f1": req_m["f1"],
        "requirement_counts": req_m,
        "constraint_precision": con_m["precision"],
        "constraint_recall": con_m["recall"],
        "constraint_f1": con_m["f1"],
        "constraint_counts": con_m,
        "technology_precision": tech_m["precision"],
        "technology_recall": tech_m["recall"],
        "technology_counts": tech_m,
        "rejected_requirement_leakage": leakage_rate(
            gold.rejected_items, list(pred.get("requirements") or [])
        ),
        "superseded_requirement_leakage": leakage_rate(
            gold.superseded_items, list(pred.get("requirements") or [])
        ),
        "unsupported_addition_rate": unsupported_addition_rate(
            list(pred.get("requirements") or []), gold.requirements
        ),
        "assertion_origin_accuracy": assertion_origin_accuracy(
            dict(pred.get("assertion_origins") or {}),
            gold.assertion_origins,
        ),
    }


def evaluate_case(case: dict, predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gold = gold_from_case(case)
    out: dict[str, Any] = {
        "id": case["id"],
        "dataset_label": case.get("dataset_label"),
        "systems": {},
    }
    for name, pred in predictions.items():
        # Contaminations checks: prediction must not be gold list identity
        if pred.get("requirements") is gold.requirements:
            raise RuntimeError(f"{name}: gold requirements used as prediction")
        out["systems"][name] = {
            "prediction_summary": {
                "n_requirements": len(pred.get("requirements") or []),
                "n_constraints": len(pred.get("constraints") or []),
                "method": pred.get("method"),
                "llm": pred.get("llm"),
            },
            "metrics": score_prediction(pred, gold),
        }
    return out


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    systems = sorted({s for r in results for s in r["systems"]})
    metrics: dict[str, Any] = {"n_scenarios": len(results), "dataset_label": "SYNTHETIC CONTROLLED BENCHMARK"}
    keys = [
        "requirement_precision",
        "requirement_recall",
        "requirement_f1",
        "constraint_precision",
        "constraint_recall",
        "constraint_f1",
        "technology_precision",
        "technology_recall",
        "rejected_requirement_leakage",
        "superseded_requirement_leakage",
        "unsupported_addition_rate",
        "assertion_origin_accuracy",
    ]
    for system in systems:
        bucket: dict[str, Any] = {}
        for key in keys:
            vals = [r["systems"][system]["metrics"][key] for r in results if system in r["systems"]]
            bucket[key] = summarize(vals)
        bucket["n"] = len(results)
        metrics[system] = bucket
    return metrics
