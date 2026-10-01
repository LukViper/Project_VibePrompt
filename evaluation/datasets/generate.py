"""Generate synthetic controlled benchmarks for RQ1–RQ5.

Datasets are explicitly labeled SYNTHETIC CONTROLLED BENCHMARK.
They do not claim real-world generalization. Metric implementations accept
future real-world datasets with the same schema.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets"
DATASET_LABEL = "SYNTHETIC CONTROLLED BENCHMARK"


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def generate_rq1(n: int = 120) -> Path:
    """≥100 conversations; gold is evaluation-only (see rq1_requirement_preservation)."""
    from evaluation.rq1_requirement_preservation.dataset import write_dataset

    out_v2 = write_dataset(n=n)
    rows = json.loads(out_v2.read_text(encoding="utf-8"))
    legacy = []
    for row in rows:
        legacy.append(
            {
                "id": row["id"],
                "synthetic": True,
                "dataset_label": DATASET_LABEL,
                "messages": row["messages"],
                "gold_requirements": row["gold_requirements"],
                "gold_constraints": row["gold_constraints"],
                "rejected": row["rejected"],
                "superseded": row["superseded"],
                "variant": row.get("variant", 0),
            }
        )
    out = DATA / "rq1" / "scenarios_v1.json"
    _write(out, legacy)
    return out


def generate_rq2(n: int = 50) -> Path:
    rows = []
    change_types = [
        "requirement_addition",
        "requirement_modification",
        "requirement_removal",
        "technology_change",
        "constraint_change",
        "architecture_change",
        "scope_change",
        "dataset_change",
        "deployment_change",
        "security_requirement_change",
    ]
    for i in range(n):
        ctype = change_types[i % len(change_types)]
        rows.append(
            {
                "id": f"RQ2-{i+1:03d}",
                "synthetic": True,
                "dataset_label": DATASET_LABEL,
                "change_type": ctype,
                "before": {
                    "requirements": ["web application dashboard"],
                    "decisions": ["react frontend", "rest api"],
                    "architecture": ["browser spa"],
                    "tests": ["browser integration test"],
                },
                "change": {
                    "requirement_modification": "android and web application",
                    "technology_change": "replace react with flutter",
                    "requirement_removal": "remove dashboard analytics",
                    "requirement_addition": "add offline mode",
                    "constraint_change": "solo developer two weeks",
                    "architecture_change": "move to modular monolith",
                    "scope_change": "mvp only core alerts",
                    "dataset_change": "use public phishing corpus",
                    "deployment_change": "deploy to single vps",
                    "security_requirement_change": "require oauth2 login",
                }[ctype],
                "gold_impact": {
                    "decisions": ["react frontend"] if "react" in ctype or "android" in ctype or "technology" in ctype else [],
                    "architecture": ["browser spa"] if ctype in {"architecture_change", "requirement_modification", "technology_change"} else [],
                    "tests": ["browser integration test"] if ctype in {"requirement_modification", "technology_change", "architecture_change"} else [],
                    "prompt": True,
                },
            }
        )
    out = DATA / "rq2" / "scenarios_v1.json"
    _write(out, rows)
    return out


def generate_rq3(n: int = 120) -> Path:
    from evaluation.rq3_grill.dataset import write_dataset

    out_v2 = write_dataset(n=n)
    rows = json.loads(out_v2.read_text(encoding="utf-8"))
    legacy = []
    for row in rows:
        legacy.append(
            {
                "id": row["id"],
                "synthetic": True,
                "dataset_label": DATASET_LABEL,
                "project_objective": row["project_objective"],
                "requirements": row["requirements"],
                "gold_issue_tags": row.get("gold_issue_tags") or [],
                "gold_severity": row.get("severity"),
                "gold_should_block": row.get("gold_should_block"),
                "attack_type": row.get("attack_type"),
                "target_entity_type": row.get("target_entity_type"),
                "expected_issue": row.get("expected_issue"),
                "expected_evidence": row.get("expected_evidence"),
            }
        )
    out = DATA / "rq3" / "scenarios_v1.json"
    _write(out, legacy)
    return out


def generate_rq4(n: int = 50) -> Path:
    rows = []
    cases = [
        ("Use BERT for classification", "paper comparing BERT and TF-IDF", "supported", True),
        ("Use Kubernetes", "", "unsupported", False),
        ("Use WebSocket", "latency requires sub-500ms push", "supported", True),
        ("Use PostgreSQL", "unverified blog post", "unverified", False),
        ("Use blockchain for auth", "contradictory cost analysis opposing blockchain", "contradicted", False),
    ]
    for i in range(n):
        decision, evidence, label, backed = cases[i % len(cases)]
        rows.append(
            {
                "id": f"RQ4-{i+1:03d}",
                "synthetic": True,
                "dataset_label": DATASET_LABEL,
                "decision": decision,
                "evidence_text": evidence,
                "evidence_verified": label == "supported",
                "gold_label": label,
                "gold_evidence_backed": backed,
            }
        )
    out = DATA / "rq4" / "scenarios_v1.json"
    _write(out, rows)
    return out


def generate_rq5(n: int = 12) -> Path:
    tasks = [
        ("rest_echo_api", "Build a REST API that echoes JSON payloads", ["POST /echo returns body", "health endpoint"]),
        ("auth_token_service", "Build a token auth service", ["register user", "login returns token", "protected route"]),
        ("crud_notes", "CRUD notes API", ["create note", "list notes", "delete note"]),
        ("log_parser", "Parse syslog lines into JSON", ["parse severity", "parse timestamp"]),
        ("csv_filter_cli", "CLI that filters CSV by column", ["filter rows", "write output file"]),
        ("word_count_pipeline", "Count words in a directory of texts", ["recursive read", "sorted counts"]),
        ("todo_backend", "Minimal todo backend", ["add todo", "complete todo"]),
        ("url_shortener", "URL shortener service", ["create short url", "redirect"]),
        ("rate_limiter", "In-memory rate limiter middleware", ["limit per key", "return 429"]),
        ("file_checksum", "Compute file checksums", ["sha256", "report missing files"]),
        ("json_schema_validator", "Validate JSON against a schema", ["accept valid", "reject invalid"]),
        ("metrics_aggregator", "Aggregate numeric metrics from JSONL", ["mean", "count"]),
    ]
    rows = []
    for i in range(min(n, len(tasks))):
        task_id, statement, acceptance = tasks[i]
        rows.append(
            {
                "id": f"RQ5-{i+1:03d}",
                "synthetic": True,
                "dataset_label": DATASET_LABEL,
                "task_id": task_id,
                "problem_statement": statement,
                "gold_requirements": acceptance,
                "acceptance_tests": [f"test_{task_id}_{j}" for j in range(len(acceptance))],
                "constraints": ["python 3.11+", "no network in tests"],
            }
        )
    out = DATA / "rq5" / "tasks_v1.json"
    _write(out, rows)
    return out


def generate_all() -> dict[str, str]:
    paths = {
        "rq1": str(generate_rq1()),
        "rq2": str(generate_rq2()),
        "rq3": str(generate_rq3()),
        "rq4": str(generate_rq4()),
        "rq5": str(generate_rq5()),
    }
    meta = {
        "dataset_id": "vibeprompt-synthetic-bench",
        "version": "2.0.0",
        "creation_method": "programmatic_templates",
        "synthetic": True,
        "dataset_label": DATASET_LABEL,
        "paths": paths,
        "known_limitations": [
            "SYNTHETIC CONTROLLED BENCHMARK — not a real-user corpus",
            "Limited lexical diversity across template variants",
            "No claim of real-world generalization",
            "RQ5 tasks are harness-only until VIBEPROMPT_AGENT_CMD is set",
            "Metric code accepts future real-world datasets with the same schema",
        ],
    }
    _write(DATA / "manifest_v1.json", [meta])
    return paths


if __name__ == "__main__":
    print(json.dumps(generate_all(), indent=2))
