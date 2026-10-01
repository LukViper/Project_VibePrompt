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

## HARNESS TEST

```bash
backend/.venv/bin/python -m evaluation.rq5_agent_execution.harness_smoke
```

Mock agent only; `scientific: false`.
