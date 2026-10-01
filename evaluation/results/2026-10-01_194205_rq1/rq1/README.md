# RQ1 Requirement Preservation (v2)

N=120 — **SYNTHETIC CONTROLLED BENCHMARK**

VibePrompt uses the real extraction→ProjectState pipeline.
Gold annotations are used **only** for post-hoc scoring.
Matching: token Jaccard ≥ 0.55 (not requirement IDs).

Baselines A/B use LLM when configured; otherwise deterministic heuristics (recorded in llm metadata).
