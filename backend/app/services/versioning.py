"""Project state versioning abstraction.

Persists meaningful snapshots on ProjectVersion while keeping an in-state
monotonic counter for UI/API consumers.
"""

from __future__ import annotations

import copy

from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import Project, ProjectVersion
from app.schemas.state import migrate_state


class StateVersioning:
    """Create and list project-state versions."""

    @staticmethod
    def bump(state: dict, reason: str) -> dict:
        state = migrate_state(state)
        state["state_version"] = int(state.get("state_version") or 1) + 1
        state.setdefault("_last_version_reason", reason)
        return state

    @staticmethod
    def snapshot(session: Session, project: Project, reason: str = "update") -> ProjectVersion:
        state = migrate_state(project.state or {})
        row = ProjectVersion(
            project_id=project.id,
            reason=reason,
            state=copy.deepcopy(state),
        )
        session.add(row)
        project.updated_at = utcnow()
        return row

    @staticmethod
    def list_versions(session: Session, project: Project) -> list[ProjectVersion]:
        return sorted(project.versions, key=lambda row: row.created_at or utcnow())
