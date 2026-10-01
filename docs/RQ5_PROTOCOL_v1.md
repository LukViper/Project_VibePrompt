# RQ5 Experimental Protocol (Frozen)

**Status:** Protocol frozen for the upcoming real-agent study.  
**Scientific execution:** **NOT YET RUN** — do not treat this document as results.  
**Harness version referenced:** `evaluation/rq5_agent_execution` (experiment_version `3.0.0` in `run.py`).  
**Dataset:** `evaluation/datasets/rq5/tasks_v1.json` (`vibeprompt-synthetic-bench/rq5` v1.0.0).

This protocol defines how a **real** coding-agent RQ5 study must be executed and reported.
It was audited against the current harness. Where the ideal study design and the
harness diverge, mismatches are listed explicitly in §14 — **the harness was not
changed** to paper over gaps.

HARNESS TEST (`python -m evaluation.rq5_agent_execution.harness_smoke`) is
**out of scope** for scientific reporting and must never be mixed into RQ5 results.

---

## 1. Objective

Compare three prompt variants under an identical downstream agent environment:

| Variant ID | Label | Intended meaning |
|------------|-------|------------------|
| `A_raw` | Raw conversation | Conversation → direct coding prompt → agent |
| `B_structured` | Structured requirements | Conversation → requirements/constraints list → agent |
| `C_vibeprompt` | VibePrompt-style | Validated-spec style prompt → agent |

**Primary question:** Does the VibePrompt-style prompt improve requirement adherence
relative to raw and structured prompts when a real coding agent implements the task?

This protocol does **not** claim that result until a configured agent run completes.

---

## 2. Tasks (frozen scientific set)

### 2.1 Dataset identity

| Field | Value |
|-------|--------|
| Path | `evaluation/datasets/rq5/tasks_v1.json` |
| Dataset id | `vibeprompt-synthetic-bench/rq5` |
| Dataset version | `1.0.0` |
| Label | `SYNTHETIC CONTROLLED BENCHMARK` |
| **N_tasks** | **12** |

### 2.2 Task IDs (frozen order)

1. `rest_echo_api`
2. `auth_token_service`
3. `crud_notes`
4. `log_parser`
5. `csv_filter_cli`
6. `word_count_pipeline`
7. `todo_backend`
8. `url_shortener`
9. `rate_limiter`
10. `file_checksum`
11. `json_schema_validator`
12. `metrics_aggregator`

### 2.3 Required fields per task (as present in v1)

Each scientific task record currently contains:

- `id`, `task_id`, `problem_statement`
- `gold_requirements` (list of strings)
- `acceptance_tests` (placeholder test names, e.g. `test_rest_echo_api_0`)
- `constraints` (currently: `python 3.11+`, `no network in tests`)
- `synthetic`, `dataset_label`

### 2.4 N (runs)

Under the current scientific runner (`run.py`):

```text
N_runs = N_tasks × N_variants = 12 × 3 = 36
```

Report all of:

| Symbol | Definition |
|--------|------------|
| `N_tasks` | 12 |
| `N_variants` | 3 (`A_raw`, `B_structured`, `C_vibeprompt`) |
| `N_runs` | 36 planned cell executions |
| `successful_runs` | runs with execution_status ∈ {EXECUTED, EXECUTED_WITH_VALIDATION, EXECUTED_WITH_PARTIAL_VALIDATION} |
| `failed_runs` | runs with execution_status = FAILED_INFRASTRUCTURE |
| `unverified_runs` | runs where every RequirementVerification status is UNVERIFIED |

Do **not** collapse these into a single score.

---

## 3. Variants A / B / C (frozen prompt construction)

Prompts are produced by `build_variant_prompts()` and written under
`evaluation/results/<timestamp>_rq5/rq5/prompts/<task_id>/` **before** agent
execution. Inputs must not be edited after generation for a registered run.

### 3.1 A — Raw (`A_raw`)

```text
conversation (synthesized if absent)
  → "You are a senior software engineer." + conversation lines
  → agent
```

If `conversation` is missing (true for current `tasks_v1.json`), the harness
synthesizes:

```text
I need: <problem_statement>
Requirement: <each gold_requirement>
```

### 3.2 B — Structured (`B_structured`)

```text
REQUIREMENTS / CONSTRAINTS / ACCEPTANCE CRITERIA sections
  → agent
```

Acceptance defaults to `gold_requirements` when `acceptance_criteria` is absent.

### 3.3 C — VibePrompt-style (`C_vibeprompt`)

```text
OBJECTIVE + CONFIRMED REQUIREMENTS + CONSTRAINTS + ACCEPTANCE CHECKLIST
  (+ REJECTED block if rejected_features present)
  → agent
```

**Frozen meaning for this study:** C uses the **same downstream agent and workspace**
as A/B. The prompt *claims* upstream validation (“Evidence and grill validation are
assumed upstream”). See §14 for the mismatch vs a live ProjectState→Grill→compile path.

---

## 4. Agent configuration

### 4.1 Required

| Variable | Role |
|----------|------|
| `VIBEPROMPT_AGENT_CMD` | Operator-authored shell command invoking the external coding agent |

If unset/empty → runner must exit with:

```text
RQ5 NOT EXECUTED
Reason: agent command unavailable
```

and must **not** emit fabricated AgentRun performance metrics.

### 4.2 Optional

| Variable | Default | Role |
|----------|---------|------|
| `VIBEPROMPT_BUILD_CMD` | unset → `NOT_CONFIGURED` | Post-agent build |
| `VIBEPROMPT_TEST_CMD` | unset → `NOT_CONFIGURED` | Post-agent tests |
| `VIBEPROMPT_RQ5_TIMEOUT` | `600` seconds | Agent wall-clock timeout |
| `VIBEPROMPT_RQ5_RETAIN_WORKSPACE` | `1` (retain) | Copy workspace into artifacts |
| `VIBEPROMPT_AGENT_MODEL` | unset | Recorded in config if provided |
| `VIBEPROMPT_AGENT_PROVIDER` | unset | Recorded as AgentRun.agent if provided (else `external_cmd`) |
| `VIBEPROMPT_RQ5_MODE` | `SCIENTIFIC` | Must remain SCIENTIFIC for this study |

### 4.3 Task delivery contract (frozen)

The harness **never** interpolates task/prompt text into `VIBEPROMPT_AGENT_CMD`.

Before launch it writes `TASK.md` and sets:

| Env var | Meaning |
|---------|---------|
| `VIBEPROMPT_TASK_DIR` | Absolute isolated workspace path |
| `VIBEPROMPT_TASK_PROMPT` | Absolute path to `TASK.md` |
| `VIBEPROMPT_TASK_ID` | Task id |
| `VIBEPROMPT_VARIANT` | Variant id |
| `VIBEPROMPT_WORKSPACE_ID` | Unique workspace id |
| `PYTHONPATH` | Repo root prepended (implementation detail) |

The agent must read the prompt file and operate **inside** `VIBEPROMPT_TASK_DIR`.

### 4.4 Vendor neutrality

Any agent (Cursor CLI, Codex, Claude Code, custom script, …) is allowed **iff** it
honors the env contract. The protocol does not hardcode a vendor.

---

## 5. Environment

### 5.1 Isolation

For every (task, variant) cell:

1. Create unique workspace (`ws-<hex>`) under a temp root  
2. Optional `seed_files` (none in current scientific tasks)  
3. Inject `TASK.md` + `VIBEPROMPT_META.json`  
4. `git init` + seed commit (`rq5-seed`)  
5. Run agent → capture git → build → test → verify  
6. Retain or destroy workspace per `VIBEPROMPT_RQ5_RETAIN_WORKSPACE`  
7. Scientific runner deletes the temp work root after copying retained workspaces

Never reuse one cell’s workspace for another.

### 5.2 Recorded environment metadata

`config.json` must include at least:

- timestamp (via `ExperimentConfig`)
- `experiment_id` / `experiment_version` (`rq5_agent_execution` / `3.0.0`)
- `dataset_id` / `dataset_version`
- `random_seed` (42 — for dataset/prompt generation determinism; agent itself may be non-deterministic)
- `rq5_config` (agent/build/test cmds, timeout, retain flag, model/provider, platform, Python version)
- `variants`, `mode=SCIENTIFIC`
- `dataset_label`

### 5.3 OS / language assumptions (tasks)

Current constraints text: Python 3.11+, no network in tests.  
Operators must ensure the agent environment can satisfy these constraints.

---

## 6. Build and test procedure

Order (frozen):

```text
agent → build → tests → requirement verification
```

### 6.1 Build

- Command: `task["build_command"]` if present, else `VIBEPROMPT_BUILD_CMD`
- If neither set → `build_status = NOT_CONFIGURED` (not PASS)
- Timeout: `min(VIBEPROMPT_RQ5_TIMEOUT, 300)`
- Record: `build_exit_code`, stdout/stderr artifact files

### 6.2 Tests

- Command: `task["test_command"]` if present, else `VIBEPROMPT_TEST_CMD`
- If neither set → `test_status = NOT_CONFIGURED` (not PASS)
- Timeout: `min(VIBEPROMPT_RQ5_TIMEOUT, 300)`
- If `junit.xml` exists in workspace after tests, its contents are appended to the
  verification evidence stream (stdout + junit text)

### 6.3 Protocol requirement for the scientific study

For a registered scientific RQ5 run, operators **must** set both
`VIBEPROMPT_BUILD_CMD` and `VIBEPROMPT_TEST_CMD` (or per-task equivalents) so that
validation is not `NOT_CONFIGURED`. Runs with missing validation remain reportable
but must be classified as partial validation (§8).

---

## 7. Requirement verification

### 7.1 Records

Reuse existing schemas/services only:

- `AgentRun` — `backend/app/schemas/agent_verification.py`
- `RequirementVerification` — same module + `backend/app/services/agent_verification.py`

Per requirement store:

| Field | Source |
|-------|--------|
| `requirement_id` | `requirement_ids[i]` or synthesized `REQ-00i` |
| `status` | PASS / FAIL / PARTIAL / UNVERIFIED / NOT_APPLICABLE / … |
| `evidence` | list of strings |
| `verification_method` | method tag |
| `agent_run_id` | linking AgentRun |

### 7.2 Decision rules (as implemented)

1. Missing evidence must not become PASS (`build_requirement_verification` demotes PASS→UNVERIFIED if evidence empty).  
2. Diff-token presence alone → **UNVERIFIED** (never PASS).  
3. PASS only when tests configured, suite status PASS, and acceptance marker appears in test stdout/junit.  
4. Suite FAIL → requirement FAIL.  
5. Build FAIL overrides a PASS to FAIL.  
6. Explicit `rejected_features` entries that equal a gold requirement text → NOT_APPLICABLE (rare path).

### 7.3 Unsupported / scope signals

`unsupported_feature_signals()` flags `rejected_features` whose tokens appear in
`git_diff` or `created_files`. Current scientific tasks **omit** `rejected_features`
(see §14).

---

## 8. Execution status vocabulary

| Status | Meaning |
|--------|---------|
| `NOT_EXECUTED` | No agent command / study not run |
| `EXECUTED` | Agent exit 0; build and test both NOT_CONFIGURED |
| `FAILED_INFRASTRUCTURE` | Agent timeout or non-zero exit |
| `EXECUTED_WITH_VALIDATION` | Agent exit 0 and build/test both configured (PASS or FAIL) |
| `EXECUTED_WITH_PARTIAL_VALIDATION` | Agent exit 0; exactly one of build/test configured |

**Rule:** Infrastructure failure is **not** agent quality failure. Report
`failed_runs` separately from requirement FAIL rates.

---

## 9. The seven metrics (independent)

Implemented in `evaluation/rq5_agent_execution/metrics.py`.  
**Never combine into one overall score.**

| # | Metric | Definition (harness) |
|---|--------|----------------------|
| 1 | **Requirement Coverage** | Per run: (# PASS verifications) / (# verifications or 1). Summarized across runs. |
| 2 | **Constraint Preservation** | Per run: `1.0` if `unsupported_features` empty else `0.0`. |
| 3 | **Acceptance-Test Pass Rate** | Per run: (# PASS among verifications with status ≠ NOT_APPLICABLE) / (# applicable). |
| 4 | **Build Success Rate** | Mean of {1 if build PASS, 0 if FAIL}; **excludes** NOT_CONFIGURED from the mean’s sample (n may be &lt; N_runs). |
| 5 | **Test Success Rate** | Same pattern for tests. |
| 6 | **Unsupported Feature Rate** | Per run: `1.0` if any unsupported_feature signal else `0.0`. |
| 7 | **Scope Deviation** | Currently **identical** to unsupported feature indicator (1 if rejected feature appears in diff/created files). |

Also report counts: `N` (=len(runs)), `successful_runs`, `failed_runs`, `unverified_runs`.

---

## 10. Failure handling

| Event | Classification | Inclusion |
|-------|----------------|-----------|
| `VIBEPROMPT_AGENT_CMD` missing | Study `NOT EXECUTED` | No scientific metrics (nulls) |
| Agent timeout / non-zero exit | `FAILED_INFRASTRUCTURE` | Counted in `failed_runs`; still present in `runs.json` |
| Build/test missing | `NOT_CONFIGURED` | Must not be treated as success |
| Build/test fail | FAIL statuses | Agent may still be EXECUTED_WITH_VALIDATION |
| Harness exception before AgentRun | Treat as infrastructure; do not invent PASS | Operator must log and exclude or re-run under §11 |

No automatic retries are implemented. A frozen study may allow **one** manual re-run
of a cell only for documented harness/environment faults (not to improve agent scores).
Any re-run must be logged in the run README.

---

## 11. Exclusion rules (reporting)

Exclude from **scientific RQ5 claims**:

1. Any `HARNESS TEST` / `mock_agent` output  
2. Runs with `label != "SCIENTIFIC"`  
3. Prior timestamped directories from incomplete/config-debug attempts (keep on disk; do not merge)  
4. Cells re-run after changing prompts or gold labels mid-study  

Include but **flag**:

1. `FAILED_INFRASTRUCTURE` cells (do not convert to quality FAIL)  
2. Cells with `NOT_CONFIGURED` build/test (partial validation)  
3. Cells where all requirements are `UNVERIFIED`

Pre-register whether primary tables use:

- **All planned cells** (intent-to-execute, N_runs=36), or  
- **Completed agent cells only** (exclude FAILED_INFRASTRUCTURE from quality means)

**Frozen default for this protocol:** report **both** tables. Primary quality means
use completed agent cells only; appendix a full-grid appendix with infrastructure failures retained.

---

## 12. Reproducibility metadata (required artifacts)

Each scientific run directory:

```text
evaluation/results/<UTC-timestamp>_rq5/rq5/
  config.json
  tasks.json
  prompts/<task_id>/{A_raw,B_structured,C_vibeprompt}.txt
  runs.json                 # only if EXECUTED
  metrics.json
  README.md
  artifacts/<workspace_id>/
    agent_stdout.txt
    agent_stderr.txt
    git_diff.patch
    build_stdout.txt / build_stderr.txt
    test_stdout.txt / test_stderr.txt
    run.json
    workspaces/…            # if retain enabled
```

Never overwrite prior result directories.

Minimum `config.json` / run metadata fields:

- timestamp, dataset version, task version, variant  
- agent command string, model/provider if available  
- build command, test command, timeout  
- platform / Python version  
- experiment_version `3.0.0`

---

## 13. Statistical reporting

### 13.1 What the harness emits today

`summarize()` per metric list:

- `n`, `mean`, `std` (population stdev), approximate **95% CI** via normal SE (`mean ± 1.96·se`)
- `median`

### 13.2 Protocol requirements for the paper/report

1. Report **all seven metrics separately** with N.  
2. Report per-variant breakdowns (A vs B vs C) — *operators must slice `runs.json` by `system_variant` if not yet automated*.  
3. State CI method: normal approximation; **underpowered / unreliable for small n**.  
4. Do **not** claim significance without a pre-registered test. If tests are added later, prefer paired comparisons across variants within task (same task_id).  
5. Distinguish **NOT EXECUTED** from **EXECUTED WITH ZERO PERFORMANCE**.  
6. Dataset label: **SYNTHETIC CONTROLLED BENCHMARK** — no real-world generalization claim.

---

## 14. Audit: protocol vs current harness (mismatches)

The following gaps were found by inspecting the implementation.  
**Harness was not modified** in this documentation pass.

| # | Topic | Protocol expectation | Harness actual | Severity |
|---|--------|----------------------|----------------|----------|
| M1 | Variant C pipeline | Live Conversation→ProjectState→Evidence→Grill→Gate→Spec→Compiler→agent | **Prompt styling only**; text says validation “assumed upstream” | High (construct validity) |
| M2 | Scientific task scaffolding | Per-task seed repos, build/test cmds, real acceptance tests | `tasks_v1.json` has **no** `seed_files`, `build_command`, `test_command`, `conversation`, `requirement_ids`, `rejected_features`, `acceptance_criteria` | High (readiness) |
| M3 | Acceptance tests | Executable tests shipped with tasks | Names like `test_rest_echo_api_0` are **placeholders**; PASS requires agent to create matching tests **and** markers to appear in stdout/junit | High |
| M4 | Constraint / scope metrics | Measure constraint adherence broadly | Both metrics depend almost entirely on `rejected_features`, which scientific tasks lack → near-trivial scores if run as-is | High |
| M5 | Untracked files in `git diff` | Full working-tree change capture | `git diff HEAD` **omits untracked files**; `created_files` from `git status` compensates for unsupported-feature signals but verification still keys off diff for some paths | Medium |
| M6 | Infrastructure vs quality in aggregates | Quality means exclude FAILED_INFRASTRUCTURE by default | `compute_rq5_metrics` includes **all** runs in coverage/acceptance lists | Medium |
| M7 | Top-level status | Reflect mixed outcomes | Scientific `run.py` sets overall `status=EXECUTED` if the loop finishes, even if many cells are FAILED_INFRASTRUCTURE | Medium |
| M8 | Per-variant metrics | First-class in metrics.json | Metrics are **pooled** across variants; variant tables require post-processing | Medium |
| M9 | PARTIAL status | Explicit partial credit | Schema supports PARTIAL; verifier **does not currently emit** PARTIAL | Low |
| M10 | Statistical tests | Pre-registered comparisons | Only descriptive `summarize()` CIs | Low (doc’d) |
| M11 | Live compile gate | C uses compiler output | No call to `prompt_compiler` / `specification` in RQ5 path | High (related to M1) |

### Implications before the real-agent study

A scientifically meaningful RQ5 run using this frozen **protocol intent** still requires
**dataset enrichment** (seed projects, real tests, rejected features where needed) and/or
harness extensions for live C-path compilation — **as a separate, versioned change**,
not silent edits during the study. Until then, any execution is limited by M1–M4.

---

## 15. Pre-flight checklist (before first scientific agent run)

```text
[ ] VIBEPROMPT_AGENT_CMD set and smoke-checked on one toy repo
[ ] VIBEPROMPT_BUILD_CMD and VIBEPROMPT_TEST_CMD set (not NOT_CONFIGURED)
[ ] tasks_v1.json frozen (hash recorded in run README)
[ ] Prompts generated and archived under prompts/
[ ] HARNESS TEST not included in scientific out_dir
[ ] Operator records agent model/provider/version
[ ] Exclusion rules (§11) acknowledged
[ ] Mismatches §14 acknowledged in the study README
[ ] RQ5 remains unreported until EXECUTED with real agent
```

---

## 16. Explicit non-claims

- This protocol file is **not** an RQ5 result.  
- Harness readiness ≠ improved agent performance.  
- Synthetic tasks ≠ real-user workloads.  
- HARNESS TEST success ≠ scientific RQ5 success.

---

## 17. References (implementation)

| Component | Path |
|-----------|------|
| Scientific runner | `evaluation/rq5_agent_execution/run.py` |
| Single-cell harness | `evaluation/rq5_agent_execution/harness.py` |
| Config / env contract | `evaluation/rq5_agent_execution/config.py` |
| Prompts A/B/C | `evaluation/rq5_agent_execution/prompts.py` |
| Verifier | `evaluation/rq5_agent_execution/verifier.py` |
| Metrics | `evaluation/rq5_agent_execution/metrics.py` |
| Workspace / git | `evaluation/rq5_agent_execution/workspace.py` |
| Executor | `evaluation/rq5_agent_execution/executor.py` |
| AgentRun / RequirementVerification | `backend/app/schemas/agent_verification.py` |
| Builders / execution status | `backend/app/services/agent_verification.py` |
| Scientific tasks | `evaluation/datasets/rq5/tasks_v1.json` |
| Operator README | `evaluation/rq5_agent_execution/README.md` |
