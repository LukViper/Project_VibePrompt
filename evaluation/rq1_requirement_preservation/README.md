# RQ1 — Requirement Preservation

**Dataset label:** `SYNTHETIC CONTROLLED BENCHMARK`  
**Do not claim real-world generalization.**

## Pipeline (valid)

```text
Conversation
 ↓
system under test (Baseline A | Baseline B | VibePrompt)
 ↓
predictions
 ↓
gold annotations (evaluation only)
 ↓
metrics
```

VibePrompt path:

```text
messages → extract_information → apply_analysis_to_state → ProjectState
        → active/compilable requirements
```

Gold is **never** an input to VibePrompt or baselines.

## Systems

| System | Description |
|--------|-------------|
| Baseline A | Direct LLM / heuristic requirement extraction from conversation |
| Baseline B | Structured JSON LLM / heuristic extraction |
| VibePrompt | Actual NLP extraction + ProjectState mutation |

LLM metadata (model, version, temperature, seed) is recorded when an LLM is used.
If unavailable, heuristics run and `llm.available=false` is recorded.

## Metrics

Defined in `evaluator.py` / `evaluation/common/metrics.py`:

- Requirement Precision / Recall / F1
- Constraint Precision / Recall / F1
- Technology Precision / Recall
- Rejected Requirement Leakage
- Superseded Requirement Leakage
- Unsupported Addition Rate
- Assertion-Origin Accuracy

Matching: normalized token Jaccard ≥ 0.55 (not requirement IDs).

## Run

```bash
backend/.venv/bin/python -m evaluation.rq1_requirement_preservation.dataset
backend/.venv/bin/python -m evaluation.rq1_requirement_preservation.run
```

## Plugging in real-world data

Provide a JSON list with the same schema as `scenarios_v2.json`
(`messages` + gold fields). Metric code does not change — only the dataset path.
