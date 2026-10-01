"""Prompt quality validator and light repair loop.

Metrics: token count, requirement/constraint/acceptance coverage, redundancy,
ambiguity, instruction density. Critical gaps trigger deterministic repair.
"""

from __future__ import annotations

import re
from typing import Any


_AMBIGUOUS = re.compile(
    r"\b(etc\.?|and so on|appropriate|suitable|as needed|somehow|maybe|TBD|TODO)\b",
    re.I,
)
_FILLER = re.compile(
    r"\b(I hope this helps|let me know|feel free|as an AI|happy to help)\b",
    re.I,
)


def estimate_tokens(text: str) -> int:
    # Approx: ~4 chars per token for English technical prose.
    return max(1, len(text) // 4)


def validate_prompt(prompt: str, spec: dict, state: dict | None = None) -> dict[str, Any]:
    state = state or {}
    functional = spec.get("functional") or []
    nonfunctional = spec.get("nonfunctional") or []
    all_reqs = functional + nonfunctional
    req_ids = [r["id"] for r in all_reqs if r.get("id")]
    present_ids = [rid for rid in req_ids if rid in prompt]
    req_coverage = (len(present_ids) / len(req_ids)) if req_ids else 1.0

    constraints = spec.get("constraints") or state.get("constraints") or {}
    constraint_checks = []
    for key in ("team_size", "duration", "budget"):
        value = constraints.get(key)
        if value is None or value == "":
            continue
        constraint_checks.append(str(value) in prompt or key.replace("_", " ") in prompt.lower())
    avoid = constraints.get("avoid") or []
    for item in avoid:
        constraint_checks.append(str(item) in prompt)
    constraint_coverage = (sum(1 for ok in constraint_checks if ok) / len(constraint_checks)) if constraint_checks else 1.0

    with_acceptance = [r for r in all_reqs if r.get("acceptance")]
    acceptance_hits = sum(1 for r in with_acceptance if r.get("acceptance") and r["acceptance"][:40] in prompt)
    # Also count checklist presence.
    checklist = prompt.upper().count("[ ]")
    acceptance_coverage = (
        max(
            (acceptance_hits / len(with_acceptance)) if with_acceptance else 1.0,
            1.0 if checklist >= max(1, len(req_ids)) else 0.5,
        )
        if req_ids
        else 1.0
    )

    lines = [ln.strip() for ln in prompt.splitlines() if ln.strip()]
    unique_ratio = (len(set(lines)) / len(lines)) if lines else 1.0
    redundancy = round(1.0 - unique_ratio, 4)

    ambiguous_hits = len(_AMBIGUOUS.findall(prompt))
    ambiguity = round(min(1.0, ambiguous_hits / max(20, len(lines))), 4)

    instruction_markers = len(re.findall(r"^(Do not|Build|Implement|Write|Create|Keep|Verify)\b", prompt, re.M | re.I))
    instruction_density = round(instruction_markers / max(1, len(lines) / 10), 4)

    filler = bool(_FILLER.search(prompt))
    missing_headings = [
        h for h in ("ACCEPTANCE CRITERIA", "IMPLEMENTATION PROCESS", "DELIVERABLES", "TECH STACK")
        if h not in prompt
    ]
    missing_reqs = [rid for rid in req_ids if rid not in prompt]

    critical = []
    if req_coverage < 1.0:
        critical.append("missing_requirements")
    if missing_headings:
        critical.append("missing_headings")
    if filler:
        critical.append("conversational_filler")

    metrics = {
        "token_count": estimate_tokens(prompt),
        "requirement_coverage": round(req_coverage, 4),
        "constraint_coverage": round(constraint_coverage, 4),
        "acceptance_coverage": round(min(1.0, acceptance_coverage), 4),
        "redundancy": redundancy,
        "ambiguity": ambiguity,
        "instruction_density": instruction_density,
        "missing_requirements": missing_reqs,
    }
    acceptable = (
        req_coverage >= 0.99
        and not filler
        and not missing_headings
        and redundancy <= 0.35
    )
    return {
        "metrics": metrics,
        "critical_gaps": critical,
        "missing_headings": missing_headings,
        "filler_detected": filler,
        "acceptable": acceptable,
        "summary": (
            "Prompt quality acceptable for agent use."
            if acceptable
            else "Prompt needs repair before final acceptance: " + ", ".join(critical or ["quality thresholds"])
        ),
    }


def repair_prompt(prompt: str, spec: dict, report: dict) -> str:
    """Deterministic repairs for critical gaps — no LLM required."""
    fixed = prompt
    for rid in report.get("metrics", {}).get("missing_requirements") or []:
        match = next(
            (r for r in (spec.get("functional") or []) + (spec.get("nonfunctional") or []) if r.get("id") == rid),
            None,
        )
        if match:
            fixed += f"\n{rid}:\n{match.get('text')}\n"
    for heading in report.get("missing_headings") or []:
        fixed += f"\n{heading}\nSee ProjectState specification.\n"
    if report.get("filler_detected"):
        fixed = _FILLER.sub("", fixed)
    # Re-dedupe blank lines
    fixed = re.sub(r"\n{3,}", "\n\n", fixed).strip() + "\n"
    for line in (
        "You are a senior software engineer.",
        "Do not remove or silently alter required functionality.",
        "Do not replace required functionality with placeholders.",
    ):
        if line not in fixed:
            fixed += f"\n{line}\n"
    return fixed


def validate_and_repair(prompt: str, spec: dict, state: dict | None = None, *, max_rounds: int = 2) -> dict:
    current = prompt
    report = validate_prompt(current, spec, state)
    rounds = 0
    while not report["acceptable"] and rounds < max_rounds:
        current = repair_prompt(current, spec, report)
        report = validate_prompt(current, spec, state)
        rounds += 1
    report["repair_rounds"] = rounds
    return {"prompt": current, "report": report}
