# Research & Evaluation Audit

Audit date: 2026-10-02. Purpose: establish what can already be measured before hardening RQs and ablations.

## Current evaluation capabilities

| Asset | Location | Status |
|-------|----------|--------|
| NLP intent / similarity / drift metrics | `evaluation/run_nlp_eval.py` | Runnable; uses `datasets/` |
| E2E journey metrics | `evaluation/run_e2e_eval.py` | Runnable |
| Baseline prompt vs VibePrompt coverage | `evaluation/baseline_comparison.py` | Scaffold; **uses requirement-ID/text presence** |
| Grill / traceability / agent / ablation READMEs | `evaluation/*/README.md` | Scaffold only — **NOT RUN** |
| Conversation fixtures | `datasets/conversations/*.json` (10) | Controlled dialogues |
| Intent / similarity / relationship / drift | `datasets/*.jsonl` | Annotated NLP data |

## Existing metrics (production-adjacent)

- Prompt validator: requirement/constraint/acceptance coverage, redundancy, ambiguity
- Compilation gate: `can_compile`, included/excluded requirements with reasons
- Integrity summary: counts only (no single score)
- Grill listing: open/resolved/deferred/blocking counts

## Shortcomings for research claims

1. No formal RQ1–RQ5 experiment harness with gold labels.
2. Baseline comparison uses ID/text string presence — forbidden as primary RQ1/RQ5 metric.
3. No ablation runners.
4. No dataset versioning metadata for research benchmarks.
5. No statistical reporting (N, mean, SD, CI).
6. RQ5 agent execution: models exist; **no agent integration** → must report `NOT EXECUTED` until available.
7. Assertion origin conflates USER extraction with explicit confirmation (`_new_requirement` auto-CONFIRMED for USER).
8. `force=true` creates `PROMPT_COMPILED` with `forced` flag but no dedicated `FORCED_COMPILATION` audit event with blocking issues snapshot.
9. Frontend Grill shows narrative only — no attack cards / respond flow.
10. Traceability lineage API exists; no expandable tree UI.

## RQ1–RQ5 status (pre-hardening)

| RQ | Status | Evidence |
|----|--------|----------|
| RQ1 Requirement preservation | IMPLEMENTED BUT NOT EVALUATED | State + compiler exist; no gold benchmark yet |
| RQ2 Change impact / traceability | IMPLEMENTED BUT NOT EVALUATED | Impact analysis + TraceLink; no gold impact set |
| RQ3 Grill effectiveness | IMPLEMENTED BUT NOT EVALUATED | Adversarial attacks; no flawed-scenario benchmark |
| RQ4 Evidence-backed decisions | IMPLEMENTED BUT NOT EVALUATED | Evidence/Claim links; no decision-support benchmark |
| RQ5 Agent adherence | NOT IMPLEMENTED (harness pending) | AgentRun models only |

## Exact files to modify

- `backend/app/schemas/assertions.py` — AssertionOrigin
- `backend/app/services/assertion_lifecycle.py` — origin → status rules
- `backend/app/services/project_state.py` — `_new_requirement` paths
- `backend/app/services/grill_session.py` — GRILL_DERIVED origin
- `backend/app/services/prompt_compiler.py` — FORCED_COMPILATION audit
- `mobile_web/lib/features/grill/grill_screen.dart` — attack cards
- `mobile_web/lib/features/project_state/project_state_panel.dart` — lineage tree
- `mobile_web/lib/services/project_service.dart` — API methods
- docs (METHODOLOGY, EVALUATION, REPRODUCIBILITY, GRILL, TRACEABILITY)

## Exact files to add

- `docs/RESEARCH_EVALUATION_AUDIT.md` (this file)
- `docs/EVALUATION.md`, `docs/REPRODUCIBILITY.md`, `docs/RESEARCH_READINESS_REPORT.md`
- `evaluation/common/*`
- `evaluation/datasets/` research benchmarks + README
- `evaluation/rq1_requirement_preservation/` … `rq5_agent_execution/`
- `evaluation/ablations/` runners
- `evaluation/run_all.py`, `evaluation/generate_report.py`
- Tests for assertion origin + force compile
- Flutter evidence/lineage widgets as needed

## Non-goals for this phase

- SQL migrations
- Live Cursor/Codex integration
- Fabricating experiment result numbers
- Overall vanity score
