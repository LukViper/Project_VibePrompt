"""RQ5 — Real coding-agent execution harness (scientific runner).

Without VIBEPROMPT_AGENT_CMD:

```text
RQ5 NOT EXECUTED
Reason: agent command unavailable
```

Uses tasks_v2 by default. Never fabricates scientific results.

Optional pilot subset (does not change default full-run semantics):

```bash
python -m evaluation.rq5_agent_execution.run --task-id rest_echo_api
python -m evaluation.rq5_agent_execution.run --task-id rest_echo_api --variant C_vibeprompt
```
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

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


def select_run_matrix(
    tasks: list[dict],
    *,
    task_id: str | None = None,
    variant: str | None = None,
) -> tuple[list[dict], tuple[str, ...], dict[str, Any]]:
    """Select task/variant cells for execution.

    Default (no filters): all tasks × all VARIANTS (12 × 3 = 36).

    ``task_id`` / ``variant`` may be a single value or a comma-separated list.
    Combined filters produce the Cartesian product of the selected sets.
    """
    available_ids = [t["task_id"] for t in tasks]
    selected_task_ids = _parse_csv_filter(task_id)
    selected_variant_names = _parse_csv_filter(variant)

    if selected_task_ids is not None:
        invalid = [tid for tid in selected_task_ids if tid not in available_ids]
        if invalid:
            raise ValueError(
                f"Invalid task-id {invalid[0]!r}. Valid task IDs: {', '.join(available_ids)}"
            )
        id_set = set(selected_task_ids)
        selected_tasks = [t for t in tasks if t["task_id"] in id_set]
        # Preserve caller order for selected_task_ids metadata
        order = {tid: i for i, tid in enumerate(selected_task_ids)}
        selected_tasks.sort(key=lambda t: order.get(t["task_id"], 0))
    else:
        selected_tasks = list(tasks)

    if selected_variant_names is not None:
        invalid_v = [v for v in selected_variant_names if v not in VARIANTS]
        if invalid_v:
            raise ValueError(
                f"Invalid variant {invalid_v[0]!r}. Valid variants: {', '.join(VARIANTS)}"
            )
        selected_variants: tuple[str, ...] = tuple(selected_variant_names)
    else:
        selected_variants = tuple(VARIANTS)

    n_planned = len(selected_tasks) * len(selected_variants)
    is_full = (
        selected_task_ids is None
        and selected_variant_names is None
        and len(selected_tasks) == len(tasks)
        and selected_variants == tuple(VARIANTS)
    )
    subset_meta = {
        "selection_mode": "FULL_SCIENTIFIC" if is_full else "PILOT_SUBSET",
        "filter_task_id": task_id,
        "filter_variant": variant,
        "selected_task_ids": [t["task_id"] for t in selected_tasks],
        "selected_variants": list(selected_variants),
        "n_tasks_selected": len(selected_tasks),
        "n_variants_selected": len(selected_variants),
        "n_runs_planned": n_planned,
        "n_runs_full_grid": len(tasks) * len(VARIANTS),
        "is_full_scientific_grid": is_full,
        "note": (
            "Full scientific grid (all tasks × all variants)."
            if is_full
            else "Pilot subset — not the full 36-run scientific grid."
        ),
    }
    return selected_tasks, selected_variants, subset_meta


def _parse_csv_filter(value: str | None) -> list[str] | None:
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        raise ValueError("Filter value must not be empty")
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _enforce_full_grid_ack(subset_meta: dict[str, Any], *, agent_available: bool) -> None:
    """Require explicit ack before launching the full 36-run scientific grid."""
    if not agent_available or not subset_meta.get("is_full_scientific_grid"):
        return
    if os.environ.get("VIBEPROMPT_RQ5_ALLOW_FULL_GRID", "").strip() == "1":
        return
    raise ValueError(
        "Refusing to launch the full 36-run scientific grid without explicit ack. "
        "Use --task-id / --variant for a pilot subset, or set "
        "VIBEPROMPT_RQ5_ALLOW_FULL_GRID=1 after reviewing the pilot and protocol."
    )


def _infra_failure_record(
    *,
    task: dict,
    variant: str,
    experiment_id: str,
    exc: BaseException,
) -> dict[str, Any]:
    """Structured cell when run_single raises — never fabricates PASS."""
    return {
        "workspace_id": None,
        "experiment_id": experiment_id,
        "task_id": task.get("task_id"),
        "system_variant": variant,
        "dataset_version": task.get("dataset_version"),
        "execution_status": "FAILED_INFRASTRUCTURE",
        "overall_outcome": "EXECUTION_FAILED",
        "failure_category": "harness_exception",
        "exit_code": None,
        "duration_seconds": None,
        "build_status": None,
        "test_status": None,
        "requirement_verifications": [],
        "unsupported_features": [],
        "constraint_violations": [],
        "scope_violations": [],
        "error": f"{type(exc).__name__}: {exc}",
        "label": "SCIENTIFIC",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RQ5 agent execution harness (scientific or pilot subset)."
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help=(
            "Restrict to one task_id or a comma-separated list from tasks_v2 (pilot). "
            "Default: all tasks."
        ),
    )
    parser.add_argument(
        "--variant",
        default=None,
        help=(
            f"Restrict to one variant or a comma-separated list. "
            f"Valid: {', '.join(VARIANTS)}. Default: all."
        ),
    )
    return parser.parse_args(argv)


def main(*, task_id: str | None = None, variant: str | None = None) -> dict:
    config = load_rq5_config(harness_test=False)
    tasks, manifest = _ensure_v2()
    selected_tasks, selected_variants, subset_meta = select_run_matrix(
        tasks, task_id=task_id, variant=variant
    )
    _enforce_full_grid_ack(subset_meta, agent_available=config.agent_available)

    selected_ids = [t["task_id"] for t in selected_tasks]
    exp_mode = (
        "SCIENTIFIC"
        if subset_meta["is_full_scientific_grid"]
        else subset_meta["selection_mode"]
    )
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
            # Reflect the *selected* grid in config.json so pilots cannot be
            # misread as the full 12-task scientific study.
            "n_tasks": len(selected_tasks),
            "task_ids": selected_ids,
            "dataset_n_tasks": manifest["n_tasks"],
            "dataset_task_ids": manifest["task_ids"],
            "rq5_config": config.to_dict(),
            "variants": list(selected_variants),
            "dataset_variants": list(VARIANTS),
            "mode": exp_mode,
            "protocol": "RQ5_PROTOCOL_v2",
            "run_subset": subset_meta,
            "is_full_scientific_grid": subset_meta["is_full_scientific_grid"],
        },
    )
    out_dir = new_run_dir("rq5") / "rq5"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_root = out_dir / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (out_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "run_subset.json").write_text(
        json.dumps(subset_meta, indent=2) + "\n", encoding="utf-8"
    )

    def execute():
        tasks_out = []
        for task in selected_tasks:
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
                "run_subset": subset_meta,
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
                    "run_subset": subset_meta,
                    "note": "RQ5 NOT EXECUTED — Reason: agent command unavailable. "
                    "Null metrics mean not measured, not zero performance.",
                },
                "readme": (
                    "# RQ5 Agent Execution\n\n"
                    "```text\nRQ5 NOT EXECUTED\nReason: agent command unavailable\n```\n\n"
                    f"Dataset: `{manifest['dataset_id']}` {manifest['dataset_version']} "
                    f"hash `{manifest['dataset_hash']}`\n\n"
                    f"Run subset: `{subset_meta['selection_mode']}` "
                    f"(n_runs_planned={subset_meta['n_runs_planned']})\n"
                ),
            }

        runs = []
        work_root = Path(tempfile.mkdtemp(prefix="vibeprompt_rq5_sci_"))
        try:
            for task in selected_tasks:
                for var in selected_variants:
                    try:
                        runs.append(
                            run_single(
                                task=task,
                                variant=var,
                                config=config,
                                work_root=work_root,
                                artifact_root=artifact_root,
                                label="SCIENTIFIC",
                                experiment_id=exp_config.experiment_id,
                            )
                        )
                    except Exception as exc:  # noqa: BLE001 — isolate cell failure
                        runs.append(
                            _infra_failure_record(
                                task=task,
                                variant=var,
                                experiment_id=exp_config.experiment_id,
                                exc=exc,
                            )
                        )
        finally:
            import shutil

            shutil.rmtree(work_root, ignore_errors=True)

        (out_dir / "runs.json").write_text(json.dumps(runs, indent=2) + "\n", encoding="utf-8")
        metrics = compute_rq5_metrics(runs)
        metrics["dataset_hash"] = manifest["dataset_hash"]
        metrics["run_subset"] = subset_meta
        agg = aggregate_experiment_status(runs, agent_available=True)
        return {
            "status": agg,
            "execution_status": agg,
            "aggregate_status": agg,
            "reason": None,
            "results": runs,
            "run_subset": subset_meta,
            "metrics": metrics,
            "readme": (
                f"# RQ5 Agent Execution\n\nSTATUS: `{agg}`\n"
                f"N_runs={len(runs)}\n"
                f"dataset_hash={manifest['dataset_hash']}\n"
                f"selection_mode={subset_meta['selection_mode']}\n"
                f"is_full_scientific_grid={subset_meta['is_full_scientific_grid']}\n"
                "Metrics: overall + A_raw/B_structured/C_vibeprompt; "
                "full_execution_grid vs completed_agent_quality.\n"
            ),
        }

    return run_experiment(config=exp_config, out_dir=out_dir, execute=execute)


if __name__ == "__main__":
    args = parse_args()
    try:
        payload = main(task_id=args.task_id, variant=args.variant)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
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
                "run_subset": payload.get("run_subset")
                or (payload.get("metrics") or {}).get("run_subset"),
                "metrics_keys": list((payload.get("metrics") or {}).keys()),
            },
            indent=2,
        )
    )
