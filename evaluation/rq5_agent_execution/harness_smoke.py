"""HARNESS TEST — mock agent + tasks_v2 subset. Never a scientific RQ5 result."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.common.reporting import new_run_dir  # noqa: E402
from evaluation.common.serialization import write_json  # noqa: E402
from evaluation.rq5_agent_execution.config import load_rq5_config  # noqa: E402
from evaluation.rq5_agent_execution.harness import run_single  # noqa: E402
from evaluation.rq5_agent_execution.metrics import compute_rq5_metrics  # noqa: E402
from evaluation.rq5_agent_execution.prompts import VARIANTS  # noqa: E402

DATA_V2 = ROOT / "evaluation" / "datasets" / "rq5" / "tasks_v2.json"
MANIFEST_V2 = ROOT / "evaluation" / "datasets" / "rq5" / "tasks_v2_manifest.json"
SMOKE_LABEL = "HARNESS TEST — not a scientific RQ5 result"


def main() -> dict:
    if not DATA_V2.exists():
        from evaluation.datasets.rq5.generate_v2 import generate

        generate()
    tasks = json.loads(DATA_V2.read_text(encoding="utf-8"))[:3]  # three tasks × 3 variants
    manifest = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
    config = load_rq5_config(harness_test=True)
    out_dir = new_run_dir("rq5_harness_test") / "rq5_harness_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_root = out_dir / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)

    write_json(
        out_dir / "config.json",
        {
            "label": SMOKE_LABEL,
            "mode": "HARNESS_TEST",
            "scientific": False,
            "dataset_hash": manifest["dataset_hash"],
            "rq5_config": config.to_dict(),
            "variants": list(VARIANTS),
            "warning": "Infrastructure validation only — not an RQ5 scientific result.",
        },
    )

    runs = []
    work_root = Path(tempfile.mkdtemp(prefix="vibeprompt_rq5_smoke_"))
    try:
        for task in tasks:
            for variant in VARIANTS:
                runs.append(
                    run_single(
                        task=task,
                        variant=variant,
                        config=config,
                        work_root=work_root,
                        artifact_root=artifact_root,
                        label="HARNESS TEST",
                    )
                )
    finally:
        import shutil

        shutil.rmtree(work_root, ignore_errors=True)

    metrics = compute_rq5_metrics(runs)
    write_json(out_dir / "runs.json", runs)
    write_json(
        out_dir / "metrics.json",
        {**metrics, "label": SMOKE_LABEL, "scientific": False, "dataset_hash": manifest["dataset_hash"]},
    )
    (out_dir / "README.md").write_text(
        f"# RQ5 HARNESS TEST\n\n**Not scientific.** N_runs={len(runs)}. "
        f"Variants A/B/C exercised with mock agent. dataset_hash={manifest['dataset_hash']}\n",
        encoding="utf-8",
    )
    return {
        "status": "HARNESS_TEST_COMPLETED",
        "label": SMOKE_LABEL,
        "scientific": False,
        "n_runs": len(runs),
        "dataset_hash": manifest["dataset_hash"],
        "metrics": metrics,
        "out_dir": str(out_dir),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
