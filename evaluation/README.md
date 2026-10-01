# Evaluation

Research evaluation for VibePrompt. Production code lives under `backend/`; this package is separate.

```bash
python -m evaluation.datasets.generate
python -m evaluation.run_all
python -m evaluation.generate_report
```

Legacy NLP scripts remain:

```bash
python evaluation/run_nlp_eval.py
python evaluation/run_e2e_eval.py
python evaluation/baseline_comparison.py
```

See [docs/EVALUATION.md](../docs/EVALUATION.md).
