# VibePrompt — Live Plan

> Source of truth for **what to build next**, aligned to the Master Development Specification.
> Companion: `progress.md`, `docs/architecture.md`, `docs/product_requirements.md`.

**Active directive:** Master Spec phases **0–11, 13–14 Complete** (2026-09-28). **Phase 12 (mobile hardened) deferred** by request.

---

## Product (one line)

Human Intent → Structured Project Understanding → Change/Conflict Detection → Research → Decision Support → Grill → Validated Spec → Agent-Executable Prompt.

The evolving **ProjectState / specification** is the product. The prompt is a compiled artifact.

---

## Status vs Master Spec phases

| Phase | Component | Planned | Implemented | Tested | Verified | Status |
|---|---|---|---|---|---|---|
| 0 | Repository audit + docs | Yes | Yes | N/A | Yes | **Complete** |
| 1 | Core domain model (Decision lifecycle, …) | Yes | Yes | Yes | Yes | **Complete** |
| 2 | AI provider abstraction (multi-provider) | Yes | Yes | Yes | Yes | **Complete** (Gemini + OpenAI + auto) |
| 3 | NLP / conversation engine | Yes | Yes | Yes | Yes | **Complete** |
| 4 | Change + conflict engine | Yes | Yes | Yes | Yes | **Complete** |
| 5 | Decision support (alternatives → user choice) | Yes | Yes | Yes | Yes | **Complete** (API + UI Accept/Reject) |
| 6 | Adaptive research (levels 0–3) | Yes | Yes | Yes | Yes | **Complete** |
| 7 | Grill (structured BLOCKING/HIGH/…) | Yes | Yes | Yes | Yes | **Complete** |
| 8 | Specification compiler | Yes | Yes | Yes | Yes | **Complete** (Master Spec sections) |
| 9 | Prompt compiler + validation | Yes | Yes | Yes | Yes | **Complete** |
| 10 | Persistence + auth | Yes | Yes | Yes | Yes | **Complete** (guest/login + schema ensure + prod secret gate) |
| 11 | Web conversational workspace | Yes | Yes | Yes | Yes | **Complete** (chat-first + decisions + summary + SSE) |
| 12 | Android + iOS (hardened) | Yes | Scaffold only | No | No | **Deferred** |
| 13 | E2E evaluation | Yes | Yes | Yes | Yes | **Complete** (A1–A7 + Master Spec 1–5 + phase suite) |
| 14 | Production readiness | Yes | Yes | Yes | Yes | **Complete** (`/readyz`, security/deployment docs, analytics) |

Verification command: `cd backend && .venv/bin/pytest -q` → **82 passed**.

---

## Non-negotiables (from Master Spec)

1. Never blindly agree.
2. Never silently change user intent.
3. Never force a technical decision — user decides after evidence/alternatives.
4. Distinguish facts from recommendations (provenance).
5. Never manufacture certainty.
6. No fake research / placeholder AI marked complete.
7. Prompt compiled from ProjectState, not raw chat.
8. One conversational workspace (capabilities, not mandatory mode tabs).

---

## Deferred / out of scope now

- Phase 12 mobile hardening (Android/iOS store polish) — Flutter scaffold remains.
- Billing UI, GitHub intelligence, full PDF document system.
