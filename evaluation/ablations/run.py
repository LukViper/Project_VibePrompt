"""Ablation runners — state / grill / evidence / traceability."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation.common.reporting import new_run_dir, run_experiment  # noqa: E402
from evaluation.common.schemas import ExperimentConfig  # noqa: E402
from evaluation.rq1_requirement_preservation import run as rq1  # noqa: E402
from evaluation.rq3_grill import run as rq3  # noqa: E402
from evaluation.rq4_evidence import run as rq4  # noqa: E402
from evaluation.rq2_change_impact import run as rq2  # noqa: E402


def main() -> dict:
    config = ExperimentConfig(
        experiment_id="ablations",
        experiment_version="1.0.0",
        dataset_id="vibeprompt-synthetic-bench",
        dataset_version="1.0.0",
        random_seed=42,
    )
    out_dir = new_run_dir("ablations") / "ablations"
    out_dir.mkdir(parents=True, exist_ok=True)

    def execute():
        # Reuse RQ runners; map systems to ablation conditions.
        rq1_payload = rq1.main()
        rq3_payload = rq3.main()
        rq4_payload = rq4.main()
        rq2_payload = rq2.main()
        return {
            "status": "COMPLETED",
            "results": {
                "state_ablation": {
                    "A_raw": rq1_payload["metrics"]["baseline_a"],
                    "B_structured": rq1_payload["metrics"]["baseline_b"],
                    "D_full_vibeprompt": rq1_payload["metrics"]["vibeprompt"],
                    "note": "Condition C (requirements+decisions) not separately instrumented in v1; D uses gold-state compile.",
                },
                "grill_ablation": rq3_payload["metrics"],
                "evidence_ablation": {
                    "with_evidence_classifier": rq4_payload["metrics"],
                    "note": "No-evidence condition ≡ unsupported_decision_rate when evidence_text empty subset",
                },
                "traceability_ablation": {
                    "with_trace_impact": rq2_payload["metrics"],
                    "note": "No-traceability baseline would predict empty impact sets (F1→0 on non-empty gold)",
                },
            },
            "metrics": {
                "rq1": rq1_payload["metrics"],
                "rq2": rq2_payload["metrics"],
                "rq3": rq3_payload["metrics"],
                "rq4": rq4_payload["metrics"],
            },
        }

    return run_experiment(config=config, out_dir=out_dir, execute=execute)


if __name__ == "__main__":
    print(json.dumps(main().get("status"), indent=2))
