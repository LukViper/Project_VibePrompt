# Research Sources and Reference Materials

Tracks external repositories, datasets, papers, APIs, and references used by VibePrompt.

**Policy:** Runtime research must not fabricate sources. Evaluation/reference materials must not be described as training data unless a real training pipeline exists. Do not copy proprietary prompt collections.

Update this file when a source is added, licensed, or retired.

---

## 1. Runtime AI / APIs

| Source | Type | License / access | Role | Status |
|---|---|---|---|---|
| Google Gemini API (`generateContent`) | Commercial API | Google AI / API ToS; key in env | Generation, optional structured extraction, planned research | **Runtime** — integrated |
| Hugging Face model hub (Sentence Transformers, NLI weights) | Model downloads | Per-model cards (typically Apache-2.0 / similar) | Embeddings, optional NLI | **Runtime** — integrated when installed |
| spaCy `en_core_web_sm` | NLP model | spaCy model license | Preprocessing | **Runtime** — optional |

---

## 2. NLP / academic references (design evaluation)

| Source | Type | Why used | Role | Status |
|---|---|---|---|---|
| Reimers & Gurevych (2019) Sentence-BERT | Paper | Semantic similarity design | Reference | Design |
| Bowman et al. SNLI; Williams et al. MultiNLI | Datasets/papers | NLI / contradiction | Reference | Design |
| Devlin et al. BERT | Paper | Transformer classification baseline context | Reference | Design |
| Gotel & Finkelstein requirements traceability | Paper | REQ IDs and coverage metrics | Reference | Design |
| ISO/IEC/IEEE 29148 | Standard | Spec completeness expectations | Reference | Design |
| Local `datasets/*.jsonl` | Annotated project data | Intent/similarity/drift evaluation | Evaluation | In-repo |

Details: `docs/literature_review.md`.

---

## 3. Software-engineering and agent prompt references

| Source | Type | Why used | Role | Status |
|---|---|---|---|---|
| SWE-bench and related SE benchmarks | Dataset / benchmark | Requirement decomposition, repo context, acceptance/tests patterns | **Reference / evaluation only** — not claimed training data | Planned use |
| Task-oriented dialogue / goal-decomposition datasets (TBD selection) | Datasets | Clarification, state tracking, pivots | Reference / evaluation | Planned |
| Public “system prompts” collections (e.g. community awesome lists such as ManuelSLemos/awesome-llm-system-prompts, EliFuzz/awesome-system-prompts) | Public repos | Structural patterns: instruction hierarchy, repo inspection, negative constraints, validation | **Pattern reference only** — do not copy proprietary text | Planned review |

When a specific repo/commit is used, record: URL, license, date accessed, and which pattern was extracted.

---

## 4. Instruction / planning corpora

| Source | Type | Why used | Role | Status |
|---|---|---|---|---|
| OpenOrca / SlimOrca (if used) | Instruction datasets | Task decomposition / multi-step planning patterns | Reference only; no private CoT reproduction | Optional / planned |

Do not store hidden chain-of-thought. Store structured decisions in ProjectState.

---

## 5. Project-internal research outputs (runtime, planned)

When ResearchProvider runs, persist:

```text
finding
source
source_type
timestamp
relevance
confidence / verification status
project_impact
```

| Field | Meaning |
|---|---|
| `source_type` | paper, docs, repo, API docs, web, dataset card, etc. |
| Distinction | User requirement vs research fact vs AI recommendation vs system assumption |

Raw search dumps are not stored as ProjectState. Concise findings + citations only.

---

## 6. Licensing checklist (before shipping a dependency)

- [ ] License compatible with project distribution
- [ ] Attribution requirements noted
- [ ] API ToS allows the intended use
- [ ] No proprietary prompt text committed
- [ ] Evaluation data labeled as evaluation, not training, when applicable

---

## 7. Change log

| Date | Change |
|---|---|
| 2026-09-27 | Initial catalog for Phase 0 documentation completion |
