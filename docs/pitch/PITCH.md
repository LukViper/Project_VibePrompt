# VibePrompt — Investor / Partner Pitch

**One-liner:** VibePrompt turns vague student project intent into a validated **ProjectState** and a **compiled, coverage-checked agent prompt** — with research, adversarial grill, and provenance — so Cursor gets truth, not chat noise.

**Interactive slides:** open [`index.html`](index.html) in a browser (← → / Space to navigate).  
**Suggested length:** 5 min (core) · 10–12 min (full) · add live A1 demo after the journey slide.

---

## Slide 1 — Title

**VibePrompt**  
Conversational Project Specification & Agentic Development Planner

- Spec-first product (prompt is the export)
- Hybrid NLP + LLM + deterministic rules
- Phases 0–14 shipped · **63** backend tests · acceptance journeys **A1–A7**

**Say:** “We’re not selling another chatbot. We’re selling the discipline layer between a confused student and an agent IDE.”

---

## Slide 2 — The problem

Students don’t fail at coding first — they fail at **specifying**.

| Failure mode | What happens |
|---|---|
| Vague briefs | “NLP + cyber, five weeks, no idea…” becomes unstructured chat |
| Scope creep & pivots | React → Flutter; facial recognition into a phishing detector |
| Prompt dumping | Whole transcript pasted into Cursor → filler + contradictions |
| No adversarial check | Friendly models agree; feasibility never stress-tested |

**Say:** “Agentic coding made implementation cheap. Bad requirements are now the expensive part.”

---

## Slide 3 — Insight

> The structured project specification is the product.  
> The Cursor prompt is a compiled export.

If **conversation** is the source of truth → every agent run inherits chaos.  
If **ProjectState** is the source of truth → every prompt is measurable, coverable, and repairable.

---

## Slide 4 — What it is / isn’t

| Is | Is not |
|---|---|
| Conversational project architect | Generic ChatGPT wrapper |
| Requirements + research + grill + architecture | Prompt generator alone |
| Hybrid NLP + LLM system | Pure LLM wrapper |
| Mentor + engineer + adversarial reviewer | Form wizard with mandatory steps |

Out of V1 scope: training an LLM from scratch; autonomously coding the student project; social networking.

---

## Slide 5 — Who we serve

**Primary:** students building academic software under time/team constraints.  
**Next:** hackathon teams, research-minded builders, developers preparing agentic sessions.  
**Entry:** Continue as Guest (ephemeral) · Login / Create Account (durable, isolated).

---

## Slide 6 — Canonical pipeline

```text
Human Intent
 → Discovery → Ideation → Customization
 → Research-on-Demand → Requirements
 → Adversarial Grill → Architecture / Tech
 → ProjectState → Prompt Compile → Validate
 → Agent-Executable Prompt → Cursor / Codex
```

Chat is the interface. Engines are the intelligence. ProjectState is durable memory.

---

## Slide 7 — Eight non-negotiables

1. **One workspace** — Ideas / Grill / Research / Compile are capabilities, not mandatory tabs  
2. **ProjectState wins** — conversation is input, not authority  
3. **Compile from state** — never dump raw chat into the final prompt  
4. **Research on demand** — provenance; no invented papers/URLs  
5. **Grill is adversarial** — weaknesses + must-resolve questions; no vanity score  
6. **Provenance** — USER / RESEARCH / AI_RECOMMENDATION / SYSTEM_DEFAULT / INFERRED  
7. **Hybrid NLP** — rules, TF-IDF, embeddings, NLI where measurable; LLM where generative  
8. **Don’t over-engineer** — one app, clear services, justified models  

---

## Slide 8 — Demo narrative (A1)

**“I need an NLP cybersecurity project… I don’t know what.”**

1. Guest starts → subject, solo, five weeks → ProjectState  
2. Ideation → detailed cards (problem, users, architecture, risks)  
3. Select phishing detector → lock core idea  
4. “Existing systems?” → research findings with RESEARCH provenance  
5. Facial recognition added → drift + grill must-resolve  
6. Architecture + tech with purpose / reason / alternative / trade-off  
7. Compile from state → validator repairs → dense agent prompt  

**Presenter tip:** run this live after the slide.

---

## Slide 9 — Capability engines

| Engine | What it does |
|---|---|
| Ideation | Detailed idea objects, not titles |
| Requirements | Actor / capability / acceptance; progressive questions; no silent overwrite |
| Research | On-demand findings; apply to requirements on request |
| Grill | 11 adversarial dimensions (clarity, dataset, AI necessity, timeline, security, …) |
| Architecture | Layers, tech recommendations, entities, justified APIs |
| Compile + Validate | Gate on conflicts/gaps; coverage / redundancy / ambiguity; repair loop |

---

## Slide 10 — Differentiation vs “just use ChatGPT”

| Dimension | Generic LLM chat | VibePrompt |
|---|---|---|
| Memory | Transcript | Versioned ProjectState |
| Conflicts | Often silent merge | Surface + ask |
| Pivots | Lost context | Dependency notices |
| Research | Often hallucinated | Provenance + no-fabricate |
| Quality | Vibes | Grill + prompt metrics |
| Agent handoff | Paste chat | Compiled, validated prompt |

---

## Slide 11 — Technology

**Backend:** FastAPI, SQLAlchemy, PostgreSQL/SQLite, spaCy, scikit-learn, Sentence Transformers, optional NLI, Gemini via routed providers (`TaskKind`: fast / reasoning / research).  

**Frontend:** Flutter (web/mobile), chat-first AppShell, guest/login, capability bar.  

**Security posture:** API keys never leave the server; ownership isolation; PBKDF2 + HMAC tokens.

---

## Slide 12 — System shape

```text
Flutter chat
  → REST + Bearer auth
  → Conversation Manager (stages)
  → NLP intent / extract / conflict / drift
  → Engines (ideas, research, grill, architecture)
  → ProjectState + versions + provenance
  → Prompt compiler → Validator → Agent prompt
```

---

## Slide 13 — Execution status

| Metric | Value |
|---|---|
| Plan phases | **0–14 complete** |
| Backend tests | **63 passed** |
| Acceptance | **A1–A7** covered |

**Honest limits:** research quality depends on Gemini configuration; streaming not in V1; production must set a strong `AUTH_SECRET`.

---

## Slide 14 — Market opportunity

1. **Agentic coding boom** — Cursor/Codex amplify bad specs as fast as good ones  
2. **Education gap** — courses teach features, not requirements discipline under AI pressure  
3. **Trust layer** — provenance + adversarial grill = auditability chat lacks  

---

## Slide 15 — Go-to-market sketch

| Path | Idea |
|---|---|
| Wedge | Course/lab deployments (guest sessions + login portfolios) |
| Expansion | Hackathons → indie builders → shared ProjectState teams |
| Monetization | Hosted seats, campus licenses, grounded research, IDE export packs |
| Moat | Workflow + state schema + evaluation harness — not a prompt template |

---

## Slide 16 — The ask

1. **Design partners** — 1–2 courses/labs with real student briefs  
2. **Grounded research** — verified search APIs for higher-confidence citations  
3. **Agent IDE pilots** — one-click export into Cursor/Codex with coverage report  
4. **Support** — UX polish, evaluation datasets, campus distribution  

---

## Slide 17 — Close

**Build the project in conversation. Ship the prompt from truth.**

VibePrompt = project mentor + requirements engineer + research assistant + adversarial reviewer + system architect + NLP engine + prompt compiler + prompt validator.

Not merely: chatbot + LLM API + text generator.

**Thank you — questions?**

---

## Appendix — Talking points by audience

### Faculty / lab lead
- Guest mode for class time; login for kept work  
- Grill mirrors supervisor questions (dataset, timeline, AI necessity)  
- Provenance makes “where did this requirement come from?” answerable  

### Student
- Don’t know the idea? Ideation still produces implementable cards  
- Pivot without losing the thread  
- Get a Cursor-ready prompt that still lists every REQ-ID  

### Investor / grant reviewer
- Spec-first wedge into agentic coding spend  
- Differentiated by state machine + evaluation, not model brand  
- Shipped MVP with automated acceptance journeys  

### Engineer evaluating the repo
- `plan.md` / `progress.md` / `docs/*` are the contract  
- Backend engines under `backend/app/services/` + `orchestration/`  
- Tests: `pytest` → 63; journeys in `tests/test_acceptance_journeys.py`  
