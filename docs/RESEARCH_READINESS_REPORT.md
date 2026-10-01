# Research Readiness Report

Date: 2026-10-02 (updated — RQ1/RQ3 scientific validity pass)

## Engineering

| Item | Status |
|------|--------|
| Tests | See latest `pytest` run |
| ProjectState v3 | Implemented |
| AssertionOrigin + lifecycle | Implemented |
| Force compilation audit (`FORCED_COMPILATION`) | Implemented |
| Grill API + iterative respond | Implemented |
| Attack ontology + targeted entity Grill | Implemented |
| Traceability lineage API | Implemented |
| Compilation report | Implemented |
| Integrity API | Implemented |
| Flutter Grill / lineage / evidence foundations | Implemented |

## Research

| RQ | Status | Classification |
|----|--------|----------------|
| RQ1 | Real VibePrompt pipeline; gold evaluation-only; ≥100 conversations; baselines A/B | **RUN (v2)** — scientifically valid design |
| RQ2 | Synthetic change-impact | **RUN** (prior versioned results retained) |
| RQ3 | Ontology + targeted attacks + diagnostics; ≥100 scenarios | **RUN (v2)** — report scores honestly; diagnostics explain misses |
| RQ4 | Label agreement + evidence-tracking ablation | **RUN (v2)** |
| RQ5 | Harness implementation-ready (vendor-neutral `VIBEPROMPT_AGENT_CMD`) | **HARNESS READY** / scientific **NOT EXECUTED** |

### Explicit validity statements

```text
RQ1:
real VibePrompt pipeline
(gold used only after execution for scoring)

RQ3:
prior adversarial detection ≈ 0.12 (coarse tag mapping — retained in older result dirs)
diagnosed failure modes → targeted ontology + entity targets
new results written to a new versioned run directory (do not overwrite)

RQ5:
infrastructure implemented
execution status: NOT EXECUTED
(until VIBEPROMPT_AGENT_CMD is supplied and a real agent run completes;
 HARNESS TEST ≠ scientific RQ5)
```

## Evidence classification for architectural claims

| Claim | Classification |
|-------|----------------|
| Explicit vs inferred assertions separated | SUPPORTED BY TEST |
| Grill responses mutate state with audit/trace | SUPPORTED BY TEST |
| Compiler excludes non-compilable requirements | SUPPORTED BY TEST |
| Force compile is auditable | SUPPORTED BY TEST |
| Targeted Grill identifies ProjectState entities | SUPPORTED BY TEST |
| Adversarial Grill > checklist | EVALUATE FROM RQ3 v2 metrics — do not assume |
| VibePrompt improves agent adherence | NOT EXECUTED (no agent) |
| Traceability improves impact accuracy | RUN on synthetic RQ2 — do not over-generalize |

## Limitations

- **SYNTHETIC CONTROLLED BENCHMARK** only — no real-world generalization
- Template families → correlated scenario variants
- RQ1 without LLM uses deterministic heuristics for baselines (recorded)
- Embedding backend may be lexical fallback
- RQ5 blocked without `VIBEPROMPT_AGENT_CMD`
- Small-N CIs use normal approximation

## Honest result policy

If an experiment is weak or negative, keep the numbers.  
If not run, mark `NOT RUN` / `NOT EXECUTED`.  
Never fabricate. Never overwrite prior result directories.
