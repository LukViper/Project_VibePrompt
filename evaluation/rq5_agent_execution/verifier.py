"""Requirement verification for RQ5 — never promotes missing evidence to PASS."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

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
    - acceptance_test_marker: per-requirement pytest/junit outcome when available
    - overall suite FAIL without per-test evidence → FAIL (conservative)
    - missing marker / no stdout → INCONCLUSIVE or UNVERIFIED (never PASS)
    - diff_presence alone never yields PASS
    """
    requirements = list(task.get("gold_requirements") or [])
    req_ids = list(task.get("requirement_ids") or [f"REQ-{i+1:03d}" for i in range(len(requirements))])
    acceptance_tests = list(task.get("acceptance_tests") or [])
    test_status = test_result.get("status")
    test_stdout = test_result.get("stdout") or ""
    test_configured = test_result.get("configured", False)
    agent_execution_failed = bool(test_result.get("agent_execution_failed"))
    per_test = _parse_test_outcomes(test_stdout)

    records: list[RequirementVerification] = []
    for i, text in enumerate(requirements):
        rid = req_ids[i] if i < len(req_ids) else f"REQ-{i+1:03d}"
        evidence: list[str] = []
        method = "unverified"
        status = VerificationResultStatus.UNVERIFIED
        explanation: str | None = None

        # Explicit rejected features are NOT_APPLICABLE if present only as rejection
        if text in (task.get("rejected_features") or []):
            records.append(
                build_requirement_verification(
                    requirement_id=rid,
                    agent_run_id=agent_run_id,
                    status=VerificationResultStatus.NOT_APPLICABLE,
                    evidence=["listed as rejected/out-of-scope"],
                    verification_method="rejected_feature",
                    test_results={"requirement_text": text, "explanation": "rejected feature"},
                )
            )
            continue

        marker = acceptance_tests[i] if i < len(acceptance_tests) else None
        marker_outcome = _lookup_marker_outcome(marker, per_test) if marker else None

        if agent_execution_failed:
            status = VerificationResultStatus.INCONCLUSIVE
            evidence = [
                "agent_execution_failed",
                f"test_status:{test_status}",
                f"stderr_ref:{test_result.get('stderr_artifact')}",
            ]
            method = "agent_execution_failed"
            explanation = (
                "Agent did not complete successfully; seed-oracle test outcomes "
                "are not treated as conclusive requirement results"
            )
            records.append(
                build_requirement_verification(
                    requirement_id=rid,
                    agent_run_id=agent_run_id,
                    status=status,
                    evidence=evidence,
                    verification_method=method,
                    test_results={
                        "requirement_text": text,
                        "acceptance_test": marker,
                        "explanation": explanation,
                        "marker_outcome": marker_outcome,
                    },
                )
            )
            continue

        if test_configured and marker and marker_outcome == "PASS":
            status = VerificationResultStatus.PASS
            evidence = [f"acceptance_test:{marker}", "marker_outcome:PASS"]
            method = "acceptance_test_marker"
        elif test_configured and marker and marker_outcome == "FAIL":
            status = VerificationResultStatus.FAIL
            evidence = [
                f"acceptance_test:{marker}",
                "marker_outcome:FAIL",
                f"stderr_ref:{test_result.get('stderr_artifact')}",
            ]
            method = "acceptance_test_marker"
            explanation = f"Acceptance test {marker} failed"
        elif test_configured and test_status == "PASS" and marker:
            if marker in test_stdout or _tokens_in(marker, test_stdout):
                status = VerificationResultStatus.PASS
                evidence = [f"acceptance_test:{marker}", "test_status:PASS"]
                method = "acceptance_test_marker"
            elif not test_stdout.strip():
                status = VerificationResultStatus.INCONCLUSIVE
                evidence = ["tests_passed_but_no_requirement_marker"]
                method = "insufficient_evidence"
                explanation = "Suite passed but per-requirement marker not observed"
            else:
                status = VerificationResultStatus.INCONCLUSIVE
                evidence = [f"missing_marker:{marker}"]
                method = "acceptance_test_marker_missing"
                explanation = f"Suite passed but marker {marker} not found in output"
        elif test_configured and test_status == "FAIL":
            if marker and marker_outcome is None:
                # Suite failed; this requirement's test did not report — inconclusive for that req
                status = VerificationResultStatus.INCONCLUSIVE
                evidence = [
                    "test_status:FAIL",
                    f"missing_marker:{marker}" if marker else "no_marker",
                    f"stderr_ref:{test_result.get('stderr_artifact')}",
                ]
                method = "acceptance_test_suite_failed_marker_missing"
                explanation = "Test suite failed; no per-requirement outcome for this marker"
            else:
                status = VerificationResultStatus.FAIL
                evidence = ["test_status:FAIL", f"stderr_ref:{test_result.get('stderr_artifact')}"]
                method = "acceptance_test_failed"
                explanation = "Acceptance/test suite failed"
        elif test_configured and test_status == "NOT_CONFIGURED":
            status = VerificationResultStatus.UNVERIFIED
            method = "tests_not_configured"
            explanation = "Tests not configured"
        elif test_configured and test_status == "TIMEOUT":
            status = VerificationResultStatus.INCONCLUSIVE
            evidence = ["test_status:TIMEOUT"]
            method = "tests_timed_out"
            explanation = "Tests timed out"
        elif not test_configured:
            # Diff-only is never enough for PASS
            if _tokens_in(text, git_diff):
                status = VerificationResultStatus.UNVERIFIED
                evidence = ["diff_mentions_requirement_tokens_only"]
                method = "diff_presence_insufficient"
                explanation = "Diff mentions requirement tokens but no tests configured"
            else:
                status = VerificationResultStatus.UNVERIFIED
                evidence = ["no_test_evidence"]
                method = "no_validation_configured"
                explanation = "No validation configured"
        else:
            status = VerificationResultStatus.INCONCLUSIVE
            method = "inconclusive"
            explanation = f"Could not determine requirement status (test_status={test_status})"

        # Build failure does not invent PASS
        if build_result.get("status") == "FAIL" and status == VerificationResultStatus.PASS:
            status = VerificationResultStatus.FAIL
            evidence.append("build_failed")
            method = "build_failed_overrides"
            explanation = "Build failed; overriding prior PASS"

        records.append(
            build_requirement_verification(
                requirement_id=rid,
                agent_run_id=agent_run_id,
                status=status,
                evidence=evidence,
                verification_method=method,
                test_results={
                    "requirement_text": text,
                    "acceptance_test": marker,
                    "explanation": explanation,
                    "marker_outcome": marker_outcome,
                },
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


def _parse_test_outcomes(blob: str) -> dict[str, str]:
    """Map test function names → PASS|FAIL from pytest -v lines and/or junit XML."""
    outcomes: dict[str, str] = {}
    if not blob:
        return outcomes

    # pytest -v: tests/test_x.py::test_foo PASSED
    for match in re.finditer(
        r"(?P<node>[\w./\\:-]+)::(?P<name>test_[\w]+)\s+(?P<result>PASSED|FAILED|ERROR|SKIPPED)",
        blob,
    ):
        name = match.group("name")
        result = match.group("result")
        if result == "PASSED":
            outcomes[name] = "PASS"
        elif result in {"FAILED", "ERROR"}:
            outcomes[name] = "FAIL"

    # junit XML fragments appended by the harness
    if "<testsuite" in blob or "<testcase" in blob:
        # ElementTree needs a single root; wrap fragments if needed
        xml_text = blob
        start = blob.find("<testsuite")
        if start < 0:
            start = blob.find("<testsuites")
        if start >= 0:
            xml_text = blob[start:]
            # Truncate trailing non-xml noise after last closing tag
            for closer in ("</testsuites>", "</testsuite>"):
                end = xml_text.rfind(closer)
                if end >= 0:
                    xml_text = xml_text[: end + len(closer)]
                    break
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                root = None
            if root is not None:
                for case in root.iter("testcase"):
                    name = case.attrib.get("name") or ""
                    # Strip parametrize suffixes: test_foo[1]
                    base = name.split("[", 1)[0]
                    if any(child.tag in {"failure", "error"} for child in case):
                        outcomes[base] = "FAIL"
                    elif any(child.tag == "skipped" for child in case):
                        outcomes.setdefault(base, "SKIP")
                    else:
                        outcomes.setdefault(base, "PASS")
    return outcomes


def _lookup_marker_outcome(marker: str, outcomes: dict[str, str]) -> str | None:
    if not marker:
        return None
    if marker in outcomes:
        return outcomes[marker]
    # Allow marker without test_ prefix mismatch already exact; try suffix match
    for name, result in outcomes.items():
        if name == marker or name.endswith(marker) or marker.endswith(name):
            return result
    return None


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
