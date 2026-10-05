"""Additional RQ5 unit tests: metrics denominators, oracle restore, verification outcomes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def test_requirement_satisfaction_uses_conclusive_denominator_only():
    from evaluation.rq5_agent_execution.metrics import compute_rq5_metrics

    runs = [
        {
            "system_variant": "A_raw",
            "execution_status": "EXECUTED_WITH_VALIDATION",
            "overall_outcome": "PARTIAL_OR_INCONCLUSIVE",
            "duration_seconds": 10.0,
            "requirement_verifications": [
                {"status": "PASS"},
                {"status": "FAIL"},
                {"status": "INCONCLUSIVE"},
                {"status": "UNVERIFIED"},
                {"status": "NOT_APPLICABLE"},
            ],
            "unsupported_features": [],
            "constraint_violations": [],
            "scope_violations": [],
            "build_status": "PASS",
            "test_status": "FAIL",
        }
    ]
    m = compute_rq5_metrics(runs)
    sat = m["completed_agent_quality"]["requirement_satisfaction_rate"]
    assert sat["mean"] == pytest.approx(0.5)
    counts = m["completed_agent_quality"]["requirement_status_counts"]
    assert counts["PASS"] == 1
    assert counts["FAIL"] == 1
    assert counts["INCONCLUSIVE"] == 1
    assert counts["UNVERIFIED"] == 1
    assert counts["NOT_APPLICABLE"] == 1
    assert counts["conclusive_denominator"] == 2
    # Legacy coverage still divides by all listed reqs
    assert m["completed_agent_quality"]["requirement_coverage"]["mean"] == pytest.approx(0.2)


def test_requirement_satisfaction_omits_runs_without_conclusive_results():
    from evaluation.rq5_agent_execution.metrics import compute_rq5_metrics

    runs = [
        {
            "system_variant": "B_structured",
            "execution_status": "EXECUTED_WITH_VALIDATION",
            "requirement_verifications": [{"status": "UNVERIFIED"}, {"status": "INCONCLUSIVE"}],
            "unsupported_features": [],
            "build_status": "PASS",
            "test_status": "PASS",
        }
    ]
    m = compute_rq5_metrics(runs)
    sat = m["completed_agent_quality"]["requirement_satisfaction_rate"]
    assert sat["mean"] is None
    assert sat["n"] == 0


def test_failed_execution_not_counted_as_requirement_pass():
    from evaluation.rq5_agent_execution.metrics import compute_rq5_metrics

    runs = [
        {
            "system_variant": "A_raw",
            "execution_status": "FAILED_INFRASTRUCTURE",
            "requirement_verifications": [{"status": "PASS"}],
            "unsupported_features": [],
            "build_status": "FAIL",
            "test_status": "FAIL",
        }
    ]
    m = compute_rq5_metrics(runs)
    assert m["completed_agent_quality"]["n"] == 0
    assert m["full_execution_grid"]["n"] == 1


def test_verifier_per_test_marker_pass_and_fail():
    from app.schemas.agent_verification import VerificationResultStatus
    from evaluation.rq5_agent_execution.verifier import verify_requirements

    task = {
        "gold_requirements": ["echo", "health"],
        "requirement_ids": ["REQ-001", "REQ-002"],
        "acceptance_tests": ["test_echo_returns_payload", "test_health_ok"],
    }
    stdout = (
        "tests/test_echo_api.py::test_echo_returns_payload PASSED\n"
        "tests/test_echo_api.py::test_health_ok FAILED\n"
    )
    vers = verify_requirements(
        task=task,
        agent_run_id="RUN-1",
        git_diff="",
        test_result={"status": "FAIL", "stdout": stdout, "configured": True},
        build_result={"status": "PASS", "configured": True},
    )
    assert vers[0].status == VerificationResultStatus.PASS
    assert vers[1].status == VerificationResultStatus.FAIL


def test_verifier_missing_marker_is_inconclusive_not_pass():
    from app.schemas.agent_verification import VerificationResultStatus
    from evaluation.rq5_agent_execution.verifier import verify_requirements

    task = {
        "gold_requirements": ["echo"],
        "requirement_ids": ["REQ-001"],
        "acceptance_tests": ["test_echo_returns_payload"],
    }
    vers = verify_requirements(
        task=task,
        agent_run_id="RUN-1",
        git_diff="",
        test_result={
            "status": "PASS",
            "stdout": "tests/test_echo_api.py::test_other PASSED\n",
            "configured": True,
        },
        build_result={"status": "PASS", "configured": True},
    )
    assert vers[0].status == VerificationResultStatus.INCONCLUSIVE
    assert vers[0].status != VerificationResultStatus.PASS


def test_verifier_agent_failure_is_inconclusive_not_fail():
    from app.schemas.agent_verification import VerificationResultStatus
    from evaluation.rq5_agent_execution.verifier import verify_requirements

    task = {
        "gold_requirements": ["echo"],
        "requirement_ids": ["REQ-001"],
        "acceptance_tests": ["test_echo_returns_payload"],
    }
    stdout = "tests/test_echo_api.py::test_echo_returns_payload FAILED\n"
    vers = verify_requirements(
        task=task,
        agent_run_id="RUN-1",
        git_diff="",
        test_result={
            "status": "FAIL",
            "stdout": stdout,
            "configured": True,
            "agent_execution_failed": True,
        },
        build_result={"status": "PASS", "configured": True},
    )
    assert vers[0].status == VerificationResultStatus.INCONCLUSIVE
    assert vers[0].verification_method == "agent_execution_failed"


def test_restore_seed_oracle_tests(tmp_path):
    from evaluation.rq5_agent_execution.harness import restore_seed_oracle_tests
    from evaluation.rq5_agent_execution.workspace import create_workspace

    seed = {
        "app/echo.py": "def echo(x): raise NotImplementedError\n",
        "tests/test_echo_api.py": "def test_echo_returns_payload():\n    assert False\n",
    }
    ws = create_workspace(
        root=tmp_path,
        task_id="t",
        system_variant="A_raw",
        prompt_text="p",
        seed_files=seed,
    )
    # Agent rewrites tests
    (ws.path / "tests" / "test_echo_api.py").write_text(
        "def test_fake_always_pass():\n    assert True\n", encoding="utf-8"
    )
    restored = restore_seed_oracle_tests(ws, seed)
    assert "tests/test_echo_api.py" in restored
    body = (ws.path / "tests" / "test_echo_api.py").read_text(encoding="utf-8")
    assert "test_echo_returns_payload" in body
    assert "test_fake_always_pass" not in body


def test_agent_run_includes_traceability_fields(tmp_path):
    from evaluation.rq5_agent_execution.config import RQ5Config
    from evaluation.rq5_agent_execution.harness import run_single

    config = RQ5Config(
        agent_cmd=f"{sys.executable} -m evaluation.rq5_agent_execution.mock_agent",
        build_cmd=None,
        test_cmd=None,
        timeout_seconds=60,
        retain_workspace=True,
        mode="HARNESS_TEST",
        agent_model="mock-model",
        agent_provider="mock",
    )
    task = {
        "task_id": "add_function",
        "dataset_version": "2.0.0",
        "problem_statement": "add",
        "gold_requirements": ["implement add"],
        "requirement_ids": ["REQ-001"],
        "acceptance_tests": [],
        "seed_files": {"tests/test_add.py": "def test_add():\n    assert True\n"},
    }
    record = run_single(
        task=task,
        variant="A_raw",
        config=config,
        work_root=tmp_path / "w",
        artifact_root=tmp_path / "a",
        label="HARNESS TEST",
        experiment_id="rq5_agent_execution",
    )
    assert record["experiment_id"] == "rq5_agent_execution"
    assert record["prompt_sha256"]
    assert record["agent_run"]["prompt_sha256"] == record["prompt_sha256"]
    assert record["agent_run"]["experiment_id"] == "rq5_agent_execution"
    assert record["agent_run"]["prompt_id"]
    assert record["agent_run"]["prompt_id"].endswith("TASK.md")
    assert "overall_outcome" in record
    assert "oracle_tests_restored" in record
    assert "tests/test_add.py" in record["oracle_tests_restored"]


def test_acceptance_pass_rate_omits_inconclusive_only_runs():
    from evaluation.rq5_agent_execution.metrics import compute_rq5_metrics

    runs = [
        {
            "system_variant": "A_raw",
            "execution_status": "EXECUTED_WITH_VALIDATION",
            "requirement_verifications": [{"status": "UNVERIFIED"}, {"status": "INCONCLUSIVE"}],
            "unsupported_features": [],
            "build_status": "PASS",
            "test_status": "PASS",
        },
        {
            "system_variant": "A_raw",
            "execution_status": "EXECUTED_WITH_VALIDATION",
            "requirement_verifications": [{"status": "PASS"}, {"status": "FAIL"}],
            "unsupported_features": [],
            "build_status": "PASS",
            "test_status": "FAIL",
        },
    ]
    m = compute_rq5_metrics(runs)
    rate = m["completed_agent_quality"]["acceptance_test_pass_rate"]
    assert rate["n"] == 1
    assert rate["mean"] == pytest.approx(0.5)


def test_tasks_v2_mock_agent_oracle_pass(tmp_path):
    """End-to-end: tasks_v2 seed + mock agent + real build/test → requirement PASS."""
    import json

    from evaluation.datasets.rq5.generate_v2 import generate
    from evaluation.rq5_agent_execution.config import RQ5Config
    from evaluation.rq5_agent_execution.harness import run_single

    path, _ = generate()
    tasks = json.loads(path.read_text(encoding="utf-8"))
    task = next(t for t in tasks if t["task_id"] == "rest_echo_api")
    config = RQ5Config(
        agent_cmd=f"{sys.executable} -m evaluation.rq5_agent_execution.mock_agent",
        build_cmd=task.get("build_command"),
        test_cmd=task.get("test_command"),
        timeout_seconds=120,
        retain_workspace=True,
        mode="HARNESS_TEST",
        agent_model=None,
        agent_provider="mock",
    )
    record = run_single(
        task=task,
        variant="A_raw",
        config=config,
        work_root=tmp_path / "w",
        artifact_root=tmp_path / "a",
        label="HARNESS TEST",
        experiment_id="rq5_agent_execution",
    )
    assert record["exit_code"] == 0
    assert record["build_status"] == "PASS"
    assert record["test_status"] == "PASS"
    statuses = [v["status"] for v in record["requirement_verifications"]]
    assert statuses
    assert all(s == "PASS" for s in statuses)
    assert record["oracle_tests_restored"]


def test_codex_wrapper_validates_env(tmp_path):
    import os
    import subprocess

    wrapper = ROOT / "evaluation" / "agent_execution" / "codex_rq5.sh"
    env = os.environ.copy()
    env.pop("VIBEPROMPT_TASK_DIR", None)
    env.pop("VIBEPROMPT_TASK_PROMPT", None)
    proc = subprocess.run(
        ["bash", str(wrapper)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "VIBEPROMPT_TASK_DIR" in (proc.stderr or "")


def test_codex_wrapper_rejects_missing_prompt_file(tmp_path):
    import os
    import subprocess

    wrapper = ROOT / "evaluation" / "agent_execution" / "codex_rq5.sh"
    env = os.environ.copy()
    env["VIBEPROMPT_TASK_DIR"] = str(tmp_path)
    env["VIBEPROMPT_TASK_PROMPT"] = str(tmp_path / "missing.md")
    proc = subprocess.run(
        ["bash", str(wrapper)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "not a file" in (proc.stderr or "").lower() or "ERROR" in (proc.stderr or "")
