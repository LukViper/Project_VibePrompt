"""RQ3 Grill diagnostics — explain missed / mismatched attacks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def diagnose_case(case: dict, prediction: dict) -> dict[str, Any] | None:
    """Return a diagnostic row when gold attack is missed or mismatched."""
    gold_type = case.get("attack_type") or case.get("gold_attack_type")
    gold_target = case.get("target_entity_type") or case.get("gold_target_entity_type")
    gold_severity = case.get("severity") or case.get("gold_severity")

    pred_types = set(prediction.get("predicted_attack_types") or [])
    pred_targets = set(prediction.get("predicted_target_types") or [])
    pred_severities = set(prediction.get("predicted_severities") or [])

    type_ok = gold_type in pred_types if gold_type else True
    target_ok = gold_target in pred_targets if gold_target else True
    # Severity: any predicted severity matching gold counts
    sev_ok = (gold_severity in pred_severities) if gold_severity else True

    detected = bool(prediction.get("detected"))
    if detected and type_ok and target_ok:
        return None  # no miss

    reasons = []
    if not detected:
        reasons.append("attack_not_detected")
    if detected and not type_ok:
        reasons.append("attack_type_mismatch")
    if detected and not target_ok:
        reasons.append("target_mismatch")
    if detected and not sev_ok:
        reasons.append("severity_mismatch")
    if not prediction.get("attacks"):
        reasons.append("no_attacks_generated")

    return {
        "scenario": case.get("scenario") or case.get("project_objective") or case.get("id"),
        "id": case.get("id"),
        "gold_target": gold_target,
        "predicted_target": sorted(pred_targets) or None,
        "gold_attack_type": gold_type,
        "predicted_attack_type": sorted(pred_types) or None,
        "gold_severity": gold_severity,
        "predicted_severity": sorted(pred_severities) or None,
        "reason_for_mismatch": "; ".join(reasons) or "unknown",
        "expected_issue": case.get("expected_issue"),
        "n_attacks": len(prediction.get("attacks") or []),
    }


def build_diagnostics(cases: list[dict], predictions: list[dict]) -> list[dict]:
    rows = []
    by_id = {p.get("id"): p for p in predictions}
    for case in cases:
        pred = by_id.get(case["id"]) or {}
        row = diagnose_case(case, pred)
        if row:
            rows.append(row)
    return rows


def write_diagnostics(out_dir: Path, rows: list[dict], *, metrics: dict | None = None) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rq3_diagnostics.json"
    md_path = out_dir / "rq3_diagnostics.md"
    payload = {
        "n_misses": len(rows),
        "misses": rows,
        "metrics_snapshot": metrics or {},
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# RQ3 Grill Diagnostics",
        "",
        f"Missed / mismatched attacks: **{len(rows)}**",
        "",
        "Do not hide low recall. This file explains failure modes.",
        "",
        "| id | gold target | pred target | gold type | pred type | reason |",
        "|----|-------------|-------------|-----------|-----------|--------|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('id')} | {r.get('gold_target')} | {r.get('predicted_target')} | "
            f"{r.get('gold_attack_type')} | {r.get('predicted_attack_type')} | {r.get('reason_for_mismatch')} |"
        )
    # Failure mode histogram
    from collections import Counter

    counts = Counter(r.get("reason_for_mismatch") for r in rows)
    lines.extend(["", "## Failure mode counts", ""])
    for reason, n in counts.most_common():
        lines.append(f"- `{reason}`: {n}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
