"""RQ1 — Requirement preservation (scientifically valid pipeline).

Conversation → system (baseline A / B / VibePrompt) → predictions
Gold annotations used ONLY after execution for scoring.

Dataset label: SYNTHETIC CONTROLLED BENCHMARK
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.common.reporting import embedding_metadata_safe, new_run_dir, run_experiment  # noqa: E402
from evaluation.common.schemas import ExperimentConfig  # noqa: E402
from evaluation.rq1_requirement_preservation.dataset import load_dataset, write_dataset  # noqa: E402
from evaluation.rq1_requirement_preservation.evaluator import aggregate, evaluate_case  # noqa: E402
from evaluation.rq1_requirement_preservation.runner import run_all_systems  # noqa: E402


def main() -> dict:
    write_dataset(n=120)
    cases = load_dataset()
    emb = embedding_metadata_safe()
    config = ExperimentConfig(
        experiment_id="rq1_requirement_preservation",
        experiment_version="2.0.0",
        dataset_id="vibeprompt-synthetic-bench/rq1",
        dataset_version="2.0.0",
        random_seed=42,
        embedding_provider=str(emb.get("provider")),
        embedding_model=str(emb.get("model")),
        parameters={
            "match": "token_jaccard>=0.55",
            "id_matching": False,
            "gold_as_prediction": False,
            "dataset_label": "SYNTHETIC CONTROLLED BENCHMARK",
            "vibeprompt_path": "extract_information→apply_analysis_to_state→ProjectState→compilable/active requirements",
        },
    )
    out_dir = new_run_dir("rq1") / "rq1"
    out_dir.mkdir(parents=True, exist_ok=True)

    def execute():
        results = []
        for case in cases:
            # Gold deliberately not passed into runners
            preds = run_all_systems(case["messages"])
            results.append(evaluate_case(case, preds))
        metrics = aggregate(results)
        return {
            "status": "COMPLETED",
            "results": results,
            "metrics": metrics,
            "readme": (
                "# RQ1 Requirement Preservation (v2)\n\n"
                f"N={len(results)} — **SYNTHETIC CONTROLLED BENCHMARK**\n\n"
                "VibePrompt uses the real extraction→ProjectState pipeline.\n"
                "Gold annotations are used **only** for post-hoc scoring.\n"
                "Matching: token Jaccard ≥ 0.55 (not requirement IDs).\n\n"
                "Baselines A/B use LLM when configured; otherwise deterministic heuristics "
                "(recorded in llm metadata).\n"
            ),
        }

    return run_experiment(config=config, out_dir=out_dir, execute=execute)


if __name__ == "__main__":
    payload = main()
    print(json.dumps({"status": payload.get("status"), "metrics": payload.get("metrics")}, indent=2))
