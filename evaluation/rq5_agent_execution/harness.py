"""Core RQ5 single-run harness — shared by scientific runner and HARNESS TEST."""

from __future__ import annotations

import json
import os
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


def run_single(
    *,
    task: dict,
    variant: str,
    config: RQ5Config,
    work_root: Path,
    artifact_root: Path,
    label: str | None = None,
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
    prompt_provenance = {
        "method": prompt_bundle.get("method"),
        "provenance": prompt_bundle.get("provenance"),
        "state_summary": prompt_bundle.get("state_summary"),
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
    git_state = capture_git_state(workspace)

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
        exit_code=agent_res.exit_code,
        duration_seconds=agent_res.duration_seconds,
        stdout_artifact=str(stdout_path),
        stderr_artifact=str(stderr_path),
        git_diff_artifact=str(diff_path),
        label=label,
        execution_status=execution_status,
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
        },
        build_result={"status": build_res.status, "configured": build_res.configured},
    )
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
        "task_id": task["task_id"],
        "system_variant": variant,
        "dataset_version": task.get("dataset_version"),
        "seed_commit": workspace.seed_commit,
        "start_time": workspace.start_time,
        "end_time": workspace.end_time,
        "exit_code": agent_res.exit_code,
        "duration_seconds": agent_res.duration_seconds,
        "execution_status": execution_status,
        "build_status": build_res.status,
        "test_status": test_res.status,
        "build_exit_code": build_res.exit_code,
        "test_exit_code": test_res.exit_code,
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
        "agent_run": agent_run.as_dict(),
        "requirement_verifications": [v.as_dict() for v in verifications],
        "unsupported_features": unsupported,
        "constraint_violations": constraint_violations,
        "scope_violations": scope_violations,
        "label": label,
    }
    (art_dir / "run.json").write_text(json.dumps(run_record, indent=2) + "\n", encoding="utf-8")
    return run_record
