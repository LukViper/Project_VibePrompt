"""Project integrity and requirement lineage APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.schemas.state import migrate_state
from app.services.integrity_store import integrity_summary
from app.services.traceability import get_requirement_lineage

router = APIRouter(tags=["integrity"])


@router.get("/projects/{project_id}/integrity")
def read_integrity(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    state = migrate_state(project.state or {})
    return integrity_summary(state)


@router.get("/projects/{project_id}/requirements/{requirement_id}/lineage")
def read_requirement_lineage(
    project_id: str,
    requirement_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    state = migrate_state(project.state or {})
    req = next((r for r in (state.get("requirements") or []) if r.get("id") == requirement_id), None)
    if req is None:
        raise HTTPException(status_code=404, detail=f"Requirement not found: {requirement_id}")
    return get_requirement_lineage(state, requirement_id)
