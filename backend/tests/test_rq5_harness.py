"""RQ5 harness unit tests — mock subprocess; never requires a real coding agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture()
def clear_agent_env(monkeypatch):
    monkeypatch.delenv("VIBEPROMPT_AGENT_CMD", raising=False)
    monkeypatch.delenv("VIBEPROMPT_BUILD_CMD", raising=False)
    monkeypatch.delenv("VIBEPROMPT_TEST_CMD", raising=False)
    monkeypatch.delenv("VIBEPROMPT_RQ5_MODE", raising=False)


def test_rq5_missing_agent_command(clear_agent_env, monkeypatch, tmp_path):
    from evaluation.datasets.generate import generate_rq5
    from evaluation.rq5_agent_execution import run as rq5

    generate_rq5()
    import evaluation.common.reporting as reporting

    monkeypatch.setattr(reporting, "new_run_dir", lambda prefix=None: tmp_path / f"run_{prefix}")
    monkeypatch.setattr(rq5, "new_run_dir", lambda prefix=None: tmp_path / f"run_{prefix}")
    payload = rq5.main()
    assert payload["status"] == "NOT EXECUTED"
    assert payload.get("execution_status") == "NOT_EXECUTED"
    assert "unavailable" in (payload.get("reason") or "").lower()
    # Null metrics — not fabricated zeros presented as results
    assert payload["metrics"]["requirement_coverage"] is None
    assert payload["metrics"]["build_success_rate"] is None


def test_rq5_does_not_fabricate_results(clear_agent_env, monkeypatch, tmp_path):
    from evaluation.rq5_agent_execution import run as rq5
    import evaluation.common.reporting as reporting

    monkeypatch.setattr(reporting, "new_run_dir", lambda prefix=None: tmp_path / f"run_{prefix}")
    monkeypatch.setattr(rq5, "new_run_dir", lambda prefix=None: tmp_path / f"run_{prefix}")
    payload = rq5.main()
    assert payload["results"] == []
    assert payload["metrics"].get("note")
    assert "NOT EXECUTED" in payload["metrics"]["note"]


def test_rq5_creates_isolated_workspace(tmp_path):
    from evaluation.rq5_agent_execution.workspace import create_workspace, destroy_workspace

    ws1 = create_workspace(
        root=tmp_path,
        task_id="t1",
        system_variant="A_raw",
        prompt_text="prompt one",
    )
    ws2 = create_workspace(
        root=tmp_path,
        task_id="t2",
        system_variant="B_structured",
        prompt_text="prompt two",
    )
    assert ws1.path != ws2.path
    assert ws1.workspace_id != ws2.workspace_id
    assert (ws1.path / "TASK.md").read_text(encoding="utf-8") == "prompt one"
    assert (ws2.path / "TASK.md").read_text(encoding="utf-8") == "prompt two"
    destroy_workspace(ws1)
    destroy_workspace(ws2)


def test_rq5_executes_agent_command(tmp_path, monkeypatch):
    from evaluation.rq5_agent_execution.config import RQ5Config
    from evaluation.rq5_agent_execution.harness import run_single

    mock = f"{sys.executable} -m evaluation.rq5_agent_execution.mock_agent"
    config = RQ5Config(
        agent_cmd=mock,
        build_cmd=None,
        test_cmd=None,
        timeout_seconds=60,
        retain_workspace=True,
        mode="HARNESS_TEST",
        agent_model=None,
        agent_provider="mock",
    )
    task = {
        "task_id": "add_function",
        "problem_statement": "add",
        "conversation": ["add"],
        "gold_requirements": ["implement add(a, b) returning a+b"],
        "requirement_ids": ["REQ-001"],
        "constraints": [],
        "acceptance_tests": ["test_add"],
        "seed_files": {},
    }
    work = tmp_path / "work"
    art = tmp_path / "art"
    work.mkdir()
    art.mkdir()
    record = run_single(
        task=task,
        variant="C_vibeprompt",
        config=config,
        work_root=work,
        artifact_root=art,
        label="HARNESS TEST",
    )
    assert record["exit_code"] == 0
    assert record["label"] == "HARNESS TEST"
    assert record["agent_run"]["id"].startswith("RUN-")


def test_rq5_captures_stdout(tmp_path):
    from evaluation.rq5_agent_execution.config import RQ5Config
    from evaluation.rq5_agent_execution.harness import run_single

    config = RQ5Config(
        agent_cmd=f"{sys.executable} -m evaluation.rq5_agent_execution.mock_agent",
        build_cmd=None,
        test_cmd=None,
        timeout_seconds=60,
        retain_workspace=True,
        mode="HARNESS_TEST",
        agent_model=None,
        agent_provider="mock",
    )
    task = {
        "task_id": "add_function",
        "problem_statement": "add",
        "gold_requirements": ["implement add"],
        "requirement_ids": ["REQ-001"],
        "acceptance_tests": [],
        "seed_files": {},
    }
    record = run_single(
        task=task,
        variant="A_raw",
        config=config,
        work_root=tmp_path / "w",
        artifact_root=tmp_path / "a",
        label="HARNESS TEST",
    )
    stdout = Path(record["artifacts"]["stdout"]).read_text(encoding="utf-8")
    assert "mock_agent completed" in stdout
    assert "HARNESS_TEST" in stdout


def test_rq5_captures_stderr(tmp_path):
    from evaluation.rq5_agent_execution.executor import run_command

    # Force a command that writes to stderr
    res = run_command(
        f'{sys.executable} -c "import sys; sys.stderr.write(\'boom-err\\n\'); sys.exit(0)"',
        cwd=tmp_path,
        env={},
        timeout_seconds=30,
        label="agent",
    )
    assert "boom-err" in res.stderr
    assert res.exit_code == 0


def test_rq5_captures_exit_code(tmp_path):
    from evaluation.rq5_agent_execution.executor import run_command

    res = run_command(
        f"{sys.executable} -c \"raise SystemExit(7)\"",
        cwd=tmp_path,
        env={},
        timeout_seconds=30,
        label="agent",
    )
    assert res.exit_code == 7
    assert res.status == "FAIL"


def test_rq5_captures_git_diff(tmp_path):
    from evaluation.rq5_agent_execution.config import RQ5Config
    from evaluation.rq5_agent_execution.harness import run_single

    (tmp_path / "w").mkdir()
    (tmp_path / "a").mkdir()
    config = RQ5Config(
        agent_cmd=f"{sys.executable} -m evaluation.rq5_agent_execution.mock_agent",
        build_cmd=None,
        test_cmd=None,
        timeout_seconds=60,
        retain_workspace=True,
        mode="HARNESS_TEST",
        agent_model=None,
        agent_provider="mock",
    )
    task = {
        "task_id": "add_function",
        "problem_statement": "add",
        "gold_requirements": ["implement add"],
        "requirement_ids": ["REQ-001"],
        "acceptance_tests": [],
        "seed_files": {},
    }
    record = run_single(
        task=task,
        variant="B_structured",
        config=config,
        work_root=tmp_path / "w",
        artifact_root=tmp_path / "a",
        label="HARNESS TEST",
    )
    diff = Path(record["artifacts"]["git_diff"]).read_text(encoding="utf-8")
    # New files may appear as untracked in status rather than diff vs HEAD;
    # either git_diff content or created_files must reflect agent output.
    assert diff is not None
    assert record["git"]["created_files"] or "add_mod" in diff or record["git"]["status_preview"]


def test_rq5_build_validation(tmp_path):
    from evaluation.rq5_agent_execution.executor import run_command

    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    res = run_command(
        f"{sys.executable} -m compileall -q .",
        cwd=tmp_path,
        env={},
        timeout_seconds=30,
        label="build",
    )
    assert res.configured
    assert res.status == "PASS"
    assert res.exit_code == 0


def test_rq5_test_validation(tmp_path):
    from evaluation.rq5_agent_execution.executor import run_command

    (tmp_path / "test_smoke.py").write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")
    res = run_command(
        f"{sys.executable} -m pytest -q",
        cwd=tmp_path,
        env={},
        timeout_seconds=60,
        label="test",
    )
    assert res.status == "PASS"


def test_rq5_missing_build_command():
    from evaluation.rq5_agent_execution.executor import run_command
    from pathlib import Path

    res = run_command(None, cwd=Path("."), env={}, timeout_seconds=5, label="build")
    assert res.status == "NOT_CONFIGURED"
    assert res.configured is False


def test_rq5_missing_test_command():
    from evaluation.rq5_agent_execution.executor import run_command
    from pathlib import Path

    res = run_command("", cwd=Path("."), env={}, timeout_seconds=5, label="test")
    assert res.status == "NOT_CONFIGURED"


def test_rq5_requirement_verification():
    from app.schemas.agent_verification import VerificationResultStatus
    from evaluation.rq5_agent_execution.verifier import verify_requirements

    task = {
        "gold_requirements": ["implement add(a, b)"],
        "requirement_ids": ["REQ-001"],
        "acceptance_tests": ["test_add"],
    }
    vers = verify_requirements(
        task=task,
        agent_run_id="RUN-1",
        git_diff="",
        test_result={"status": "PASS", "stdout": "test_add PASSED", "configured": True},
        build_result={"status": "PASS", "configured": True},
    )
    assert len(vers) == 1
    assert vers[0].status == VerificationResultStatus.PASS
    assert vers[0].requirement_id == "REQ-001"
    assert vers[0].evidence


def test_rq5_does_not_mark_unverified_as_pass():
    from app.schemas.agent_verification import VerificationResultStatus
    from app.services.agent_verification import build_requirement_verification
    from evaluation.rq5_agent_execution.verifier import verify_requirements

    # Service guard
    rec = build_requirement_verification(
        requirement_id="REQ-001",
        agent_run_id="RUN-1",
        status=VerificationResultStatus.PASS,
        evidence=[],
    )
    assert rec.status == VerificationResultStatus.UNVERIFIED

    # Diff-only must not PASS
    task = {
        "gold_requirements": ["implement add(a, b)"],
        "requirement_ids": ["REQ-001"],
        "acceptance_tests": ["test_add"],
    }
    vers = verify_requirements(
        task=task,
        agent_run_id="RUN-1",
        git_diff="+def add(a, b): return a+b",
        test_result={"status": "NOT_CONFIGURED", "stdout": "", "configured": False},
        build_result={"status": "NOT_CONFIGURED", "configured": False},
    )
    assert vers[0].status == VerificationResultStatus.UNVERIFIED


def test_rq5_variant_isolation(tmp_path):
    from evaluation.rq5_agent_execution.config import RQ5Config
    from evaluation.rq5_agent_execution.harness import run_single
    from evaluation.rq5_agent_execution.prompts import build_variant_prompts

    task = {
        "task_id": "add_function",
        "problem_statement": "add numbers",
        "conversation": ["please add"],
        "gold_requirements": ["implement add(a, b) returning a+b"],
        "requirement_ids": ["REQ-001"],
        "constraints": ["stdlib"],
        "acceptance_tests": [],
        "seed_files": {},
    }
    prompts = build_variant_prompts(task)
    assert prompts["A_raw"] != prompts["B_structured"] != prompts["C_vibeprompt"]
    # Frozen: regenerating does not mutate task
    task_copy = dict(task)
    build_variant_prompts(task)
    assert task == task_copy

    config = RQ5Config(
        agent_cmd=f"{sys.executable} -m evaluation.rq5_agent_execution.mock_agent",
        build_cmd=None,
        test_cmd=None,
        timeout_seconds=60,
        retain_workspace=True,
        mode="HARNESS_TEST",
        agent_model=None,
        agent_provider="mock",
    )
    (tmp_path / "w").mkdir()
    (tmp_path / "a").mkdir()
    a = run_single(task=task, variant="A_raw", config=config, work_root=tmp_path / "w", artifact_root=tmp_path / "a", label="HARNESS TEST")
    b = run_single(task=task, variant="B_structured", config=config, work_root=tmp_path / "w", artifact_root=tmp_path / "a", label="HARNESS TEST")
    assert a["workspace_id"] != b["workspace_id"]
    assert a["system_variant"] == "A_raw"
    assert b["system_variant"] == "B_structured"
