"""Gold annotation schema for RQ1.

Gold is evaluation-only. It must never be passed into VibePrompt or baselines
as system output / prediction.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


DATASET_LABEL = "SYNTHETIC CONTROLLED BENCHMARK"


@dataclass
class GoldAnnotation:
    """Authoritative labels used only after system execution."""

    requirements: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    rejected_items: list[str] = field(default_factory=list)
    superseded_items: list[str] = field(default_factory=list)
    assertion_origins: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def gold_from_case(case: dict) -> GoldAnnotation:
    """Extract gold from a scenario dict. Never mutate or return as prediction."""
    origins = case.get("assertion_origins") or case.get("gold_assertion_origins") or {}
    return GoldAnnotation(
        requirements=list(case.get("gold_requirements") or []),
        constraints=list(case.get("gold_constraints") or []),
        technologies=list(case.get("gold_technologies") or []),
        decisions=list(case.get("gold_decisions") or []),
        rejected_items=list(case.get("rejected") or case.get("rejected_items") or []),
        superseded_items=list(case.get("superseded") or case.get("superseded_items") or []),
        assertion_origins=dict(origins),
    )


def assert_not_gold_as_prediction(prediction: Any, gold: GoldAnnotation) -> None:
    """Raise if prediction is identity-equal to the gold object / gold requirement list.

    Used by tests to catch oracle contamination regressions.
    """
    if prediction is gold:
        raise AssertionError("Gold annotation object used as prediction")
    if isinstance(prediction, list) and prediction is gold.requirements:
        raise AssertionError("Gold requirements list used as prediction")
    # Detect trivial copy-from-gold: exact same list object identity after extraction
    if isinstance(prediction, dict) and prediction.get("_from_gold") is True:
        raise AssertionError("Prediction flagged as derived from gold")
