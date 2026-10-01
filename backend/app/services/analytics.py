"""Privacy-conscious product analytics (Master Spec §36).

Events are counted without storing private conversation content.
"""

from __future__ import annotations

from collections import Counter
from threading import Lock

ALLOWED_EVENTS = {
    "project_created",
    "idea_refined",
    "conflict_detected",
    "research_started",
    "decision_made",
    "grill_started",
    "grill_completed",
    "specification_generated",
    "prompt_generated",
    "prompt_exported",
}

_COUNTS: Counter[str] = Counter()
_LOCK = Lock()


def track(event: str, *, metadata: dict | None = None) -> None:
    """Increment an allow-listed product event. Metadata must not include message bodies."""
    if event not in ALLOWED_EVENTS:
        return
    if metadata:
        # Drop any accidental content-bearing keys.
        for key in ("content", "message", "prompt", "email", "password"):
            metadata.pop(key, None)
    with _LOCK:
        _COUNTS[event] += 1


def snapshot() -> dict[str, int]:
    with _LOCK:
        return dict(_COUNTS)
