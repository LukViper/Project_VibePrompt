"""Generate REPORT.md from the latest evaluation results directory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def latest_run() -> Path | None:
    if not RESULTS.exists():
        return None
    # Prefer runs that contain summary.json (full suite), else newest directory.
    with_summary = sorted(
        [p for p in RESULTS.iterdir() if p.is_dir() and (p / "summary.json").exists()],
        key=lambda p: p.name,
    )
    if with_summary:
        return with_summary[-1]
    runs = sorted([p for p in RESULTS.iterdir() if p.is_dir()], key=lambda p: p.name)
    return runs[-1] if runs else None


def main(run_dir: Path | None = None) -> Path:
    run_dir = run_dir or latest_run()
    if run_dir is None:
        raise SystemExit("No evaluation results found. Run: python -m evaluation.run_all")
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {"run_dir": str(run_dir), "experiments": {}}
        for child in run_dir.iterdir():
            metrics = child / "metrics.json"
            if metrics.exists():
                summary["experiments"][child.name] = {
                    "status": "UNKNOWN",
                    "metrics": json.loads(metrics.read_text(encoding="utf-8")),
                }

    lines = [
        "# VibePrompt Evaluation Report",
        "",
        f"Run directory: `{run_dir}`",
        "",
        "## Experiments",
        "",
    ]
    for name, payload in (summary.get("experiments") or {}).items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- status: `{payload.get('status')}`")
        if payload.get("reason"):
            lines.append(f"- reason: {payload['reason']}")
        metrics = payload.get("metrics") or {}
        lines.append("```json")
        lines.append(json.dumps(metrics, indent=2))
        lines.append("```")
        lines.append("")
    lines.extend(
        [
            "## Limitations",
            "",
            "- Synthetic datasets — not real-world generalization.",
            "- RQ1 vibeprompt column is gold-state compile upper bound.",
            "- RQ5 agent metrics are null until an agent is configured.",
            "- Small-N CIs use normal approximation; interpret cautiously.",
            "",
            "## Fabrication policy",
            "",
            "This report is generated only from written `metrics.json` / `summary.json` files.",
            "",
        ]
    )
    report = run_dir / "REPORT.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report}")
    return report


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    main(target)
