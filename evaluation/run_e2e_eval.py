"""Replay annotated conversations and score requirement retention signals.

The script prints only values it computes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///evaluation_e2e.db")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("GEMINI_API_KEY", "")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.session import engine  # noqa: E402
from app.main import app  # noqa: E402


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    results = []
    for path in sorted((ROOT / "datasets" / "conversations").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        created = client.post("/projects", json={"description": case["messages"][0]}).json()
        project_id = created["id"]
        last = created.get("analysis") or {}
        for message in case["messages"][1:]:
            last = client.post(f"/projects/{project_id}/messages", json={"content": message}).json()
        state = client.get(f"/projects/{project_id}/state").json()
        expected = case["expect"]
        checks = {}
        if "subject" in expected:
            checks["subject"] = state["academic"]["subject"] == expected["subject"]
        if "team_size" in expected:
            checks["team_size"] = state["constraints"]["team_size"] == expected["team_size"]
        if "conflict" in expected:
            open_conflicts = [item for item in state.get("conflicts") or [] if item.get("status") == "open"]
            checks["conflict"] = (len(open_conflicts) > 0) == expected["conflict"]
        if "drift" in expected:
            checks["drift"] = bool((last.get("drift") or state.get("drift") or {}).get("potential_drift")) == expected["drift"]
        if "scope" in expected:
            checks["scope"] = bool((last.get("scope") or state.get("scope") or {}).get("detected")) == expected["scope"]
        if expected.get("specification"):
            spec = client.post(f"/projects/{project_id}/specification")
            prompt = client.post(f"/projects/{project_id}/prompt")
            checks["specification"] = spec.status_code == 200 and "## 18. Acceptance Criteria" in spec.json()["markdown"]
            checks["prompt_coverage"] = prompt.json()["coverage"]["missing"] == []
        results.append({"case": path.name, "checks": checks, "passed": all(checks.values()) if checks else True})
    summary = {"cases": len(results), "passed": sum(item["passed"] for item in results), "results": results}
    out = ROOT / "evaluation" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "e2e_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
