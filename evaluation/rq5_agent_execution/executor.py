"""Safe subprocess execution for RQ5 agent / build / test steps."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass
class CommandResult:
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    configured: bool

    @property
    def status(self) -> str:
        if not self.configured:
            return "NOT_CONFIGURED"
        if self.timed_out:
            return "TIMEOUT"
        if self.exit_code is None:
            return "ERROR"
        if self.exit_code == 0:
            return "PASS"
        return "FAIL"


def run_command(
    command: str | None,
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: float,
    label: str,
) -> CommandResult:
    """Run an operator-configured command.

    Task content is never interpolated into `command` — only env vars carry paths.
    Uses shell execution because agent CLIs are operator-authored strings; injection
    risk is limited to the trusted config, not task payloads.
    """
    if command is None or not str(command).strip():
        return CommandResult(
            command="",
            exit_code=None,
            stdout="",
            stderr=f"{label}: not configured",
            duration_seconds=0.0,
            timed_out=False,
            configured=False,
        )

    full_env = os.environ.copy()
    full_env.update(dict(env))
    start = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    stdout = stderr = ""
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=str(cwd),
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_group(proc)
            stdout, stderr = proc.communicate(timeout=5)
            exit_code = proc.returncode if proc.returncode is not None else -1
            stderr = (stderr or "") + f"\n[{label}] timed out after {timeout_seconds}s"
    except OSError as exc:
        stderr = f"{label}: failed to start: {exc}"
        exit_code = -1
    duration = time.monotonic() - start
    return CommandResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout or "",
        stderr=stderr or "",
        duration_seconds=duration,
        timed_out=timed_out,
        configured=True,
    )


def _kill_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass
