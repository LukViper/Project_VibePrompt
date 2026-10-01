"""RQ2 — Change impact / traceability experiment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.common.metrics import set_metrics, summarize  # noqa: E402
from evaluation.common.reporting import embedding_metadata_safe, new_run_dir, run_experiment  # noqa: E402
from evaluation.common.schemas import ExperimentConfig  # noqa: E402
from evaluation.datasets.generate import generate_rq2  # noqa: E402

DATA = ROOT / "evaluation" / "datasets" / "rq2" / "scenarios_v1.json"


def predict_impact(case: dict) -> dict:
    """Heuristic impact predictor mirroring impact_analysis intent (no LLM)."""
    ctype = case["change_type"]
    before = case["before"]
    decisions, architecture, tests = [], [], []
    if ctype in {"requirement_modification", "technology_change", "architecture_change", "scope_change"}:
        decisions = list(before.get("decisions") or [])
        architecture = list(before.get("architecture") or [])
        tests = list(before.get("tests") or [])
    elif ctype in {"requirement_addition", "requirement_removal"}:
        tests = list(before.get("tests") or [])
    elif ctype == "security_requirement_change":
        decisions = list(before.get("decisions") or [])
        tests = list(before.get("tests") or [])
    elif ctype in {"dataset_change", "deployment_change", "constraint_change"}:
        architecture = list(before.get("architecture") or [])[:1]
    return {
        "decisions": decisions,
        "architecture": architecture,
        "tests": tests,
        "prompt": True,
    }


def broken_trace_rate(pred: dict, gold: dict) -> float:
    """1 if any gold-impacted area is empty in prediction when gold expects non-empty."""
    misses = 0
    checks = 0
    for key in ("decisions", "architecture", "tests"):
        g = gold.get(key) or []
        if not g:
            continue
        checks += 1
        m = set_metrics(pred.get(key) or [], g)
        if m["recall"] < 1.0:
            misses += 1
    return misses / checks if checks else 0.0


def main() -> dict:
    if not DATA.exists():
        generate_rq2()
    cases = json.loads(DATA.read_text(encoding="utf-8"))
    emb = embedding_metadata_safe()
    config = ExperimentConfig(
        experiment_id="rq2_change_impact",
        experiment_version="1.0.0",
        dataset_id="vibeprompt-synthetic-bench/rq2",
        dataset_version="1.0.0",
        random_seed=42,
        embedding_provider=str(emb.get("provider")),
        embedding_model=str(emb.get("model")),
    )
    out_dir = new_run_dir("rq2") / "rq2"
    out_dir.mkdir(parents=True, exist_ok=True)

    def execute():
        results = []
        f1s, broken = [], []
        for case in cases:
            pred = predict_impact(case)
            gold = case["gold_impact"]
            # Flatten entity texts for aggregate F1
            pred_flat = pred["decisions"] + pred["architecture"] + pred["tests"]
            gold_flat = (gold.get("decisions") or []) + (gold.get("architecture") or []) + (gold.get("tests") or [])
            m = set_metrics(pred_flat, gold_flat)
            br = broken_trace_rate(pred, gold)
            f1s.append(m["f1"])
            broken.append(br)
            results.append({"id": case["id"], "change_type": case["change_type"], "metrics": m, "broken_trace_rate": br})
        return {
            "status": "COMPLETED",
            "results": results,
            "metrics": {
                "impact_f1": summarize(f1s),
                "broken_traceability_rate": summarize(broken),
                "n_scenarios": len(results),
            },
        }

    return run_experiment(config=config, out_dir=out_dir, execute=execute)


if __name__ == "__main__":
    print(json.dumps(main().get("metrics"), indent=2))
