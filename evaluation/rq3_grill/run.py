"""RQ3 — Grill effectiveness with targeted attack ontology.

Comparisons (fixed meanings — do not retune after seeing results):
  A — No Grill
  B — Existing checklist Grill
  C — Targeted adversarial Grill (ontology + ProjectState entity targets)

Dataset label: SYNTHETIC CONTROLLED BENCHMARK
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.common.metrics import rate, summarize  # noqa: E402
from evaluation.common.reporting import embedding_metadata_safe, new_run_dir, run_experiment  # noqa: E402
from evaluation.common.schemas import ExperimentConfig  # noqa: E402
from evaluation.rq3_grill.dataset import load_dataset, write_dataset  # noqa: E402
from evaluation.rq3_grill.diagnostics import build_diagnostics, write_diagnostics  # noqa: E402


def no_grill(_case: dict) -> dict:
    """A — No Grill."""
    return {
        "attacks": [],
        "detected": False,
        "predicted_attack_types": [],
        "predicted_target_types": [],
        "predicted_severities": [],
        "critical_detected": False,
        "resolved": False,
    }


def checklist_grill(case: dict) -> dict:
    """B — Existing checklist Grill (keyword tags, no entity targeting)."""
    text = (case.get("scenario") or case.get("project_objective") or "").lower()
    tags = []
    mapping = {
        "RESOURCE_FEASIBILITY": ["7b", "vram", "laptop", "gpu", "train"],
        "LATENCY": ["real-time", "realtime", "latency"],
        "EVALUATION": ["99.99", "accuracy", "evaluation"],
        "SCOPE": ["blockchain", "iot", "four weeks", "solo"],
        "DATA_AVAILABILITY": ["no dataset", "without a dataset", "dataset"],
        "SECURITY": ["threat model", "security", "pii"],
        "DEPLOYMENT": ["without monitoring", "production"],
        "RELIABILITY": ["high availability", "without redundancy"],
        "TECHNOLOGY_JUSTIFICATION": ["kafka", "because", "modern"],
        "ARCHITECTURE_MISMATCH": ["rest polling", "real-time"],
        "TIMELINE": ["two-week", "two week", "solo deadline"],
        "SCALABILITY": ["millions", "single vm"],
        "COST": ["$0", "budget"],
        "REQUIREMENT_AMBIGUITY": ["somehow", "appropriate", "etc"],
        "DEPENDENCY": ["unmaintained"],
        "CONTRADICTION": ["offline-only", "contradiction"],
        "MAINTAINABILITY": ["no tests", "no ci"],
        "ASSUMPTION": ["assumption"],
    }
    for ontology, keys in mapping.items():
        if any(k in text for k in keys):
            tags.append(ontology)
    gold = case.get("attack_type")
    detected = gold in tags if gold else bool(tags)
    return {
        "attacks": [{"type": "checklist", "attack_type": t, "target_type": None} for t in tags],
        "detected": detected,
        "predicted_attack_types": tags,
        "predicted_target_types": [],
        "predicted_severities": ["HIGH"] if case.get("gold_should_block") and tags else ["MEDIUM"] if tags else [],
        "critical_detected": bool(case.get("gold_should_block") and detected),
        "resolved": False,
        "method": "checklist",
    }


def targeted_adversarial_grill(case: dict) -> dict:
    """C — Targeted adversarial Grill against ProjectState entities."""
    from app.services.grill_attack_generators import generate_attacks_from_state
    from app.services.project_state import empty_state
    from app.services.targeted_grill import generate_targeted_attacks

    state = empty_state()
    obj = case.get("scenario") or case["project_objective"]
    state["project"]["objective"] = obj
    state["requirements"] = [
        {
            "id": "REQ-001",
            "text": obj,
            "status": "active",
            "type": "functional",
            "assertion_status": "CONFIRMED",
            "assertion_origin": "USER_EXPLICIT",
            "version": 1,
            "provenance": {"source": "USER", "user_approved": True},
        }
    ]
    if "solo" in obj.lower() or "four weeks" in obj.lower() or "two-week" in obj.lower():
        state["constraints"] = {"team_size": 1, "duration": "4 weeks", "avoid": []}
    # Prefer targeted generator; also run full generators for coverage
    attacks = generate_targeted_attacks(state)
    if not attacks:
        attacks = generate_attacks_from_state(state)

    pred_types = []
    pred_targets = []
    pred_sevs = []
    for a in attacks:
        at = a.get("ontology_type") or a.get("attack_type")
        if at:
            pred_types.append(str(at))
        if a.get("target_type"):
            pred_targets.append(str(a["target_type"]))
        if a.get("severity"):
            pred_sevs.append(str(a["severity"]).upper())

    gold_type = case.get("attack_type")
    gold_target = case.get("target_entity_type")
    detected = gold_type in pred_types if gold_type else bool(pred_types)
    # Target accuracy: among attacks whose type matches gold, did any hit gold target?
    target_hit = False
    if gold_type and gold_target:
        for a in attacks:
            at = str(a.get("ontology_type") or a.get("attack_type") or "")
            if at == gold_type and str(a.get("target_type") or "") == gold_target:
                target_hit = True
                break
    elif gold_target:
        target_hit = gold_target in pred_targets
    critical = case.get("severity") == "HIGH" or case.get("gold_should_block")
    critical_detected = bool(critical and detected)
    return {
        "attacks": attacks,
        "detected": detected,
        "target_identified": target_hit,
        "predicted_attack_types": list(dict.fromkeys(pred_types)),
        "predicted_target_types": list(dict.fromkeys(pred_targets)),
        "predicted_severities": list(dict.fromkeys(pred_sevs)),
        "critical_detected": critical_detected,
        "resolved": False,
        "method": "targeted_adversarial",
    }


def score_system(cases: list[dict], preds: list[dict]) -> dict:
    by_id = {p["id"]: p for p in preds}
    det_p, det_r, type_acc, tgt_acc, sev_acc, crit, fpr, resol = [], [], [], [], [], [], [], []
    for case in cases:
        pred = by_id[case["id"]]
        gold_type = case["attack_type"]
        detected = bool(pred.get("detected"))
        # Precision/recall of detection relative to gold presence (every case has a gold attack)
        tp = 1 if detected else 0
        fp = 1 if (pred.get("predicted_attack_types") and not detected and gold_type not in pred.get("predicted_attack_types", [])) else 0
        # Simpler: detection recall = detected; precision = type match among predicted
        det_r.append(1.0 if detected else 0.0)
        if pred.get("predicted_attack_types"):
            det_p.append(1.0 if gold_type in pred["predicted_attack_types"] else 0.0)
            fpr.append(0.0 if gold_type in pred["predicted_attack_types"] else 1.0)
        else:
            det_p.append(1.0)  # no predictions → no false positives
            fpr.append(0.0)
        type_acc.append(1.0 if gold_type in (pred.get("predicted_attack_types") or []) else 0.0)
        tgt_acc.append(1.0 if pred.get("target_identified") else (1.0 if case["target_entity_type"] in (pred.get("predicted_target_types") or []) else 0.0))
        sev_acc.append(1.0 if case["severity"] in (pred.get("predicted_severities") or []) else 0.0)
        if case.get("severity") == "HIGH":
            crit.append(1.0 if pred.get("critical_detected") else 0.0)
        resol.append(1.0 if pred.get("resolved") else 0.0)
        _ = tp  # reserved for future micro-averaging

    def f1_from_lists(ps, rs):
        # Mean P/R then F1
        from statistics import mean

        p = mean(ps) if ps else 0.0
        r = mean(rs) if rs else 0.0
        return (2 * p * r / (p + r)) if (p + r) else 0.0

    n_critical = sum(1 for c in cases if c.get("severity") == "HIGH")
    return {
        "n_scenarios": len(cases),
        "n_critical_scenarios": n_critical,
        "attack_detection_precision": summarize(det_p),
        "attack_detection_recall": summarize(det_r),
        "attack_detection_f1": {
            "n": len(cases),
            "mean": f1_from_lists(det_p, det_r),
        },
        "critical_issue_detection_rate": summarize(crit) if crit else summarize([]),
        "target_identification_accuracy": summarize(tgt_acc),
        "attack_type_accuracy": summarize(type_acc),
        "severity_accuracy": summarize(sev_acc),
        "false_positive_rate": summarize(fpr),
        "resolution_rate": summarize(resol),
    }


def main() -> dict:
    write_dataset(n=120)
    cases = load_dataset()
    emb = embedding_metadata_safe()
    config = ExperimentConfig(
        experiment_id="rq3_grill",
        experiment_version="2.0.0",
        dataset_id="vibeprompt-synthetic-bench/rq3",
        dataset_version="2.0.0",
        random_seed=42,
        embedding_provider=str(emb.get("provider")),
        embedding_model=str(emb.get("model")),
        parameters={
            "dataset_label": "SYNTHETIC CONTROLLED BENCHMARK",
            "systems": {"A": "no_grill", "B": "checklist_grill", "C": "targeted_adversarial_grill"},
        },
    )
    out_dir = new_run_dir("rq3") / "rq3"
    out_dir.mkdir(parents=True, exist_ok=True)

    def execute():
        systems = {
            "A_no_grill": no_grill,
            "B_checklist_grill": checklist_grill,
            "C_targeted_adversarial": targeted_adversarial_grill,
        }
        all_preds = {}
        results = []
        for name, fn in systems.items():
            preds = []
            for case in cases:
                pred = fn(case)
                pred["id"] = case["id"]
                preds.append(pred)
            all_preds[name] = preds
        metrics = {name: score_system(cases, preds) for name, preds in all_preds.items()}

        # Per-case detail for C + diagnostics
        c_preds = all_preds["C_targeted_adversarial"]
        for case, pred in zip(cases, c_preds):
            results.append(
                {
                    "id": case["id"],
                    "gold_attack_type": case["attack_type"],
                    "gold_target": case["target_entity_type"],
                    "gold_severity": case["severity"],
                    "detected": pred["detected"],
                    "target_identified": pred.get("target_identified"),
                    "predicted_attack_types": pred["predicted_attack_types"],
                    "predicted_target_types": pred["predicted_target_types"],
                    "n_attacks": len(pred.get("attacks") or []),
                }
            )
        diag_rows = build_diagnostics(cases, c_preds)
        write_diagnostics(out_dir, diag_rows, metrics=metrics.get("C_targeted_adversarial"))
        # Also copy diagnostics to results root sibling naming
        write_diagnostics(out_dir.parent, diag_rows, metrics=metrics.get("C_targeted_adversarial"))

        return {
            "status": "COMPLETED",
            "results": results,
            "metrics": metrics,
            "diagnostics_n_misses": len(diag_rows),
            "readme": (
                "# RQ3 Grill (v2)\n\n"
                f"N={len(cases)} SYNTHETIC CONTROLLED BENCHMARK scenarios.\n\n"
                "A=No Grill, B=Checklist, C=Targeted adversarial (ontology).\n\n"
                "See `rq3_diagnostics.md` for missed-attack failure modes.\n"
                "Do not hide low scores; diagnose them.\n"
            ),
        }

    return run_experiment(config=config, out_dir=out_dir, execute=execute)


if __name__ == "__main__":
    payload = main()
    print(json.dumps({"status": payload.get("status"), "metrics": payload.get("metrics"), "diagnostics_n_misses": payload.get("diagnostics_n_misses")}, indent=2))
