# Evaluation

These scripts compute metrics from `datasets/`. They do not embed assumed scores.

```bash
python evaluation/run_nlp_eval.py
python evaluation/run_e2e_eval.py
python evaluation/baseline_comparison.py
```

`run_nlp_eval.py` reports cross-validated TF-IDF baselines, the held-out runtime classifier, Spearman and Pearson correlation for similarity, duplicate precision/recall, and held-out drift precision/recall. The embedding backend in the output is whichever backend actually loaded.

`baseline_comparison.py` is the RQ5 comparison: a prompt built by concatenating the conversation versus a prompt compiled from the specification.
