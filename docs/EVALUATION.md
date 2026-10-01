# Evaluation

Status labels: **IMPLEMENTED**, **RUN**, **NOT RUN**, **NOT EXECUTED**.

All current datasets are labeled **SYNTHETIC CONTROLLED BENCHMARK**.  
Do **not** claim real-world generalization. Metric code accepts future real-world
datasets with the same schema without changing metric implementations.

## Research questions

| RQ | Question | Status |
|----|----------|--------|
| RQ1 | Requirement preservation vs baselines | **RUN** (v2 — real VibePrompt pipeline; gold evaluation-only) |
| RQ2 | Change-impact / traceability accuracy | **RUN** (synthetic; prior results retained) |
| RQ3 | Grill effectiveness (A/B/C + ontology + diagnostics) | **RUN** (v2 — targeted attacks; diagnostics explain misses) |
| RQ4 | Evidence integrity + tracking ablation | **RUN** (v2 — two experiments) |
| RQ5 | Coding-agent requirement adherence | **HARNESS READY** / scientific run **NOT EXECUTED** without agent |

## RQ1–RQ4

Unchanged. See prior versioned result directories under `evaluation/results/`.

## RQ5

### Infrastructure

Implemented vendor-neutral harness:

```text
RQ5 Harness → VIBEPROMPT_AGENT_CMD → External Coding Agent → Isolated Workspace
```

Task delivery: prompt written to `TASK.md`; paths passed via env
(`VIBEPROMPT_TASK_DIR`, `VIBEPROMPT_TASK_PROMPT`, …) — task text is never
shell-interpolated into the command. See `evaluation/rq5_agent_execution/README.md`.

### Scientific execution status

```text
RQ5 NOT EXECUTED
Reason: agent command unavailable
```

until `VIBEPROMPT_AGENT_CMD` is set and a real agent run completes.

The harness being ready does **not** demonstrate improved coding-agent performance.

Null metrics mean **not measured**, not zero performance.

### HARNESS TEST

```bash
backend/.venv/bin/python -m evaluation.rq5_agent_execution.harness_smoke
```

Deterministic mock agent + 5 smoke tasks. Labelled **HARNESS TEST** — never a
scientific RQ5 result.

### Configuration

```bash
export VIBEPROMPT_AGENT_CMD='my-agent --workspace "$VIBEPROMPT_TASK_DIR" --prompt-file "$VIBEPROMPT_TASK_PROMPT"'
export VIBEPROMPT_BUILD_CMD='python -m compileall -q .'   # optional
export VIBEPROMPT_TEST_CMD='python -m pytest -q'          # optional
export VIBEPROMPT_RQ5_TIMEOUT=600
```

Missing build/test → `NOT_CONFIGURED` (not PASS).

Reuses `AgentRun` / `RequirementVerification` schemas; missing evidence → `UNVERIFIED`, never silent PASS.

## Commands

```bash
backend/.venv/bin/python -m evaluation.rq5_agent_execution.run
backend/.venv/bin/python -m evaluation.rq5_agent_execution.harness_smoke
```

Outputs are **versioned** under `evaluation/results/<timestamp>_*/` — prior runs are not overwritten.

## Limitations

- Synthetic controlled data only (RQ1–RQ4)
- RQ5 empirical results require an external agent command
- HARNESS TEST must not be cited as RQ5 science
