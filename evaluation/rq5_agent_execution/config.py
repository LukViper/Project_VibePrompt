"""RQ5 configuration — vendor-neutral agent command contract.

How the agent receives the task
--------------------------------
`VIBEPROMPT_AGENT_CMD` is an operator-configured shell command. The harness never
interpolates task/prompt text into the command string (avoids injection).

Instead, before invoking the command, the harness sets environment variables:

| Variable | Meaning |
|----------|---------|
| `VIBEPROMPT_TASK_DIR` | Absolute path to the isolated workspace |
| `VIBEPROMPT_TASK_PROMPT` | Absolute path to the injected prompt file (`TASK.md`) |
| `VIBEPROMPT_TASK_ID` | Task identifier |
| `VIBEPROMPT_VARIANT` | `A_raw` / `B_structured` / `C_vibeprompt` |
| `VIBEPROMPT_WORKSPACE_ID` | Unique workspace id for this run |

The coding agent (Cursor CLI, Codex, Claude Code, custom script, …) must read
the prompt from `VIBEPROMPT_TASK_PROMPT` and operate inside `VIBEPROMPT_TASK_DIR`.

Example:

```bash
export VIBEPROMPT_AGENT_CMD='my-agent --workspace "$VIBEPROMPT_TASK_DIR" --prompt-file "$VIBEPROMPT_TASK_PROMPT"'
export VIBEPROMPT_BUILD_CMD='python -m compileall .'
export VIBEPROMPT_TEST_CMD='python -m pytest -q'
export VIBEPROMPT_RQ5_TIMEOUT=600
```
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RQ5Config:
    agent_cmd: str | None
    build_cmd: str | None
    test_cmd: str | None
    timeout_seconds: float
    retain_workspace: bool
    mode: str  # SCIENTIFIC | HARNESS_TEST
    agent_model: str | None
    agent_provider: str | None

    @property
    def agent_available(self) -> bool:
        return bool(self.agent_cmd and self.agent_cmd.strip())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["agent_available"] = self.agent_available
        data["environment"] = {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cwd_note": "each run uses an isolated temp workspace",
        }
        # Never claim scientific completion from harness test mode
        data["scientific"] = self.mode == "SCIENTIFIC" and self.agent_available
        return data


def load_rq5_config(*, harness_test: bool = False) -> RQ5Config:
    mode = "HARNESS_TEST" if harness_test else os.environ.get("VIBEPROMPT_RQ5_MODE", "SCIENTIFIC")
    if harness_test:
        mode = "HARNESS_TEST"
    timeout_raw = os.environ.get("VIBEPROMPT_RQ5_TIMEOUT", "600")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 600.0
    retain = os.environ.get("VIBEPROMPT_RQ5_RETAIN_WORKSPACE", "1").strip() not in {"0", "false", "False"}
    agent_cmd = os.environ.get("VIBEPROMPT_AGENT_CMD")
    if harness_test and not agent_cmd:
        # Built-in deterministic mock — never used for scientific RQ5
        agent_cmd = f"{sys.executable} -m evaluation.rq5_agent_execution.mock_agent"
    return RQ5Config(
        agent_cmd=agent_cmd.strip() if agent_cmd else None,
        build_cmd=_optional_cmd("VIBEPROMPT_BUILD_CMD"),
        test_cmd=_optional_cmd("VIBEPROMPT_TEST_CMD"),
        timeout_seconds=timeout,
        retain_workspace=retain,
        mode=mode,
        agent_model=os.environ.get("VIBEPROMPT_AGENT_MODEL"),
        agent_provider=os.environ.get("VIBEPROMPT_AGENT_PROVIDER"),
    )


def _optional_cmd(name: str) -> str | None:
    val = os.environ.get(name)
    if val is None or not str(val).strip():
        return None
    return str(val).strip()
