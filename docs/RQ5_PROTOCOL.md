# RQ5 Experimental Protocol — Version 2 (Validity Repair)

**Protocol version:** `v2`  
**Status:** Validity-ready design frozen. **Scientific execution: NOT EXECUTED.**  
**Previous protocol:** retained at [`docs/RQ5_PROTOCOL_v1.md`](RQ5_PROTOCOL_v1.md) (research history).  
**Harness experiment_version:** `4.0.0`  
**Dataset:** `tasks_v2.json` — see §2.

This protocol supersedes v1 for the upcoming real-agent study. It repairs construct
validity so RQ5 measures:

```text
Raw Conversation
vs
Structured Requirements
vs
VibePrompt validated ProjectState / specification
```

not merely three prompt formats.

---

## 1. Mismatch resolution (M1–M8)

| ID | Status | Resolution |
|----|--------|------------|
| **M1** | **Resolved** | Variant C invokes `c_pipeline.run_vibeprompt_c_pipeline` → production extract → `apply_analysis_to_state` → Grill → gate → `_structured`/`_markdown` → `render_prompt` |
| **M2** | **Resolved** | `tasks_v2.json` includes conversation, seed_files, build/test cmds, rejected_features, acceptance_criteria |
| **M3** | **Resolved** | Seed trees ship real `tests/test_*.py` with `def test_…` matching `acceptance_tests` (oracle exists before agent) |
| **M4** | **Resolved** | Every task has `rejected_features`; metrics use unsupported + constraint/scope violation signals |
| **M5** | **Resolved** | `capture_git_state` stages all changes (`git add -A` + `diff --cached`) then resets; records created/untracked |
| **M6** | **Resolved** | Dual views: `full_execution_grid` vs `completed_agent_quality` (excludes `FAILED_INFRASTRUCTURE`) |
| **M7** | **Resolved** | Aggregate status: `NOT_EXECUTED` / `EXECUTED` / `EXECUTED_WITH_FAILURES` / `EXECUTED_COMPLETE` |
| **M8** | **Resolved** | `metrics.json` includes `overall`, `A_raw`, `B_structured`, `C_vibeprompt` with n/mean/std/median/CI |

---

## 2. Dataset v2 (frozen)

| Field | Value |
|-------|--------|
| Path | `evaluation/datasets/rq5/tasks_v2.json` |
| Manifest | `evaluation/datasets/rq5/tasks_v2_manifest.json` |
| dataset_id | `vibeprompt-synthetic-bench/rq5` |
| dataset_version | `2.0.0` |
| dataset_hash | `sha256:3ef5210642376aab1e86b53660a130b92e76a938885e58ec6d638169ba8bfc87` |
| N_tasks | 12 |
| Label | `SYNTHETIC CONTROLLED BENCHMARK` |

**Do not modify `tasks_v2.json` during a registered scientific study.**  
`tasks_v1.json` is retained for history and must not be overwritten.

### Task IDs

`rest_echo_api`, `auth_token_service`, `crud_notes`, `log_parser`, `csv_filter_cli`,
`word_count_pipeline`, `todo_backend`, `url_shortener`, `rate_limiter`, `file_checksum`,
`json_schema_validator`, `metrics_aggregator`

### N_runs

```text
N_runs = 12 tasks × 3 variants = 36
```

---

## 3. Variants (fairness)

Same task, same seed repository (`seed_commit`), same agent/model/timeout/build/tests/verification.

| Variant | Path |
|---------|------|
| `A_raw` | Conversation → direct prompt → agent |
| `B_structured` | Conversation → structured requirements/constraints/rejected → agent |
| `C_vibeprompt` | Conversation → **real** VibePrompt pipeline → compilable specification prompt → agent |

Seed files are committed **before** `TASK.md` injection so A/B/C share an identical seed tree.

---

## 4. Variant C provenance (required)

```text
conversation
 → extract_information / intent / relationship
 → apply_analysis_to_state (+ constraint cues)
 → ProjectState (origins preserved)
 → Grill attack generation
 → Grill resolve/defer from conversational evidence (does not promote inferred→CONFIRMED)
 → compilation_gate
 → specification._structured / _markdown (compilable only)
 → render_prompt
 → agent
```

Assertion origins unchanged:

```text
USER_EXPLICIT → CONFIRMED
LLM_INFERRED / GRILL_DERIVED / RESEARCH_DERIVED / SYSTEM_GENERATED → PROPOSED
```

Only authoritative (compilable) requirements enter the specification blocks.

Provenance JSON is written beside each C prompt under `prompts/<task_id>/C_vibeprompt.provenance.json`.

---

## 5. Acceptance oracle

- Tests live in seed `tests/` **before** the agent runs.  
- Agent cannot satisfy the benchmark by inventing matching test names alone.  
- Verification still requires markers in test stdout/junit after execution.

---

## 6. Metrics (seven, independent)

Reported under `overall` / per-variant, each with **full_execution_grid** and **completed_agent_quality**:

1. Requirement Coverage  
2. Constraint Preservation (rejected hits **or** constraint violations)  
3. Acceptance-Test Pass Rate  
4. Build Success Rate  
5. Test Success Rate  
6. Unsupported Feature Rate  
7. Scope Deviation (rejected / scope violation signals)

Also: `n`, `successful_runs`, `failed_runs`, `unverified_runs`.  
**No combined score.**

---

## 7. Aggregate status semantics

| Status | Meaning |
|--------|---------|
| `NOT_EXECUTED` | No agent command / no runs |
| `EXECUTED_COMPLETE` | All cells completed agent execution (quality statuses) |
| `EXECUTED_WITH_FAILURES` | Mix of completed + `FAILED_INFRASTRUCTURE`, or all infra failures |
| `EXECUTED` | Other partial completed states |

---

## 8. Remaining scientific limitations

1. Grill resolution in C uses controlled resolve/defer from conversation — not a full interactive multi-turn Grill with a human.  
2. NLP extraction quality limits what enters ProjectState from free text (construct still real, coverage may be partial).  
3. Dataset remains **SYNTHETIC CONTROLLED BENCHMARK** — no real-world generalization.  
4. Agent nondeterminism is outside harness control; record model/provider/seed if available.  
5. Constraint/scope detectors are heuristic (import/keyword based), not formal static analysis.  
6. HARNESS TEST / mock agent results are **not** scientific RQ5.

---

## 9. Pre-flight (unchanged policy)

Do not run scientific RQ5 until:

```text
[ ] VIBEPROMPT_AGENT_CMD configured
[ ] Build/test cmds set
[ ] tasks_v2 hash verified against manifest
[ ] C provenance inspected for a sample task
[ ] This protocol v2 acknowledged
[ ] Pilot subset reviewed (see §9.1)
```

Until then:

```text
RQ5 scientific execution = NOT EXECUTED
```

### 9.1 Pilot subset vs full grid

Pilot (recommended first — e.g. one task × three variants):

```bash
export VIBEPROMPT_AGENT_CMD="$PWD/evaluation/agent_execution/codex_rq5.sh"
export VIBEPROMPT_AGENT_PROVIDER=codex
export VIBEPROMPT_BUILD_CMD='python -m compileall -q .'
export VIBEPROMPT_TEST_CMD='python -m pytest -v --tb=line --junitxml=junit.xml'

backend/.venv/bin/python -m evaluation.rq5_agent_execution.run --task-id rest_echo_api
```

Filtered runs write `run_subset.json` with `is_full_scientific_grid: false` and
`config.json` `mode: PILOT_SUBSET`. Do **not** cite them as the full scientific study.

Full 36-run grid requires explicit operator ack:

```bash
export VIBEPROMPT_RQ5_ALLOW_FULL_GRID=1
backend/.venv/bin/python -m evaluation.rq5_agent_execution.run
```

Interpret metrics only together with `run_subset.is_full_scientific_grid`.
