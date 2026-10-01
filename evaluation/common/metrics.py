"""Metric definitions for RQ1–RQ5.

All set-based metrics use token-normalized text matching against gold labels.
Requirement IDs are NEVER used as the primary match key.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from statistics import mean, pstdev
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_text(text: str) -> str:
    tokens = _TOKEN_RE.findall((text or "").lower())
    return " ".join(tokens)


def token_set(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def texts_match(a: str, b: str, *, threshold: float = 0.55) -> bool:
    """Jaccard overlap on tokens — primary matching for gold labels."""
    sa, sb = token_set(a), token_set(b)
    if not sa or not sb:
        return normalize_text(a) == normalize_text(b) and bool(normalize_text(a))
    overlap = len(sa & sb) / len(sa | sb)
    return overlap >= threshold


def match_predicted_to_gold(
    predicted: Iterable[str],
    gold: Iterable[str],
    *,
    threshold: float = 0.55,
) -> tuple[int, int, int]:
    """Return tp, fp, fn using greedy best-match without ID equality."""
    gold_list = list(gold)
    pred_list = list(predicted)
    used_gold: set[int] = set()
    tp = 0
    for pred in pred_list:
        best_i = None
        best_score = -1.0
        for i, g in enumerate(gold_list):
            if i in used_gold:
                continue
            sa, sb = token_set(pred), token_set(g)
            if not sa or not sb:
                score = 1.0 if normalize_text(pred) == normalize_text(g) and normalize_text(pred) else 0.0
            else:
                score = len(sa & sb) / len(sa | sb)
            if score > best_score:
                best_score = score
                best_i = i
        if best_i is not None and best_score >= threshold:
            used_gold.add(best_i)
            tp += 1
    fp = len(pred_list) - tp
    fn = len(gold_list) - tp
    return tp, fp, fn


def precision(tp: int, fp: int) -> float:
    return tp / (tp + fp) if (tp + fp) else 1.0


def recall(tp: int, fn: int) -> float:
    return tp / (tp + fn) if (tp + fn) else 1.0


def f1(p: int | float, r: int | float) -> float:
    # Accept either (tp-style misuse) or actual precision/recall floats.
    if isinstance(p, float) or isinstance(r, float):
        return (2 * p * r / (p + r)) if (p + r) else 0.0
    # fallback unused
    return 0.0


def f1_from_counts(tp: int, fp: int, fn: int) -> float:
    p = precision(tp, fp)
    r = recall(tp, fn)
    return (2 * p * r / (p + r)) if (p + r) else 0.0


def rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "std": None, "ci95_low": None, "ci95_high": None}
    n = len(values)
    m = mean(values)
    sd = pstdev(values) if n > 1 else 0.0
    # Normal approx 95% CI; document limitation for small n.
    se = sd / math.sqrt(n) if n else 0.0
    return {
        "n": n,
        "mean": m,
        "std": sd,
        "ci95_low": m - 1.96 * se,
        "ci95_high": m + 1.96 * se,
        "median": sorted(values)[n // 2],
    }


def set_metrics(predicted: list[str], gold: list[str], *, threshold: float = 0.55) -> dict[str, float]:
    tp, fp, fn = match_predicted_to_gold(predicted, gold, threshold=threshold)
    p = precision(tp, fp)
    r = recall(tp, fn)
    return {
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
        "precision": p,
        "recall": r,
        "f1": f1_from_counts(tp, fp, fn),
        "n_predicted": float(len(predicted)),
        "n_gold": float(len(gold)),
    }


def leakage_rate(forbidden: list[str], emitted: list[str], *, threshold: float = 0.55) -> float:
    """Fraction of forbidden items that still appear in emitted set."""
    if not forbidden:
        return 0.0
    leaked = 0
    for item in forbidden:
        if any(texts_match(item, out, threshold=threshold) for out in emitted):
            leaked += 1
    return leaked / len(forbidden)


def unsupported_addition_rate(predicted: list[str], gold: list[str], *, threshold: float = 0.55) -> float:
    """Fraction of predicted items with no gold match."""
    if not predicted:
        return 0.0
    tp, fp, _fn = match_predicted_to_gold(predicted, gold, threshold=threshold)
    return fp / len(predicted)
