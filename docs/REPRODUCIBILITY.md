# Reproducibility

## Seeds

`evaluation.common.seeds.set_seed(42)` sets Python `random`, `PYTHONHASHSEED`, and NumPy when available.

Every experiment writes `config.json` including:

```text
dataset_id, dataset_version, experiment_version, random_seed,
model, embedding_provider, embedding_model, parameters, timestamp
```

## Reproduce a full suite

```bash
cd /path/to/Prompting
python -m evaluation.datasets.generate
python -m evaluation.run_all
python -m evaluation.generate_report
```

Backend unit tests:

```bash
cd backend && .venv/bin/python -m pytest -q
```

## Embedding metadata

Experiments record the active embedding provider via `embedding_metadata()`. Lexical fallback is explicitly labeled and is **not** claimed as semantic equivalence.

## Statistical reporting

`summarize()` reports N, mean, population std, and normal-approx 95% CI. For small synthetic N, treat CIs as descriptive, not confirmatory.

Paired significance tests are **not** auto-selected in v1; document any future test choice with its assumptions.

## What not to do

- Do not hand-edit `metrics.json` to “improve” numbers
- Do not present synthetic results as field studies
- Do not combine metrics into a single overall score
