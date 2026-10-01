"""Run all evaluation experiments into a timestamped results directory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from evaluation.common.reporting import new_run_dir  # noqa: E402
from evaluation.common.serialization import write_json  # noqa: E402
from evaluation.datasets.generate import generate_all  # noqa: E402
from evaluation.rq1_requirement_preservation import run as rq1  # noqa: E402
from evaluation.rq2_change_impact import run as rq2  # noqa: E402
from evaluation.rq3_grill import run as rq3  # noqa: E402
from evaluation.rq4_evidence import run as rq4  # noqa: E402
from evaluation.rq5_agent_execution import run as rq5  # noqa: E402


def main() -> Path:
    generate_all()
    run_root = new_run_dir("full")
    summary = {"run_dir": str(run_root), "experiments": {}}
    for name, mod in [
        ("rq1", rq1),
        ("rq2", rq2),
        ("rq3", rq3),
        ("rq4", rq4),
        ("rq5", rq5),
    ]:
        payload = mod.main()
        summary["experiments"][name] = {
            "status": payload.get("status"),
            "reason": payload.get("reason"),
            "metrics": payload.get("metrics"),
        }
    write_json(run_root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return run_root


if __name__ == "__main__":
    main()
