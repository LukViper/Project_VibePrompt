# Traceability

Status: **implemented** (JSON `TraceLink` on ProjectState). No graph database.

## TraceLink

Stored on `state.trace_links`:

| Field | Meaning |
|-------|---------|
| `source_type` / `source_id` | Origin entity |
| `target_type` / `target_id` | Destination entity |
| `relationship` | Link kind |
| `confidence` | Optional |
| `provenance` | Optional provenance dict |

Entity types include: `REQUIREMENT`, `CLAIM`, `ASSUMPTION`, `EVIDENCE`, `DECISION`, `ATTACK`, `VERIFICATION`, `AGENT_RUN`, `ARCHITECTURE`, `RESEARCH_FINDING`.

## Relationship types

`SUPPORTS`, `SUPPORTED_BY`, `DERIVED_FROM`, `DEPENDS_ON`, `AFFECTS`, `CHALLENGES`, `RESOLVES`, `VERIFIES`, `SUPERSEDES`.

## Lineage

`GET /projects/{id}/requirements/{requirement_id}/lineage`

Returns:

- `direct_links` involving the requirement
- `chains` — BFS paths outward from the requirement
- `version_lineage` — per-requirement change history (`changed_by`, `change_reason`, affected entities)

Example chain:

```text
REQ-009 → CLAIM-003 → EVIDENCE-004
REQ-009 → ATTACK-017 → DEC-012
```

## Validation

`validate_traceability(state)` runs before compilation:

- warnings: missing provenance, missing assertion status, missing acceptance criteria on confirmed requirements, high-risk assumptions without evidence
- blocking: unresolved blocking Grill attacks; rejected/superseded items still marked active

Broken traceability surfaces in the compilation report’s `traceability_status` and the integrity API’s `traceability` section — never collapsed into a single score.
