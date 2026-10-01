"""Requirement verification for RQ5 — never promotes missing evidence to PASS."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.schemas.agent_verification import RequirementVerification, VerificationResultStatus  # noqa: E402
from app.services.agent_verification import build_requirement_verification  # noqa: E402


def verify_requirements(
    *,
    task: dict,
    agent_run_id: str,
    git_diff: str,
    test_result: dict[str, Any],
    build_result: dict[str, Any],
) -> list[RequirementVerification]:
    """Verify each gold requirement conservatively.

    Methods:
    - acceptance_test_marker: if task lists per-requirement test ids and tests PASS
    - diff_presence: weak signal only → PARTIAL at best, never auto-PASS alone
    - otherwise UNVERIFIED
    """
    requirements = list(task.get("gold_requirements") or [])
    req_ids = list(task.get("requirement_ids") or [f"REQ-{i+1:03d}" for i in range(len(requirements))])
    acceptance_tests = list(task.get("acceptance_tests") or [])
    test_status = test_result.get("status")
    test_stdout = test_result.get("stdout") or ""
    test_configured = test_result.get("configured", False)

    records: list[RequirementVerification] = []
    for i, text in enumerate(requirements):
        rid = req_ids[i] if i < len(req_ids) else f"REQ-{i+1:03d}"
        evidence: list[str] = []
        method = "unverified"
        status = VerificationResultStatus.UNVERIFIED

        # Explicit rejected features are NOT_APPLICABLE if present only as rejection
        if text in (task.get("rejected_features") or []):
            records.append(
                build_requirement_verification(
                    requirement_id=rid,
                    agent_run_id=agent_run_id,
                    status=VerificationResultStatus.NOT_APPLICABLE,
                    evidence=["listed as rejected/out-of-scope"],
                    verification_method="rejected_feature",
                )
            )
            continue

        marker = acceptance_tests[i] if i < len(acceptance_tests) else None
        if test_configured and test_status == "PASS" and marker:
            # Require marker to appear in test output OR rely on overall pass with named test
            if marker in test_stdout or _tokens_in(marker, test_stdout):
                status = VerificationResultStatus.PASS
                evidence = [f"acceptance_test:{marker}", "test_status:PASS"]
                method = "acceptance_test_marker"
            elif test_status == "PASS" and not test_stdout.strip():
                # Tests passed but no per-requirement evidence → UNVERIFIED
                status = VerificationResultStatus.UNVERIFIED
                evidence = ["tests_passed_but_no_requirement_marker"]
                method = "insufficient_evidence"
            else:
                status = VerificationResultStatus.UNVERIFIED
                evidence = [f"missing_marker:{marker}"]
                method = "acceptance_test_marker_missing"
        elif test_configured and test_status == "FAIL":
            status = VerificationResultStatus.FAIL
            evidence = ["test_status:FAIL", f"stderr_ref:{test_result.get('stderr_artifact')}"]
            method = "acceptance_test_failed"
        elif test_configured and test_status == "NOT_CONFIGURED":
            status = VerificationResultStatus.UNVERIFIED
            method = "tests_not_configured"
        elif not test_configured:
            # Diff-only is never enough for PASS
            if _tokens_in(text, git_diff):
                status = VerificationResultStatus.UNVERIFIED
                evidence = ["diff_mentions_requirement_tokens_only"]
                method = "diff_presence_insufficient"
            else:
                status = VerificationResultStatus.UNVERIFIED
                evidence = ["no_test_evidence"]
                method = "no_validation_configured"
        else:
            status = VerificationResultStatus.UNVERIFIED
            method = "inconclusive"

        # Build failure does not invent PASS
        if build_result.get("status") == "FAIL" and status == VerificationResultStatus.PASS:
            status = VerificationResultStatus.FAIL
            evidence.append("build_failed")
            method = "build_failed_overrides"

        records.append(
            build_requirement_verification(
                requirement_id=rid,
                agent_run_id=agent_run_id,
                status=status,
                evidence=evidence,
                verification_method=method,
                test_results={"requirement_text": text, "acceptance_test": marker},
            )
        )
    return records


def unsupported_feature_signals(task: dict, git_diff: str, created_files: list[str]) -> list[str]:
    """Detect likely implementation of explicitly rejected features."""
    hits = []
    blob = (git_diff or "") + "\n" + "\n".join(created_files or [])
    for feat in task.get("rejected_features") or []:
        # Prefer strong keyword detectors; avoid weak token overlap on "Do not add …"
        if _rejected_keyword_hit(feat, blob):
            hits.append(feat)
            continue
        # Fallback: require high overlap AND at least one distinctive noun (>=5 chars)
        tokens = [t for t in re.findall(r"[a-z0-9_]{3,}", (feat or "").lower())]
        distinctive = [t for t in tokens if t not in {"not", "add", "use", "the", "and", "for", "do"} and len(t) >= 5]
        if distinctive and all(t in blob.lower() for t in distinctive):
            # Only flag if implementation-like context exists for that token
            if any(
                f"import {t}" in blob.lower()
                or f"from {t}" in blob.lower()
                or f"def {t}" in blob.lower()
                or f"{t}." in blob.lower()
                for t in distinctive
            ):
                hits.append(feat)
    return hits


def constraint_violation_signals(task: dict, git_diff: str, created_files: list[str]) -> list[str]:
    """Flag obvious violations of stated constraints (e.g. redis when stdlib-only)."""
    blob = ((git_diff or "") + "\n" + "\n".join(created_files or [])).lower()
    hits = []
    for c in task.get("constraints") or []:
        cl = c.lower()
        if "stdlib" in cl or "standard library" in cl:
            for banned in ("import redis", "import requests", "import django", "from kafka"):
                if banned in blob:
                    hits.append(f"constraint:{c} violated by {banned}")
        if "in-memory" in cl or "no network" in cl:
            for banned in ("import requests", "http://", "https://"):
                if banned in blob and "example.com" not in blob:
                    # url shortener seeds mention example.com in tests — allow that
                    if "example.com" in blob:
                        continue
                    hits.append(f"constraint:{c} possible network usage")
    return list(dict.fromkeys(hits))


def scope_violation_signals(task: dict, git_diff: str, created_files: list[str]) -> list[str]:
    """Scope deviations = rejected feature hits (alias used by metrics)."""
    return unsupported_feature_signals(task, git_diff, created_files)


def _rejected_keyword_hit(feat: str, blob: str) -> bool:
    """Stronger check for common rejected tech keywords."""
    low = blob.lower()
    fl = feat.lower()
    keywords = []
    for kw in ("redis", "kafka", "delete", "external api", "cloud", "auth", "sql"):
        if kw in fl:
            keywords.append(kw)
    if not keywords:
        return False
    # Implementation smell: importing/using the banned tech
    for kw in keywords:
        if kw == "delete":
            if "def delete_" in low or "delete_note" in low or "delete_user" in low:
                return True
        elif kw == "redis" and ("import redis" in low or "from redis" in low):
            return True
        elif kw == "kafka" and ("import kafka" in low or "from kafka" in low):
            return True
        elif kw == "sql" and ("import sqlite3" not in low) and ("sqlalchemy" in low or "psycopg" in low):
            return True
    return False


def _tokens_in(needle: str, haystack: str) -> bool:
    tokens = [t for t in re.findall(r"[a-z0-9_]{3,}", (needle or "").lower())]
    if not tokens or not haystack:
        return False
    low = haystack.lower()
    return sum(1 for t in tokens if t in low) >= max(1, len(tokens) // 2)
