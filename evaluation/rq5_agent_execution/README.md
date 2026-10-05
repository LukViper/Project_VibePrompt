# RQ5 — Real coding-agent execution harness

**Scientific status:**

```text
RQ5 NOT EXECUTED
Reason: agent command unavailable
```

until `VIBEPROMPT_AGENT_CMD` is set.

**Protocol:** [`docs/RQ5_PROTOCOL.md`](../../docs/RQ5_PROTOCOL.md) (v2).  
**Dataset:** `evaluation/datasets/rq5/tasks_v2.json` (v1 retained).

## Variant C

Uses the **real** VibePrompt pipeline (`c_pipeline.py`): extraction → ProjectState →
Grill → compilation gate → specification → `render_prompt`. Provenance JSON is
written next to each C prompt.

## Pilot subset (not the full 36-run grid)

```bash
export VIBEPROMPT_AGENT_CMD="$PWD/evaluation/agent_execution/codex_rq5.sh"
export VIBEPROMPT_AGENT_PROVIDER=codex
export VIBEPROMPT_BUILD_CMD='python -m compileall -q .'
export VIBEPROMPT_TEST_CMD='python -m pytest -v --tb=line --junitxml=junit.xml'

backend/.venv/bin/python -m evaluation.rq5_agent_execution.run --task-id rest_echo_api
```

Filtered runs write `run_subset.json` with `is_full_scientific_grid: false` and must
not be reported as the full scientific experiment. `config.json` records
`mode: PILOT_SUBSET` and selected `task_ids` only.

Full 36-run grid (after pilot review):

```bash
export VIBEPROMPT_RQ5_ALLOW_FULL_GRID=1
backend/.venv/bin/python -m evaluation.rq5_agent_execution.run
```

## HARNESS TEST

```bash
backend/.venv/bin/python -m evaluation.rq5_agent_execution.harness_smoke
```

Mock agent only; `scientific: false`.
