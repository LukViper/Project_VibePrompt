"""Core RQ5 single-run harness — shared by scientific runner and HARNESS TEST."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from evaluation.rq5_agent_execution.config import RQ5Config
from evaluation.rq5_agent_execution.executor import run_command
from evaluation.rq5_agent_execution.prompts import build_prompts_with_provenance
from evaluation.rq5_agent_execution.verifier import (
    constraint_violation_signals,
    scope_violation_signals,
    unsupported_feature_signals,
    verify_requirements,
)
from evaluation.rq5_agent_execution.workspace import (
    Workspace,
    capture_git_state,
    create_workspace,
    destroy_workspace,
    retain_workspace,
)

def _pythonpath_with_repo_root() -> str:
    root = str(Path(__file__).resolve().parents[2])
    existing = os.environ.get("PYTHONPATH", "")
    parts = [root]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def restore_seed_oracle_tests(workspace: Workspace, seed_files: dict[str, str] | None) -> list[str]:
    """Rewrite seed `tests/` into the workspace before verification.

    Agents may rewrite or delete acceptance tests. Oracle tests must come from the
    frozen task seed so exit-code-0 / invented tests cannot silently inflate scores.
    """
    restored: list[str] = []
    if not seed_files:
        return restored
    tests_root = workspace.path / "tests"
    if tests_root.exists():
        shutil.rmtree(tests_root)
    for rel, content in seed_files.items():
        if not rel.startswith("tests/"):
            continue
        target = workspace.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        restored.append(rel)
    return restored


def _failure_category(
    *,
    agent_exit_code: int | None,
    agent_timed_out: bool,
    build_status: str | None,
    test_status: str | None,
    execution_status: str,
) -> str | None:
    if agent_timed_out:
        return "agent_timeout"
    if agent_exit_code is None:
        return "agent_not_started"
    if agent_exit_code != 0:
        return "agent_nonzero_exit"
    if build_status == "FAIL":
        return "build_failed"
    if test_status == "FAIL":
        return "tests_failed"
    if execution_status == "FAILED_INFRASTRUCTURE":
        return "infrastructure"
    return None


def _overall_outcome(
    *,
    execution_status: str,
    verifications: list[Any],
) -> str:
    if execution_status == "FAILED_INFRASTRUCTURE":
        return "EXECUTION_FAILED"
    if execution_status == "NOT_EXECUTED":
        return "NOT_EXECUTED"
    statuses = [getattr(v, "status", None) for v in verifications]
    values = [s.value if hasattr(s, "value") else s for s in statuses]
    conclusive = [s for s in values if s in {"PASS", "FAIL"}]
    if not conclusive:
        return "INCONCLUSIVE"
    if all(s == "PASS" for s in conclusive) and not any(
        s in {"UNVERIFIED", "INCONCLUSIVE", "PARTIAL"} for s in values
    ):
        return "TASK_COMPLETE"
    if any(s == "FAIL" for s in values):
        return "REQUIREMENTS_FAILED"
    return "PARTIAL_OR_INCONCLUSIVE"


def run_single(
    *,
    task: dict,
    variant: str,
    config: RQ5Config,
    work_root: Path,
    artifact_root: Path,
    label: str | None = None,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    """Execute one task/variant in an isolated workspace.

    Reuses AgentRun / RequirementVerification from backend schemas via service helpers.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from app.services.agent_verification import (
        build_agent_run,
        classify_execution_status,
    )

    prompts = build_prompts_with_provenance(task)
    if variant not in prompts:
        raise ValueError(f"unknown variant: {variant}")
    prompt_bundle = prompts[variant]
    prompt_text = prompt_bundle["prompt"]
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    prompt_provenance = {
        "method": prompt_bundle.get("method"),
        "provenance": prompt_bundle.get("provenance"),
        "state_summary": prompt_bundle.get("state_summary"),
        "prompt_sha256": prompt_hash,
    }

    work_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)

    # Per-task build/test override smoke tasks; else global config
    build_cmd = task.get("build_command") or config.build_cmd
    test_cmd = task.get("test_command") or config.test_cmd

    workspace = create_workspace(
        root=work_root,
        task_id=task["task_id"],
        system_variant=variant,
        prompt_text=prompt_text,
        seed_files=task.get("seed_files"),
    )

    env = {
        "VIBEPROMPT_TASK_DIR": str(workspace.path),
        "VIBEPROMPT_TASK_PROMPT": str(workspace.prompt_path),
        "VIBEPROMPT_TASK_ID": task["task_id"],
        "VIBEPROMPT_VARIANT": variant,
        "VIBEPROMPT_WORKSPACE_ID": workspace.workspace_id,
        "PYTHONPATH": _pythonpath_with_repo_root(),
    }

    agent_res = run_command(
        config.agent_cmd,
        cwd=workspace.path,
        env=env,
        timeout_seconds=config.timeout_seconds,
        label="agent",
    )
    workspace.mark_finished(agent_res.exit_code)
    # Capture agent-produced tree before oracle restoration mutates tests/
    git_state_agent = capture_git_state(workspace)
    oracle_restored = restore_seed_oracle_tests(workspace, task.get("seed_files"))

    build_res = run_command(
        build_cmd,
        cwd=workspace.path,
        env=env,
        timeout_seconds=min(config.timeout_seconds, 300),
        label="build",
    )
    test_res = run_command(
        test_cmd,
        cwd=workspace.path,
        env=env,
        timeout_seconds=min(config.timeout_seconds, 300),
        label="test",
    )
    git_state = git_state_agent
    # Prefer junit if the test command produced one
    junit_path = workspace.path / "junit.xml"
    junit_text = junit_path.read_text(encoding="utf-8") if junit_path.exists() else ""
    test_stdout_for_verify = (test_res.stdout or "") + "\n" + junit_text

    # Persist large artifacts as files
    art_dir = artifact_root / workspace.workspace_id
    art_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = art_dir / "agent_stdout.txt"
    stderr_path = art_dir / "agent_stderr.txt"
    diff_path = art_dir / "git_diff.patch"
    build_out = art_dir / "build_stdout.txt"
    build_err = art_dir / "build_stderr.txt"
    test_out = art_dir / "test_stdout.txt"
    test_err = art_dir / "test_stderr.txt"
    stdout_path.write_text(agent_res.stdout, encoding="utf-8")
    stderr_path.write_text(agent_res.stderr, encoding="utf-8")
    diff_path.write_text(git_state["git_diff"], encoding="utf-8")
    build_out.write_text(build_res.stdout, encoding="utf-8")
    build_err.write_text(build_res.stderr, encoding="utf-8")
    test_out.write_text(test_res.stdout, encoding="utf-8")
    test_err.write_text(test_res.stderr, encoding="utf-8")

    execution_status = classify_execution_status(
        agent_exit_code=agent_res.exit_code,
        agent_timed_out=agent_res.timed_out,
        build_status=build_res.status,
        test_status=test_res.status,
    ).value
    failure_category = _failure_category(
        agent_exit_code=agent_res.exit_code,
        agent_timed_out=agent_res.timed_out,
        build_status=build_res.status,
        test_status=test_res.status,
        execution_status=execution_status,
    )

    # Provisional AgentRun id for verification linkage; enriched after verification.
    agent_run = build_agent_run(
        project_id=task.get("task_id", "unknown"),
        agent=config.agent_provider or "external_cmd",
        model=config.agent_model,
        repository=str(workspace.path),
        started_at=workspace.start_time,
        completed_at=workspace.end_time,
        build_status=build_res.status,
        test_status=test_res.status,
        output_summary=(agent_res.stdout or "")[:500],
        commit_before=git_state["commit_before"],
        commit_after=git_state["commit_after"],
        workspace_id=workspace.workspace_id,
        task_id=task["task_id"],
        system_variant=variant,
        prompt_id=str(workspace.prompt_path),
        exit_code=agent_res.exit_code,
        duration_seconds=agent_res.duration_seconds,
        stdout_artifact=str(stdout_path),
        stderr_artifact=str(stderr_path),
        git_diff_artifact=str(diff_path),
        label=label,
        execution_status=execution_status,
        experiment_id=experiment_id,
        prompt_sha256=prompt_hash,
        prompt_artifact=str(workspace.prompt_path),
        seed_commit=workspace.seed_commit,
        dataset_version=task.get("dataset_version"),
        oracle_tests_restored=oracle_restored,
        failure_category=failure_category,
        agent_timed_out=agent_res.timed_out,
        execution_config={
            "timeout_seconds": config.timeout_seconds,
            "build_cmd": build_cmd,
            "test_cmd": test_cmd,
            "agent_cmd_configured": bool(config.agent_cmd),
            "mode": config.mode,
            "retain_workspace": config.retain_workspace,
        },
    )

    verifications = verify_requirements(
        task=task,
        agent_run_id=agent_run.id,
        git_diff=git_state["git_diff"],
        test_result={
            "status": test_res.status,
            "stdout": test_stdout_for_verify,
            "configured": test_res.configured,
            "stderr_artifact": str(test_err),
            # Agent infrastructure failure must not turn seed-stub test FAILs into
            # conclusive requirement FAILs in the quality interpretation path.
            "agent_execution_failed": execution_status == "FAILED_INFRASTRUCTURE",
        },
        build_result={"status": build_res.status, "configured": build_res.configured},
    )
    overall_outcome = _overall_outcome(
        execution_status=execution_status,
        verifications=verifications,
    )
    # Attach outcome onto the mutable AgentRun extras
    agent_run_dict = agent_run.as_dict()
    agent_run_dict["overall_outcome"] = overall_outcome
    agent_run_dict["failure_category"] = failure_category

    unsupported = unsupported_feature_signals(
        task, git_state["git_diff"], git_state["created_files"]
    )
    constraint_violations = constraint_violation_signals(
        task, git_state["git_diff"], git_state["created_files"]
    )
    scope_violations = scope_violation_signals(
        task, git_state["git_diff"], git_state["created_files"]
    )

    retained = None
    if config.retain_workspace:
        retained = str(retain_workspace(workspace, artifact_root / "workspaces"))
    else:
        destroy_workspace(workspace)

    run_record = {
        "workspace_id": workspace.workspace_id,
        "experiment_id": experiment_id,
        "task_id": task["task_id"],
        "system_variant": variant,
        "dataset_version": task.get("dataset_version"),
        "seed_commit": workspace.seed_commit,
        "prompt_sha256": prompt_hash,
        "start_time": workspace.start_time,
        "end_time": workspace.end_time,
        "exit_code": agent_res.exit_code,
        "duration_seconds": agent_res.duration_seconds,
        "execution_status": execution_status,
        "overall_outcome": overall_outcome,
        "failure_category": failure_category,
        "build_status": build_res.status,
        "test_status": test_res.status,
        "build_exit_code": build_res.exit_code,
        "test_exit_code": test_res.exit_code,
        "oracle_tests_restored": oracle_restored,
        "prompt_provenance": prompt_provenance,
        "artifacts": {
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "git_diff": str(diff_path),
            "build_stdout": str(build_out),
            "build_stderr": str(build_err),
            "test_stdout": str(test_out),
            "test_stderr": str(test_err),
            "workspace_copy": retained,
        },
        "git": {
            "commit_before": git_state["commit_before"],
            "seed_commit": git_state.get("seed_commit"),
            "commit_after": git_state["commit_after"],
            "changed_files": git_state["changed_files"],
            "created_files": git_state["created_files"],
            "deleted_files": git_state["deleted_files"],
            "renamed_files": git_state.get("renamed_files") or [],
            "untracked_files": git_state.get("untracked_files") or [],
            "status_preview": (git_state["git_status"] or "")[:2000],
        },
        "agent_run": agent_run_dict,
        "requirement_verifications": [v.as_dict() for v in verifications],
        "unsupported_features": unsupported,
        "constraint_violations": constraint_violations,
        "scope_violations": scope_violations,
        "label": label,
    }
    (art_dir / "run.json").write_text(json.dumps(run_record, indent=2) + "\n", encoding="utf-8")
    return run_record
