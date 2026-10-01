"""RQ5 — Real coding-agent execution harness (scientific runner).

Without VIBEPROMPT_AGENT_CMD:

```text
RQ5 NOT EXECUTED
Reason: agent command unavailable
```

Uses tasks_v2 by default. Never fabricates scientific results.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.common.reporting import new_run_dir, run_experiment  # noqa: E402
from evaluation.common.schemas import ExperimentConfig  # noqa: E402
from evaluation.rq5_agent_execution.config import load_rq5_config  # noqa: E402
from evaluation.rq5_agent_execution.harness import run_single  # noqa: E402
from evaluation.rq5_agent_execution.metrics import (  # noqa: E402
    aggregate_experiment_status,
    compute_rq5_metrics,
)
from evaluation.rq5_agent_execution.prompts import VARIANTS, build_prompts_with_provenance  # noqa: E402

DATA_V2 = ROOT / "evaluation" / "datasets" / "rq5" / "tasks_v2.json"
MANIFEST_V2 = ROOT / "evaluation" / "datasets" / "rq5" / "tasks_v2_manifest.json"


def _ensure_v2() -> tuple[list[dict], dict]:
    if not DATA_V2.exists() or not MANIFEST_V2.exists():
        from evaluation.datasets.rq5.generate_v2 import generate

        generate()
    tasks = json.loads(DATA_V2.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
    return tasks, manifest


def main() -> dict:
    config = load_rq5_config(harness_test=False)
    tasks, manifest = _ensure_v2()

    exp_config = ExperimentConfig(
        experiment_id="rq5_agent_execution",
        experiment_version="4.0.0",
        dataset_id=manifest["dataset_id"],
        dataset_version=manifest["dataset_version"],
        random_seed=42,
        model=config.agent_model or "n/a",
        parameters={
            "dataset_label": manifest["dataset_label"],
            "dataset_hash": manifest["dataset_hash"],
            "n_tasks": manifest["n_tasks"],
            "task_ids": manifest["task_ids"],
            "rq5_config": config.to_dict(),
            "variants": list(VARIANTS),
            "mode": "SCIENTIFIC",
            "protocol": "RQ5_PROTOCOL_v2",
        },
    )
    out_dir = new_run_dir("rq5") / "rq5"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_root = out_dir / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (out_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    def execute():
        tasks_out = []
        for task in tasks:
            bundles = build_prompts_with_provenance(task)
            prompt_dir = out_dir / "prompts" / task["task_id"]
            prompt_dir.mkdir(parents=True, exist_ok=True)
            for name, bundle in bundles.items():
                (prompt_dir / f"{name}.txt").write_text(bundle["prompt"], encoding="utf-8")
                (prompt_dir / f"{name}.provenance.json").write_text(
                    json.dumps(
                        {
                            "method": bundle.get("method"),
                            "provenance": bundle.get("provenance"),
                            "state_summary": bundle.get("state_summary"),
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            tasks_out.append(
                {
                    "id": task["id"],
                    "task_id": task["task_id"],
                    "gold_requirements": task.get("gold_requirements"),
                    "constraints": task.get("constraints"),
                    "rejected_features": task.get("rejected_features"),
                    "acceptance_tests": task.get("acceptance_tests"),
                }
            )
        (out_dir / "tasks.json").write_text(json.dumps(tasks_out, indent=2) + "\n", encoding="utf-8")

        if not config.agent_available:
            reason = "agent command unavailable"
            return {
                "status": "NOT EXECUTED",
                "execution_status": "NOT_EXECUTED",
                "aggregate_status": "NOT_EXECUTED",
                "reason": reason,
                "results": [],
                "metrics": {
                    "n": 0,
                    "successful_runs": 0,
                    "failed_runs": 0,
                    "unverified_runs": 0,
                    "requirement_coverage": None,
                    "constraint_preservation": None,
                    "acceptance_test_pass_rate": None,
                    "build_success_rate": None,
                    "test_success_rate": None,
                    "unsupported_feature_rate": None,
                    "scope_deviation": None,
                    "dataset_hash": manifest["dataset_hash"],
                    "note": "RQ5 NOT EXECUTED — Reason: agent command unavailable. "
                    "Null metrics mean not measured, not zero performance.",
                },
                "readme": (
                    "# RQ5 Agent Execution\n\n"
                    "```text\nRQ5 NOT EXECUTED\nReason: agent command unavailable\n```\n\n"
                    f"Dataset: `{manifest['dataset_id']}` {manifest['dataset_version']} "
                    f"hash `{manifest['dataset_hash']}`\n"
                ),
            }

        runs = []
        work_root = Path(tempfile.mkdtemp(prefix="vibeprompt_rq5_sci_"))
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
                            label="SCIENTIFIC",
                        )
                    )
        finally:
            import shutil

            shutil.rmtree(work_root, ignore_errors=True)

        (out_dir / "runs.json").write_text(json.dumps(runs, indent=2) + "\n", encoding="utf-8")
        metrics = compute_rq5_metrics(runs)
        metrics["dataset_hash"] = manifest["dataset_hash"]
        agg = aggregate_experiment_status(runs, agent_available=True)
        return {
            "status": agg,
            "execution_status": agg,
            "aggregate_status": agg,
            "reason": None,
            "results": runs,
            "metrics": metrics,
            "readme": (
                f"# RQ5 Agent Execution\n\nSTATUS: `{agg}`\n"
                f"N_runs={len(runs)}\n"
                f"dataset_hash={manifest['dataset_hash']}\n"
                "Metrics: overall + A_raw/B_structured/C_vibeprompt; "
                "full_execution_grid vs completed_agent_quality.\n"
            ),
        }

    return run_experiment(config=exp_config, out_dir=out_dir, execute=execute)


if __name__ == "__main__":
    payload = main()
    status = payload.get("status")
    reason = payload.get("reason")
    if status == "NOT EXECUTED" or payload.get("aggregate_status") == "NOT_EXECUTED":
        print("RQ5 NOT EXECUTED")
        print(f"Reason: {reason or 'agent command unavailable'}")
    print(
        json.dumps(
            {
                "status": status,
                "aggregate_status": payload.get("aggregate_status"),
                "reason": reason,
                "metrics_keys": list((payload.get("metrics") or {}).keys()),
            },
            indent=2,
        )
    )
