"""RQ5 metrics — overall + per-variant; full grid vs completed-agent quality views."""

from __future__ import annotations

from typing import Any

from evaluation.common.metrics import summarize

QUALITY_STATUSES = {
    "EXECUTED",
    "EXECUTED_WITH_VALIDATION",
    "EXECUTED_WITH_PARTIAL_VALIDATION",
}


def compute_rq5_metrics(runs: list[dict]) -> dict[str, Any]:
    """Compute metrics with dual views and per-variant breakdowns.

    Quality means exclude FAILED_INFRASTRUCTURE.
    Full execution grid includes all planned cells.
    """
    if not runs:
        return {
            "n": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "unverified_runs": 0,
            "overall": {},
            "note": "no runs",
        }

    successful = sum(1 for r in runs if r.get("execution_status") in QUALITY_STATUSES)
    failed = sum(1 for r in runs if r.get("execution_status") == "FAILED_INFRASTRUCTURE")
    unverified = sum(
        1
        for r in runs
        if (r.get("requirement_verifications") or [])
        and all(v.get("status") == "UNVERIFIED" for v in r["requirement_verifications"])
    )

    completed = [r for r in runs if r.get("execution_status") in QUALITY_STATUSES]

    payload: dict[str, Any] = {
        "n": len(runs),
        "n_planned": len(runs),
        "successful_runs": successful,
        "failed_runs": failed,
        "unverified_runs": unverified,
        "full_execution_grid": _metrics_for_runs(runs, label="full_grid_includes_infrastructure_failures"),
        "completed_agent_quality": _metrics_for_runs(
            completed, label="excludes_FAILED_INFRASTRUCTURE"
        ),
        "overall": _metrics_for_runs(completed, label="alias_of_completed_agent_quality"),
    }

    for variant in ("A_raw", "B_structured", "C_vibeprompt"):
        v_all = [r for r in runs if r.get("system_variant") == variant]
        v_ok = [r for r in v_all if r.get("execution_status") in QUALITY_STATUSES]
        payload[variant] = {
            "n_planned": len(v_all),
            "n_completed": len(v_ok),
            "failed_runs": sum(1 for r in v_all if r.get("execution_status") == "FAILED_INFRASTRUCTURE"),
            "full_execution_grid": _metrics_for_runs(v_all, label="variant_full"),
            "completed_agent_quality": _metrics_for_runs(v_ok, label="variant_quality"),
            # Convenience: primary quality view at top of variant block
            **{
                k: v
                for k, v in _metrics_for_runs(v_ok, label="variant_quality").items()
                if k
                in {
                    "requirement_coverage",
                    "constraint_preservation",
                    "acceptance_test_pass_rate",
                    "build_success_rate",
                    "test_success_rate",
                    "unsupported_feature_rate",
                    "scope_deviation",
                }
            },
        }
    return payload


def _metrics_for_runs(runs: list[dict], *, label: str) -> dict[str, Any]:
    if not runs:
        empty = {"n": 0, "mean": None, "std": None, "ci95_low": None, "ci95_high": None, "median": None}
        return {
            "label": label,
            "n": 0,
            "requirement_coverage": dict(empty),
            "constraint_preservation": dict(empty),
            "acceptance_test_pass_rate": dict(empty),
            "build_success_rate": {"n": 0, "mean": None, "note": "no runs"},
            "test_success_rate": {"n": 0, "mean": None, "note": "no runs"},
            "unsupported_feature_rate": dict(empty),
            "scope_deviation": dict(empty),
        }

    coverage, constraint_pres, accept_pass, build_ok, test_ok, unsupported, scope_dev = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )

    for run in runs:
        vers = run.get("requirement_verifications") or []
        n_req = len(vers) or 1
        n_pass = sum(1 for v in vers if v.get("status") == "PASS")
        coverage.append(n_pass / n_req)

        # Constraint preservation: no rejected-feature hits AND constraint cues respected
        unsupported_hits = list(run.get("unsupported_features") or [])
        constraint_violations = list(run.get("constraint_violations") or [])
        constraint_pres.append(0.0 if (unsupported_hits or constraint_violations) else 1.0)
        unsupported.append(1.0 if unsupported_hits else 0.0)
        # Scope deviation: rejected features OR explicit scope violations
        scope_hits = unsupported_hits + list(run.get("scope_violations") or [])
        scope_dev.append(1.0 if scope_hits else 0.0)

        applicable = [v for v in vers if v.get("status") != "NOT_APPLICABLE"]
        if applicable:
            accept_pass.append(sum(1 for v in applicable if v.get("status") == "PASS") / len(applicable))
        else:
            accept_pass.append(0.0)

        bs = run.get("build_status")
        ts = run.get("test_status")
        if bs == "PASS":
            build_ok.append(1.0)
        elif bs == "FAIL":
            build_ok.append(0.0)
        if ts == "PASS":
            test_ok.append(1.0)
        elif ts == "FAIL":
            test_ok.append(0.0)

    return {
        "label": label,
        "n": len(runs),
        "requirement_coverage": summarize(coverage),
        "constraint_preservation": summarize(constraint_pres),
        "acceptance_test_pass_rate": summarize(accept_pass),
        "build_success_rate": summarize(build_ok)
        if build_ok
        else {"n": 0, "mean": None, "note": "NOT_CONFIGURED or absent"},
        "test_success_rate": summarize(test_ok)
        if test_ok
        else {"n": 0, "mean": None, "note": "NOT_CONFIGURED or absent"},
        "unsupported_feature_rate": summarize(unsupported),
        "scope_deviation": summarize(scope_dev),
    }


def aggregate_experiment_status(runs: list[dict], *, agent_available: bool) -> str:
    """Top-level status reflecting what actually happened."""
    if not agent_available:
        return "NOT_EXECUTED"
    if not runs:
        return "NOT_EXECUTED"
    failed = sum(1 for r in runs if r.get("execution_status") == "FAILED_INFRASTRUCTURE")
    ok = sum(1 for r in runs if r.get("execution_status") in QUALITY_STATUSES)
    if failed and ok:
        return "EXECUTED_WITH_FAILURES"
    if failed and not ok:
        return "EXECUTED_WITH_FAILURES"
    if ok == len(runs):
        return "EXECUTED_COMPLETE"
    return "EXECUTED"
