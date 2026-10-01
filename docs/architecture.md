# VibePrompt Architecture

Documents **as-built** repository reality and **Master Spec target**. Keep aligned with `plan.md` and `docs/product_requirements.md`.

---

## 1. Product role

```text
Human Intent
 → Structured Project Understanding (ProjectState)
 → Change / Conflict Detection
 → Research (adaptive)
 → Decision Support (user decides)
 → Adversarial Grill
 → Validated Specification
 → Agent-Executable Prompt
```

Chat is the interface. **ProjectState** is the source of truth. The prompt is a compiled artifact.

---

## 2. As-built architecture (2026-09-28 audit)

```text
┌──────────────────────────────────────────────┐
│ mobile_web (Flutter)                         │
│ Guest / Login → chat-first AppShell          │
│ Capability bar: Ideas, Research, Grill, …    │
│ Inline idea cards in chat                    │
└─────────────────────┬────────────────────────┘
                      │ REST + Bearer token
                      ▼
┌──────────────────────────────────────────────┐
│ FastAPI (backend/app)                        │
│ /auth /projects /messages /ideas             │
│ /grill /architecture /prompt(+validate)      │
└─────────────────────┬────────────────────────┘
                      │
     conversation.py + ConversationManager
     NLP (intent, extract, embed, contradict, drift)
                      │
              ProjectState (schema_version 2)
                      │
     ideation / research / grill / architecture
     prompt_compiler → prompt_validator
                      │
         SQLite (local) or PostgreSQL + pgvector
```

### Module map (actual paths)

| Concern | Path |
|---|---|
| API | `backend/app/api/*` |
| Auth | `backend/app/auth/*` |
| Settings | `backend/app/config/settings.py` |
| ORM | `backend/app/models/*` |
| ProjectState schema | `backend/app/schemas/state.py`, `provenance.py` |
| Conversation | `backend/app/services/conversation.py` |
| State mutations | `backend/app/services/project_state.py` |
| Versioning | `backend/app/services/versioning.py` |
| Ideation | `backend/app/services/idea_generation.py` |
| Research | `backend/app/services/research.py`, `llm/research.py` |
| Grill | `backend/app/services/grill.py` |
| Architecture | `backend/app/services/architecture.py` |
| Spec / Prompt | `specification.py`, `prompt_compiler.py`, `prompt_validator.py` |
| NLP | `backend/app/nlp/*` |
| LLM | `backend/app/llm/*` (Gemini + router by TaskKind) |
| Client | `mobile_web/lib/{widgets,features,services,models}` |

### Runtime / environment

| Item | Reality |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy, Alembic present |
| Local DB | Often `sqlite+pysqlite:///./vibeprompt.db` via `.env` |
| Compose | Postgres/pgvector + backend (`docker-compose.yml`) |
| LLM | `GEMINI_API_KEY` server-side only |
| Auth | HMAC bearer tokens; PBKDF2 password hashes; guest users |
| Client | Flutter (web + android/ios folders); Provider + http |
| Tests | 63 backend pytest tests; datasets + evaluation scripts |
| Schema drift | `create_all` + `ensure_schema.py` for SQLite column adds |

### What is reusable

- ProjectState v2 + provenance helpers  
- Hybrid NLP stack and ConversationManager  
- Ideation, grill dimensions, research service, prompt compile/validate  
- Guest/login ownership isolation  
- Chat-first Flutter shell + capability invocations  
- Acceptance journeys A1–A7 as regression anchors  

### Architectural contradictions vs Master Spec

| Master Spec expectation | Status after 2026-09-28 update |
|---|---|
| Decision lifecycle PROPOSED/ACTIVE/SUPERSEDED/… | **Implemented** in ProjectState + approve/reject API |
| Never force tech decisions | Architecture writes **PROPOSED** only; user must approve |
| Adaptive research levels 0–3 | **Implemented** (`select_research_level`) |
| Grill BLOCKING / HIGH RISK / … | **Implemented** (`grill_report` structured + narrative) |
| Change impact (Web→mobile, auth, DB) | **Implemented** (`impact_analysis`) + Master Spec tests 1–5 |
| Multi-provider AIProvider | Still Gemini-centric |
| Streaming to clients | Not implemented |
| Dedicated DB tables for grill/research | Still mostly JSON on ProjectState |
| Analytics events | Not implemented |

---

## 3. Target architecture (Master Spec)

```text
Flutter conversational workspace
  → REST (+ streaming later)
  → Auth / Projects / Conversations
  → NLP pipeline (intent, extract, normalize, change detect)
  → ProjectState service (versioned)
  → Conflict + Impact Analysis
  → Decision Support (PROPOSED → user → ACTIVE)
  → Research engine (levels 0–3)
  → Grill engine (structured adversarial report)
  → Specification compiler
  → Prompt compiler + validator
  → Persistence (Postgres), auditability
```

Preferred evolution: **introduce clear service boundaries** (even if folders stay under `services/` initially) rather than a big-bang rewrite into empty packages.

Provider abstraction target:

```text
LLMProvider ← GeminiProvider, OpenAIProvider, …
EmbeddingProvider
ResearchProvider (level-aware)
```

---

## 4. Data entities

**Present:** users, projects, project_versions, conversations, messages, requirements, requirement_versions, decisions, ideas, specifications, final_prompts.

**Missing / thin vs Master Spec:** decision_dependencies, research_sources, research_findings (as first-class tables), grill_reports (persisted mostly inside ProjectState JSON), prompt_versions (prompt rows exist; versioning incomplete), conflicts table (in-state only).

---

## 5. Security (current)

- Bearer auth + project ownership checks  
- Rate limiting middleware  
- Security headers  
- Keys only in server `.env`  
- Prompt-injection flag in preprocessing  

Gaps: production `AUTH_SECRET`, fuller LLM output validation policy, stronger migration discipline, audit log for sensitive ops.

---

## 6. Frontend experience (current)

- One primary chat workspace  
- Capability bar invokes ideation/research/grill/architecture/compile  
- Ideas rendered inline (not mandatory Ideas tab)  
- Grill/prompt still open as sheets for long text  

Target: more contextual cards for conflict, research, grill findings, and decision choices inside the conversation.

---

## 7. Implementation policy

1. Preserve working NLP / ProjectState / prompt paths.  
2. Prefer additive domain-model upgrades with migrations.  
3. Gate AI recommendations behind user decision capture.  
4. Do not mark Master Spec phases complete without tests matching §§37–38.  
5. Phase order follows `plan.md` after Phase 0 approval.
