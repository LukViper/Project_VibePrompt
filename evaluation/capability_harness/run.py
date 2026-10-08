"""Capability harness — hit ideas / architecture / grill APIs across domains.

Ensures VibePrompt capabilities are processed under gates (not free-form misuse):
  - ideation requires a subject/domain and stays on-domain
  - architecture requires project substance
  - grill requires something real to challenge

Usage:
  cd /path/to/Prompting
  python -m evaluation.capability_harness.run
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///evaluation_capability.db")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("GEMINI_API_KEY", "")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.session import engine  # noqa: E402
from app.main import app  # noqa: E402

# Domains exercised through the live API under the capability harness.
CASES = [
    {
        "id": "computer_networks",
        "seed": "for computer networks ?",
        "forbid_in_ideas": ["churn", "sales forecasting", "customer segmentation"],
        "require_any_in_ideas": ["network", "protocol", "traffic", "sdn", "wireless", "packet"],
    },
    {
        "id": "nlp",
        "seed": "I need a project for NLP.",
        "forbid_in_ideas": ["sales forecasting"],
        "require_any_in_ideas": ["text", "language", "nlp", "citation", "forum", "classif", "phish"],
    },
    {
        "id": "cybersecurity",
        "seed": "I need a cybersecurity project.",
        "forbid_in_ideas": ["sales forecasting", "customer churn"],
        "require_any_in_ideas": ["phish", "security", "log", "vulnerab", "malware", "threat"],
    },
    {
        "id": "data_science",
        "seed": "I want a data science project.",
        "forbid_in_ideas": [],
        "require_any_in_ideas": ["churn", "forecast", "segment", "fraud", "demand", "predict"],
    },
]


def _titles(ideas: list) -> str:
    return " ".join(str(item.get("title") or "") for item in ideas).lower()


def _run_case(client: TestClient, case: dict) -> dict:
    created = client.post("/projects", json={"description": case["seed"]})
    project_id = created.json()["id"]
    state = client.get(f"/projects/{project_id}/state").json()
    subject = ((state.get("academic") or {}).get("subject") or "").lower()

    # Empty-capability misuse checks on a fresh blank project are separate;
    # here we always seed a domain first.
    ideas_resp = client.post(f"/projects/{project_id}/ideas")
    arch_before_idea = None
    grill_before_idea = None

    # Architecture / grill should still gate if only subject exists (no core idea).
    # After ideation+select they should succeed.
    result = {
        "case": case["id"],
        "seed": case["seed"],
        "subject": subject,
        "checks": {},
    }

    result["checks"]["ideas_http_ok"] = ideas_resp.status_code == 200
    ideas = ideas_resp.json() if ideas_resp.status_code == 200 else []
    if not isinstance(ideas, list):
        ideas = ideas.get("ideas") or []
    blob = _titles(ideas)
    result["checks"]["ideas_count"] = len(ideas) >= 3
    result["checks"]["no_forbidden"] = all(tok not in blob for tok in case["forbid_in_ideas"])
    result["checks"]["has_domain_signal"] = any(tok in blob for tok in case["require_any_in_ideas"]) if ideas else False

    # Gate: architecture before selecting an idea may still pass if subject alone
    # filled objective — assert grill/architecture after select.
    if ideas:
        chosen = ideas[0]
        client.post(f"/projects/{project_id}/ideas/{chosen['id']}/select")

    arch = client.post(f"/projects/{project_id}/architecture")
    result["checks"]["architecture_ok"] = arch.status_code == 200
    if arch.status_code == 200:
        body = arch.json()
        result["checks"]["architecture_harness"] = (body.get("provenance") or {}).get("harness") == "capability_harness"

    grill = client.post(f"/projects/{project_id}/grill")
    result["checks"]["grill_ok"] = grill.status_code == 200
    if grill.status_code == 200:
        body = grill.json()
        result["checks"]["grill_harness"] = (body.get("provenance") or {}).get("harness") == "capability_harness"

    # Misuse: blank project must not allow free-form capability spam.
    blank = client.post("/projects", json={"title": "Empty"}).json()["id"]
    blank_ideas = client.post(f"/projects/{blank}/ideas")
    blank_arch = client.post(f"/projects/{blank}/architecture")
    blank_grill = client.post(f"/projects/{blank}/grill")
    result["checks"]["blank_ideas_gated"] = blank_ideas.status_code == 400
    result["checks"]["blank_architecture_gated"] = blank_arch.status_code == 400
    result["checks"]["blank_grill_gated"] = blank_grill.status_code == 400

    result["idea_titles"] = [i.get("title") for i in ideas[:5]]
    result["passed"] = all(result["checks"].values())
    result["arch_probe"] = arch_before_idea
    result["grill_probe"] = grill_before_idea
    return result


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    results = [_run_case(client, case) for case in CASES]
    summary = {
        "harness": "capability_harness",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cases": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "results": results,
    }
    out = ROOT / "evaluation" / "results"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    path = out / f"{stamp}_capability_harness.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "capability_harness_latest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if summary["passed"] != summary["cases"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
