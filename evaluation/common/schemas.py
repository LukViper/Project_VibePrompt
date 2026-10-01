"""Shared evaluation schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ExperimentConfig:
    experiment_id: str
    experiment_version: str
    dataset_id: str
    dataset_version: str
    random_seed: int
    model: str = "n/a"
    embedding_provider: str = "n/a"
    embedding_model: str = "n/a"
    parameters: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricResult:
    name: str
    value: float | None
    n: int
    mean: float | None = None
    std: float | None = None
    ci95_low: float | None = None
    ci95_high: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
