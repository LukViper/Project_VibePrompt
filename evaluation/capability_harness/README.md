# Capability harness

Processes **ideas**, **architecture**, and **grill** through gated API calls so VibePrompt cannot be misused as a free-form consultant on an empty project.

## What it checks

For each domain (`computer_networks`, `nlp`, `cybersecurity`, `data_science`):

1. Seed subject via `POST /projects`
2. `POST /projects/{id}/ideas` — on-domain titles, no cross-domain DS drift
3. Select an idea, then `POST .../architecture` and `POST .../grill`
4. Blank project must return **400** for all three capabilities

## Run

```bash
python -m evaluation.capability_harness.run
```

Results land in `evaluation/results/*_capability_harness.json`.
