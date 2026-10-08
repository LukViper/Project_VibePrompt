"""Intent classification.

Baselines: keyword rules, TF-IDF + logistic regression, TF-IDF + SVM.
A transformer classifier can be attached later; it is not required for V1.
LLM classification is an optional extra baseline and is not on the default path.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from app.config.settings import get_settings

INTENT_LABELS = [
    "PROJECT_DESCRIPTION",
    "ADD_REQUIREMENT",
    "REMOVE_REQUIREMENT",
    "MODIFY_REQUIREMENT",
    "ASK_QUESTION",
    "ASK_FEASIBILITY",
    "SELECT_IDEA",
    "REJECT_IDEA",
    "REQUEST_GRILL",
    "REQUEST_PROFESSIONAL_REVIEW",
    "REQUEST_RESEARCH",
    "GENERATE_IDEAS",
    "APPLY_RESEARCH",
    "REQUEST_ARCHITECTURE",
    "CHANGE_TECHNOLOGY",
    "CHANGE_SCOPE",
    "FINALIZE_PROJECT",
    "GENERATE_PROMPT",
]

_RULES: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\b(grill mode|grill me|find (the )?weaknesses|tear this apart)\b", re.I), "REQUEST_GRILL", 0.96),
    (re.compile(
        r"\b("
        r"too (big|broad|ambitious|much|large|complex|hard)|"
        r"(unrealistic|overscoped|over[- ]?scoped)|"
        r"this idea is too|"
        r"(narrow|simplify|scale back) (the )?(scope|idea|project)"
        r")\b",
        re.I,
    ), "ASK_FEASIBILITY", 0.91),
    (re.compile(r"\b(professional (mode|review)|review this (like|as) a supervisor|supervisor review)\b", re.I), "REQUEST_PROFESSIONAL_REVIEW", 0.95),
    (re.compile(r"\b(generate|compile|export) (the |a )?(final )?(cursor )?prompt\b", re.I), "GENERATE_PROMPT", 0.96),
    (re.compile(
        r"\b(already exist|existing (systems|tools|papers)|find (datasets?|papers?|apis?)|"
        r"recent (papers?|work)|known limitations|are there (any )?(existing )?systems|"
        r"research (this|that|whether|if)|look up|search for (papers?|datasets?))\b",
        re.I,
    ), "REQUEST_RESEARCH", 0.93),
    (re.compile(
        r"\b(suggest(?:\s+\w+){0,3}\s+ideas?|give me (?:more )?(?:project )?ideas?|"
        r"generate ideas|more (?:project )?ideas|other ideas|brainstorm|"
        r"don'?t know what to build|no idea what to (build|make))\b",
        re.I,
    ), "GENERATE_IDEAS", 0.92),
    (re.compile(
        r"\b(apply (the )?research|use (the )?research (findings|results)|"
        r"turn research into requirements|add research (to|as) requirements)\b",
        re.I,
    ), "APPLY_RESEARCH", 0.94),
    (re.compile(
        r"\b(propose|suggest|design|recommend).{0,40}\b(architecture|tech stack|database schema|api(s)?)\b|"
        r"\b(architecture|system design|tech stack)\b|"
        r"\bhow should i (build|architect|structure|implement)\b|"
        r"\bhow (do|would|should) (i|we) build\b",
        re.I,
    ), "REQUEST_ARCHITECTURE", 0.91),
    (re.compile(r"\b(finalize|lock (the )?(spec|project|requirements)|we are done)\b", re.I), "FINALIZE_PROJECT", 0.9),
    (re.compile(r"\b(select|choose|go with|i('ll| will) take) (idea|option)\b", re.I), "SELECT_IDEA", 0.93),
    (re.compile(r"\breject idea\b|\bdon't like idea\b|\bskip idea\b", re.I), "REJECT_IDEA", 0.93),
    (re.compile(
        r"\b("
        r"actually[,.]?\s*(forget|scrap|drop|never\s*mind)|"
        r"forget (that|this|it)|"
        r"something completely different|"
        r"start over|change (of )?direction"
        r")\b",
        re.I,
    ), "CHANGE_SCOPE", 0.88),
    (re.compile(r"\b(remove|drop|delete|get rid of|scrap)\b", re.I), "REMOVE_REQUIREMENT", 0.92),
    # Forbid / reject feature polarity — must outrank the generic "add" rule below.
    (re.compile(
        r"\b("
        r"(?:do not|don't|never|must not|shall not)\s+"
        r"(?:add|use|include|call|build|enable|install|introduce|support|rely on)|"
        r"avoid\s+(?:using|adding|building|calling|including)"
        r")\b",
        re.I,
    ), "REMOVE_REQUIREMENT", 0.94),
    (re.compile(r"\b(is it feasible|can we actually|is it possible|will it fit)\b", re.I), "ASK_FEASIBILITY", 0.9),
    (re.compile(r"\b(switch|replace|change).{0,40}\b(python|java|react|django|bert|postgres|postgresql|flutter|mysql)\b", re.I), "CHANGE_TECHNOLOGY", 0.9),
    (re.compile(r"\b(use|using|switch to|let's use)\b.{0,40}\b(python|java|bert|postgres|postgresql|react|flutter|mysql|mongodb|fastapi)\b", re.I), "CHANGE_TECHNOLOGY", 0.84),
    (re.compile(r"\b(narrow|expand|reduce|increase) the scope\b", re.I), "CHANGE_SCOPE", 0.9),
    (re.compile(r"\b(instead of|change the|modify the|update the|make it)\b", re.I), "MODIFY_REQUIREMENT", 0.82),
    (re.compile(r"\b(add|also include|let's add|and let's add|we should also|include a)\b", re.I), "ADD_REQUIREMENT", 0.86),
    (re.compile(r"\b(related to|move toward|pivot toward|change direction)\b", re.I), "CHANGE_SCOPE", 0.7),
    # Questions often omit '?'. Match these before the PROJECT_DESCRIPTION default.
    (re.compile(
        r"^\s*how (does |do |will |can |would )?(it|this|that)\s+works?\b",
        re.I,
    ), "ASK_QUESTION", 0.9),
    (re.compile(
        r"\bhow (will|does|do|can|would|is|are) .{0,60}(work|used|use|help)\b",
        re.I,
    ), "ASK_QUESTION", 0.86),
    (re.compile(
        r"\b(what|who) (is|are) .{0,40}(end[- ]?)?users?\b|"
        r"\bwhat is common for .{0,40}users?\b|"
        r"\b(end[- ]?user|user experience|how (?:do|will) users)\b",
        re.I,
    ), "ASK_QUESTION", 0.86),
    (re.compile(r"\b(what|how|why|when|where|which)\b.+\?", re.I), "ASK_QUESTION", 0.72),
    (re.compile(r"^\s*(how|what|why|who|when|where|which)\b.{0,80}$", re.I), "ASK_QUESTION", 0.7),
    (re.compile(r"\?$", re.I), "ASK_QUESTION", 0.55),
]


class IntentClassifier:
    def __init__(self) -> None:
        self.logreg: Pipeline | None = None
        self.svm: Pipeline | None = None
        self._trained = False

    def _rule_scores(self, text: str) -> dict[str, float]:
        scores = {label: 0.0 for label in INTENT_LABELS}
        for pattern, label, weight in _RULES:
            if pattern.search(text):
                scores[label] = max(scores[label], weight)
        if max(scores.values()) < 0.5:
            scores["PROJECT_DESCRIPTION"] = 0.62
        return scores

    def ensure_trained(self) -> None:
        if self._trained:
            return
        path = Path(get_settings().dataset_dir) / "intent_train.jsonl"
        rows = _read_jsonl(path)
        if len(rows) < 10:
            self._trained = True
            return
        texts = [row["text"] for row in rows]
        labels = [row["intent"] for row in rows]
        self.logreg = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=400)),
        ])
        self.svm = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LinearSVC()),
        ])
        self.logreg.fit(texts, labels)
        self.svm.fit(texts, labels)
        self._trained = True

    def classify(self, text: str) -> dict:
        self.ensure_trained()
        rule_scores = self._rule_scores(text)
        rule_label = max(rule_scores, key=rule_scores.get)
        rule_confidence = rule_scores[rule_label]
        model_label = None
        model_confidence = 0.0
        method = "rules"
        if self.logreg is not None:
            probabilities = self.logreg.predict_proba([text])[0]
            index = int(np.argmax(probabilities))
            model_label = self.logreg.classes_[index]
            model_confidence = float(probabilities[index])
            method = "tfidf_logreg"
        chosen = rule_label
        confidence = rule_confidence
        if model_label and model_confidence >= 0.45 and model_confidence >= rule_confidence - 0.05:
            chosen = model_label
            confidence = model_confidence
            method = "tfidf_logreg"
        elif model_label and rule_confidence > model_confidence:
            method = "rules"
        # Strong action cues stay with the rule baseline so a small trained model
        # cannot swallow an explicit add, remove, or technology change.
        if rule_scores["CHANGE_TECHNOLOGY"] >= 0.84:
            chosen = "CHANGE_TECHNOLOGY"
            confidence = rule_scores["CHANGE_TECHNOLOGY"]
            method = "rules"
        if rule_scores["ADD_REQUIREMENT"] >= 0.86:
            chosen = "ADD_REQUIREMENT"
            confidence = rule_scores["ADD_REQUIREMENT"]
            method = "rules"
        # Forbid/reject polarity outranks the generic "add" cue ("Do not add X").
        if rule_scores["REMOVE_REQUIREMENT"] >= 0.9:
            chosen = "REMOVE_REQUIREMENT"
            confidence = rule_scores["REMOVE_REQUIREMENT"]
            method = "rules"
        for label in (
            "REQUEST_GRILL",
            "REQUEST_PROFESSIONAL_REVIEW",
            "REQUEST_RESEARCH",
            "GENERATE_IDEAS",
            "APPLY_RESEARCH",
            "REQUEST_ARCHITECTURE",
            "GENERATE_PROMPT",
            "SELECT_IDEA",
            "REJECT_IDEA",
            "FINALIZE_PROJECT",
        ):
            if rule_scores[label] >= 0.9:
                chosen = label
                confidence = rule_scores[label]
                method = "rules"
                break
        return {
            "intent": chosen,
            "confidence": round(float(confidence), 4),
            "method": method,
            "rule_intent": rule_label,
            "model_intent": model_label,
            "svm_intent": None if self.svm is None else str(self.svm.predict([text])[0]),
        }


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    import json

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


_CLASSIFIER = IntentClassifier()


def classify_intent(text: str) -> dict:
    return _CLASSIFIER.classify(text)


def evaluate_intent_models(rows: list[dict]) -> dict:
    """Cross-validated metrics. Returns only numbers computed from ``rows``."""
    texts = [row["text"] for row in rows]
    labels = [row["intent"] for row in rows]
    labels_sorted = sorted(set(labels))
    pipelines = {
        "tfidf_logreg": Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=400)),
        ]),
        "tfidf_svm": Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LinearSVC()),
        ]),
    }
    min_class = min(labels.count(label) for label in labels_sorted)
    folds = max(2, min(5, min_class))
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=7)
    report = {"folds": folds, "support": len(rows), "models": {}}
    for name, pipeline in pipelines.items():
        predicted = cross_val_predict(pipeline, texts, labels, cv=splitter)
        matrix = confusion_matrix(labels, predicted, labels=labels_sorted)
        report["models"][name] = {
            "accuracy": accuracy_score(labels, predicted),
            "precision_macro": precision_score(labels, predicted, average="macro", zero_division=0),
            "recall_macro": recall_score(labels, predicted, average="macro", zero_division=0),
            "f1_macro": f1_score(labels, predicted, average="macro", zero_division=0),
            "labels": labels_sorted,
            "confusion_matrix": matrix.tolist(),
        }
    return report
