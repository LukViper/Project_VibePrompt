# VibePrompt Product Requirements

Derived from the Master Development Specification. This is the product contract for planning and verification.

---

## 1. Product thesis

VibePrompt is a production-oriented **AI project specification and decision-support platform**.

Core pipeline:

```text
Human Intent
→ Structured Project Understanding
→ Change / Conflict Detection
→ Research
→ Decision Support
→ Adversarial Project Grill
→ Validated Specification
→ Agent-Executable Prompt
```

The final prompt is an **output**, not the core product. The evolving structured project understanding is the product.

---

## 2. Non-negotiable philosophy

| Rule | Meaning |
|---|---|
| Never blindly agree | Surface impact when new intent affects existing decisions |
| Never silently change intent | Preserve stated platforms/constraints unless user chooses otherwise |
| Never force technical decisions | Evidence → alternatives → trade-offs → **user decision** |
| Provenance | USER / RESEARCH / AI_RECOMMENDATION / SYSTEM_DEFAULT / INFERRED |
| No manufactured certainty | If evidence is inconclusive, say so |

---

## 3. Users

- **A.** Users with an idea who need coherent specification.
- **B.** Users without a developed idea who need domain-aware ideation + discovery.

Must work for beginners and experienced builders. Guest path required for core experience; auth for persistence.

---

## 4. Required capabilities

1. Natural-language discovery and intent understanding  
2. Requirement + constraint extraction (structured)  
3. Durable **ProjectState** (not chat-as-truth)  
4. Meaningful change detection vs existing state  
5. Conflict / compatibility / scope-change classification  
6. Impact analysis with consequences explained  
7. Adaptive research (levels 0–3) with evidence confidence  
8. Decision support: alternatives, pros/cons, trade-offs, user choice  
9. Decision lifecycle: PROPOSED → ACTIVE / SUPERSEDED / REJECTED / UNCERTAIN  
10. Adversarial Grill with structured findings (no vanity scores)  
11. Specification compiler from state  
12. Agent prompt compiler + coverage validation / repair  
13. Versioning + resume summary  
14. Guest + authenticated isolation  

---

## 5. Explicit non-goals (V1)

- Autonomous coding of the student’s application  
- Full Cursor/Codex product integration  
- Billing UI (architect for future usage tracking only)  
- Mandatory multi-step wizards replacing conversation  
- Fabricated research sources  
- Silent auto-rewrite of project after Grill  

---

## 6. Critical regression scenarios

| # | Scenario | Expected |
|---|---|---|
| 1 | Web → Android + iOS + Web | SCOPE_CHANGE / architecture impact; no silent PWA conversion |
| 2 | No auth → private project histories | Potential conflict surfaced |
| 3 | PostgreSQL → MongoDB | Database dependency impact |
| 4 | No login → login required | Direct conflict/change |
| 5 | Uncertain tech decision | UNCERTAIN; no fabricated winner |

---

## 7. Success criterion (first milestone)

```text
Messy idea → ProjectState → user changes requirement
→ impact/conflict explained → evidence/options → user chooses
→ state updates → Grill → realistic plan → validated spec → agent prompt
```

If this loop is unreliable, do not prioritize UI polish or new integrations.

---

## 8. Platforms

Eventually: Web, Android, iOS via shared frontend architecture (Flutter candidate; decision must remain replaceable and user-approved).
