"""Report computed NLP metrics. Do not hard-code results in documentation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.nlp.drift import calculate_drift, select_drift_threshold  # noqa: E402
from app.nlp.embeddings import create_embedding, get_embedder  # noqa: E402
from app.nlp.intent import IntentClassifier, evaluate_intent_models  # noqa: E402
from app.nlp.similarity import cosine_similarity  # noqa: E402
from app.services.project_state import empty_state  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def score_labels(expected, predicted, labels):
    return {
        "accuracy": accuracy_score(expected, predicted),
        "precision_macro": precision_score(expected, predicted, average="macro", zero_division=0),
        "recall_macro": recall_score(expected, predicted, average="macro", zero_division=0),
        "f1_macro": f1_score(expected, predicted, average="macro", zero_division=0),
        "labels": labels,
        "confusion_matrix": confusion_matrix(expected, predicted, labels=labels).tolist(),
    }


def main() -> None:
    data = ROOT / "datasets"
    train = load_jsonl(data / "intent_train.jsonl")
    test = load_jsonl(data / "intent_test.jsonl")
    pairs = load_jsonl(data / "similarity.jsonl")
    drift_rows = load_jsonl(data / "drift_validation.jsonl")
    classifier = IntentClassifier()
    classifier.ensure_trained()
    predicted = [classifier.classify(row["text"])["intent"] for row in test]
    expected = [row["intent"] for row in test]
    labels = sorted(set(expected))
    similarities = [
        cosine_similarity(create_embedding(row["text_a"]), create_embedding(row["text_b"]))
        for row in pairs
    ]
    human = [row["similarity"] for row in pairs]
    spearman = spearmanr(similarities, human)
    pearson = pearsonr(similarities, human)
    duplicate_gold = [int(row["similarity"] >= 3) for row in pairs]
    duplicate_pred = [int(score >= 0.72) for score in similarities]
    split = max(4, len(drift_rows) // 2)
    threshold = select_drift_threshold(drift_rows[:split])
    drift_expected = []
    drift_predicted = []
    for row in drift_rows[split:]:
        state = empty_state()
        state["core_idea"] = {
            "primary_domain": "NLP",
            "primary_objective": row["objective"],
            "locked": True,
        }
        state["project"]["objective"] = row["objective"]
        state["domains"] = ["nlp"]
        report = calculate_drift(state, [row["requirement"]])
        drift_expected.append(int(row["drift"]))
        drift_predicted.append(int(report["potential_drift"]))
    report = {
        "embedding_backend": get_embedder().name,
        "note": "Figures are computed by this script from the local datasets. They are not universal model scores.",
        "intent_cross_validation_classical": evaluate_intent_models(train),
        "intent_held_out_runtime_classifier": score_labels(expected, predicted, labels),
        "similarity": {
            "spearman": None if np.isnan(spearman.statistic) else float(spearman.statistic),
            "pearson": None if np.isnan(pearson.statistic) else float(pearson.statistic),
            "duplicate_precision": precision_score(duplicate_gold, duplicate_pred, zero_division=0),
            "duplicate_recall": recall_score(duplicate_gold, duplicate_pred, zero_division=0),
            "pairs": len(pairs),
        },
        "drift_held_out": {
            "threshold_selection": threshold,
            "precision": precision_score(drift_expected, drift_predicted, zero_division=0) if drift_expected else None,
            "recall": recall_score(drift_expected, drift_predicted, zero_division=0) if drift_expected else None,
            "f1": f1_score(drift_expected, drift_predicted, zero_division=0) if drift_expected else None,
            "support": len(drift_expected),
        },
    }
    out = ROOT / "evaluation" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "nlp_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
