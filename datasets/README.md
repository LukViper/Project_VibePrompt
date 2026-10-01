# Annotated data

Initial single-annotator labels for the Version 1 experiments. They are a gold set for development, not a multi-annotator corpus.

Rebuild with:

```bash
python datasets/build_datasets.py
```

| File | Contents |
|---|---|
| `intent_train.jsonl` | Intent utterances for TF-IDF baselines |
| `intent_test.jsonl` | Held-out intent utterances, including examples from the plan |
| `similarity.jsonl` | Pairs with human similarity 0–3 and a relationship label |
| `relationship.jsonl` | Same pairs, relationship field populated |
| `drift_validation.jsonl` | Objective / requirement / drift bit, used to select a threshold |
| `conversations/` | Ten end-to-end cases from the evaluation plan |
