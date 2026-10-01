# VibePrompt Architecture Audit

Audit date: 2026-10-01. Purpose: map the existing system before evolving it into an evidence-tracked conversational requirements-engineering platform for coding agents.

## Product direction

**Today:** conversation → structured `ProjectState` → Grill checklist → specification → agent prompt.

**Target:** conversation → NLP extraction → `ProjectState` (claims, requirements, assumptions, evidence, decisions) → adversarial Grill (targeted attacks + resolution) → traceability validation → specification → prompt compiler → (recorded) agent runs → requirement verification → updated `ProjectState`.

The validated state/specification is the product; the prompt is a compiled artifact.

---

## Current architecture

| Layer | Location | Role |
|-------|----------|------|
| API | `backend/app/main.py`, `backend/app/api/*` | FastAPI: auth, projects, chat, requirements, ideas, prompts, decisions |
| Orchestration | `backend/app/orchestration/conversation_manager.py` | Chooses next action from intent + stage; does not use chat history as source of truth |
| Conversation | `backend/app/services/conversation.py` | Message handling, intent routing, state updates |
| ProjectState | `backend/app/services/project_state.py`, `backend/app/schemas/state.py` | Authoritative JSON on `Project.state`; requirements, decisions, research, grill, conflicts |
| NLP | `backend/app/nlp/*` | Intent, extraction, similarity, drift, contradiction, embeddings |
| Grill | `backend/app/services/grill.py` | Dimension-based adversarial review; outputs `grill_findings` / `grill_report` |
| Research | `backend/app/services/research.py` | `ResearchProvider` + levels; findings on state; **PROPOSED** decisions, not auto-requirements |
| Specification | `backend/app/services/specification.py` | Markdown + structured spec from state |
| Prompt pipeline | `backend/app/services/prompt_compiler.py`, `prompt_validator.py` | Gate → compile → validate/repair |
| Impact | `backend/app/services/impact_analysis.py` | Change impact on decisions/architecture |
| Persistence | `backend/app/models/project.py` | `Project.state` JSON + normalized `Requirement`/`Decision` rows synced from state |
| Frontend | `mobile_web/lib/*` | Flutter web/mobile: chat, grill, spec, prompt, basic state panel |
| Evaluation | `evaluation/*.py`, `datasets/*` | NLP metrics, e2e, baseline prompt comparison |

### Data flow (current)

1. User message → `classify_intent` + `extract` → `apply_extraction` in `project_state.py`.
2. Requirements created via `_new_requirement` (USER provenance by default); similarity `_link` can merge/modify.
3. Research on demand → findings appended to `state.research`; non-system findings → `propose_decision(..., PROPOSED)`.
4. User **apply research** → explicit `_new_requirement` with RESEARCH provenance (`apply_research`).
5. Grill → `_dimension_checks` → narrative report on state (not entity-targeted attacks yet).
6. Compile → `compilation_gate` (objective, active reqs, open conflicts) → spec → prompt.

### Authoritative state

- **`Project.state`** (migrated via `migrate_state`) is authoritative for the application.
- SQL `requirements` / `decisions` tables are synced for querying/history (`_sync_requirements`, `_sync_decisions`); not a second ProjectState implementation.

---

## ProjectState schema (v2 today)

Defined in `backend/app/schemas/state.py` (`ProjectStateModel`, `schema_version=2`).

Important fields:

- **Lifecycle:** `conversation_stage`, `conversation_context`, `exploration`
- **Project:** `project`, `academic`, `constraints`, `core_idea`, `idea`
- **Requirements:** list of dicts (`id`, `type`, `text`, `status`, `version`, `provenance`, `versions`, optional `acceptance`)
- **Decisions:** normalized `DecisionStatus` (PROPOSED/ACTIVE/…)
- **Research:** list of findings with `verification_status`, `provenance`
- **Grill:** `grill_findings`, `grill_report`
- **Quality:** `conflicts`, `drift`, `scope`, `readiness_gaps`, `open_questions`
- **Outputs:** `prompt`, `prompt_metrics`

**Not yet present (target):** claims, assumptions, first-class evidence list, grill attacks/responses, trace links, audit events, agent runs, requirement verifications, unified `AssertionStatus` on entities.

---

## Grill (current)

- File: `backend/app/services/grill.py`
- Dimensions: problem clarity, scope, dataset, feasibility, AI necessity, evaluation, research potential, deployment, security, dependency risk, timeline, objective alignment.
- Output: severity-tagged dimension rows; weaknesses/missing/risks; **generic** questions (often not bound to `REQ-*`).
- `conversational_challenge` for chat; full `grill()` persists structured report.
- **Gap:** no `GrillAttack` / `GrillResponse` entities; no iterative resolution loop tied to state mutations.

---

## Research (current)

- File: `backend/app/services/research.py`; provider: `backend/app/llm/research.py`
- Levels LEVEL_0–LEVEL_3; strips suspect fabricated URLs.
- Findings stored on `state.research` with `verification_status` default **unverified**.
- Creates **PROPOSED** `research_finding` decisions; chat copy says findings are not locked requirements.
- **Gap:** no separate Evidence/Claim records; no trace links from research → evidence → decision.

---

## Prompt compiler & validation

- `compilation_gate`: open conflicts, missing objective, no active requirements.
- Compiler uses active requirements from spec; does not yet filter by assertion lifecycle or grill attack blocking.
- Validator: coverage metrics, headings, redundancy; uses requirement ID substring presence (known limitation for RQ5).

---

## Embeddings (current)

- `backend/app/nlp/embeddings.py`: `EmbeddingBackend` — SentenceTransformer if available, else `HashingVectorizer` (512-d).
- `name` property reports backend; used in similarity linking (`_link` threshold 0.78) — **candidate** merge only, not NLI-validated truth.

---

## Tests (current)

18 modules under `backend/tests/`: state migration, auth, NLP, drift, grill, research, requirements engine, prompt quality, orchestration, acceptance journeys, etc.

**Gaps relative to target:** assertion invariants, entity-targeted grill, traceability, compilation blocking on attacks, verification loop, research→requirement auto-creation guard tests.

---

## Frontend integration

- `ProjectService` + `ApiClient` call project/message/prompt endpoints.
- `ProjectStatePanel` / `StateScreen`: title, requirements list, decisions, conflicts — **no** integrity dimensions, evidence, or trace view yet.
- Grill/spec/prompt screens exist and must remain.

---

## Duplicate / overlap

- Decisions vs research findings vs requirements — overlapping narratives; target separates **Claim** vs **Requirement** vs **Evidence**.
- Grill dimension output vs `open_questions` / `readiness_gaps` — related but not linked by ID.
- `Decision.evidence` list vs dedicated Evidence entity — will consolidate on Evidence + TraceLink.

---

## Functionality that must remain unchanged

- Guest/auth flows, project CRUD, chat orchestration, idea generation/selection, existing API routes (backward compatible extensions OK).
- `migrate_state` upgrade path for legacy projects.
- Research provider abstraction and LEVEL_0 “no invented sources” behavior.
- Prompt compiler pipeline (extend gate, do not replace wholesale).
- Existing test suite passing unless explicitly superseded by new invariants.

---

## Implementation map

### Modify (planned / in progress)

| File | Change |
|------|--------|
| `backend/app/schemas/state.py` | v3 fields: claims, assumptions, evidence, grill_attacks, grill_responses, trace_links, audit_events, agent_runs, verifications; requirement `assertion_status` |
| `backend/app/services/project_state.py` | assertion defaults on new requirements; optional audit hooks |
| `backend/app/services/research.py` | emit Evidence + Claim; no auto-requirements |
| `backend/app/services/grill.py` | persist targeted `GrillAttack` records |
| `backend/app/services/prompt_compiler.py` | strengthened compilation gate |
| `backend/app/nlp/embeddings.py` | provider-style backends + metadata |
| `mobile_web/lib/features/project_state/project_state_panel.dart` | Project Integrity panel |
| `docs/architecture.md`, README | align with implementation status |

### Add

| File | Purpose |
|------|---------|
| `backend/app/schemas/assertions.py` | AssertionStatus, entity enums |
| `backend/app/schemas/grill_entities.py` | GrillAttack, GrillResponse |
| `backend/app/schemas/traceability.py` | TraceLink |
| `backend/app/schemas/agent_verification.py` | AgentRun, RequirementVerification |
| `backend/app/services/assertion_lifecycle.py` | Invariants & promotion rules |
| `backend/app/services/integrity_store.py` | Create/list claims, assumptions, evidence |
| `backend/app/services/grill_attack_generators.py` | Dimension → targeted attacks |
| `backend/app/services/traceability.py` | Links + validation helpers |
| `backend/app/services/audit_log.py` | Immutable audit events |
| `backend/tests/test_state_integrity.py` | Phase 1 tests |
| `backend/tests/test_grill_attacks.py` | Phase 2 tests |
| `backend/tests/test_traceability.py` | Phase 3 tests |
| `backend/tests/test_compilation_gate_integrity.py` | Phase 4 tests |
| `evaluation/grill/`, `evaluation/traceability/`, etc. | RQ experiment scaffolding |

---

## Phased rollout (this repo)

1. **Phase 1** — Assertion lifecycle, claims, assumptions, evidence (+ tests) ✅ started  
2. **Phase 2** — GrillAttack, generators, iterative hooks (+ tests)  
3. **Phase 3** — TraceLink, lineage metadata, validation (+ tests)  
4. **Phase 4** — Compilation gate + compiler filters (+ tests)  
5. **Phase 5** — AgentRun, RequirementVerification models (+ tests)  
6. **Phase 6** — Evaluation baselines/ablations  
7. **Phase 7** — Frontend Project Integrity UI  

---

## Definition of done tracking

See master spec §34; this audit is the baseline checklist. Update README/docs with **implemented / experimental / planned** labels as each phase lands.
