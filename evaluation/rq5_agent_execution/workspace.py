"""Isolated workspace lifecycle for RQ5 — identical seeds across A/B/C."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Workspace:
    workspace_id: str
    path: Path
    task_id: str
    system_variant: str
    prompt_path: Path
    start_time: str
    seed_commit: str | None = None
    end_time: str | None = None
    exit_code: int | None = None
    commit_before: str | None = None

    def mark_finished(self, exit_code: int | None) -> None:
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.exit_code = exit_code


def create_workspace(
    *,
    root: Path,
    task_id: str,
    system_variant: str,
    prompt_text: str,
    seed_files: dict[str, str] | None = None,
) -> Workspace:
    """Create isolated workspace: seed commit first, then inject prompt (same seed for all variants)."""
    workspace_id = f"ws-{uuid.uuid4().hex[:12]}"
    path = root / workspace_id
    path.mkdir(parents=True, exist_ok=False)

    for rel, content in (seed_files or {}).items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    _git(path, ["init"])
    _git(path, ["config", "user.email", "rq5-harness@local"])
    _git(path, ["config", "user.name", "RQ5 Harness"])
    _git(path, ["add", "-A"])
    _git(path, ["commit", "-m", "rq5-seed", "--allow-empty"])
    seed_commit = _git_stdout(path, ["rev-parse", "HEAD"])

    # Prompt injected AFTER seed commit so A/B/C share identical seed trees
    prompt_path = path / "TASK.md"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    (path / "VIBEPROMPT_META.json").write_text(
        '{"workspace_id":"%s","task_id":"%s","variant":"%s","seed_commit":"%s"}'
        % (workspace_id, task_id, system_variant, seed_commit),
        encoding="utf-8",
    )

    return Workspace(
        workspace_id=workspace_id,
        path=path,
        task_id=task_id,
        system_variant=system_variant,
        prompt_path=prompt_path,
        start_time=datetime.now(timezone.utc).isoformat(),
        seed_commit=seed_commit,
        commit_before=seed_commit,
    )


def destroy_workspace(workspace: Workspace) -> None:
    if workspace.path.exists():
        shutil.rmtree(workspace.path, ignore_errors=True)


def retain_workspace(workspace: Workspace, dest_root: Path) -> Path:
    dest = dest_root / workspace.workspace_id
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(workspace.path, dest)
    return dest


def capture_git_state(workspace: Workspace) -> dict:
    """Capture complete working-tree changes including untracked files.

    Strategy: stage all changes with `git add -A`, take `git diff --cached` against
    seed HEAD (includes new files), then `git reset` to leave the tree unstaged.
    Also record porcelain status classification.
    """
    status_before = _git_stdout(workspace.path, ["status", "--porcelain"])
    _git(workspace.path, ["add", "-A"])
    full_diff = _git_stdout(workspace.path, ["diff", "--cached", "HEAD"])
    # Also keep unstaged-style HEAD diff for compatibility
    head_diff = _git_stdout(workspace.path, ["diff", "HEAD"])
    _git(workspace.path, ["reset", "-q", "HEAD"])

    status = _git_stdout(workspace.path, ["status", "--porcelain"])
    commit_after = _git_stdout(workspace.path, ["rev-parse", "HEAD"])
    changed: list[str] = []
    created: list[str] = []
    deleted: list[str] = []
    renamed: list[str] = []
    for line in (status or status_before).splitlines():
        if not line.strip():
            continue
        code = line[:2]
        name = line[3:].strip() if len(line) > 3 else line.strip()
        if "R" in code:
            renamed.append(name)
        elif "D" in code:
            deleted.append(name)
        elif "?" in code or "A" in code:
            # untracked or added
            created.append(name.split(" -> ")[-1] if " -> " in name else name)
        else:
            changed.append(name)

    # Explicit untracked file list
    untracked = _git_stdout(
        workspace.path, ["ls-files", "--others", "--exclude-standard"]
    ).splitlines()
    for u in untracked:
        if u and u not in created:
            created.append(u)

    return {
        "commit_before": workspace.commit_before,
        "seed_commit": workspace.seed_commit,
        "commit_after": commit_after or workspace.commit_before,
        "git_diff": full_diff or head_diff,
        "git_diff_head_only": head_diff,
        "git_status": status or status_before,
        "changed_files": changed,
        "created_files": created,
        "deleted_files": deleted,
        "renamed_files": renamed,
        "untracked_files": [u for u in untracked if u],
    }


def _git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _git_stdout(cwd: Path, args: list[str]) -> str:
    proc = _git(cwd, args)
    return (proc.stdout or "").strip()
