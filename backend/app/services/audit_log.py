"""Append-only audit events on ProjectState."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def append_audit_event(
    state: dict,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor: str = "system",
    before: Any = None,
    after: Any = None,
    reason: str = "",
) -> dict:
    event = {
        "event_id": str(uuid4()),
        "project_id": state.get("project_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before": before,
        "after": after,
        "reason": reason,
    }
    state.setdefault("audit_events", []).append(event)
    return event
