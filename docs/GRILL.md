# Grill — Adversarial Requirements Review

Status: **implemented** (API + iterative loop). Experimental evaluation metrics remain scaffolded.

## Purpose

Grill challenges concrete ProjectState entities. It is not a vanity checklist and does not produce a single project score.

## Attack generation

`POST /projects/{id}/grill` runs the existing dimension checks and converts non-positive high/medium findings into `GrillAttack` records via `generate_attacks_from_state()`.

Each attack includes:

- `target_type` / `target_id` (requirement, assumption, project, …)
- `attack_type` (generator name, e.g. `FeasibilityAttackGenerator`)
- `challenge`, `rationale`, `evidence_required`, `failure_condition`
- `severity`, `blocking`
- `target_fingerprint` — hash of the target’s current text/status

Duplicates are suppressed when an open (or resolved) attack already exists for the same target + challenge **and** the same fingerprint.

## Attack prioritization

`get_next_grill_attack(state)` returns the highest-priority unresolved attack:

1. Blocking attacks first
2. Higher severity (`HIGH` → `MEDIUM` → `LOW`)
3. Attack-type priority (objective/feasibility/dataset before lower-severity scope/research)

`GET /projects/{id}/grill` returns open / resolved / deferred / blocking lists and counts.
`GET /projects/{id}/grill/next` returns the next attack only.

## Response handling

`POST /projects/{id}/grill/{attack_id}/respond`

Body:

```json
{
  "response_text": "Below 500 ms.",
  "resolution_type": "RESOLVED",
  "create_requirement": null,
  "create_evidence": null,
  "create_decision": null,
  "mutate": true
}
```

Resolution types: `RESOLVED`, `ACCEPTED`, `REJECTED`, `DEFERRED`, `PARTIALLY_RESOLVED`.

## State transitions

When `mutate=true` and the resolution is not `REJECTED`/`DEFERRED`, the service may:

| User answer pattern | Mutation |
|---------------------|----------|
| Latency / real-time threshold | Create **PROPOSED** requirement (never locked) |
| Paper / dataset / evidence citation | Create **UNVERIFIED** evidence + claim |
| WebSocket / SSE / transport choice | Create **PROPOSED** decision |
| Explicit `create_*` fields | Controlled creation as requested |

Every mutation writes:

- audit event (`GRILL_ATTACK_RESOLVED`, `REQUIREMENT_CREATED`, …)
- trace links (`ATTACK → REQUIREMENT|DECISION|EVIDENCE|CLAIM`)

## Blocking behavior

High-severity open attacks are `blocking=true`. The compilation gate refuses to compile while blocking unresolved attacks remain, unless `force=true`.

## Iterative loop

```text
Grill round → generate attacks → next attack → user response
→ state mutation → re-evaluate → generate next (no duplicates)
```

After each response, generators run again. Unchanged targets (same fingerprint) do not receive duplicate attacks.
