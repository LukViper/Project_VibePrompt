"""RQ3 dataset — ≥100 controlled scenarios with gold attack ontology annotations.

Label: SYNTHETIC CONTROLLED BENCHMARK
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "evaluation" / "datasets" / "rq3" / "scenarios_v2.json"

DATASET_LABEL = "SYNTHETIC CONTROLLED BENCHMARK"

# Explicit ontology scenarios: (scenario, target_entity_type, attack_type, severity, expected_issue, evidence)
_SCENARIO_SEEDS: list[tuple[str, str, str, str, str, str]] = [
    (
        "Train a 7B model locally on hardware with insufficient VRAM.",
        "ASSUMPTION",
        "RESOURCE_FEASIBILITY",
        "HIGH",
        "insufficient GPU memory",
        "VRAM/hardware specification",
    ),
    (
        "Real-time analytics dashboard with no latency requirement stated.",
        "REQUIREMENT",
        "LATENCY",
        "HIGH",
        "unspecified real-time latency",
        "latency SLA",
    ),
    (
        "Achieve 99.99% accuracy without an evaluation plan.",
        "CLAIM",
        "EVALUATION",
        "HIGH",
        "missing evaluation methodology",
        "metrics and validation set",
    ),
    (
        "AI blockchain IoT mobile cloud product in four weeks solo.",
        "CONSTRAINT",
        "SCOPE",
        "HIGH",
        "scope exceeds timeline/staffing",
        "MVP scope reduction",
    ),
    (
        "Deep learning classifier with no dataset identified.",
        "ASSUMPTION",
        "DATA_AVAILABILITY",
        "HIGH",
        "no concrete dataset",
        "dataset name or collection plan",
    ),
    (
        "Security monitoring without a threat model.",
        "ASSUMPTION",
        "SECURITY",
        "MEDIUM",
        "missing threat model",
        "threat model document",
    ),
    (
        "Production deploy without monitoring.",
        "DECISION",
        "DEPLOYMENT",
        "MEDIUM",
        "no observability",
        "monitoring and rollback criteria",
    ),
    (
        "High availability without redundancy.",
        "ARCHITECTURE",
        "RELIABILITY",
        "HIGH",
        "availability without failover",
        "redundancy design",
    ),
    (
        "Use Kafka because it is modern, with no throughput justification.",
        "DECISION",
        "TECHNOLOGY_JUSTIFICATION",
        "MEDIUM",
        "unjustified technology choice",
        "load/throughput evidence",
    ),
    (
        "REST polling for a real-time collaborative editor.",
        "ARCHITECTURE",
        "ARCHITECTURE_MISMATCH",
        "HIGH",
        "transport mismatch for real-time",
        "websocket or push design",
    ),
    (
        "Enterprise multi-region system with a two-week solo deadline.",
        "CONSTRAINT",
        "TIMELINE",
        "HIGH",
        "timeline incompatible with scope",
        "reduced MVP",
    ),
    (
        "Store PII in logs without retention or access controls.",
        "REQUIREMENT",
        "SECURITY",
        "HIGH",
        "PII handling gap",
        "data handling policy",
    ),
    (
        "Scale to millions of users on a single VM assumption.",
        "ASSUMPTION",
        "SCALABILITY",
        "HIGH",
        "single-node scale assumption",
        "capacity plan",
    ),
    (
        "Budget is $0 but plan includes managed Kubernetes and paid APIs.",
        "CONSTRAINT",
        "COST",
        "HIGH",
        "cost contradiction",
        "cost model",
    ),
    (
        "System should somehow handle appropriate authentication etc.",
        "REQUIREMENT",
        "REQUIREMENT_AMBIGUITY",
        "MEDIUM",
        "vague acceptance criteria",
        "measurable auth requirements",
    ),
    (
        "Depend on an unmaintained GitHub library for core crypto.",
        "DECISION",
        "DEPENDENCY",
        "HIGH",
        "risky dependency",
        "supported crypto library",
    ),
    (
        "Claim the model can be trained locally without measuring resources.",
        "CLAIM",
        "RESOURCE_FEASIBILITY",
        "HIGH",
        "unverified local training claim",
        "hardware benchmark",
    ),
    (
        "Contradiction: must be offline-only and also require live cloud APIs.",
        "REQUIREMENT",
        "CONTRADICTION",
        "HIGH",
        "offline vs cloud contradiction",
        "resolved mode decision",
    ),
    (
        "Maintainability ignored: no tests, no CI, production launch next week.",
        "ASSUMPTION",
        "MAINTAINABILITY",
        "MEDIUM",
        "no maintainability plan",
        "test/CI plan",
    ),
    (
        "Assumption that public phishing corpora are legally usable without review.",
        "ASSUMPTION",
        "DATA_AVAILABILITY",
        "MEDIUM",
        "licensing assumption",
        "license check",
    ),
]


def generate_rq3_scenarios(n: int = 120) -> list[dict]:
    rows = []
    for i in range(n):
        scenario, target, attack, severity, issue, evidence = _SCENARIO_SEEDS[i % len(_SCENARIO_SEEDS)]
        rows.append(
            {
                "id": f"RQ3-{i + 1:03d}",
                "dataset_label": DATASET_LABEL,
                "synthetic": True,
                "scenario": scenario,
                "project_objective": scenario,
                "requirements": [scenario],
                "target_entity_type": target,
                "attack_type": attack,
                "severity": severity,
                "expected_issue": issue,
                "expected_evidence": evidence,
                "gold_should_block": severity == "HIGH",
                # Legacy fields for older scorers
                "gold_issue_tags": [attack.lower(), issue.split()[0].lower()],
                "gold_severity": severity,
                "variant": i % len(_SCENARIO_SEEDS),
            }
        )
    return rows


def write_dataset(n: int = 120, path: Path | None = None) -> Path:
    path = path or DATA_PATH
    rows = generate_rq3_scenarios(n=n)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return path


def load_dataset(path: Path | None = None) -> list[dict]:
    path = path or DATA_PATH
    if not path.exists():
        write_dataset(path=path)
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    p = write_dataset()
    print(json.dumps({"path": str(p), "n": len(load_dataset())}, indent=2))
