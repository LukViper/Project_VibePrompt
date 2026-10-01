"""Experiment runner utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from evaluation.common.schemas import ExperimentConfig
from evaluation.common.seeds import set_seed
from evaluation.common.serialization import write_json

ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = ROOT / "evaluation" / "results"


def new_run_dir(prefix: str | None = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    name = f"{stamp}_{prefix}" if prefix else stamp
    path = RESULTS_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_experiment(
    *,
    config: ExperimentConfig,
    out_dir: Path,
    execute: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    set_seed(config.random_seed)
    write_json(out_dir / "config.json", config.to_dict())
    payload = execute()
    write_json(out_dir / "results.json", payload.get("results", payload))
    write_json(out_dir / "metrics.json", payload.get("metrics", {}))
    readme = payload.get("readme") or _default_readme(config, payload)
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    return payload


def _default_readme(config: ExperimentConfig, payload: dict[str, Any]) -> str:
    status = payload.get("status", "COMPLETED")
    return (
        f"# {config.experiment_id}\n\n"
        f"- status: `{status}`\n"
        f"- dataset: `{config.dataset_id}` v{config.dataset_version}\n"
        f"- seed: `{config.random_seed}`\n"
        f"- n: `{payload.get('metrics', {}).get('n', 'see metrics.json')}`\n"
        f"- timestamp: `{config.timestamp}`\n"
    )


def embedding_metadata_safe() -> dict[str, Any]:
    try:
        import sys

        sys.path.insert(0, str(ROOT / "backend"))
        from app.nlp.embeddings import embedding_metadata

        return embedding_metadata()
    except Exception as exc:  # pragma: no cover
        return {"provider": "unavailable", "error": str(exc)}
