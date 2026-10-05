# RQ5 Pilot Report — polarity fix re-run (`rest_echo_api` × 3)
**Result directory:** `evaluation/results/2026-10-05_042303_rq5/rq5/`
**Selection:** `PILOT_SUBSET` — not the full 36-run grid.

## Requirement polarity (pre-agent)
| Variant | Positive requirements | Rejected / avoid |
|---|---|---|
| A_raw | conversation includes echo + health; Redis only as 'Do not add…' | Redis, external APIs (in conversation) |
| B_structured | gold echo + health | `REJECTED / OUT OF SCOPE`: Do not add Redis; Do not call external APIs |
| C_vibeprompt | included: `[{'id': 'REQ-001', 'text': "Support a health() function returning {'status': 'ok'}", 'assertion_status': 'CONFIRMED'}, {'id': 'REQ-002', 'text': 'The backend must use Python', 'assertion_status': 'CONFIRMED'}]` | avoid recorded in ProjectState; Redis **not** in included |

## Execution / verification

| Variant | Exit | Build | Test | Requirements | Outcome | Unsupported |
|---|---|---|---|---|---|---|
| A_raw | 0 | PASS | PASS | REQ-001=PASS, REQ-002=PASS | TASK_COMPLETE | none |
| B_structured | 0 | PASS | PASS | REQ-001=PASS, REQ-002=PASS | TASK_COMPLETE | none |
| C_vibeprompt | 0 | PASS | PASS | REQ-001=PASS, REQ-002=PASS | TASK_COMPLETE | none |

## Metrics (completed agent quality)
- requirement_satisfaction_rate: `{'n': 3, 'mean': 1.0, 'std': 0.0, 'ci95_low': 1.0, 'ci95_high': 1.0, 'median': 1.0}`
- task_completion_rate: `{'n': 3, 'mean': 1.0, 'std': 0.0, 'ci95_low': 1.0, 'ci95_high': 1.0, 'median': 1.0, 'n_complete': 3}`
- unsupported_feature_rate: `{'n': 3, 'mean': 0.0, 'std': 0.0, 'ci95_low': 0.0, 'ci95_high': 0.0, 'median': 0.0}`

## Interpretation limits
- n=3 cells on one synthetic task — no cross-variant superiority claims.
- C may still under-extract some gold positives (e.g. echo) due to NLP coverage; that is distinct from rejected→positive polarity, which this re-run validates as fixed for Redis.
