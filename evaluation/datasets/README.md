# Evaluation datasets

## Dataset ID

`vibeprompt-synthetic-bench`

## Version

`1.0.0`

## Creation method

Programmatic templates via `python -m evaluation.datasets.generate`.

## Annotation schema

Each RQ folder contains JSON arrays of scenarios with gold labels.

| RQ | File | Gold fields |
|----|------|-------------|
| RQ1 | `rq1/scenarios_v1.json` | `gold_requirements`, `gold_constraints`, `rejected`, `superseded` |
| RQ2 | `rq2/scenarios_v1.json` | `gold_impact` |
| RQ3 | `rq3/scenarios_v1.json` | `gold_issue_tags`, `gold_severity`, `gold_should_block` |
| RQ4 | `rq4/scenarios_v1.json` | `gold_label`, `gold_evidence_backed` |
| RQ5 | `rq5/tasks_v1.json` | `gold_requirements`, `acceptance_tests` |

## Label definition

- Matching uses **token Jaccard ≥ 0.55**, not requirement IDs.
- All rows set `"synthetic": true`.

## Limitations

- Synthetic / controlled — do **not** claim real-world generalization.
- Template reuse creates correlated examples; treat N carefully.
- RQ5 requires an external coding agent for full execution.

Regenerate:

```bash
python -m evaluation.datasets.generate
```
