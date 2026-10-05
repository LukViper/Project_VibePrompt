# RQ5 Pilot Report — rest_echo_api × 3 variants

**Result directory:** `evaluation/results/2026-10-05_040604_rq5/rq5/`  
**Selection:** `PILOT_SUBSET` — **not** the full 36-run scientific grid  
(`is_full_scientific_grid: false`, `n_runs_planned: 3`)

## Observed measurements

| Variant | Agent exit | Build | Oracle tests | Requirement results | overall_outcome | Duration (s) | Unsupported features |
|---------|------------|-------|--------------|---------------------|-----------------|--------------|----------------------|
| A_raw | 0 | PASS | PASS | REQ-001 PASS, REQ-002 PASS | TASK_COMPLETE | 29.4 | none |
| B_structured | 0 | PASS | PASS | REQ-001 PASS, REQ-002 PASS | TASK_COMPLETE | 26.1 | none |
| C_vibeprompt | 0 | PASS | FAIL | REQ-001 FAIL, REQ-002 PASS | REQUIREMENTS_FAILED | 84.2 | `Do not add Redis` |

Aggregates (completed agent quality, n=3):

- Requirement satisfaction (PASS/(PASS+FAIL)): mean **0.833** (5 PASS / 6 conclusive)
- Task completion rate: **2/3**
- Build success rate: **1.0**
- Test success rate: **0.667**
- Unsupported feature rate: **0.333** (C only)

Oracle seed tests were restored before verification (`oracle_tests_restored`).

## Interpretations (limited)

This is a **single-task pilot** (n=3 cells). It validates that the harness, Codex wrapper, AgentRun records, requirement verification, and metrics path execute end to end. It does **not** support claims that any variant outperforms another.

## Research-validity note (C prompt content)

Inspection of `prompts/rest_echo_api/C_vibeprompt.txt` shows the real VibePrompt C pipeline extracted **Redis as a positive requirement / database** despite conversation text rejecting Redis. Baselines A/B list Redis only under rejected/out-of-scope. This is consistent with protocol limitation §8.2 (NLP extraction quality) and is part of what RQ5 measures for variant C — not a harness fabrication. Full-study interpretation must account for this construct difference.

## Sandbox blocker (first attempt)

An earlier attempt under a restricted sandbox failed all three cells with Codex `Permission denied` on `~/.codex/tmp` (`FAILED_INFRASTRUCTURE`). That run is **not** scientific evidence. The successful pilot above was executed with unrestricted local permissions so Codex could initialize.
