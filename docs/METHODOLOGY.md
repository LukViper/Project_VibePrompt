# Methodology

Status: describes **implemented** ProjectState methodology and evaluation design.
Agent-execution (RQ5) remains **NOT EXECUTED** until `VIBEPROMPT_AGENT_CMD` is configured.

## Core idea

VibePrompt maintains an auditable model of intent. The prompt is a compiled artifact of validated state — not the product itself.

## Entity roles

| Entity | Role | Default lifecycle |
|--------|------|-------------------|
| **Claim** | Asserted statement (user / research / inference). Not a requirement. | `MENTIONED` / `PROPOSED` |
| **Evidence** | Supporting material with provenance and verification status | `UNVERIFIED` until explicitly verified |
| **Assumption** | Risky belief; primary Grill target | `PROPOSED`, grill_status `UNRESOLVED` |
| **Decision** | Choice with alternatives/evidence | `PROPOSED` until user approves → `ACTIVE` |
| **Requirement** | Binding intent for compilation | Must be `CONFIRMED` or `LOCKED` (+ `status=active`) to compile |
| **GrillAttack** | Targeted challenge against a concrete entity | `OPEN` → response → `RESOLVED`/`DEFERRED`/`REJECTED` |
| **Verification** | Post-implementation check against a requirement | Model only (`AgentRun` / `RequirementVerification`) |

## Assertion lifecycle

```text
MENTIONED → INFERRED → PROPOSED → CONFIRMED → LOCKED
                    ↘ REJECTED / SUPERSEDED
```

Illegal skips (enforced by `promotion_allowed`):

- `INFERRED → CONFIRMED` / `INFERRED → LOCKED`
- `PROPOSED → LOCKED` (must confirm first)

Promotion APIs: `/assertions/{id}/propose|confirm|reject|lock|supersede`.

## Research path

```text
query → finding → Evidence (UNVERIFIED) + Claim → optional PROPOSED decision
```

Research never silently creates requirements. Applying research remains an explicit user action.

## Grill path

```text
Scenario → identify claim/assumption → target ProjectState entity
        → attack ontology type → structured GrillAttack
```

Attack ontology includes: `RESOURCE_FEASIBILITY`, `DATA_AVAILABILITY`, `LATENCY`,
`SCALABILITY`, `SECURITY`, `EVALUATION`, `DEPENDENCY`, `SCOPE`, `COST`, `TIMELINE`,
`ASSUMPTION`, `CONTRADICTION`, `REQUIREMENT_AMBIGUITY`, `ARCHITECTURE_MISMATCH`,
`TECHNOLOGY_JUSTIFICATION`, `DEPLOYMENT`, `RELIABILITY`, `MAINTAINABILITY`.

Attacks reference concrete Requirements / Assumptions / Claims / Decisions /
Constraints / Architecture components whenever possible.

## Compilation

Only requirements passing `requirement_is_compilable()` enter the specification/prompt.

Excluded items appear in the compilation report with reasons (e.g. `PROPOSED but not user-confirmed`, `SUPERSEDED by REQ-011`).

Blocking unresolved Grill attacks prevent compilation unless forced.

## Similarity

Embeddings identify **candidate** relationships only. Similarity thresholds do not alone establish contradictions or duplicates as authoritative truth.

## Assertion origin (explicit vs inferred)

Every requirement carries `assertion_origin`:

| Origin | Initial status |
|--------|----------------|
| `USER_EXPLICIT` | `CONFIRMED` |
| `USER_INFERRED` | `PROPOSED` |
| `LLM_INFERRED` | `PROPOSED` |
| `GRILL_DERIVED` | `PROPOSED` |
| `RESEARCH_DERIVED` | `PROPOSED` |
| `SYSTEM_GENERATED` | `PROPOSED` |
| `AGENT_DERIVED` | `PROPOSED` |

Only explicit user confirmation (or `USER_EXPLICIT` creation) yields authoritative requirements for compilation.

Force compilation (`force=true`) always emits a `FORCED_COMPILATION` audit event with blocking-issue snapshot.

## Evaluation methodology

### Dataset policy

Current corpora are **SYNTHETIC CONTROLLED BENCHMARK**.  
They do not support real-world generalization claims. Future real-world datasets
plug in via the same schema; metrics stay unchanged.

### RQ1 — Requirement preservation

Valid pipeline (v2):

```text
Conversation → system under test → predictions → gold scoring
```

VibePrompt uses `extract_information` + `apply_analysis_to_state` (no gold input).  
Baselines A/B use LLM when configured, else recorded heuristics.  
Matching: token Jaccard ≥ 0.55 (never requirement-ID equality).

### RQ3 — Grill

Compare A (none) / B (checklist) / C (targeted ontology). Meanings are fixed
before results. Diagnostics explain every miss (`rq3_diagnostics.*`).  
Do not tune for vanity scores.

### RQ4 — Evidence

Two experiments: label agreement; No Tracking vs Tracking on deliberate
unsupported tech decisions with evidence variants. Report rates separately.

### RQ5 — Agent execution

Harness is **implementation-ready** (isolated workspace, agent/build/test capture,
`AgentRun` / `RequirementVerification`, independent metrics).

Empirical status without an agent command:

```text
RQ5 NOT EXECUTED
Reason: agent command unavailable
```

Task contract: write `TASK.md`; pass paths via `VIBEPROMPT_TASK_*` env vars.
Never fabricate results. HARNESS TEST (mock agent) validates infrastructure only
and must not be reported as scientific RQ5.

Never invent numbers. Experiment outputs are versioned; prior runs are retained.
