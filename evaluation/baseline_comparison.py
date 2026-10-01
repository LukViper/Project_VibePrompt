"""RQ5 comparison scaffold.

Baseline: concatenate the conversation and call it a prompt.
VibePrompt: compile from the structured specification.

Coverage is computed, not assumed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///evaluation_baseline.db")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("GEMINI_API_KEY", "")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.session import engine  # noqa: E402
from app.main import app  # noqa: E402


def coverage(requirements: list[dict], prompt: str) -> float:
    if not requirements:
        return 1.0
    hits = 0
    for req in requirements:
        if req["id"] in prompt or req["text"].lower() in prompt.lower():
            hits += 1
    return hits / len(requirements)


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    rows = []
    path = ROOT / "datasets" / "conversations" / "10_final_specification.json"
    case = json.loads(path.read_text(encoding="utf-8"))
    created = client.post("/projects", json={"description": case["messages"][0]}).json()
    project_id = created["id"]
    state = client.get(f"/projects/{project_id}/state").json()
    active = [req for req in state.get("requirements") or [] if req.get("status") == "active"]
    baseline = "You are a senior software engineer.\n\nConversation:\n" + "\n".join(case["messages"])
    vibe = client.post(f"/projects/{project_id}/prompt").json()["content"]
    rows.append({
        "case": path.name,
        "baseline_coverage": coverage(active, baseline),
        "vibeprompt_coverage": coverage(active, vibe),
        "baseline_has_placeholders_ban": "placeholders" in baseline.lower(),
        "vibeprompt_has_placeholders_ban": "placeholders" in vibe.lower(),
        "requirement_count": len(active),
    })
    out = ROOT / "evaluation" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "baseline_comparison.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
