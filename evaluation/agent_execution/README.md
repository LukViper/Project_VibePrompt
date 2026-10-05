# RQ5 — Agent implementation comparison

Compare raw conversation prompts vs structured requirements vs full VibePrompt validated specification.

**Harness status:** implementation-ready (`evaluation/rq5_agent_execution/`).

**Scientific status without `VIBEPROMPT_AGENT_CMD`:**

```text
RQ5 NOT EXECUTED
Reason: agent command unavailable
```

## Codex wrapper

`codex_rq5.sh` is the recommended agent command for Codex CLI:

```bash
export VIBEPROMPT_AGENT_CMD="$PWD/evaluation/agent_execution/codex_rq5.sh"
export VIBEPROMPT_AGENT_PROVIDER=codex
export VIBEPROMPT_BUILD_CMD='python -m compileall -q .'
export VIBEPROMPT_TEST_CMD='python -m pytest -v --tb=line --junitxml=junit.xml'
export VIBEPROMPT_RQ5_TIMEOUT=600
```

The wrapper requires `VIBEPROMPT_TASK_DIR` and `VIBEPROMPT_TASK_PROMPT`, validates them,
and runs `codex exec --sandbox workspace-write -C "$VIBEPROMPT_TASK_DIR"` with the
prompt on stdin (no shell interpolation of task text into the command line).

See [README](../rq5_agent_execution/README.md) for the agent command contract.
HARNESS TEST (`python -m evaluation.rq5_agent_execution.harness_smoke`) validates
infrastructure only and is **not** a scientific RQ5 result.
