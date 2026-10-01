# Architecture Decision Records (ADRs)

Canonical decision log for VibePrompt. Mirrored summaries live in `plan.md`. Update when a decision is accepted, superseded, or rejected.

---

## ADR-001 — Unified conversational interface

**Status:** Accepted / implemented (Phase 12).

**Decision:** One chatbot workspace. Ideas, Grill, Research, Specification, and Compile are capabilities (chips / sheets), not mandatory navigation tabs.

**Reason:** Continuous project development; mode switching conflicts with the product definition.

**Consequences:** `AppShell` is chat-first with a capability bar; Conversation Manager owns stage transitions.

---

## ADR-002 — ProjectState is the source of truth

**Status:** Accepted / partially implemented.

**Decision:** Structured ProjectState (not raw conversation history) drives specification and prompts.

**Reason:** Requirement retention, conflict handling, and prompt coverage require durable structure. Already partially implemented.

**Consequences:** Extend schema with architecture, research, provenance, grill, prompt metrics, `conversation_stage`.

---

## ADR-003 — Research invoked on demand

**Status:** Accepted / implemented (Phase 5).

**Decision:** No user-facing Research mode. Conversation Manager / engines request research when external evidence is needed.

**Reason:** Avoid mode switching; reduce unnecessary API cost.

**Consequences:** `ResearchProvider` + `services/research.py`; findings stored with RESEARCH provenance; never fabricate sources.

---

## ADR-004 — Prompt compiled from ProjectState

**Status:** Accepted / implemented (Phases 10–11).

**Decision:** Prompt compiler reads ProjectState (+ related structured artifacts), not the full chat transcript. Validator + repair run before acceptance; compile gate blocks on open conflicts / missing objective / no requirements unless `force=true`.

**Reason:** Token efficiency, low redundancy, measurable coverage; matches agentic coding needs.

**Consequences:** `prompt_compiler.py` + `prompt_validator.py`; metrics on `prompt_metrics`.

---

## ADR-005 — Hybrid NLP + LLM

**Status:** Accepted / implemented for baseline NLP.

**Decision:** Keep spaCy, scikit-learn, Sentence Transformers, optional NLI for understanding; Gemini for generation and optional validated extraction.

**Reason:** Avoid LLM-wrapper-only product; measurable NLP components remain.

**Consequences:** Do not add NLP models without functional justification.

---

## ADR-006 — Gemini as primary LLM provider

**Status:** Accepted / implemented (single model).

**Decision:** Gemini API behind `LLMProvider`; API key in environment only; never sent to Flutter.

**Reason:** Existing integration; provider abstraction allows future backends.

**Consequences:** Add ResearchProvider and model routing; do not scatter raw HTTP Gemini calls.

---

## ADR-007 — Adversarial Grill (not chat-about-idea)

**Status:** Accepted (design). Current grill is partial checklist.

**Decision:** Grill is adversarial project validation across problem, scope, dataset, feasibility, AI necessity, evaluation, research, deployment, security, dependencies, timeline. Output structured findings—not vanity scores. Iterative.

**Reason:** Master product requirement; catches weak specs before prompt compile.

**Consequences:** Upgrade `grill.py`; integrate as GRILL stage after requirements.

---

## ADR-008 — Decision provenance

**Status:** Accepted (design). Not in schema yet.

**Decision:** Tag requirements/decisions with USER | RESEARCH | AI_RECOMMENDATION | SYSTEM_DEFAULT | INFERRED, plus reason and approval.

**Reason:** Users must distinguish facts, recommendations, and assumptions.

**Consequences:** Phase 1 data model; UI can show “where did this come from?”

---

## ADR-009 — Guest vs authenticated persistence

**Status:** Accepted / implemented (Phase 9).

**Decision:** Guest = temporary full functionality (`is_guest`, `is_ephemeral` projects). Logged-in = durable projects/versions/prompts with ownership isolation. HMAC bearer tokens; PBKDF2 password hashes. Legacy anonymous (`user_id=null`) rows remain reachable without a token for migration/tests; owned projects require matching bearer.

**Reason:** Privacy clarity; product entry requirement.

**Consequences:** `/auth/guest`, `/auth/register`, `/auth/login`, `/auth/me`; project list/rename/delete/claim; Flutter onboarding entry points.

---

## ADR-010 — Flutter single codebase

**Status:** Accepted / implemented.

**Decision:** Keep Flutter for web, Android, iOS.

**Reason:** Existing client and platforms.

**Consequences:** Phase 12 UX rewrite inside `mobile_web/`, not a new SPA framework.

---

## ADR-011 — PostgreSQL + pgvector; SQLite for tests

**Status:** Accepted / implemented.

**Decision:** Production Postgres with vector extension; SQLite for pytest and light local runs via `DATABASE_URL`.

**Reason:** Existing schema, migration, compose.

---

## ADR-012 — Prompt validation before final acceptance

**Status:** Accepted (design). Not implemented.

**Decision:** After compile, validate coverage/redundancy/ambiguity; repair missing critical requirements; show quality report; allow return to planning.

**Reason:** Incomplete prompts must not ship silently.

---

## ADR-013 — Progressive questioning

**Status:** Accepted (design). Partial via open_questions today.

**Decision:** Ask the single highest-value missing question; update state; repeat. No 15-question forms.

**Reason:** Conversational UX; higher completion rates.

---

## ADR-014 — Pivots update dependents with notification

**Status:** Accepted (design). Partial tech overwrite today.

**Decision:** On technology/requirement pivots, update dependents and tell the user meaningful consequences. Never silent major mutation.

**Reason:** Trust and conflict handling.

---

## ADR-015 — External prompt/agent patterns as references only

**Status:** Accepted.

**Decision:** Use public system-prompt / SWE-bench / dialogue datasets as structural or evaluation references. Do not copy proprietary prompts or claim training that did not occur.

**Reason:** Legal safety and honesty. Tracked in `docs/research_sources.md`.

---

## Superseded

| Item | Note |
|---|---|
| Mode-oriented V1 UI as product surface | Superseded by ADR-001 |
| Prior academic-only `plan.md` roadmap | Replaced by current `plan.md`; literature kept in `docs/literature_review.md` |
